"""
Seed the local NIN registry with 50 realistic Nigerian records
for development and testing.

Run:  python seed_nin.py
"""
import random
from app import create_app, db
from app.models.nin_record import NinRecord

FIRST_NAMES = [
    "Amina", "Chukwuemeka", "Fatima", "Ibrahim", "Ngozi",
    "Abubakar", "Chisom", "Hauwa", "Emeka", "Zainab",
    "Adaeze", "Musa", "Bola", "Yakubu", "Ifeoma",
    "Suleiman", "Chidinma", "Aliyu", "Blessing", "Garba",
    "Funmilayo", "Umar", "Nneka", "Danladi", "Obianuju",
]

LAST_NAMES = [
    "Adeyemi", "Okonkwo", "Abubakar", "Aliyu", "Nwachukwu",
    "Bello", "Okafor", "Ibrahim", "Adamu", "Eze",
    "Lawal", "Nwosu", "Umar", "Okeke", "Hassan",
    "Sani", "Chukwu", "Danladi", "Onwudiwe", "Mohammed",
]

MIDDLE_NAMES = ["Fatima", "James", "Grace", "Ahmed", "Mary",
                "Sunday", "Blessing", "John", "Patience", ""]

STATES = [
    "Kano", "Lagos", "Kogi", "Borno", "Rivers",
    "FCT Abuja", "Kaduna", "Ogun", "Enugu", "Delta",
]

LGAS = {
    "Kano":      ["Kano Municipal", "Nasarawa", "Fagge"],
    "Lagos":     ["Lagos Island", "Ikeja", "Alimosho"],
    "Kogi":      ["Lokoja", "Idah", "Okene"],
    "Borno":     ["Maiduguri", "Jere", "Konduga"],
    "Rivers":    ["Port Harcourt", "Obio-Akpor", "Bonny"],
    "FCT Abuja": ["Abuja Municipal", "Bwari", "Gwagwalada"],
    "Kaduna":    ["Kaduna North", "Kaduna South", "Zaria"],
    "Ogun":      ["Abeokuta North", "Ijebu Ode", "Sagamu"],
    "Enugu":     ["Enugu North", "Enugu South", "Nkanu"],
    "Delta":     ["Warri", "Asaba", "Ughelli North"],
}

def random_dob():
    y = random.randint(1950, 2003)
    m = random.randint(1, 12)
    d = random.randint(1, 28)
    return f"{d:02d}-{m:02d}-{y}"

def random_phone():
    return f"080{random.randint(10000000, 99999999)}"


app = create_app()
with app.app_context():
    existing = NinRecord.query.count()
    if existing >= 50:
        print(f"Registry already has {existing} records — skipping.")
    else:
        nin_base = 10000000100   # offset from beneficiary seeds
        added = 0
        for i in range(60):       # try 60, stop when we have 50 new ones
            nin = str(nin_base + i).zfill(11)
            if NinRecord.nin_exists(nin):
                continue

            state = random.choice(STATES)
            lgas  = LGAS.get(state, ["Central LGA"])

            rec = NinRecord(
                firstname  = random.choice(FIRST_NAMES),
                lastname   = random.choice(LAST_NAMES),
                middlename = random.choice(MIDDLE_NAMES) or None,
                gender     = random.choice(["Male", "Female"]),
                birthdate  = random_dob(),
                phone      = random_phone(),
                state_of_origin = state,
                lga_of_origin   = random.choice(lgas),
            )
            NinRecord.set_nin(rec, nin)
            db.session.add(rec)
            added += 1
            if added >= 50:
                break

        db.session.commit()
        print(f"Added {added} NIN records to local registry.")
        print(f"Total records: {NinRecord.query.count()}")
        print("\nSample NINs for testing (not ending in 0 or 5):")
        for r in NinRecord.query.limit(5).all():
            print(f"  {r.nin_masked}  {r.full_name}  DOB:{r.birthdate}")
