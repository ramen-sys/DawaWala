"""Run, store and reopen safety analyses (FR-8 to FR-15) and manage list risk factors (FR-14)."""

from __future__ import annotations

from collections import Counter
from datetime import date

from fastapi import status
from sqlalchemy import select, update
from sqlalchemy.orm import Session, selectinload

from app.core.config import settings
from app.core.errors import AppError
from app.engine import ConfirmedItem, KnowledgeBase, analyze
from app.engine.models import CASCADE, CONTRAINDICATION, DDI, DUPLICATE
from app.models import AnalysisResult, AnalysisWarning, MedicationList, RiskFactor
from app.models.enums import ConfirmationFlag, ConfirmationStatus, FactorType, Freshness, SeverityBand, WarningCategory
from app.schemas.analysis import AnalysisOut, AnalysisSummary, RiskFactors, RiskFactorsOut
from app.services.explanations import explain
from app.services.scoring import ranking_key, score_warning

DISCLAIMER = "Decision support only. This is not medical advice. Discuss these results with your doctor or pharmacist."
NO_WARNINGS_MESSAGE = "No interactions were found in the knowledge base for the medications analysed"

_CATEGORY = {
    DDI: WarningCategory.DDI,
    DUPLICATE: WarningCategory.DUPLICATE,
    CONTRAINDICATION: WarningCategory.CONTRAINDICATION,
    CASCADE: WarningCategory.CASCADE,
}
FACTOR_NAMES = tuple(RiskFactors.model_fields)  # age_range, kidney_function, liver_function


# --------------------------------------------------------------------------
# Risk factors (FR-14)
# --------------------------------------------------------------------------


def current_risk_factors(med_list: MedicationList) -> RiskFactors:
    stored = {
        str(getattr(rf.factor_type, "value", rf.factor_type)): rf.factor_value
        for rf in med_list.risk_factors
        if str(getattr(rf.factor_type, "value", rf.factor_type)) in FACTOR_NAMES
    }
    return RiskFactors(**stored)


def mark_analyses_outdated(db: Session, list_id: int) -> bool:
    """SAF-08: earlier results of this list are no longer current. Returns True if any changed."""
    result = db.execute(
        update(AnalysisResult)
        .where(AnalysisResult.list_id == list_id, AnalysisResult.freshness == Freshness.CURRENT)
        .values(freshness=Freshness.OUTDATED)
    )
    return result.rowcount > 0


def set_risk_factors(db: Session, med_list: MedicationList, factors: RiskFactors) -> RiskFactorsOut:
    """Replace the list's factors. Changing them outdates earlier analyses (FR-14, SAF-08);
    the list itself stays confirmed, because its medications did not change."""
    before = current_risk_factors(med_list)
    by_type = {str(getattr(rf.factor_type, "value", rf.factor_type)): rf for rf in med_list.risk_factors}
    for name in FACTOR_NAMES:
        value = getattr(factors, name)
        row = by_type.get(name)
        if row is None:
            med_list.risk_factors.append(
                RiskFactor(user_id=med_list.user_id, factor_type=FactorType(name), factor_value=value)
            )
        else:
            row.factor_value = value
    outdated = before != factors and mark_analyses_outdated(db, med_list.id)
    db.commit()
    return RiskFactorsOut(**factors.model_dump(), analysis_outdated=outdated)


# --------------------------------------------------------------------------
# Analysis (FR-8 to FR-13, FR-15)
# --------------------------------------------------------------------------


def _confirmed_items(med_list: MedicationList) -> list[ConfirmedItem]:
    items = []
    for item in med_list.items:
        if item.confirmation_flag == ConfirmationFlag.ACCEPTED:
            items.append(ConfirmedItem(item.id, item.medication_id, item.raw_text))
        elif item.confirmation_flag == ConfirmationFlag.KEPT_UNRECOGNISED:
            items.append(ConfirmedItem(item.id, None, item.raw_text))  # reported under "Not analysed"
    return items


