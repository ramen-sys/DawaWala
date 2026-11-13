from fastapi import APIRouter, Query, Request, status
from sqlalchemy import func, or_, select
from sqlalchemy.orm import selectinload

from app.core.config import settings
from app.core.deps import CurrentUser, DbSession, client_ip
from app.core.errors import AppError
from app.models.enums import AuthEventType, UserRole
from app.models import CascadeRule, Contraindication, DrugInteraction, Medication
from app.schemas.medication_list import MedicationSearchResult
from app.services.auth_event_service import record_event
from app.services.knowledge_base_service import reload_knowledge_base
from app.services.normalization import alias_matches, escape_like

router = APIRouter(prefix="/medications", tags=["Knowledge base"])


@router.get("/knowledge-base", summary="Knowledge-base version, update date and coverage (SAF-07)")
def knowledge_base_info(_: CurrentUser, db: DbSession):
    return {
        "version": settings.KB_VERSION,
        "updated_on": settings.KB_UPDATED_ON,
        "medications": db.scalar(select(func.count()).select_from(Medication)),
        "interactions": db.scalar(select(func.count()).select_from(DrugInteraction)),
        "contraindications": db.scalar(select(func.count()).select_from(Contraindication)),
        "cascade_rules": db.scalar(select(func.count()).select_from(CascadeRule)),
    }


@router.post(
    "/knowledge-base/reload",
    summary="Admin: reload the safety rules after scripts.import_kb_rules, without a restart",
)
def reload_kb(user: CurrentUser, db: DbSession, request: Request):
    if user.role != UserRole.ADMIN:
        record_event(db, AuthEventType.AUTHZ_DENIED, user.id, client_ip(request))
        raise AppError(status.HTTP_403_FORBIDDEN, "forbidden", "Only an administrator can reload the knowledge base.")
    kb = reload_knowledge_base(db)
    return {
        "version": kb.version,
        "updated_on": kb.updated,
        "medications": len(kb.medications),
        "interactions": sum(len(rules) for rules in kb.interactions.values()),
        "contraindications": sum(len(rules) for rules in kb.contraindications.values()),
        "cascade_rules": len(kb.cascades),
    }


@router.get(
    "/search",
    response_model=list[MedicationSearchResult],
    summary="Type-ahead suggestions from the knowledge base (FR-3)",
)
def search_medications(
    _: CurrentUser,
    db: DbSession,
    q: str = Query(min_length=2, max_length=100),
    limit: int = Query(default=10, ge=1, le=25),
):
    term = q.strip().lower()
    pattern = escape_like(term) + "%"  # prefix match, served by the trigram indexes
    meds = db.scalars(
        select(Medication)
        .where(or_(Medication.standard_name.ilike(pattern, escape="\\"), alias_matches(pattern)))
        .options(selectinload(Medication.aliases))
        .order_by(Medication.standard_name)
        .limit(limit)
    ).all()

    results = []
    for med in meds:
        # Tell the UI which name matched, e.g. "Panadol" when the user typed "pan".
        if med.standard_name.lower().startswith(term):
            matched_on = med.standard_name
        else:
            matched_on = next(a for a in med.alias_names if a.lower().startswith(term))
        results.append(
            MedicationSearchResult(
                id=med.id, standard_name=med.standard_name, drug_class=med.drug_class, matched_on=matched_on
            )
        )
    return results
