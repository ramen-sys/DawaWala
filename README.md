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
uvicorn app.main:app --reload   # FastAPI
```

### Frontend Setup

```bash
cd frontend
npm install
npm run dev
```

### Database Setup

```bash
createdb dawawala
# Run migrations once the backend is configured
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