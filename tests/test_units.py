"""Database-free unit tests for security helpers, validation and the normalization pre-processor."""

import pytest
from pydantic import ValidationError

from app.core.security import create_access_token, decode_access_token, hash_password, verify_password
from app.schemas.auth import UserRegister
from app.models.enums import ConfidenceLabel
from app.schemas.medication_list import MedicationNames
from app.services.normalization import confidence_label, extract_drug_term


def test_hash_and_verify_password():
    h = hash_password("Secret123")
    assert h != hash_password("Secret123")  # salted
    assert verify_password("Secret123", h)
    assert not verify_password("secret123", h)
    assert not verify_password("Secret123", "not-a-hash")


def test_token_roundtrip():
    token, ttl = create_access_token(42, "user")
    assert ttl == 1800
    assert decode_access_token(token) == 42
    assert decode_access_token("garbage") is None


@pytest.mark.parametrize("pw", ["Secret12", "abc12345", "Pass word 9"])
def test_valid_passwords(pw):
    UserRegister(name="A", email="a@example.com", password=pw)


@pytest.mark.parametrize("pw", ["Sec12", "abcdefgh", "12345678", "a1" + "x" * 80])
def test_invalid_passwords(pw):
    with pytest.raises(ValidationError):
        UserRegister(name="A", email="a@example.com", password=pw)


def test_medication_names_are_whitespace_normalized():
    data = MedicationNames(names=["  Panadol   500  mg "])
    assert data.names == ["Panadol 500 mg"]


@pytest.mark.parametrize(
    "score, label",
    [(None, None), (100, ConfidenceLabel.HIGH), (90, ConfidenceLabel.HIGH), (89, ConfidenceLabel.LOW),
     (70, ConfidenceLabel.LOW), (69, ConfidenceLabel.UNRECOGNISED), (0, ConfidenceLabel.UNRECOGNISED)],
)
def test_confidence_label_thresholds(score, label):
    """FR-6 / SAF-04: >= 90 High, 70-89 Low, below 70 unrecognised."""
    assert confidence_label(score) == label


@pytest.mark.parametrize(
    "raw, expected",
    [
        ("Panadol 500mg", "Panadol"),
        ("Brufen 400 mg tablet", "Brufen"),
        ("Augmentin 625mg tabs BD", "Augmentin"),
        ("Rivotril 0.5mg", "Rivotril"),
        ("Amoxicillin/clavulanate", "Amoxicillin/clavulanate"),
        ("500 mg", ""),
    ],
)
def test_extract_drug_term(raw, expected):
    assert extract_drug_term(raw) == expected
