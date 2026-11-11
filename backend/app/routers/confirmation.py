from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.deps import get_current_user, get_db   # match your existing dependency names
from app.models import MedicationList, MedicationListItem, OcrExtractionResult, PrescriptionImage
from app.models.enums import OcrStatus
from app.schemas.medication_list import ImageCandidatesOut, ImageMedicineCandidates, MedicationCandidate
from app.services import confirmation as svc
from app.services.normalization import confidence_label, extract_strengths, resolve_term

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


@router.get(
    "/{list_id}/images/{image_id}/candidates",
    response_model=ImageCandidatesOut,
    summary="Get all medicine candidates extracted from one image",
)
def get_image_candidates(
    list_id: int,
    image_id: int,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    lst = owned_list(db, list_id, user)
    image = db.scalar(
        select(PrescriptionImage)
        .where(PrescriptionImage.id == image_id, PrescriptionImage.list_id == lst.id)
    )
    if image is None:
        raise HTTPException(404, detail={"code": "not_found", "message": "Image not found."})
    if image.ocr_status != OcrStatus.COMPLETED:
        raise HTTPException(409, detail={"code": "ocr_not_completed", "message": "Image OCR is not complete."})

    extraction = db.scalar(
        select(OcrExtractionResult).where(OcrExtractionResult.image_id == image.id)
    )
    if extraction is None:
        raise HTTPException(404, detail={"code": "not_found", "message": "Image OCR results were not found."})

    medicines = []
    for result in extraction.candidates:
        item = db.get(MedicationListItem, result["item_id"])
        if item is None or item.list_id != lst.id:
            continue
        medicines.append(
            ImageMedicineCandidates(
                item_id=item.id,
                text=item.raw_text,
                confirmation_flag=item.confirmation_flag,
                match_score=item.match_score,
                confidence_label=confidence_label(item.match_score),
                ocr_confidence=result.get("confidence"),
                source_line=result.get("source_line", item.raw_text),
                prescription_details=result.get("prescription_details", ""),
                strengths=extract_strengths(result.get("prescription_details", "")),
                candidates=[MedicationCandidate.model_validate(c) for c in result.get("candidates", [])],
            )
        )

    return ImageCandidatesOut(
        image_id=image.id,
        ocr_status=image.ocr_status,
        raw_text=extraction.raw_text,
        medicines=medicines,
    )


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