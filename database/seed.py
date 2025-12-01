from datetime import datetime, timedelta, UTC
import hashlib
from sqlalchemy import text
from web import create_app, db
from web.models import Flight, AircraftType, Seat

app = create_app()

# this makes sure the required tables and columns actually exist.
# - creates AircraftType and Seat tables if they're missing.
# - checks the flight table and adds aircraft_type_id if it isn't there.
def ensure_schema():
    AircraftType.__table__.create(bind=db.engine, checkfirst=True)
    Seat.__table__.create(bind=db.engine, checkfirst=True)

    cols = db.session.execute(text("PRAGMA table_info('flight')")).fetchall()
    colnames = {row[1] for row in cols}
    if "aircraft_type_id" not in colnames:
        db.session.execute(text("ALTER TABLE flight ADD COLUMN aircraft_type_id INTEGER"))
        db.session.commit()

# dollars to cents
def cents(n: float) -> int:
    return int(round(n * 100))


def stable_noise(key: str, low=-0.03, high=0.03) -> float:
    h = hashlib.sha256(key.encode()).hexdigest()
    rnd = int(h[:8], 16) / 0xFFFFFFFF
    return low + (high - low) * rnd

# makes sure the preset aircraft types exist (A320, B747, A380).
# if they already exist, update their info. If not, create them.
# these presets define layout, row count, and which cabin each row belongs to.
def ensure_aircraft_types():
    presets = [
        dict(
            code="A320", name="Airbus A320", total_rows=30, layout="ABC DEF",
            class_map=[{"from": 1, "to": 4, "class": "Business"},
                       {"from": 5, "to": 30, "class": "Economy"}],
        ),
        dict(
            code="B747", name="Boeing 747", total_rows=60, layout="ABC DEFG HJK",
            class_map=[{"from": 1, "to": 4, "class": "First"},
                       {"from": 5, "to": 18, "class": "Business"},
                       {"from": 19, "to": 60, "class": "Economy"}],
        ),
        dict(
            code="A380", name="Airbus A380", total_rows=65, layout="ABC DEFG HJK",
            class_map=[{"from": 1, "to": 5, "class": "First"},
                       {"from": 6, "to": 20, "class": "Business"},
                       {"from": 21, "to": 65, "class": "Economy"}],
        ),
    ]
    existing = {a.code: a for a in AircraftType.query.all()}
    changed = False
    for p in presets:
        if p["code"] in existing:
            a = existing[p["code"]]
            a.name, a.total_rows, a.layout, a.class_map = (
                p["name"], p["total_rows"], p["layout"], p["class_map"]
            )
            changed = True
        else:
            db.session.add(AircraftType(**p))
            changed = True
    if changed:
        db.session.commit()

# chooses which aircraft type to use based on ticket price.
# higher priced flights use larger/more premium planes.
def pick_aircraft_code(price_cents: int) -> str:
    p = (price_cents or 0) / 100.0
    if p >= 600:
        return "A380"
    if p >= 300:
        return "B747"
    return "A320"

# helps generate seat order for each row.
def letters_from_layout(layout_str: str):
    letters = []
    for group in layout_str.split():
        letters.extend(list(group))
    return letters

# figures out which cabin/class a given row belongs to based on the aircraft's class_map.
def cabin_for_row(row: int, class_map):
    for block in class_map:
        if block["from"] <= row <= block["to"]:
            return block["class"]
    return "Economy"

# Assigns aircraft types to flights that don't have one.
# Then generates seats for every flight that doesn’t already have seats.
# Seats are created using the aircraft’s row count, seat letters, and cabin class map.
def attach_aircraft_to_flights_and_seed_seats():
    atypes = {a.code: a for a in AircraftType.query.all()}
    flights = Flight.query.all()
    touched = 0
    for f in flights:
        if f.aircraft_type_id is None:
            f.aircraft_type_id = atypes[pick_aircraft_code(f.price_cents)].id
            touched += 1
    if touched:
        db.session.commit()

    atypes_by_id = {a.id: a for a in AircraftType.query.all()}
    total_new = 0

    for f in flights:
        if not f.aircraft_type_id:
            continue

        exists = db.session.query(Seat.id).filter_by(flight_id=f.id).limit(1).first()
        if exists:
            continue

        atype = atypes_by_id[f.aircraft_type_id]
        letters = letters_from_layout(atype.layout)

        batch = []
        for r in range(1, atype.total_rows + 1):
            cab = cabin_for_row(r, atype.class_map)
            for ch in letters:
                s = Seat(
                    flight_id=f.id,
                    row_num=r,
                    seat_letter=ch,
                    cabin_class=cab,
                    is_blocked=(r == 1 and ch in ("E", "F")),
                )
                batch.append(s)

        db.session.bulk_save_objects(batch)
        db.session.commit()
        total_new += len(batch)

    print(f"Seeded seats: {total_new}")


