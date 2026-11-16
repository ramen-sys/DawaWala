"""FR-3 (manual medication entry), medication-list REST endpoints, SEC-05 ownership, SAF-08."""

from sqlalchemy import select

from app.models import AnalysisResult, MedicationList
from app.models.enums import ConfirmationStatus, Freshness, ListSource

API = "/api/v1/medication-lists"


def create(client, headers, names):
    return client.post(API, json={"names": names}, headers=headers)


# ---------- FR-3: create ----------

def test_create_draft_manual_list(client, make_user):
    _, h = make_user()
    r = create(client, h, ["Panadol 500mg", "  Brufen   400 mg ", "UnknownDrugXyz"])
    assert r.status_code == 201, r.text
    data = r.json()
    assert data["confirmation_status"] == "draft"
    assert data["source"] == "manual"
    assert data["item_count"] == 3
    items = data["items"]
    assert [i["raw_text"] for i in items] == ["Panadol 500mg", "Brufen 400 mg", "UnknownDrugXyz"]
    assert all(i["confirmation_flag"] == "unresolved" for i in items)


def test_names_are_passed_to_normalization(client, make_user):
    _, h = make_user()
    items = create(client, h, ["Panadol 500mg", "ibuprofen", "RISEK 20mg", "UnknownDrugXyz"]).json()["items"]
    assert items[0]["medication"] == {"id": items[0]["medication"]["id"], "standard_name": "Paracetamol",
                                      "drug_class": "Analgesic / antipyretic"}
    assert items[0]["confidence_label"] == "high" and items[0]["match_score"] == 100
    assert items[1]["medication"]["standard_name"] == "Ibuprofen"
    assert items[2]["medication"]["standard_name"] == "Omeprazole"
    assert items[3]["medication"] is None
    assert items[3]["confidence_label"] is None and items[3]["match_score"] is None


def test_name_length_limits(client, make_user):
    _, h = make_user()
    assert create(client, h, ["A"]).status_code == 422
    assert create(client, h, ["x" * 101]).status_code == 422
    assert create(client, h, ["ab", "x" * 100]).status_code == 201


def test_list_requires_at_least_one_and_at_most_30(client, make_user):
    _, h = make_user()
    assert create(client, h, []).status_code == 422
    r = create(client, h, [f"Drug{i}" for i in range(31)])
    assert r.status_code == 422
    assert "names" in r.json()["fields"]
    assert create(client, h, [f"Drug{i}" for i in range(30)]).status_code == 201


def test_add_items_respects_30_limit(client, make_user):
    _, h = make_user()
    list_id = create(client, h, [f"Drug{i}" for i in range(28)]).json()["id"]
    r = client.post(f"{API}/{list_id}/items", json={"names": ["A1", "A2", "A3"]}, headers=h)
    assert r.status_code == 422
    assert r.json()["code"] == "list_full"
    r = client.post(f"{API}/{list_id}/items", json={"names": ["Panadol", "Calpol"]}, headers=h)
    assert r.status_code == 201
    data = r.json()
    assert data["item_count"] == 30
    assert data["items"][-1]["raw_text"] == "Calpol"


# ---------- read / history ----------

def test_get_list_and_history(client, make_user):
    _, h = make_user()
    first = create(client, h, ["Panadol"]).json()
    second = create(client, h, ["Brufen", "Risek"]).json()

    r = client.get(API, headers=h)
    assert r.status_code == 200
    history = r.json()
    assert [l["id"] for l in history] == [second["id"], first["id"]]
    assert [l["item_count"] for l in history] == [2, 1]
    assert "items" not in history[0]

    r = client.get(f"{API}/{first['id']}", headers=h)
    assert r.status_code == 200
    assert r.json()["items"][0]["raw_text"] == "Panadol"


def test_history_is_empty_for_new_user(client, make_user):
    _, h = make_user()
    assert client.get(API, headers=h).json() == []


# ---------- edit / delete ----------

def test_update_item_renormalizes(client, make_user):
    _, h = make_user()
    lst = create(client, h, ["Panadl"]).json()
    item_id = lst["items"][0]["id"]
    assert lst["items"][0]["medication"] is None
    r = client.patch(f"{API}/{lst['id']}/items/{item_id}", json={"raw_text": "Panadol"}, headers=h)
    assert r.status_code == 200
    assert r.json()["items"][0]["medication"]["standard_name"] == "Paracetamol"


def test_delete_item_and_list(client, make_user):
    _, h = make_user()
    lst = create(client, h, ["Panadol", "Brufen"]).json()
    r = client.delete(f"{API}/{lst['id']}/items/{lst['items'][0]['id']}", headers=h)
    assert r.status_code == 200
    assert [i["raw_text"] for i in r.json()["items"]] == ["Brufen"]

    assert client.delete(f"{API}/{lst['id']}", headers=h).status_code == 204
    assert client.get(f"{API}/{lst['id']}", headers=h).status_code == 404


