from datetime import datetime, timedelta
import math, hashlib, random
from web import create_app, db
from web.models import Flight

app = create_app()

def cents(n: float) -> int:
    """CAD dollars -> integer cents."""
    return int(round(n * 100))

def stable_noise(key: str, low=-0.03, high=0.03) -> float:
    """
    Deterministic tiny noise per flight using a hash.
    Keeps prices stable across re-seeds for same (route, time).
    """
    h = hashlib.sha256(key.encode()).hexdigest()
    rnd = int(h[:8], 16) / 0xFFFFFFFF 
    return low + (high - low) * rnd

with app.app_context():
    now = datetime.utcnow().replace(minute=0, second=0, microsecond=0)

    routes = [
        # Canada <-> USA
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

        # USA transcons & majors
        ("JFK","LAX",280), ("LAX","JFK",285),
        ("JFK","SFO",300), ("SFO","JFK",305),
        ("JFK","MIA",170), ("MIA","JFK",175),
        ("JFK","ORD",160), ("ORD","JFK",160),
        ("LAX","SFO",120), ("SFO","LAX",120),
        ("SEA","SFO",140), ("SFO","SEA",140),
        ("SEA","LAX",170), ("LAX","SEA",170),
        ("ORD","LAX",260), ("LAX","ORD",260),
        ("DFW","LAX",210), ("LAX","DFW",210),

        # Transatlantic
        ("YYZ","LHR",650), ("LHR","YYZ",640),
        ("YYZ","CDG",620), ("CDG","YYZ",615),
        ("YYZ","AMS",610), ("AMS","YYZ",605),
        ("JFK","LHR",600), ("LHR","JFK",600),
        ("JFK","CDG",580), ("CDG","JFK",580),

        # Transpacific / Long-haul
        ("YYZ","HND",900), ("HND","YYZ",890),
        ("YYZ","NRT",890), ("NRT","YYZ",880),
        ("JFK","HND",950), ("HND","JFK",945),
        ("LAX","HND",820), ("HND","LAX",815),

        # Middle East
        ("YYZ","DXB",920), ("DXB","YYZ",910),
        ("JFK","DXB",880), ("DXB","JFK",875),

        # Europe hops
        ("LHR","CDG",120), ("CDG","LHR",120),
        ("LHR","AMS",130), ("AMS","LHR",130),
        ("CDG","AMS",110), ("AMS","CDG",110),

        # Canada domestic extras
        ("YVR","YYC",150), ("YYC","YVR",150),
        ("YVR","YUL",360), ("YUL","YVR",360),
        ("YUL","YOW",110), ("YOW","YUL",110),
    ]

    # 21 days out, 5 departures/day per route
    day_offsets = list(range(1, 22))
    time_offsets = [
        timedelta(hours=6,  minutes=30),  # early AM
        timedelta(hours=9,  minutes=45),  # mid-morning
        timedelta(hours=13, minutes=15),  # early afternoon
        timedelta(hours=18, minutes=30),  # evening
        timedelta(hours=21, minutes=0),   # late
    ]

    # Price multipliers by time slot (morning cheaper, evening pricier)
    slot_mult = {
        0: -0.06,  # 6:30
        1: -0.02,  # 9:45
        2: +0.00,  # 13:15
        3: +0.07,  # 18:30
        4: +0.03,  # 21:00
    }

    # Weekend bump (Fri/Sat)
    def weekend_bump(dt: datetime) -> float:
        return 0.08 if dt.weekday() in (4, 5) else 0.0

    min_dt = now + timedelta(days=min(day_offsets)) + min(time_offsets)
    max_dt = now + timedelta(days=max(day_offsets)) + max(time_offsets)
    existing = set(
        (f.origin, f.destination, f.depart_time)
        for f in db.session.query(Flight.origin, Flight.destination, Flight.depart_time)
        .filter(Flight.depart_time >= min_dt, Flight.depart_time <= max_dt)
        .all()
    )

    to_insert = []
    for origin, dest, base in routes:
        for d in day_offsets:
            for idx, t_off in enumerate(time_offsets):
                depart = now + timedelta(days=d) + t_off
                price = base * (1 + slot_mult[idx] + weekend_bump(depart))
                noise = stable_noise(f"{origin}-{dest}-{depart.isoformat()}")  # +/- ~3%
                price = max(60, price * (1 + noise)) 

                key = (origin, dest, depart)
                if key in existing:
                    continue
                existing.add(key)
                to_insert.append(
                    Flight(
                        origin=origin,
                        destination=dest,
                        depart_time=depart,
                        price_cents=cents(price),
                    )
                )

    if to_insert:
        CHUNK = 1000
        for i in range(0, len(to_insert), CHUNK):
            db.session.bulk_save_objects(to_insert[i:i+CHUNK])
            db.session.commit()
        print(f"Seeded {len(to_insert)} flights.")
    else:
        print("No new flights to seed (all present).")


    if Flight.query.count() == 0:
        samples = [
            Flight(origin="YYZ", destination="JFK", depart_time=now + timedelta(days=1, hours=3), price_cents=cents(220)),
            Flight(origin="YYZ", destination="RDU", depart_time=now + timedelta(days=2, hours=1), price_cents=cents(350)),
            Flight(origin="LAX", destination="JFK", depart_time=now + timedelta(days=3, hours=2), price_cents=cents(280)),
            Flight(origin="JFK", destination="LHR", depart_time=now + timedelta(days=5, hours=5), price_cents=cents(450)),
        ]
        db.session.add_all(samples)
        db.session.commit()
        print("Added baseline sample flights.")
