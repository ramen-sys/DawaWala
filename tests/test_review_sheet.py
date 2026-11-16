"""Clinical review sheet (SAF-09): approvals are kept, and reset when a rule changes."""

import csv
import importlib.util
import shutil
from pathlib import Path

import pytest

from app.engine.loader import DEFAULT_KB_DIR

_spec = importlib.util.spec_from_file_location(
    "review_sheet", Path(__file__).resolve().parents[1] / "knowledge_base" / "review_sheet.py"
)
review_sheet = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(review_sheet)


@pytest.fixture
def sandbox(tmp_path, monkeypatch):
    kb_dir = tmp_path / "kb"
    shutil.copytree(DEFAULT_KB_DIR, kb_dir)
    monkeypatch.setattr(review_sheet, "SHEET", tmp_path / "review" / "clinical_review.csv")
    monkeypatch.setattr(review_sheet, "EVIDENCE", tmp_path / "review" / "evidence_check.csv")
    monkeypatch.setattr(review_sheet, "DEFAULT_KB_DIR", kb_dir)
    return kb_dir


def write(rows):
    path = review_sheet.SHEET
    path.parent.mkdir(exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=review_sheet.RULE_COLUMNS + review_sheet.REVIEW_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)


def approve(row):
    row.update(reviewer_name="Dr A", reviewer_role="Pharmacist", review_date="2026-11-05", decision="approved")


def test_approval_kept_until_rule_changes(sandbox):
    sheet = review_sheet.build(sandbox)
    assert len(sheet) == 27
    approve(sheet[0])
    write(sheet)
    assert review_sheet.status(review_sheet.build(sandbox)) == (1, [])

    interactions = sandbox / "interactions.csv"
    text = interactions.read_text(encoding="utf-8")
    assert "Taking these together increases" in text
    interactions.write_text(text.replace("Taking these together increases", "Taking these together raises"),
                            encoding="utf-8")
    first = review_sheet.build(sandbox)[0]
    assert first["decision"] == ""
    assert first["reviewer_comments"].startswith("[rule changed after review; previous decision: approved]")


def test_incomplete_or_invalid_decisions_are_reported(sandbox):
    sheet = review_sheet.build(sandbox)
    sheet[0]["decision"] = "approved"
    sheet[1]["decision"] = "ok"
    approved, problems = review_sheet.status(sheet)
    assert approved == 0
    assert any("approved without reviewer" in p for p in problems)
    assert any("'ok' must be one of" in p for p in problems)


def test_evidence_summary_is_merged(sandbox):
    review_sheet.EVIDENCE.parent.mkdir(exist_ok=True)
    review_sheet.EVIDENCE.write_text("rule_id,summary\nCAS-0001,supported by test\n", encoding="utf-8")
    row = next(r for r in review_sheet.build(sandbox) if r["rule_id"] == "CAS-0001")
    assert row["evidence_check"] == "supported by test"
    assert row["severity"] == ""


def test_main_check_exits_1_until_all_approved(sandbox, capsys):
    assert review_sheet.main(["--check"]) == 1
    assert "Clinically approved: 0/27" in capsys.readouterr().out
