"""End-to-end smoke test against a running server.

Usage (server must be running):  python -m scripts.smoke_test [base_url]
"""

import sys
import uuid

import httpx

BASE = (sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8000").rstrip("/")
API = f"{BASE}/api/v1"


def check(label: str, response: httpx.Response, expected: int) -> dict | list | None:
    ok = response.status_code == expected
    print(f"[{'PASS' if ok else 'FAIL'}] {label}: {response.status_code}")
    if not ok:
        print("       ", response.text)
        sys.exit(1)
    return response.json() if response.content else None


def show_items(lst: dict) -> None:
    for item in lst["items"]:
        med = item["medication"]
        target = f"{med['standard_name']} ({med['drug_class']})" if med else "-- not recognised yet --"
        print(f"        - {item['raw_text']!r:22} -> {target}")


def main() -> None:
    with httpx.Client(timeout=60) as c:
        check("health", c.get(f"{BASE}/health"), 200)

        demo = check("login demo account", c.post(f"{API}/auth/login",
                     json={"email": "demo@dawawala.pk", "password": "Demo1234"}), 200)
        h = {"Authorization": f"Bearer {demo['access_token']}"}
        admin = check("login admin account", c.post(f"{API}/auth/login",
                      json={"email": "admin@dawawala.pk", "password": "Admin1234"}), 200)
        print(f"        roles: demo={demo['user']['role']}, admin={admin['user']['role']}")
        kb = check("knowledge-base info", c.get(f"{API}/medications/knowledge-base", headers=h), 200)
        print(f"        KB v{kb['version']} ({kb['updated_on']}): {kb['medications']} medications, "
              f"{kb['contraindications']} contraindications")
        history = check("demo history", c.get(f"{API}/medication-lists", headers=h), 200)
        for lst in history:
            print(f"        - list {lst['id']}: {lst['item_count']} items, {lst['confirmation_status']}")

        email = f"smoke_{uuid.uuid4().hex[:8]}@example.com"
        check("register", c.post(f"{API}/auth/register",
              json={"name": "Smoke Test", "email": email, "password": "Smoke1234"}), 201)
        check("duplicate register", c.post(f"{API}/auth/register",
              json={"name": "Smoke Test", "email": email, "password": "Smoke1234"}), 409)
        check("weak password", c.post(f"{API}/auth/register",
              json={"name": "Smoke Test", "email": f"x{email}", "password": "abcdefgh"}), 422)
        check("wrong password", c.post(f"{API}/auth/login", json={"email": email, "password": "Nope12345"}), 401)
        tok = check("login", c.post(f"{API}/auth/login", json={"email": email, "password": "Smoke1234"}), 200)
        h2 = {"Authorization": f"Bearer {tok['access_token']}"}
        check("me", c.get(f"{API}/auth/me", headers=h2), 200)
        check("no token -> 401", c.get(f"{API}/medication-lists"), 401)

        lst = check("create list (Kaggle brand names)", c.post(f"{API}/medication-lists", headers=h2,
                    json={"names": ["Panadol Extra", "Augmentin 625mg", "Montiget 10mg", "Some odd name"]}), 201)
        show_items(lst)
        lst = check("add items", c.post(f"{API}/medication-lists/{lst['id']}/items", headers=h2,
                    json={"names": ["Ciproxin 500mg"]}), 201)
        item_id = lst["items"][3]["id"]
        lst = check("edit item", c.patch(f"{API}/medication-lists/{lst['id']}/items/{item_id}", headers=h2,
                    json={"raw_text": "Flagyl 400mg"}), 200)
        show_items(lst)
        check("delete item", c.delete(f"{API}/medication-lists/{lst['id']}/items/{item_id}", headers=h2), 200)
        found = check("search 'zyr'", c.get(f"{API}/medications/search", params={"q": "zyr"}, headers=h2), 200)
        print(f"        -> {[(m['standard_name'], m['matched_on']) for m in found]}")
        check("other user's list -> 403", c.get(f"{API}/medication-lists/{history[0]['id']}", headers=h2), 403)
        check("delete list", c.delete(f"{API}/medication-lists/{lst['id']}", headers=h2), 204)
        check("delete account", c.delete(f"{API}/auth/me", headers=h2), 204)
    print("All smoke checks passed.")


if __name__ == "__main__":
    main()
