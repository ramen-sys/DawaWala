# Dawawala: Prescription Interaction Checker

A web-based medication-safety decision-support tool. Users can enter medications manually or upload an image of a printed prescription or medication label. The system extracts and normalizes drug names, confirms them with the user, and then checks the confirmed list for drug-drug interactions, duplicates, contraindications, and prescribing cascades. Every warning comes with a plain-language explanation and a transparent risk-priority score that shows the factors behind it.

> **Disclaimer:** Dawawala is a decision-support prototype. It does not diagnose conditions or replace advice from a doctor or pharmacist.

## Features

- User registration and JWT-based login
- Manual medication entry
- Prescription/label image upload with OCR text extraction
- Drug-name normalization using NLP and fuzzy matching
- User confirmation of medications before any analysis runs
- Rule-based drug-drug interaction (DDI) detection
- Duplicate medication detection
- Contraindication detection based on patient risk factors
- Prescribing-cascade detection
- Patient-risk-priority scoring with an itemized factor breakdown
- Plain-language explanations for every warning

## Tech Stack

| Layer | Technology |
|---|---|
| Backend | Python, FastAPI or Django REST Framework |
| Database | PostgreSQL |
| Authentication | JWT |
| OCR | Tesseract or EasyOCR |
| NLP / Matching | Lightweight NLP, fuzzy matching |
| Data processing | Pandas |
| Frontend | React.js, TailwindCSS, HTML |

## Repository Structure

```
dawawala/
├── backend/          # API, authentication, medication lists, analysis endpoints
├── frontend/         # React + Tailwind user interface
├── ocr/              # Image upload handling, OCR, NLP normalization, fuzzy matching
├── knowledge_base/   # Medication data, interaction rules, cascade rules
├── docs/             # SRS, diagrams, API contract
├── tests/            # Automated tests
└── README.md
```

## Getting Started

### Prerequisites

- Python 3.11+
- Node.js 18+ and npm
- PostgreSQL 14+
- Tesseract OCR (if using Tesseract)

### Backend Setup

```bash
cd backend
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env            # then fill in your database URL and JWT secret
alembic upgrade head            # create / update the database schema
python -m scripts.seed          # Kaggle medicines knowledge base + demo accounts
uvicorn app.main:app --reload   # FastAPI
```

Interactive API docs (OpenAPI / Swagger): <http://127.0.0.1:8000/docs>. Click **Authorize** and paste the
`access_token` returned by `POST /api/v1/auth/login`.

**Demo accounts** (created by `scripts.seed`):

| E-mail | Password | Role |
|---|---|---|
| `demo@dawawala.pk` | `Demo1234` | `user` (patient) |
| `doctor@dawawala.pk` | `Doctor1234` | `user` (healthcare professional) |
| `admin@dawawala.pk` | `Admin1234` | `admin` (may maintain the knowledge base) |

Roles follow FR-1: `user` covers patients and healthcare professionals (same workflow); `admin` is a
healthcare professional who may also import/update knowledge-base records.

