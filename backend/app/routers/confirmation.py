from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.deps import get_current_user, get_db   # match your existing dependency names
from app.models import MedicationList, MedicationListItem
from app.services import confirmation as svc
from app.services.normalization import resolve_term

router = APIRouter(prefix="/medication-lists", tags=["confirmation"])


class AcceptBody(BaseModel):
    medication_id: int | None = None


def owned_list(db: Session, list_id: int, user) -> MedicationList:
    lst = db.get(MedicationList, list_id)
    if lst is None:
        raise HTTPException(404, detail={"code": "not_found", "message": "List not found."})
    if lst.user_id != user.id:
        raise HTTPException(403, detail={"code": "forbidden", "message": "This list belongs to another user."})
    return lst


def owned_item(db: Session, lst: MedicationList, item_id: int) -> MedicationListItem:
    item = db.get(MedicationListItem, item_id)
    if item is None or item.list_id != lst.id:
        raise HTTPException(404, detail={"code": "not_found", "message": "Item not found."})
    return item


@router.get("/{list_id}/items/{item_id}/candidates")
def get_candidates(list_id: int, item_id: int, db: Session = Depends(get_db), user=Depends(get_current_user)):
    lst = owned_list(db, list_id, user)
    item = owned_item(db, lst, item_id)
    return {"item_id": item.id, "raw_text": item.raw_text, "candidates": resolve_term(db, item.raw_text)}


@router.post("/{list_id}/items/{item_id}/accept")
def accept(list_id: int, item_id: int, body: AcceptBody, db: Session = Depends(get_db), user=Depends(get_current_user)):
    lst = owned_list(db, list_id, user)
    item = owned_item(db, lst, item_id)
    svc.accept_item(db, lst, item, body.medication_id)
    db.commit()
    return {"item_id": item.id, "status": item.confirmation_flag.value}


@router.post("/{list_id}/items/{item_id}/keep-unrecognised")
def keep(list_id: int, item_id: int, db: Session = Depends(get_db), user=Depends(get_current_user)):
    lst = owned_list(db, list_id, user)
    item = owned_item(db, lst, item_id)
    svc.keep_unrecognised(db, lst, item)
    db.commit()
    return {"item_id": item.id, "status": item.confirmation_flag.value}


@router.post("/{list_id}/confirm")
def confirm(list_id: int, db: Session = Depends(get_db), user=Depends(get_current_user)):
    lst = owned_list(db, list_id, user)
    svc.confirm_list(db, lst)
    db.commit()
    return {"list_id": lst.id, "status": lst.confirmation_status.value}