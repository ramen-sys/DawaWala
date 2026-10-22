"""Enumerated values from SRS Section 5.1 and Appendix A.2."""

from enum import StrEnum

import sqlalchemy as sa


class UserRole(StrEnum):
    PATIENT = "patient"
    HEALTHCARE_PROFESSIONAL = "healthcare_professional"


class ListSource(StrEnum):
    MANUAL = "manual"
    OCR = "ocr"
    MIXED = "mixed"


class ConfirmationStatus(StrEnum):
    DRAFT = "draft"
    CONFIRMED = "confirmed"


class ConfirmationFlag(StrEnum):
    UNRESOLVED = "unresolved"
    ACCEPTED = "accepted"
    KEPT_UNRECOGNISED = "kept_unrecognised"
    REMOVED = "removed"


class ConfidenceLabel(StrEnum):
    HIGH = "high"
    LOW = "low"
    UNRECOGNISED = "unrecognised"


class OcrStatus(StrEnum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class Severity(StrEnum):
    MINOR = "minor"
    MODERATE = "moderate"
    MAJOR = "major"
    CONTRAINDICATED = "contraindicated"


class FactorType(StrEnum):
    AGE_RANGE = "age_range"
    KIDNEY_FUNCTION = "kidney_function"
    LIVER_FUNCTION = "liver_function"
    OTHER = "other"


class WarningCategory(StrEnum):
    DDI = "ddi"
    DUPLICATE = "duplicate"
    CONTRAINDICATION = "contraindication"
    CASCADE = "cascade"


class SeverityBand(StrEnum):
    LOW = "low"
    MODERATE = "moderate"
    HIGH = "high"
    CRITICAL = "critical"


class Freshness(StrEnum):
    CURRENT = "current"
    OUTDATED = "outdated"


def enum_column(enum_cls: type[StrEnum], name: str) -> sa.Enum:
    """Store enums as VARCHAR + CHECK constraint so new values only need a migration, not a type change."""
    return sa.Enum(
        enum_cls,
        name=name,
        native_enum=False,
        create_constraint=True,
        length=32,
        values_callable=lambda e: [m.value for m in e],
        validate_strings=True,
    )
