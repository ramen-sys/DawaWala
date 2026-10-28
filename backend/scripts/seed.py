"""Idempotent demo seed: imports the Kaggle knowledge base, then creates demo accounts with sample lists.

Run from the backend/ directory:  python -m scripts.seed
"""

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.core.security import hash_password
from app.db.session import SessionLocal
from app.models import MedicationList, User
from app.models.enums import UserRole
from app.services.medication_list_service import build_item
from scripts import import_medicines

# Patients and healthcare professionals both use the "user" role (FR-1); only the admin
# account may maintain the knowledge base.
DEMO_USERS = [
    ("Demo Patient", "demo@dawawala.pk", "Demo1234", UserRole.USER),
    ("Dr. Demo Pharmacist", "doctor@dawawala.pk", "Doctor1234", UserRole.USER),
    ("Demo KB Admin", "admin@dawawala.pk", "Admin1234", UserRole.ADMIN),
]

# Product names exactly as they appear on Pakistani packs (all present in the Kaggle dataset,
# except "Coughnil", which is deliberately left unrecognised).
DEMO_LISTS = {
    "demo@dawawala.pk": [
        ["Panadol 500mg", "Calpol", "Brufen 400mg", "Arinac Forte", "Risek 20mg"],
        ["Disprin", "Augmentin 625mg", "Piriton", "Coughnil"],
    ],
    "doctor@dawawala.pk": [
        ["Rivotril 0.5mg", "Ciproxin 500mg", "Celebrex", "Tamsol D", "Losec 20mg"],
    ],
}


def seed_demo_users(db: Session) -> None:
    for name, email, password, role in DEMO_USERS:
        user = db.scalar(select(User).where(User.email == email))
        if user is None:
            user = User(name=name, email=email, password_hash=hash_password(password), role=role)
            db.add(user)
            db.flush()
        user.role = role  # also fixes demo accounts created before the User/Admin roles
        user.failed_login_attempts = 0
        user.locked_until = None

        existing = {
            tuple(item.raw_text for item in ml.items)
            for ml in db.scalars(
                select(MedicationList)
                .where(MedicationList.user_id == user.id)
                .options(selectinload(MedicationList.items))
            )
        }
        for names in DEMO_LISTS.get(email, []):
            if tuple(names) in existing:
                continue
            med_list = MedicationList(user_id=user.id)
            med_list.items = [build_item(db, n) for n in names]
            db.add(med_list)
        db.flush()


def main() -> None:
    rows, _ = import_medicines.load_dataset()
    medications, min_ages = import_medicines.build_records(rows)
    with SessionLocal() as db:
        n_meds, n_ci = import_medicines.import_into_db(db, medications, min_ages)
        seed_demo_users(db)
        db.commit()
    print(f"Knowledge base: {n_meds} medications, {n_ci} age contraindications (from Kaggle dataset)")
    for _, email, password, role in DEMO_USERS:
        print(f"Demo account: {email} / {password} ({role.value})")


if __name__ == "__main__":
    main()
