"""Test fixtures.

Tests run against the configured PostgreSQL database, but inside a throwaway schema
(``test_<random>``) that is created at the start of the session and dropped at the end,
so real data is never touched.
"""

import uuid
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from app.core.config import settings
from app.db.base import Base
from app.db.session import SessionLocal, get_db
from app.engine import ConfirmedItem, load_kb, load_kb_from_db
from app.main import app
from app.models import Medication, MedicationAlias

TEST_SCHEMA = f"test_{uuid.uuid4().hex[:10]}"


@pytest.fixture(scope="session")
def engine():
    base_engine = create_engine(settings.DATABASE_URL, pool_pre_ping=True)
    with base_engine.begin() as conn:
        # pg_trgm provides gin_trgm_ops for the name indexes; it is database-wide, not per schema.
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS pg_trgm"))
        conn.execute(text(f'CREATE SCHEMA "{TEST_SCHEMA}"'))
    test_engine = base_engine.execution_options(schema_translate_map={None: TEST_SCHEMA})
    Base.metadata.create_all(test_engine)
    _seed_kb(test_engine)
    yield test_engine
    with base_engine.begin() as conn:
        conn.execute(text(f'DROP SCHEMA "{TEST_SCHEMA}" CASCADE'))
    base_engine.dispose()


def _medication(name: str, drug_class: str, aliases: list[str]) -> Medication:
    return Medication(
        standard_name=name,
        drug_class=drug_class,
        source="test fixture",
        aliases=[MedicationAlias(alias=a) for a in aliases],
    )


def _seed_kb(test_engine) -> None:
    """Small fixed knowledge base so list/normalization tests do not depend on the Kaggle import."""
    Session = sessionmaker(bind=test_engine)
    with Session() as db:
        db.add_all([
            _medication("Paracetamol", "Analgesic / antipyretic", ["Panadol", "Calpol"]),
            _medication("Ibuprofen", "NSAID", ["Brufen"]),
            _medication("Omeprazole", "Proton-pump inhibitor", ["Risek", "Losec"]),
        ])
        db.commit()


@pytest.fixture(scope="session")
def session_factory(engine):
    return sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


@pytest.fixture(scope="session")
def client(session_factory):
    def override_get_db():
        db = session_factory()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture
def db(session_factory):
    with session_factory() as session:
        yield session


def unique_email(prefix: str = "user") -> str:
    return f"{prefix}_{uuid.uuid4().hex[:8]}@example.com"


@pytest.fixture
def make_user(client):
    """Register a user and return (credentials, auth headers)."""

    def _make(password: str = "Secret123", role: str = "user") -> tuple[dict, dict]:
        creds = {"name": "Test User", "email": unique_email(), "password": password, "role": role}
        r = client.post("/api/v1/auth/register", json=creds)
        assert r.status_code == 201, r.text
        r = client.post("/api/v1/auth/login", json={"email": creds["email"], "password": password})
        assert r.status_code == 200, r.text
        return creds, {"Authorization": f"Bearer {r.json()['access_token']}"}

    return _make


FIXTURE_KB = Path(__file__).parent / "engine" / "fixtures" / "kb"


@pytest.fixture(scope="session")
def kb():
    """Frozen test knowledge base (QA-TST-02). Change it only on purpose."""
    return load_kb(FIXTURE_KB)


@pytest.fixture(scope="session")
def real_kb():
    """The knowledge base stored in PostgreSQL."""
    with SessionLocal() as db:
        return load_kb_from_db(db)


@pytest.fixture
def items(kb):
    """Build a confirmed list from names as a user might enter them.

    items("Panadol", "warfarin") -> ConfirmedItems with resolved ids.
    A name prefixed with "?" is kept as unrecognised (medication_id None).
    """
    lookup = {}
    for med in kb.medications.values():
        lookup[med.standard_name.lower()] = med.medication_id
        for alias in med.aliases:
            lookup[alias.lower()] = med.medication_id

    def build(*names):
        result = []
        for i, name in enumerate(names, start=1):
            if name.startswith("?"):
                result.append(ConfirmedItem(i, None, name[1:]))
            else:
                result.append(ConfirmedItem(i, lookup[name.lower()], name))
        return result

    return build


def by_rule(result_or_warnings, rule_id):
    warnings = getattr(result_or_warnings, "warnings", result_or_warnings)
    return [w for w in warnings if w.rule_id == rule_id]
