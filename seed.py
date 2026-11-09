"""
Database Seeder — populates the NRDS database with realistic Nigerian data.
Run once after `flask db upgrade`:

    python seed.py

The seeder is idempotent: re-running it safely checks for existing records
before inserting.
"""

import sys
from datetime import date, datetime, timedelta, timezone
import random

from app import create_app, db
from app.models.zone import State, LocalGovernmentArea, DistributionPoint
from app.models.user import User
from app.models.inventory import Warehouse, InventoryItem, StockMovement
from app.models.beneficiary import Beneficiary, BeneficiaryHousehold
from app.models.distribution import DistributionBatch, DistributionRecord
from app.utils.helpers import generate_household_code, generate_batch_code

# ---------------------------------------------------------------------------
# Nigeria States (all 36 + FCT)
# ---------------------------------------------------------------------------

NIGERIA_STATES = [
    ("Abia", "AB", "South East", 5.4527, 7.5248),
    ("Adamawa", "AD", "North East", 9.3265, 12.3984),
    ("Akwa Ibom", "AK", "South South", 5.0077, 7.8497),
    ("Anambra", "AN", "South East", 6.2209, 6.9370),
    ("Bauchi", "BA", "North East", 10.3158, 9.8442),
    ("Bayelsa", "BY", "South South", 4.7719, 6.0699),
    ("Benue", "BE", "North Central", 7.1906, 8.1300),
    ("Borno", "BO", "North East", 11.8333, 13.1500),
    ("Cross River", "CR", "South South", 5.9631, 8.3302),
    ("Delta", "DE", "South South", 5.5324, 5.8987),
    ("Ebonyi", "EB", "South East", 6.2649, 8.0137),
    ("Edo", "ED", "South South", 6.3350, 5.6037),
    ("Ekiti", "EK", "South West", 7.7190, 5.3110),
    ("Enugu", "EN", "South East", 6.4584, 7.5464),
    ("FCT Abuja", "FC", "North Central", 9.0579, 7.4951),
    ("Gombe", "GO", "North East", 10.2791, 11.1670),
    ("Imo", "IM", "South East", 5.5720, 7.0588),
    ("Jigawa", "JI", "North West", 12.1754, 9.3439),
    ("Kaduna", "KD", "North West", 10.5222, 7.4383),
    ("Kano", "KN", "North West", 12.0022, 8.5920),
    ("Katsina", "KT", "North West", 12.9816, 7.6180),
    ("Kebbi", "KB", "North West", 12.4539, 4.1975),
    ("Kogi", "KO", "North Central", 7.8011, 6.7371),
    ("Kwara", "KW", "North Central", 8.4966, 4.5421),
    ("Lagos", "LA", "South West", 6.5244, 3.3792),
    ("Nasarawa", "NA", "North Central", 8.4996, 8.1999),
    ("Niger", "NI", "North Central", 9.9310, 5.5983),
    ("Ogun", "OG", "South West", 6.9980, 3.4737),
    ("Ondo", "ON", "South West", 7.2510, 5.1950),
    ("Osun", "OS", "South West", 7.5629, 4.5200),
    ("Oyo", "OY", "South West", 7.8500, 3.9470),
    ("Plateau", "PL", "North Central", 9.2182, 9.5179),
    ("Rivers", "RI", "South South", 4.8156, 7.0498),
    ("Sokoto", "SO", "North West", 13.0059, 5.2476),
    ("Taraba", "TA", "North East", 8.8939, 11.3600),
    ("Yobe", "YO", "North East", 12.2939, 11.4390),
    ("Zamfara", "ZA", "North West", 12.1704, 6.6640),
]

# ---------------------------------------------------------------------------
# LGA samples per state (3 per state for demo)
# ---------------------------------------------------------------------------

