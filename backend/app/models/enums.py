"""Enumerated values from SRS Section 5.1 and Appendix A.2.

Every enum is stored in PostgreSQL as VARCHAR + CHECK constraint (see ``enum_column``), so the
database itself rejects any value that is not listed here.
"""

from enum import StrEnum

import sqlalchemy as sa


class UserRole(StrEnum):
    """user.role (FR-1, Appendix A.2).

    USER covers both patients and healthcare professionals (same workflow).
    ADMIN is a healthcare professional who may also import/update knowledge-base records.
    """

    USER = "user"
    ADMIN = "admin"


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
    """Rule severity of an interaction or contraindication. Table 5.2 scores them 10 / 30 / 50 / 70."""

    MINOR = "minor"
    MODERATE = "moderate"
    MAJOR = "major"
    CONTRAINDICATED = "contraindicated"


class FactorType(StrEnum):
    """Patient risk-factor types (FR-14). OTHER is for extra factors defined in the knowledge base."""

    AGE_RANGE = "age_range"
    KIDNEY_FUNCTION = "kidney_function"
    LIVER_FUNCTION = "liver_function"
    OTHER = "other"


# Allowed factor values per factor type (Appendix A.2, risk_factor.value). OTHER is free text
# because FR-14 lets the knowledge base define additional factors.
FACTOR_VALUES: dict[FactorType, tuple[str, ...]] = {
    FactorType.AGE_RANGE: ("under_18", "18_64", "65_plus", "unknown"),
    FactorType.KIDNEY_FUNCTION: ("normal", "impaired", "unknown"),
    FactorType.LIVER_FUNCTION: ("normal", "impaired", "unknown"),
}


def factor_pair_check_sql(type_col: str = "factor_type", value_col: str = "factor_value") -> str:
    """SQL for a CHECK constraint that only allows valid (factor_type, factor_value) pairs.

    Used by both risk_factors and contraindications so a typo such as "under18" is rejected
    by the database instead of silently never matching.
    """
    clauses = []
    for factor_type, values in FACTOR_VALUES.items():
        allowed = ", ".join(f"'{v}'" for v in values)
        clauses.append(f"({type_col} = '{factor_type.value}' AND {value_col} IN ({allowed}))")
    clauses.append(f"({type_col} = '{FactorType.OTHER.value}')")
    return " OR ".join(clauses)


def factor_type_array_check_sql(column: str) -> str:
    """SQL for a CHECK constraint that every element of a VARCHAR[] column is a valid FactorType."""
    allowed = ", ".join(f"'{f.value}'" for f in FactorType)
    return f"{column} <@ ARRAY[{allowed}]::varchar[]"


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


class AuthEventType(StrEnum):
    """Authentication events and authorization failures recorded for SEC-10."""

    REGISTER = "register"
    LOGIN_SUCCESS = "login_success"
    LOGIN_FAILED = "login_failed"
    LOGIN_REFUSED_LOCKED = "login_refused_locked"
    ACCOUNT_LOCKED = "account_locked"
    ACCOUNT_DELETED = "account_deleted"
    AUTHZ_DENIED = "authz_denied"


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
