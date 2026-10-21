from fastapi import APIRouter, Query
from sqlalchemy import func, or_, select

from app.core.config import settings
from app.core.deps import CurrentUser, DbSession
from app.models import CascadeRule, Contraindication, DrugInteraction, Medication
from app.schemas.medication_list import MedicationSearchResult
from app.services.normalization import alias_matches

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
    pattern = term.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%"
    meds = db.scalars(
        select(Medication)
        .where(
            or_(
                func.lower(Medication.standard_name).like(pattern, escape="\\"),
                alias_matches(lambda a: a.like(pattern, escape="\\")),
            )
        )
        .order_by(Medication.standard_name)
        .limit(limit)
    ).all()

    results = []
    for med in meds:
        if med.standard_name.lower().startswith(term):
            matched_on = med.standard_name
        else:
            matched_on = next(a for a in med.aliases if a.lower().startswith(term))
        results.append(
            MedicationSearchResult(
                id=med.id, standard_name=med.standard_name, drug_class=med.drug_class, matched_on=matched_on
            )
        )
    return results
