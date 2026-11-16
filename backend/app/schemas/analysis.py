from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict

from app.models.enums import Freshness, SeverityBand, WarningCategory

AgeRange = Literal["under_18", "18_64", "65_plus", "unknown"]
OrganFunction = Literal["normal", "impaired", "unknown"]


class RiskFactors(BaseModel):
    """FR-14: optional patient factors for one list. Anything not given is "unknown"."""

    model_config = ConfigDict(extra="forbid")

    age_range: AgeRange = "unknown"
    kidney_function: OrganFunction = "unknown"
    liver_function: OrganFunction = "unknown"


class RiskFactorsOut(RiskFactors):
    # True when saving these factors made an earlier analysis outdated (FR-14: prompt to re-run).
    analysis_outdated: bool = False


class ScoreFactor(BaseModel):
    factor: str
    points: int


class WarningMedication(BaseModel):
    id: int
    name: str


class WarningOut(BaseModel):
    id: int
    rank: int
    category: WarningCategory
    rule_id: str
    score: int
    severity_band: SeverityBand
    score_factors: list[ScoreFactor]
    medications: list[WarningMedication]
    explanation: str
    details: dict


class NotAnalysedOut(BaseModel):
    item_id: int | str
    entered_text: str
    reason: Literal["unrecognised", "not_in_knowledge_base"]


class NotAssessedOut(BaseModel):
    rule_id: str
    medication_id: int
    medication_name: str
    missing_factor: str


class AnalysisSummary(BaseModel):
    id: int
    list_id: int
    created_at: datetime
    freshness: Freshness
    kb_version: str
    warning_count: int
    band_counts: dict[SeverityBand, int]


class AnalysisOut(AnalysisSummary):
    disclaimer: str
    kb_updated_on: str
    kb_stale: bool
    # Set only when there are no warnings (SAF-03: never "safe").
    no_warnings_message: str | None
    risk_factors: RiskFactors
    warnings: list[WarningOut]
    not_analysed: list[NotAnalysedOut]
    not_assessed: list[NotAssessedOut]