The knowledge base comes from the Kaggle
[Pakistan Medicines Dataset](https://www.kaggle.com/datasets/muhammadabdullah222/pakistan-medicines-dataset):
87 products merged into 69 standard medications (brand names kept as aliases) and 51 age-restriction
contraindications. To re-import it on its own, run `python -m scripts.import_medicines`. Column choices and the
brand-to-generic mapping are documented in [`knowledge_base/README.md`](knowledge_base/README.md). The data is
not clinically reviewed (SAF-09).

### API (backend core)

All endpoints are under `/api/v1`. Protected endpoints need `Authorization: Bearer <token>`; they return
`401` without a valid token and `403` for another user's data. Errors use one JSON shape:
`{"code": "...", "message": "...", "fields": {...}}`.

| Method | Path | Purpose |
|---|---|---|
| POST | `/auth/register` | FR-1: create account (name, email, password, role) |
| POST | `/auth/login` | FR-2: get a 30-minute JWT; 5 failed attempts lock the account for 15 minutes |
| GET | `/auth/me` | Current user |
| DELETE | `/auth/me` | SEC-08: delete account and all its data |
| POST | `/medication-lists` | FR-3: create a draft list from 1–30 names (2–100 chars each) |
| GET | `/medication-lists` | History of the user's lists |
| GET / DELETE | `/medication-lists/{id}` | Read or delete a list |
| POST | `/medication-lists/{id}/items` | Add medications (max 30 per list) |
| PATCH / DELETE | `/medication-lists/{id}/items/{item_id}` | Edit or remove a medication |
| GET | `/medications/search?q=` | Type-ahead suggestions from the knowledge base |
| GET | `/medications/knowledge-base` | Knowledge-base version, date and coverage (SAF-07) |

Authentication events and authorization failures (SEC-10) are stored in the `auth_events` table (user ID,
event type, time, IP - never passwords, tokens or medications) and also written to `backend/logs/auth.log`.
Both are kept for 90 days; the API deletes older `auth_events` rows at startup and then once a day.

Editing a confirmed list returns it to `draft` and marks earlier analyses `outdated` (FR-7, SAF-08).
Typed names are passed to `app/services/normalization.py`, which currently resolves only exact
standard-name / brand-name matches; the fuzzy matcher (FR-6) plugs in behind the same function.

### Database migrations

The schema is managed with Alembic in `backend/alembic/`. It implements the 12 entities of SRS Table 5.1
(the "Warning" entity is the `warnings` table; its Python class is `AnalysisWarning`). Additions and why:

| Addition | Reason |
|---|---|
| `users.failed_login_attempts`, `users.locked_until` | account lock state (Appendix A.2, FR-2) |
| `analysis_results.freshness` | analysis freshness (Appendix A.2, SAF-08) |
| `rule_code`, `source` on `drug_interactions`, `contraindications`, `cascade_rules` | rule ID carried by every warning in `warnings.rule_reference` (QA-EXP-04); data source recorded with the rules (Section 5.3) |
| `medications.source`, `medications.external_code` | data source (5.3); optional external code such as ATC (5.4) |
| `medication_aliases` table (pg_trgm index) | the Medication "Aliases/brand names" attribute as rows, so fuzzy matching meets PERF-03 |
| `cascade_rule_triggers`, `cascade_rule_downstream` | the Cascade Rule medication sets, with real foreign keys |
| `contraindications.factor_type` + `factor_value` | the "Patient condition/factor" attribute, validated with the same values as `risk_factors` |
| `auth_events` | SEC-10 authentication log |

CHECK constraints reject invalid factor values (for example `under18`) and unknown entries in
`drug_interactions.relevant_risk_factors`. The knowledge-base version is global (`KB_VERSION`) and is stored on
every analysis result. An automated test (`tests/test_schema_and_import.py`) checks all of this. After changing
a model in `backend/app/models/`:

```bash
alembic revision --autogenerate -m "describe the change"
alembic upgrade head
```

### Running tests

```bash
# from the repository root, with the backend venv active
pytest                                   # tests run in a temporary schema that is dropped afterwards
python -m scripts.smoke_test             # from backend/, against a running server
```

### Frontend Setup

```bash
cd frontend
npm install
npm run dev
```

### Database Setup

The project uses a hosted PostgreSQL database on Neon; put its connection string in `backend/.env` as
`DATABASE_URL` (see `backend/.env.example`). For a local database instead:

```bash
createdb dawawala
cd backend && alembic upgrade head
```

## Team

| Member | Roll No | Area |
|---|---|---|
| Rameen Sohail | CS-24058 | Backend core, auth, database |
| Muhammad Usman Shahzad | CS-24074 | OCR and normalization pipeline |
| Muhammad Anas Faisal | CS-24083 | Safety engine and knowledge base |
| Muhammad Mustafa Ahmed | CS-24089 | Frontend, risk scoring, explanations |

## Contributing

1. Create a feature branch from `main`: `git checkout -b feature/<short-name>`
2. Reference the relevant SRS ID in commit messages, for example `FR-8: add DDI rule lookup`
3. Open a pull request and get at least one teammate to review it before merging
4. Keep `main` working at all times

## Requirements Reference

The full specification is in [`docs/SRS.pdf`](docs/SRS.pdf). Key requirement IDs:

- FR-1 to FR-13: functional requirements
- NFR-01 to NFR-07: non-functional requirements
- BR-01 to BR-05: business and safety rules

## License

To be decided by the team.