LGA_SAMPLES = {
    "Kano": [("Kano Municipal", 11.9964, 8.5200), ("Nasarawa", 11.9600, 8.5950), ("Fagge", 11.9890, 8.4900)],
    "Borno": [("Maiduguri", 11.8333, 13.1500), ("Jere", 11.7800, 13.1700), ("Konduga", 11.6500, 13.4000)],
    "Kogi": [("Lokoja", 7.8011, 6.7371), ("Idah", 7.1006, 6.7285), ("Okene", 7.5573, 6.2419)],
    "Lagos": [("Lagos Island", 6.4541, 3.3947), ("Ikeja", 6.5958, 3.3396), ("Alimosho", 6.5564, 3.2697)],
    "Rivers": [("Port Harcourt", 4.8156, 7.0498), ("Obio-Akpor", 4.8500, 7.0200), ("Bonny", 4.4462, 7.1670)],
    "FCT Abuja": [("Abuja Municipal", 9.0579, 7.4951), ("Bwari", 9.1833, 7.3833), ("Gwagwalada", 8.9430, 7.0890)],
}

FIRST_NAMES = [
    "Amina", "Chukwuemeka", "Fatima", "Ibrahim", "Ngozi",
    "Abubakar", "Chisom", "Hauwa", "Emeka", "Zainab",
    "Adaeze", "Musa", "Bola", "Yakubu", "Ifeoma",
    "Suleiman", "Chidinma", "Aliyu", "Blessing", "Garba",
]
LAST_NAMES = [
    "Adeyemi", "Okonkwo", "Abubakar", "Aliyu", "Nwachukwu",
    "Bello", "Okafor", "Ibrahim", "Adamu", "Eze",
    "Lawal", "Nwosu", "Umar", "Okeke", "Hassan",
    "Sani", "Chukwu", "Danladi", "Onwudiwe", "Mohammed",
]


