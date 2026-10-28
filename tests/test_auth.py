"""FR-1 (registration), FR-2 (authentication), SEC-01/02/03/05/08/10."""

import logging
from datetime import datetime, timedelta, timezone

from jose import jwt
from sqlalchemy import func, select

from app.core.config import settings
from app.models import AuthEvent, User
from app.models.enums import AuthEventType
from app.services.auth_event_service import purge_old_events
from tests.conftest import unique_email

API = "/api/v1/auth"


def register(client, **overrides):
    body = {"name": "Ali Khan", "email": unique_email(), "password": "Secret123", "role": "user"}
    body.update(overrides)
    return client.post(f"{API}/register", json=body), body


# ---------- FR-1: registration ----------

def test_register_success_returns_user_without_password(client):
    r, body = register(client, email=f"Mixed.{unique_email('Case')}".replace("example.com", "Example.COM"))
    assert r.status_code == 201
    data = r.json()
    assert data["message"]
    assert data["user"]["email"] == body["email"].lower()
    assert data["user"]["role"] == "user"
    assert "password" not in str(data).lower()


def test_register_admin_role(client):
    r, _ = register(client, role="admin")
    assert r.status_code == 201
    assert r.json()["user"]["role"] == "admin"


def test_role_defaults_to_user(client):
    body = {"name": "No Role", "email": unique_email(), "password": "Secret123"}
    r = client.post(f"{API}/register", json=body)
    assert r.status_code == 201
    assert r.json()["user"]["role"] == "user"


def test_password_stored_as_bcrypt_hash(client, db):
    r, body = register(client)
    user = db.scalar(select(User).where(User.email == body["email"]))
    assert user.password_hash != body["password"]
    assert user.password_hash.startswith("$2")


def test_register_duplicate_email_case_insensitive(client):
    r, body = register(client)
    assert r.status_code == 201
    r2, _ = register(client, email=body["email"].upper())
    assert r2.status_code == 409
    assert r2.json()["code"] == "email_taken"
    assert "email" in r2.json()["fields"]


def test_register_invalid_email(client):
    r, _ = register(client, email="not-an-email")
    assert r.status_code == 422
    assert r.json()["code"] == "validation_error"
    assert "email" in r.json()["fields"]


def test_register_password_rules(client):
    for bad in ["short1", "allletters", "12345678"]:
        r, _ = register(client, password=bad)
        assert r.status_code == 422, bad
        assert "password" in r.json()["fields"]


def test_register_invalid_role_and_blank_name(client):
    for old_role in ("patient", "healthcare_professional", "superuser"):
        r, _ = register(client, role=old_role)
        assert r.status_code == 422, old_role
        assert "role" in r.json()["fields"]
    r, _ = register(client, name="   ")
    assert r.status_code == 422
    assert "name" in r.json()["fields"]


# ---------- FR-2: authentication ----------

