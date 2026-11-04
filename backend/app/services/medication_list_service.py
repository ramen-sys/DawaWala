from fastapi import status
from sqlalchemy import func, select, update
from sqlalchemy.orm import Session, selectinload

from app.core.config import settings
from app.core.errors import AppError
from app.models import AnalysisResult, MedicationList, MedicationListItem, User
from app.models.enums import AuthEventType, ConfirmationFlag, ConfirmationStatus, Freshness, ListSource
from app.schemas.medication_list import (
    MedicationItemOut,
    MedicationListOut,
    MedicationListSummary,
    MedicationRef,
)
from app.services.auth_event_service import record_event
from app.services.normalization import confidence_label, normalize_name


def _active_items(med_list: MedicationList) -> list[MedicationListItem]:
    return [i for i in med_list.items if i.confirmation_flag != ConfirmationFlag.REMOVED]


def to_item_out(item: MedicationListItem) -> MedicationItemOut:
    return MedicationItemOut(
        id=item.id,
        raw_text=item.raw_text,
        medication=MedicationRef.model_validate(item.medication) if item.medication else None,
        match_score=item.match_score,
        confidence_label=confidence_label(item.match_score),
        confirmation_flag=item.confirmation_flag,
    )


def to_summary(med_list: MedicationList, item_count: int | None = None) -> MedicationListSummary:
    return MedicationListSummary(
        id=med_list.id,
        source=med_list.source,
        confirmation_status=med_list.confirmation_status,
        item_count=item_count if item_count is not None else len(_active_items(med_list)),
        created_at=med_list.created_at,
    )


def to_detail(med_list: MedicationList) -> MedicationListOut:
    return MedicationListOut(
        **to_summary(med_list).model_dump(),
        items=[to_item_out(i) for i in med_list.items],
    )


def _load(db: Session, list_id: int) -> MedicationList | None:
    return db.scalar(
        select(MedicationList)
        .where(MedicationList.id == list_id)
        .options(selectinload(MedicationList.items).selectinload(MedicationListItem.medication))
        .execution_options(populate_existing=True)
    )


def get_owned_list(db: Session, user: User, list_id: int, ip: str | None = None) -> MedicationList:
    """SEC-05: 404 if the list does not exist, 403 if it belongs to another user."""
    med_list = _load(db, list_id)
    if med_list is None:
        raise AppError(status.HTTP_404_NOT_FOUND, "list_not_found", "This medication list does not exist.")
    if med_list.user_id != user.id:
        record_event(db, AuthEventType.AUTHZ_DENIED, user.id, ip)
        raise AppError(status.HTTP_403_FORBIDDEN, "forbidden", "You do not have access to this medication list.")
    return med_list


def _ensure_capacity(med_list: MedicationList, adding: int) -> None:
    current = len(_active_items(med_list))
    if current + adding > settings.MAX_MEDS_PER_LIST:
        remaining = max(0, settings.MAX_MEDS_PER_LIST - current)
        raise AppError(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            "list_full",
            f"A list can hold at most {settings.MAX_MEDS_PER_LIST} medications. "
            f"You can add {remaining} more.",
            fields={"names": f"At most {remaining} more medication(s) can be added."},
        )


def _mark_list_edited(db: Session, med_list: MedicationList) -> None:
    """FR-7 / SAF-08: editing a confirmed list returns it to draft and marks earlier analyses outdated."""
    med_list.confirmation_status = ConfirmationStatus.DRAFT
    db.execute(
        update(AnalysisResult)
        .where(AnalysisResult.list_id == med_list.id, AnalysisResult.freshness == Freshness.CURRENT)
        .values(freshness=Freshness.OUTDATED)
    )


def build_item(db: Session, raw_text: str) -> MedicationListItem:
    norm = normalize_name(db, raw_text)
    return MedicationListItem(
        raw_text=raw_text,
        medication_id=norm.medication_id,
        match_score=norm.match_score,
        confirmation_flag=ConfirmationFlag.UNRESOLVED,
    )


def create_list(db: Session, user: User, names: list[str]) -> MedicationList:
    med_list = MedicationList(
        user_id=user.id,
        source=ListSource.MANUAL,
        confirmation_status=ConfirmationStatus.DRAFT,
    )
    med_list.items = [build_item(db, name) for name in names]
    db.add(med_list)
    db.commit()
    return _load(db, med_list.id)


def list_user_lists(db: Session, user: User) -> list[MedicationListSummary]:
    counts = (
        select(MedicationListItem.list_id, func.count().label("n"))
        .where(MedicationListItem.confirmation_flag != ConfirmationFlag.REMOVED)
        .group_by(MedicationListItem.list_id)
        .subquery()
    )
    rows = db.execute(
        select(MedicationList, func.coalesce(counts.c.n, 0))
        .outerjoin(counts, counts.c.list_id == MedicationList.id)
        .where(MedicationList.user_id == user.id)
        .order_by(MedicationList.created_at.desc(), MedicationList.id.desc())
    ).all()
    return [to_summary(ml, n) for ml, n in rows]


def add_items(db: Session, med_list: MedicationList, names: list[str]) -> MedicationList:
    _ensure_capacity(med_list, len(names))
    for name in names:
        med_list.items.append(build_item(db, name))
    if med_list.source == ListSource.OCR:
        med_list.source = ListSource.MIXED
    _mark_list_edited(db, med_list)
    db.commit()
    return _load(db, med_list.id)


def _get_item(med_list: MedicationList, item_id: int) -> MedicationListItem:
    for item in med_list.items:
        if item.id == item_id:
            return item
    raise AppError(status.HTTP_404_NOT_FOUND, "item_not_found", "This medication is not in the list.")


def update_item(db: Session, med_list: MedicationList, item_id: int, raw_text: str) -> MedicationList:
    item = _get_item(med_list, item_id)
    norm = normalize_name(db, raw_text)
    item.raw_text = raw_text
    item.medication_id = norm.medication_id
    item.match_score = norm.match_score
    item.confirmation_flag = ConfirmationFlag.UNRESOLVED
    _mark_list_edited(db, med_list)
    db.commit()
    return _load(db, med_list.id)


def delete_item(db: Session, med_list: MedicationList, item_id: int) -> MedicationList:
    item = _get_item(med_list, item_id)
    med_list.items.remove(item)
    _mark_list_edited(db, med_list)
    db.commit()
    return _load(db, med_list.id)


def delete_list(db: Session, med_list: MedicationList) -> None:
    db.delete(med_list)
    db.commit()
