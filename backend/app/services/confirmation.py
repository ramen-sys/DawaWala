from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models import AnalysisResult, Medication, MedicationList, MedicationListItem
from app.models.enums import ConfirmationFlag, ConfirmationStatus, Freshness
from app.services.normalization import resolve_term


def add_item(db: Session, lst: MedicationList, raw_text: str) -> MedicationListItem:
    """Add a typed or OCR term. The top candidate is only a suggestion until the user accepts it."""
    if len(lst.items) >= 30:
        raise HTTPException(409, detail={"code": "list_full", "message": "A list can hold at most 30 medicines."})
    candidates = resolve_term(db, raw_text)
    item = MedicationListItem(
        list_id=lst.id,
        raw_text=raw_text[:100],
        medication_id=candidates[0]["medication_id"] if candidates else None,
        match_score=candidates[0]["match_score"] if candidates else None,
        confirmation_flag=ConfirmationFlag.UNRESOLVED,
    )
    db.add(item)
    mark_list_edited(db, lst)
    return item


def mark_list_edited(db: Session, lst: MedicationList) -> None:
    """Any change returns the list to draft and marks earlier analyses outdated (FR-7, SAF-08)."""
    lst.confirmation_status = ConfirmationStatus.DRAFT
    for analysis in lst.analyses:
        analysis.freshness = Freshness.OUTDATED


def accept_item(db: Session, lst: MedicationList, item: MedicationListItem, medication_id: int | None) -> None:
    """User accepts the suggestion, or chooses another medicine by ID."""
    target = medication_id if medication_id is not None else item.medication_id
    if target is None or db.get(Medication, target) is None:
        raise HTTPException(422, detail={"code": "no_medicine", "message": "Choose a medicine from the list, or keep it as unrecognised."})
    item.medication_id = target
    item.match_score = None  # the user made the choice, not the matcher
    item.confirmation_flag = ConfirmationFlag.ACCEPTED
    mark_list_edited(db, lst)


def keep_unrecognised(db: Session, lst: MedicationList, item: MedicationListItem) -> None:
    item.medication_id = None
    item.confirmation_flag = ConfirmationFlag.KEPT_UNRECOGNISED
    mark_list_edited(db, lst)


def confirm_list(db: Session, lst: MedicationList) -> None:
    """Confirm only when every item is resolved and at least one medicine is accepted (FR-7)."""
    unresolved = [i for i in lst.items if i.confirmation_flag == ConfirmationFlag.UNRESOLVED]
    if unresolved:
        raise HTTPException(409, detail={
            "code": "unresolved_items",
            "message": f"{len(unresolved)} item(s) still need a decision.",
            "fields": {"item_ids": [i.id for i in unresolved]},
        })
    if not any(i.confirmation_flag == ConfirmationFlag.ACCEPTED for i in lst.items):
        raise HTTPException(409, detail={"code": "nothing_confirmed", "message": "At least one medicine must be confirmed."})
    lst.confirmation_status = ConfirmationStatus.CONFIRMED