def test_unknown_item_returns_404(client, make_user):
    _, h = make_user()
    lst = create(client, h, ["Panadol"]).json()
    r = client.patch(f"{API}/{lst['id']}/items/999999", json={"raw_text": "Brufen"}, headers=h)
    assert r.status_code == 404
    assert r.json()["code"] == "item_not_found"


def test_editing_confirmed_list_returns_to_draft_and_outdates_analysis(client, make_user, db):
    """FR-7 / SAF-08."""
    _, h = make_user()
    lst = create(client, h, ["Panadol"]).json()

    med_list = db.get(MedicationList, lst["id"])
    med_list.confirmation_status = ConfirmationStatus.CONFIRMED
    med_list.source = ListSource.OCR
    db.add(AnalysisResult(list_id=med_list.id, kb_version="1.0"))
    db.commit()

    r = client.post(f"{API}/{lst['id']}/items", json={"names": ["Brufen"]}, headers=h)
    assert r.status_code == 201
    assert r.json()["confirmation_status"] == "draft"
    assert r.json()["source"] == "mixed"

    db.expire_all()
    analysis = db.scalar(select(AnalysisResult).where(AnalysisResult.list_id == lst["id"]))
    assert analysis.freshness == Freshness.OUTDATED


# ---------- SEC-05: authentication and ownership ----------

def test_all_list_endpoints_require_token(client, make_user):
    _, h = make_user()
    lst = create(client, h, ["Panadol"]).json()
    lid, iid = lst["id"], lst["items"][0]["id"]
    calls = [
        ("post", API, {"names": ["Panadol"]}),
        ("get", API, None),
        ("get", f"{API}/{lid}", None),
        ("delete", f"{API}/{lid}", None),
        ("post", f"{API}/{lid}/items", {"names": ["Brufen"]}),
        ("patch", f"{API}/{lid}/items/{iid}", {"raw_text": "Brufen"}),
        ("delete", f"{API}/{lid}/items/{iid}", None),
        ("get", "/api/v1/medications/search?q=pan", None),
        ("get", "/api/v1/medications/knowledge-base", None),
    ]
    for method, url, body in calls:
        kwargs = {"json": body} if body is not None else {}
        r = getattr(client, method)(url, **kwargs)
        assert r.status_code == 401, (method, url, r.status_code)


def test_other_users_list_is_forbidden(client, make_user):
    _, owner = make_user()
    _, intruder = make_user()
    lst = create(client, owner, ["Panadol"]).json()
    lid, iid = lst["id"], lst["items"][0]["id"]
    calls = [
        ("get", f"{API}/{lid}", None),
        ("delete", f"{API}/{lid}", None),
        ("post", f"{API}/{lid}/items", {"names": ["Brufen"]}),
        ("patch", f"{API}/{lid}/items/{iid}", {"raw_text": "Brufen"}),
        ("delete", f"{API}/{lid}/items/{iid}", None),
    ]
    for method, url, body in calls:
        kwargs = {"json": body} if body is not None else {}
        r = getattr(client, method)(url, headers=intruder, **kwargs)
        assert r.status_code == 403, (method, url, r.status_code)
        assert r.json()["code"] == "forbidden"
    assert lst["id"] not in [l["id"] for l in client.get(API, headers=intruder).json()]
    # Owner's list is untouched.
    r = client.get(f"{API}/{lid}", headers=owner)
    assert r.status_code == 200 and r.json()["item_count"] == 1


def test_missing_list_is_404(client, make_user):
    _, h = make_user()
    r = client.get(f"{API}/99999999", headers=h)
    assert r.status_code == 404
    assert r.json() == {"code": "list_not_found", "message": "This medication list does not exist."}


# ---------- type-ahead ----------

def test_medication_search_by_name_and_brand(client, make_user):
    _, h = make_user()
    r = client.get("/api/v1/medications/search", params={"q": "pan"}, headers=h)
    assert r.status_code == 200
    results = r.json()
    assert results[0]["standard_name"] == "Paracetamol"
    assert results[0]["matched_on"] in {"Panadol", "Panadol Extend"}
    assert all(m["matched_on"].lower().startswith("pan") for m in results)

    r = client.get("/api/v1/medications/search", params={"q": "IBU"}, headers=h)
    assert r.json()[0]["standard_name"] == "Ibuprofen"
    assert r.json()[0]["matched_on"] == "Ibuprofen"

    r = client.get("/api/v1/medications/search", params={"q": "%%"}, headers=h)
    assert r.json() == []

    assert client.get("/api/v1/medications/search", params={"q": "p"}, headers=h).status_code == 422


def test_knowledge_base_info(client, make_user):
    _, h = make_user()
    r = client.get("/api/v1/medications/knowledge-base", headers=h)
    assert r.status_code == 200
    data = r.json()
    assert data["version"] and data["updated_on"]
    assert data["medications"] >= 3