def seed():
    app = create_app()
    with app.app_context():
        print("=== NRDS Database Seeder ===")

        # ------------------------------------------------------------------
        # 1. States
        # ------------------------------------------------------------------
        if State.query.count() == 0:
            print("Seeding states...")
            for name, code, zone, lat, lon in NIGERIA_STATES:
                st = State(name=name, code=code, geopolitical_zone=zone,
                           latitude=lat, longitude=lon)
                db.session.add(st)
            db.session.commit()
            print(f"  Added {State.query.count()} states.")
        else:
            print("  States already seeded, skipping.")

        # ------------------------------------------------------------------
        # 2. LGAs
        # ------------------------------------------------------------------
        if LocalGovernmentArea.query.count() == 0:
            print("Seeding LGAs...")
            state_map = {s.name: s.id for s in State.query.all()}
            count = 0
            for state_name, lgas in LGA_SAMPLES.items():
                sid = state_map.get(state_name)
                if not sid:
                    continue
                for lga_name, lat, lon in lgas:
                    db.session.add(LocalGovernmentArea(
                        name=lga_name, state_id=sid, latitude=lat, longitude=lon,
                        population=random.randint(50_000, 800_000),
                    ))
                    count += 1
            db.session.commit()
            print(f"  Added {count} LGAs.")
        else:
            print("  LGAs already seeded, skipping.")

        # ------------------------------------------------------------------
        # 3. Distribution Points
        # ------------------------------------------------------------------
        if DistributionPoint.query.count() == 0:
            print("Seeding distribution points...")
            lgas = LocalGovernmentArea.query.all()
            count = 0
            for lga in lgas:
                for i in range(1, 4):  # 3 points per LGA
                    lat_offset = random.uniform(-0.05, 0.05)
                    lon_offset = random.uniform(-0.05, 0.05)
                    dp = DistributionPoint(
                        name=f"{lga.name} Community Centre {i}",
                        address=f"Zone {i}, {lga.name}",
                        lga_id=lga.id,
                        latitude=lga.latitude + lat_offset,
                        longitude=lga.longitude + lon_offset,
                        capacity=random.randint(100, 500),
                        contact_person=f"{random.choice(LAST_NAMES)} (Coordinator)",
                        contact_phone=f"080{random.randint(10000000, 99999999)}",
                    )
                    db.session.add(dp)
                    count += 1
            db.session.commit()
            print(f"  Added {count} distribution points.")
        else:
            print("  Distribution points already seeded, skipping.")

        # ------------------------------------------------------------------
        # 4. Admin user
        # ------------------------------------------------------------------
        if not User.query.filter_by(username="admin").first():
            print("Creating admin user...")
            admin = User(
                username="admin",
                email="admin@nrds.gov.ng",
                full_name="System Administrator",
                role="admin",
                organisation="NEMA",
                is_active=True,
            )
            admin.set_password("Admin@1234")
            db.session.add(admin)
            db.session.commit()
            print("  Admin user created. Username: admin / Password: Admin@1234")
        else:
            print("  Admin user already exists, skipping.")

        # ------------------------------------------------------------------
        # 5. Sample staff users
        # ------------------------------------------------------------------
        sample_users = [
            ("field_kano", "field.kano@nrds.gov.ng", "Amina Bello", "field_officer", "NEMA Kano"),
            ("warehouse_borno", "wh.borno@nrds.gov.ng", "Umar Hassan", "warehouse", "SEMA Borno"),
            ("logistics_01", "logistics@nrds.gov.ng", "Chukwuemeka Obi", "logistics", "NEMA HQ"),
            ("coordinator_01", "coord@nrds.gov.ng", "Fatima Aliyu", "programme_coord", "NEMA"),
            ("partner_wfp", "partner.wfp@wfp.org", "David Smith", "partner", "WFP Nigeria"),
        ]

        for uname, email, fname, role, org in sample_users:
            if not User.query.filter_by(username=uname).first():
                u = User(username=uname, email=email, full_name=fname,
                         role=role, organisation=org, is_active=True)
                u.set_password("Password@123")
                db.session.add(u)
        db.session.commit()
        print("  Sample staff users created (password: Password@123)")

        # ------------------------------------------------------------------
        # 6. Warehouses
        # ------------------------------------------------------------------
        if Warehouse.query.count() == 0:
            print("Seeding warehouses...")
            state_map = {s.name: s for s in State.query.all()}
            wh_data = [
                ("NEMA Kano Warehouse", "WH-KN-01", "Kano", 11.9700, 8.5350, 500.0),
                ("NEMA Borno Warehouse", "WH-BO-01", "Borno", 11.8200, 13.1400, 800.0),
                ("NEMA Lagos Warehouse", "WH-LA-01", "Lagos", 6.5100, 3.3600, 300.0),
                ("NEMA Kogi Warehouse", "WH-KO-01", "Kogi", 7.7900, 6.7200, 250.0),
                ("NEMA FCT Warehouse", "WH-FC-01", "FCT Abuja", 9.0400, 7.4700, 600.0),
                ("NEMA Rivers Warehouse", "WH-RI-01", "Rivers", 4.8000, 7.0300, 350.0),
            ]
            for name, code, state_name, lat, lon, cap in wh_data:
                st = state_map.get(state_name)
                if not st:
                    continue
                wh = Warehouse(
                    name=name, code=code, state_id=st.id,
                    latitude=lat, longitude=lon, capacity_tonnes=cap,
                    manager_name=random.choice(LAST_NAMES) + " " + random.choice(FIRST_NAMES),
                    manager_phone=f"080{random.randint(10000000, 99999999)}",
                )
                db.session.add(wh)
            db.session.commit()
            print(f"  Added {Warehouse.query.count()} warehouses.")
        else:
            print("  Warehouses already seeded, skipping.")

        # ------------------------------------------------------------------
        # 7. Inventory Items
        # ------------------------------------------------------------------
        if InventoryItem.query.count() == 0:
            print("Seeding inventory items...")
            admin_user = User.query.filter_by(username="admin").first()
            warehouses = Warehouse.query.all()
            items_template = [
                ("Rice (50kg bag)", "Food", "bags", 200, 50),
                ("Beans (25kg bag)", "Food", "bags", 150, 30),
                ("Vegetable Oil (5L)", "Food", "units", 300, 60),
                ("Maize Flour (10kg)", "Food", "bags", 100, 25),
                ("Bottled Water (20L)", "Water", "units", 500, 100),
                ("Water Purification Tablets", "Water", "packs", 200, 40),
                ("Oral Rehydration Salts", "Medicine", "packs", 300, 50),
                ("Paracetamol (500mg)", "Medicine", "cartons", 150, 30),
                ("Malaria RDT Kit", "Medicine", "kits", 100, 20),
                ("Emergency Tent (4-person)", "Shelter", "units", 80, 15),
                ("Tarpaulin Sheet", "Shelter", "rolls", 120, 25),
                ("Blanket", "Shelter", "units", 250, 50),
                ("Clothing Bundle (family)", "Clothing", "bundles", 200, 40),
                ("Hygiene Kit", "Hygiene", "kits", 300, 60),
                ("Soap Bar (multipacks)", "Hygiene", "packs", 400, 80),
            ]
            count = 0
            for wh in warehouses:
                for item_name, category, unit, qty, threshold in items_template:
                    item = InventoryItem(
                        warehouse_id=wh.id,
                        item_name=item_name,
                        category=category,
                        unit=unit,
                        quantity_available=float(qty),
                        minimum_threshold=float(threshold),
                        donor="NEMA / WFP",
                        batch_number=f"BATCH-{datetime.now(timezone.utc).year}-{random.randint(1000,9999)}",
                    )
                    db.session.add(item)
                    db.session.flush()
                    mv = StockMovement(
                        item_id=item.id,
                        warehouse_id=wh.id,
                        movement_type="receipt",
                        quantity=float(qty),
                        notes="Initial seeded stock",
                        performed_by=admin_user.id,
                    )
                    db.session.add(mv)
                    count += 1
            db.session.commit()
            print(f"  Added {count} inventory items.")
        else:
            print("  Inventory items already seeded, skipping.")

        # ------------------------------------------------------------------
        # 8. Sample beneficiaries
        # ------------------------------------------------------------------
        if Beneficiary.query.count() == 0:
            print("Seeding beneficiaries (100 records)...")
            lgas = LocalGovernmentArea.query.all()
            admin = User.query.filter_by(username="admin").first()
            nin_base = 10000000000

            for i in range(100):
                lga = random.choice(lgas)
                nin = str(nin_base + i).zfill(11)

                household = BeneficiaryHousehold(
                    household_code=generate_household_code(),
                    head_of_household_nin=nin,
                    address=f"No. {random.randint(1, 50)}, {lga.name}",
                    lga_id=lga.id,
                    household_size=random.randint(1, 7),
                    registered_by=admin.id,
                )
                db.session.add(household)
                db.session.flush()

                b = Beneficiary(
                    first_name=random.choice(FIRST_NAMES),
                    last_name=random.choice(LAST_NAMES),
                    date_of_birth=date(
                        random.randint(1950, 2005),
                        random.randint(1, 12),
                        random.randint(1, 28),
                    ),
                    gender=random.choice(["Male", "Female"]),
                    phone=f"080{random.randint(10000000, 99999999)}",
                    lga_id=lga.id,
                    address=f"No. {random.randint(1,50)}, {lga.name}",
                    household=household,
                    is_head_of_household=True,
                    is_elderly=random.random() < 0.1,
                    is_disabled=random.random() < 0.05,
                    nin_verified=not nin.endswith(("0", "5")),
                    verification_date=datetime.now(timezone.utc),
                    verification_notes="Seeded verification",
                    registered_by=admin.id,
                )
                b.set_nin(nin)  # hash the NIN
                db.session.add(b)

            db.session.commit()
            print(f"  Added {Beneficiary.query.count()} beneficiaries.")
        else:
            print("  Beneficiaries already seeded, skipping.")

        # ------------------------------------------------------------------
        # 9. Sample distribution batch
        # ------------------------------------------------------------------
        if DistributionBatch.query.count() == 0:
            print("Seeding sample distribution batch...")
            admin = User.query.filter_by(username="admin").first()
            wh = Warehouse.query.first()
            if wh:
                batch = DistributionBatch(
                    batch_code=generate_batch_code(),
                    title="2026 Flood Response — Kogi State",
                    disaster_type="Flood",
                    description="Emergency relief distribution for Kogi flood victims.",
                    source_warehouse_id=wh.id,
                    planned_date=date.today(),
                    status="planned",
                    created_by=admin.id,
                )
                db.session.add(batch)
                db.session.commit()
                print(f"  Created sample batch: {batch.batch_code}")
        else:
            print("  Distribution batches already seeded, skipping.")

        # ------------------------------------------------------------------
        # 10. Sample distribution records
        # ------------------------------------------------------------------
        if DistributionRecord.query.count() == 0:
            print("Seeding distribution records...")
            admin = User.query.filter_by(username="admin").first()
            batches = DistributionBatch.query.all()
            beneficiaries = Beneficiary.query.filter_by(status="active").all()
            dist_points = DistributionPoint.query.filter_by(is_active=True).all()
            count = 0

            for batch in batches:
                wh = batch.source_warehouse
                if not wh:
                    continue
                items = InventoryItem.query.filter_by(warehouse_id=wh.id).all()
                if not items or not beneficiaries or not dist_points:
                    continue

                # Pick a random subset of beneficiaries for this batch
                batch_beneficiaries = random.sample(
                    beneficiaries, min(len(beneficiaries), random.randint(15, 25))
                )
                used_pairs = set()
                batch_count = 0

                for beneficiary in batch_beneficiaries:
                    item = random.choice(items)
                    pair = (beneficiary.id, item.id)
                    if pair in used_pairs:
                        continue
                    used_pairs.add(pair)

                    qty = random.randint(1, 5)
                    if item.quantity_available < qty:
                        continue

                    dp = random.choice(dist_points)
                    nin_confirmed = random.random() < 0.8

                    record = DistributionRecord(
                        batch_id=batch.id,
                        beneficiary_id=beneficiary.id,
                        household_id=beneficiary.household_id,
                        distribution_point_id=dp.id,
                        item_id=item.id,
                        quantity_given=float(qty),
                        status="completed",
                        nin_confirmed=nin_confirmed,
                        confirmed_by=admin.id if nin_confirmed else None,
                        distribution_timestamp=datetime.now(timezone.utc) - timedelta(
                            days=random.randint(0, 7),
                            hours=random.randint(0, 23),
                        ),
                        recorded_by=admin.id,
                    )
                    db.session.add(record)

                    item.quantity_available -= qty

                    mv = StockMovement(
                        item_id=item.id,
                        warehouse_id=wh.id,
                        movement_type="dispatch",
                        quantity=float(qty),
                        reference_number=batch.batch_code,
                        notes=f"Distribution batch {batch.batch_code}",
                        performed_by=admin.id,
                        batch_id=batch.id,
                    )
                    db.session.add(mv)
                    batch_count += 1
                    count += 1

                # Move planned batches to in_progress once they have records
                if batch_count > 0 and batch.status == "planned":
                    batch.status = "in_progress"
                    batch.start_date = datetime.now(timezone.utc) - timedelta(
                        days=random.randint(1, 7)
                    )

            db.session.commit()
            print(f"  Added {count} distribution records.")
        else:
            print("  Distribution records already seeded, skipping.")

        print("\n=== Seeding complete! ===")
        print("Admin login: username=admin / password=Admin@1234")
        print("Staff login: password=Password@123")


if __name__ == "__main__":
    seed()