with app.app_context():
    ensure_schema()

    now = datetime.now(UTC).replace(minute=0, second=0, microsecond=0)

    routes = [
        ("YYZ","JFK",220), ("JFK","YYZ",215),
        ("YYZ","EWR",215), ("EWR","YYZ",210),
        ("YYZ","LGA",215), ("LGA","YYZ",210),
        ("YYZ","LAX",420), ("LAX","YYZ",415),
        ("YYZ","SFO",410), ("SFO","YYZ",405),
        ("YYZ","SEA",360), ("SEA","YYZ",355),
        ("YYZ","YVR",360), ("YVR","YYZ",355),
        ("YYZ","YYC",240), ("YYC","YYZ",235),
        ("YYZ","YUL",140), ("YUL","YYZ",140),
        ("YYZ","YOW",120), ("YOW","YYZ",120),
        ("YYZ","ORD",230), ("ORD","YYZ",225),
        ("YYZ","MIA",310), ("MIA","YYZ",305),
        ("YYZ","ATL",260), ("ATL","YYZ",255),
        ("YYZ","DFW",300), ("DFW","YYZ",295),
        ("YYZ","BOS",200), ("BOS","YYZ",195),
        ("YYZ","RDU",350), ("RDU","YYZ",345),

        ("JFK","LAX",280), ("LAX","JFK",285),
        ("JFK","SFO",300), ("SFO","JFK",305),
        ("JFK","MIA",170), ("MIA","JFK",175),
        ("JFK","ORD",160), ("ORD","JFK",160),
        ("LAX","SFO",120), ("SFO","LAX",120),
        ("SEA","SFO",140), ("SFO","SEA",140),
        ("SEA","LAX",170), ("LAX","SEA",170),
        ("ORD","LAX",260), ("LAX","ORD",260),
        ("DFW","LAX",210), ("LAX","DFW",210),

        ("YYZ","LHR",650), ("LHR","YYZ",640),
        ("YYZ","CDG",620), ("CDG","YYZ",615),
        ("YYZ","AMS",610), ("AMS","YYZ",605),
        ("JFK","LHR",600), ("LHR","JFK",600),
        ("JFK","CDG",580), ("CDG","JFK",580),

        ("YYZ","HND",900), ("HND","YYZ",890),
        ("YYZ","NRT",890), ("NRT","YYZ",880),
        ("JFK","HND",950), ("HND","JFK",945),
        ("LAX","HND",820), ("HND","LAX",815),

        ("YYZ","DXB",920), ("DXB","YYZ",910),
        ("JFK","DXB",880), ("DXB","JFK",875),

        ("LHR","CDG",120), ("CDG","LHR",120),
        ("LHR","AMS",130), ("AMS","LHR",130),
        ("CDG","AMS",110), ("AMS","CDG",110),

        ("YVR","YYC",150), ("YYC","YVR",150),
        ("YVR","YUL",360), ("YUL","YVR",360),
        ("YUL","YOW",110), ("YOW","YUL",110),
    ]
# how long into the future the database seeds flights for (22)
    day_offsets = list(range(0, 22))
    time_offsets = [
        timedelta(hours=6, minutes=30),
        timedelta(hours=9, minutes=45),
        timedelta(hours=13, minutes=15),
        timedelta(hours=18, minutes=30),
        timedelta(hours=21, minutes=0),
    ]

    slot_mult = {0: -0.06, 1: -0.02, 2: +0.00, 3: +0.07, 4: +0.03}

# weekend price bump
    def weekend_bump(dt):
        return 0.08 if dt.weekday() in (4, 5) else 0.0

    now_min = now + timedelta(days=min(day_offsets)) + min(time_offsets)
    now_max = now + timedelta(days=max(day_offsets)) + max(time_offsets)

    existing = set(
        (f.origin, f.destination, f.depart_time)
        for f in db.session.query(Flight.origin, Flight.destination, Flight.depart_time)
        .filter(Flight.depart_time >= now_min,
                Flight.depart_time <= now_max)
        .all()
    )

    to_insert = []

    # Generate new flights for every route × day × time slot combination.
    # Price is base_price × (slot multiplier + weekend bump + small random noise).
    for origin, dest, base in routes:
        for d in day_offsets:
            for idx, t_off in enumerate(time_offsets):
                depart = now + timedelta(days=d) + t_off
                price = base * (1 + slot_mult[idx] + weekend_bump(depart))
                noise = stable_noise(f"{origin}-{dest}-{depart.isoformat()}")
                price = max(60, price * (1 + noise))

                key = (origin, dest, depart)
                if key in existing:
                    continue
                existing.add(key)

                to_insert.append(Flight(
                    origin=origin,
                    destination=dest,
                    depart_time=depart,
                    price_cents=cents(price),
                ))

# slows down the insertion of flights to avoid large transactions.
    if to_insert:
        CHUNK = 1000
        for i in range(0, len(to_insert), CHUNK):
            db.session.bulk_save_objects(to_insert[i:i+CHUNK])
            db.session.commit()
        print(f"Seeded {len(to_insert)} flights.")
    else:
        print("No new flights to seed.")

# last checks
    ensure_aircraft_types()
    attach_aircraft_to_flights_and_seed_seats()
