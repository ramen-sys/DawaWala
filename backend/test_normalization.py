from app.db.session import SessionLocal
from app.services.normalization import fuzzy_candidates, extract_strengths

db = SessionLocal()
for t in ["Panadol", "ARINAC", "Arinac Forte", "Pseudoephedrine HCI", "Panadol 3", "Pain & Fever"]:
    print(t, extract_strengths(t), fuzzy_candidates(db, t))

for t in ["Arinac 200mg/30mg", "Arinac Forte 400mg + 60mg"]:
    print(t, extract_strengths(t), fuzzy_candidates(db, t))
db.close()