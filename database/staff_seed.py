from datetime import datetime
import random

from web import create_app, db
from web.models import User, Customer, Booking, Flight

app = create_app()

def seed_staff_user():
    email = "sameer-abdullah@skywing.com"
    password = "c"

    user = User.query.filter_by(email=email.lower()).first()

    if user:
        print("[INFO] Staff user already exists:", email)
    else:
        user = User(email=email.lower())
        user.set_password(password)
        db.session.add(user)
        db.session.commit()
        print("[OK] Created staff user:", email)


def seed_customers():
    first_names = [
        "Amina","Layla","Omar","Yusuf","Fatima","Maryam","Noor","Daniyal","Ibrahim","Zain","Ayaan",
        "Hassan","Husna","Bilal","Ayesha","Sana","Fahad","Imran","Ali","Sara","Zara",
        "John","Michael","Emily","Sophia","Olivia","James","Liam","Noah","Emma","Ava","Ethan","Mason",
        "Luca","Mateo","Isabella","Mila","Nina","Marco","Ana",
    ]

    last_names = [
        "Khan","Hussain","Abdullah","Rahman","Patel","Siddiqui","Ali","Sheikh","Qureshi","Nawaz",
        "Smith","Brown","Anderson","Miller","Garcia","Martinez","Taylor",
        "Ivanov","Popov","Kovacs","Novak","Silva","Costa","Rossi",
    ]

    created = 0
    for _ in range(200):
        f = random.choice(first_names)
        l = random.choice(last_names)
        email = f"{f.lower()}.{l.lower()}{random.randint(10,999)}@gmail.com"
        phone = f"647-{random.randint(100,999)}-{random.randint(1000,9999)}"

        if not Customer.query.filter_by(email=email).first():
            cust = Customer(
                first_name=f,
                last_name=l,
                email=email,
                phone=phone
            )
            db.session.add(cust)
            created += 1

    db.session.commit()
    print(f"[OK] Seeded {created} customers.")


from datetime import datetime, timedelta
import random

def seed_bookings():
    customers = Customer.query.all()
    if not customers:
        print("[WARN] No customers found. Run seed_customers() first.")
        return

    now = datetime.utcnow()
    start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    end = start + timedelta(days=1)

    flights_today = (
        Flight.query
        .filter(Flight.depart_time >= start,
                Flight.depart_time < end)
        .all()
    )

    if not flights_today:
        print("[WARN] No flights today found in DB. Falling back to first 50 flights.")
        flights_today = Flight.query.limit(50).all()

    created = 0

    for fl in flights_today:
        num = random.randint(5, 20)
        chosen_customers = random.sample(customers, min(num, len(customers)))

        for cust in chosen_customers:
            seat_row = random.randint(1, 30)
            seat_letter = random.choice(["A", "B", "C", "D", "E", "F"])
            seat_code = f"{seat_row}{seat_letter}"

            existing = Booking.query.filter_by(
                flight_id=fl.id,
                seat_code=seat_code
            ).first()
            if existing:
                continue

            b = Booking(
                customer_id=cust.id,
                flight_id=fl.id,
                seat_code=seat_code,
            )
            db.session.add(b)
            created += 1

    db.session.commit()
    print(f"[OK] Seeded {created} bookings for today's (or fallback) flights.")



with app.app_context():
    print("---- Seeding staff + customers + bookings ----")
    seed_staff_user()
    seed_customers()
    seed_bookings()
    print("---- DONE ----")
