from typing import Annotated

from fastapi import APIRouter, Depends, Request, status

from app.core.deps import CurrentUser, DbSession, client_ip
from app.engine import KnowledgeBase
from app.schemas.analysis import AnalysisOut, AnalysisSummary, RiskFactors, RiskFactorsOut
from app.schemas.common import ErrorResponse
from app.services import analysis_service as svc
from app.services.knowledge_base_service import get_knowledge_base
from app.services.medication_list_service import get_owned_list


def knowledge_base(db: DbSession) -> KnowledgeBase:
    return get_knowledge_base(db)


CurrentKB = Annotated[KnowledgeBase, Depends(knowledge_base)]

router = APIRouter(
    prefix="/medication-lists",
    tags=["Analysis"],
    responses={
        401: {"model": ErrorResponse, "description": "Missing or invalid token"},
        403: {"model": ErrorResponse, "description": "List belongs to another user"},
        404: {"model": ErrorResponse, "description": "List or analysis not found"},
    },
)


@router.get("/{list_id}/risk-factors", response_model=RiskFactors, summary="FR-14: Get the list's patient factors")
def get_risk_factors(list_id: int, user: CurrentUser, db: DbSession, request: Request):
    return svc.current_risk_factors(get_owned_list(db, user, list_id, client_ip(request)))


@router.put(
    "/{list_id}/risk-factors",
    response_model=RiskFactorsOut,
    summary="FR-14: Set the list's patient factors (omitted ones become unknown)",
)
def put_risk_factors(list_id: int, data: RiskFactors, user: CurrentUser, db: DbSession, request: Request):
    med_list = get_owned_list(db, user, list_id, client_ip(request))
    return svc.set_risk_factors(db, med_list, data)


@router.post(
    "/{list_id}/analyses",
    response_model=AnalysisOut,
    status_code=status.HTTP_201_CREATED,
    summary="FR-8 to FR-15: Analyse a confirmed list and store the result",
    responses={
        409: {"model": ErrorResponse, "description": "The list is not confirmed (BR-01)"},
        503: {"model": ErrorResponse, "description": "Knowledge base unavailable"},
    },
)
def run_analysis(list_id: int, user: CurrentUser, db: DbSession, kb: CurrentKB, request: Request):
    med_list = get_owned_list(db, user, list_id, client_ip(request))
    return svc.to_out(svc.run_analysis(db, med_list, kb))


@router.get("/{list_id}/analyses", response_model=list[AnalysisSummary], summary="FR-15: Earlier analyses of a list")
def list_analyses(list_id: int, user: CurrentUser, db: DbSession, request: Request):
    return svc.list_analyses(db, get_owned_list(db, user, list_id, client_ip(request)))


@router.get("/{list_id}/analyses/{analysis_id}", response_model=AnalysisOut, summary="FR-15: Reopen an analysis")
def get_analysis(list_id: int, analysis_id: int, user: CurrentUser, db: DbSession, request: Request):
    med_list = get_owned_list(db, user, list_id, client_ip(request))
    return svc.to_out(svc.get_analysis(db, med_list, analysis_id))