def test_login_success_returns_30_min_jwt(client):
    _, body = register(client)
    r = client.post(f"{API}/login", json={"email": body["email"], "password": body["password"]})
    assert r.status_code == 200
    data = r.json()
    assert data["token_type"] == "bearer"
    assert data["expires_in"] == 30 * 60
    claims = jwt.decode(data["access_token"], settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
    assert claims["exp"] - claims["iat"] == 30 * 60
    assert claims["sub"] == str(data["user"]["id"])


def test_login_email_is_case_insensitive(client):
    _, body = register(client)
    r = client.post(f"{API}/login", json={"email": body["email"].upper(), "password": body["password"]})
    assert r.status_code == 200


def test_login_error_does_not_reveal_whether_email_exists(client):
    _, body = register(client)
    wrong_pw = client.post(f"{API}/login", json={"email": body["email"], "password": "Wrong1234"})
    no_user = client.post(f"{API}/login", json={"email": unique_email(), "password": "Wrong1234"})
    assert wrong_pw.status_code == no_user.status_code == 401
    assert wrong_pw.json() == no_user.json()


def test_account_locks_after_5_failures_and_unlocks_after_15_min(client, db):
    _, body = register(client)
    for _ in range(4):
        r = client.post(f"{API}/login", json={"email": body["email"], "password": "Wrong1234"})
        assert r.status_code == 401
    r = client.post(f"{API}/login", json={"email": body["email"], "password": "Wrong1234"})
    assert r.status_code == 423
    assert r.json()["code"] == "account_locked"

    # Even the right password is refused while locked.
    r = client.post(f"{API}/login", json={"email": body["email"], "password": body["password"]})
    assert r.status_code == 423

    user = db.scalar(select(User).where(User.email == body["email"]))
    remaining = user.locked_until - datetime.now(timezone.utc)
    assert timedelta(minutes=14) < remaining <= timedelta(minutes=15)

    user.locked_until = datetime.now(timezone.utc) - timedelta(seconds=1)
    db.commit()
    r = client.post(f"{API}/login", json={"email": body["email"], "password": body["password"]})
    assert r.status_code == 200


def test_successful_login_resets_failed_counter(client):
    _, body = register(client)
    for _ in range(4):
        client.post(f"{API}/login", json={"email": body["email"], "password": "Wrong1234"})
    assert client.post(f"{API}/login", json={"email": body["email"], "password": body["password"]}).status_code == 200
    # Counter was reset, so 4 more failures still do not lock.
    for _ in range(4):
        assert client.post(f"{API}/login", json={"email": body["email"], "password": "Wrong1234"}).status_code == 401


def test_auth_events_logged_without_secrets(client, caplog):
    with caplog.at_level(logging.INFO, logger="dawawala.auth"):
        r, body = register(client)
        client.post(f"{API}/login", json={"email": body["email"], "password": "Wrong1234"})
        token = client.post(f"{API}/login", json={"email": body["email"], "password": body["password"]}).json()
    user_id = r.json()["user"]["id"]
    messages = [rec.getMessage() for rec in caplog.records if rec.name == "dawawala.auth"]
    for event in ("register", "login_failed", "login_success"):
        assert any(f"event={event} user_id={user_id}" in m for m in messages), event
    joined = "\n".join(messages)
    assert body["password"] not in joined and "Wrong1234" not in joined
    assert token["access_token"] not in joined and body["email"] not in joined


def test_auth_events_stored_in_table(client, db):
    r, body = register(client)
    user_id = r.json()["user"]["id"]
    client.post(f"{API}/login", json={"email": body["email"], "password": "Wrong1234"})
    client.post(f"{API}/login", json={"email": body["email"], "password": body["password"]})

    events = db.scalars(select(AuthEvent).where(AuthEvent.user_id == user_id).order_by(AuthEvent.id)).all()
    assert [e.event_type for e in events] == [
        AuthEventType.REGISTER, AuthEventType.LOGIN_FAILED, AuthEventType.LOGIN_SUCCESS
    ]
    assert all(e.ip_address and e.created_at for e in events)
    # The table has no column that could hold a password, token, e-mail or medication.
    assert set(AuthEvent.__table__.columns.keys()) == {"id", "user_id", "event_type", "ip_address", "created_at"}


def test_failed_login_for_unknown_email_is_stored_without_user(client, db):
    email = unique_email("ghost")
    before = db.scalar(select(func.count()).select_from(AuthEvent).where(AuthEvent.user_id.is_(None)))
    client.post(f"{API}/login", json={"email": email, "password": "Wrong1234"})
    after = db.scalar(select(func.count()).select_from(AuthEvent).where(AuthEvent.user_id.is_(None)))
    assert after == before + 1


def test_lockout_and_forbidden_access_are_stored(client, make_user, db):
    _, body = register(client)
    for _ in range(5):
        client.post(f"{API}/login", json={"email": body["email"], "password": "Wrong1234"})
    user = db.scalar(select(User).where(User.email == body["email"]))
    types = db.scalars(select(AuthEvent.event_type).where(AuthEvent.user_id == user.id)).all()
    assert AuthEventType.ACCOUNT_LOCKED in types

    _, owner = make_user()
    lst = client.post("/api/v1/medication-lists", json={"names": ["Panadol"]}, headers=owner).json()
    intruder_creds, intruder = make_user()
    assert client.get(f"/api/v1/medication-lists/{lst['id']}", headers=intruder).status_code == 403
    intruder_id = db.scalar(select(User.id).where(User.email == intruder_creds["email"]))
    types = db.scalars(select(AuthEvent.event_type).where(AuthEvent.user_id == intruder_id)).all()
    assert AuthEventType.AUTHZ_DENIED in types


def test_auth_events_older_than_90_days_are_purged(db):
    now = datetime.now(timezone.utc)
    old = AuthEvent(event_type=AuthEventType.LOGIN_FAILED, ip_address="10.0.0.1", created_at=now - timedelta(days=91))
    recent = AuthEvent(event_type=AuthEventType.LOGIN_FAILED, ip_address="10.0.0.2", created_at=now - timedelta(days=89))
    db.add_all([old, recent])
    db.commit()
    old_id, recent_id = old.id, recent.id

    assert purge_old_events(db, now) >= 1
    assert db.get(AuthEvent, old_id) is None
    assert db.get(AuthEvent, recent_id) is not None


# ---------- Protected endpoints / JWT ----------

def test_me_requires_token(client):
    r = client.get(f"{API}/me")
    assert r.status_code == 401
    assert r.json()["code"] == "not_authenticated"
    assert r.headers.get("www-authenticate") == "Bearer"


def test_me_rejects_tampered_and_expired_tokens(client, make_user):
    creds, headers = make_user()
    assert client.get(f"{API}/me", headers=headers).json()["email"] == creds["email"]

    tampered = headers["Authorization"][:-3] + "abc"
    assert client.get(f"{API}/me", headers={"Authorization": tampered}).status_code == 401

    expired = jwt.encode(
        {"sub": "1", "type": "access", "exp": datetime.now(timezone.utc) - timedelta(minutes=1)},
        settings.JWT_SECRET_KEY,
        algorithm=settings.JWT_ALGORITHM,
    )
    assert client.get(f"{API}/me", headers={"Authorization": f"Bearer {expired}"}).status_code == 401

    forged = jwt.encode({"sub": "1", "type": "access"}, "wrong-secret", algorithm="HS256")
    assert client.get(f"{API}/me", headers={"Authorization": f"Bearer {forged}"}).status_code == 401


def test_delete_account_removes_user_and_lists(client, make_user, db):
    creds, headers = make_user()
    r = client.post("/api/v1/medication-lists", json={"names": ["Panadol"]}, headers=headers)
    assert r.status_code == 201
    assert client.delete(f"{API}/me", headers=headers).status_code == 204
    assert db.scalar(select(User).where(User.email == creds["email"])) is None
    # Token of a deleted user no longer works.
    assert client.get(f"{API}/me", headers=headers).status_code == 401
    r = client.post(f"{API}/login", json={"email": creds["email"], "password": creds["password"]})
    assert r.status_code == 401
