from fastapi import APIRouter, Request, status

from app.core.deps import CurrentUser, DbSession, client_ip
from app.schemas.common import ErrorResponse
from app.schemas.medication_list import (
    MedicationItemUpdate,
    MedicationListOut,
    MedicationListSummary,
    MedicationNames,
)
from app.services import medication_list_service as svc

router = APIRouter(
    prefix="/medication-lists",
    tags=["Medication lists"],
    responses={
        401: {"model": ErrorResponse, "description": "Missing or invalid token"},
        403: {"model": ErrorResponse, "description": "List belongs to another user"},
        404: {"model": ErrorResponse, "description": "List or item not found"},
    },
)


@router.post(
    "",
    response_model=MedicationListOut,
    status_code=status.HTTP_201_CREATED,
    summary="FR-3: Create a draft list from manually entered names",
)
def create_list(data: MedicationNames, user: CurrentUser, db: DbSession):
    return svc.to_detail(svc.create_list(db, user, data.names))


@router.get("", response_model=list[MedicationListSummary], summary="History: my medication lists")
def list_lists(user: CurrentUser, db: DbSession):
    return svc.list_user_lists(db, user)


@router.get("/{list_id}", response_model=MedicationListOut, summary="Get one list with its items")
def get_list(list_id: int, user: CurrentUser, db: DbSession, request: Request):
    return svc.to_detail(svc.get_owned_list(db, user, list_id, client_ip(request)))


@router.delete("/{list_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Delete a list")
def delete_list(list_id: int, user: CurrentUser, db: DbSession, request: Request):
    svc.delete_list(db, svc.get_owned_list(db, user, list_id, client_ip(request)))


@router.post(
    "/{list_id}/items",
    response_model=MedicationListOut,
    status_code=status.HTTP_201_CREATED,
    summary="FR-3: Add one or more medications to a list",
)
def add_items(list_id: int, data: MedicationNames, user: CurrentUser, db: DbSession, request: Request):
    med_list = svc.get_owned_list(db, user, list_id, client_ip(request))
    return svc.to_detail(svc.add_items(db, med_list, data.names))


@router.patch("/{list_id}/items/{item_id}", response_model=MedicationListOut, summary="Edit a medication name")
def update_item(
    list_id: int, item_id: int, data: MedicationItemUpdate, user: CurrentUser, db: DbSession, request: Request
):
    med_list = svc.get_owned_list(db, user, list_id, client_ip(request))
    return svc.to_detail(svc.update_item(db, med_list, item_id, data.raw_text))


@router.delete("/{list_id}/items/{item_id}", response_model=MedicationListOut, summary="Remove a medication")
def delete_item(list_id: int, item_id: int, user: CurrentUser, db: DbSession, request: Request):
    med_list = svc.get_owned_list(db, user, list_id, client_ip(request))
    return svc.to_detail(svc.delete_item(db, med_list, item_id))