def run_analysis(db: Session, med_list: MedicationList, kb: KnowledgeBase) -> AnalysisResult:
    # BR-01 / SAF-01: never analyse a list the user has not confirmed.
    if med_list.confirmation_status != ConfirmationStatus.CONFIRMED:
        raise AppError(
            status.HTTP_409_CONFLICT,
            "list_not_confirmed",
            "Please review and confirm the medication list before running the analysis.",
        )

    factors = current_risk_factors(med_list)
    patient = {name: value for name, value in factors.model_dump().items() if value != "unknown"}
    result = analyze(_confirmed_items(med_list), kb, patient)

    scored = [(w, score_warning(w)) for w in result.warnings]
    scored.sort(key=lambda pair: ranking_key(*pair))

    mark_analyses_outdated(db, med_list.id)  # only the newest analysis of a list is current
    row = AnalysisResult(
        list_id=med_list.id,
        kb_version=result.kb_version,
        kb_updated_on=result.kb_updated,
        freshness=Freshness.CURRENT,
        risk_factors=factors.model_dump(),
        not_analysed=[
            {"item_id": n.item_id, "entered_text": n.entered_text, "reason": n.reason} for n in result.not_analysed
        ],
        not_assessed=[
            {"rule_id": n.rule_id, "medication_id": n.medication_id, "medication_name": n.medication_name,
             "missing_factor": n.missing_factor}
            for n in result.not_assessed
        ],
    )
    for rank, (warning, score) in enumerate(scored):
        row.warnings.append(
            AnalysisWarning(
                rank=rank,
                category=_CATEGORY[warning.category],
                rule_reference=warning.rule_id,
                related_medications=[
                    {"id": med_id, "name": name}
                    for med_id, name in zip(warning.medication_ids, warning.medication_names, strict=True)
                ],
                score=score.score,
                severity_band=score.band,
                score_factors=score.factors,
                explanation=explain(warning),
                details={
                    **warning.details,
                    "rule_severity": warning.severity,
                    "description": warning.description,
                    "relevant_factors": list(warning.relevant_factors),
                    "matched_factors": list(warning.matched_factors),
                },
            )
        )
    db.add(row)
    db.commit()
    return get_analysis(db, med_list, row.id)


def list_analyses(db: Session, med_list: MedicationList) -> list[AnalysisSummary]:
    rows = db.scalars(
        select(AnalysisResult)
        .where(AnalysisResult.list_id == med_list.id)
        .options(selectinload(AnalysisResult.warnings))
        .order_by(AnalysisResult.timestamp.desc(), AnalysisResult.id.desc())
    ).all()
    return [to_summary(row) for row in rows]


def get_analysis(db: Session, med_list: MedicationList, analysis_id: int) -> AnalysisResult:
    row = db.scalar(
        select(AnalysisResult)
        .where(AnalysisResult.id == analysis_id, AnalysisResult.list_id == med_list.id)
        .options(selectinload(AnalysisResult.warnings))
        .execution_options(populate_existing=True)
    )
    if row is None:
        raise AppError(status.HTTP_404_NOT_FOUND, "analysis_not_found", "This analysis does not exist.")
    return row


def _band_counts(row: AnalysisResult) -> dict[SeverityBand, int]:
    counts = Counter(w.severity_band for w in row.warnings)
    return {band: counts.get(band, 0) for band in SeverityBand}


def to_summary(row: AnalysisResult) -> AnalysisSummary:
    return AnalysisSummary(
        id=row.id,
        list_id=row.list_id,
        created_at=row.timestamp,
        freshness=row.freshness,
        kb_version=row.kb_version,
        warning_count=len(row.warnings),
        band_counts=_band_counts(row),
    )


def is_stale(kb_updated_on: str, today: date | None = None) -> bool:
    """SAF-07: results from a knowledge base older than KB_STALE_DAYS may be out of date."""
    try:
        updated = date.fromisoformat(kb_updated_on)
    except ValueError:
        return True  # unknown date: say so rather than imply it is current
    return ((today or date.today()) - updated).days > settings.KB_STALE_DAYS


def to_out(row: AnalysisResult) -> AnalysisOut:
    warnings = sorted(row.warnings, key=lambda w: w.rank)
    return AnalysisOut(
        **to_summary(row).model_dump(),
        disclaimer=DISCLAIMER,
        kb_updated_on=row.kb_updated_on,
        kb_stale=is_stale(row.kb_updated_on),
        no_warnings_message=None if warnings else NO_WARNINGS_MESSAGE,
        risk_factors=RiskFactors(**(row.risk_factors or {})),
        warnings=[
            {
                "id": w.id, "rank": w.rank, "category": w.category, "rule_id": w.rule_reference,
                "score": w.score, "severity_band": w.severity_band, "score_factors": w.score_factors,
                "medications": w.related_medications, "explanation": w.explanation, "details": w.details,
            }
            for w in warnings
        ],
        not_analysed=row.not_analysed or [],
        not_assessed=row.not_assessed or [],
    )
