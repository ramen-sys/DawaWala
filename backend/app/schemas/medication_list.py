from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.core.config import settings
from app.models.enums import ConfidenceLabel, ConfirmationFlag, ConfirmationStatus, ListSource


def clean_medication_name(value: str) -> str:
    value = " ".join(value.split())
    if not settings.NAME_MIN_LEN <= len(value) <= settings.NAME_MAX_LEN:
        raise ValueError(
            f"Each medication name must be {settings.NAME_MIN_LEN}-{settings.NAME_MAX_LEN} characters long."
        )
    return value


class MedicationNames(BaseModel):
    names: list[str] = Field(min_length=1, examples=[["Panadol", "Brufen 400mg"]])

    @field_validator("names")
    @classmethod
    def validate_names(cls, names: list[str]) -> list[str]:
        if len(names) > settings.MAX_MEDS_PER_LIST:
            raise ValueError(f"A list can contain at most {settings.MAX_MEDS_PER_LIST} medications.")
        return [clean_medication_name(n) for n in names]


class MedicationItemUpdate(BaseModel):
    raw_text: str = Field(examples=["Augmentin"])

    @field_validator("raw_text")
    @classmethod
    def validate_raw_text(cls, v: str) -> str:
        return clean_medication_name(v)


class MedicationRef(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    standard_name: str
    drug_class: str | None


class MedicationItemOut(BaseModel):
    id: int
    raw_text: str
    medication: MedicationRef | None
    match_score: int | None
    confidence_label: ConfidenceLabel | None
    confirmation_flag: ConfirmationFlag


class MedicationListSummary(BaseModel):
    id: int
    source: ListSource
    confirmation_status: ConfirmationStatus
    item_count: int
    created_at: datetime


class MedicationListOut(MedicationListSummary):
    items: list[MedicationItemOut]


class MedicationSearchResult(BaseModel):
    id: int
    standard_name: str
    drug_class: str | None
    matched_on: str
