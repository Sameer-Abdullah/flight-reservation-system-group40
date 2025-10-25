from datetime import datetime, timedelta
from web import create_app, db
from web.models import Flight

app = create_app()
with app.app_context():
    if Flight.query.count() == 0:
        flights = [
            Flight(origin="YYZ", destination="JFK", depart_time=datetime.utcnow()+timedelta(days=1, hours=3), price_cents=22000),
            Flight(origin="YYZ", destination="RDU", depart_time=datetime.utcnow()+timedelta(days=2, hours=1), price_cents=35000),
            Flight(origin="LAX", destination="JFK", depart_time=datetime.utcnow()+timedelta(days=3, hours=2), price_cents=28000),
            Flight(origin="NYC", destination="LON", depart_time=datetime.utcnow()+timedelta(days=5, hours=5), price_cents=45000),
        ]
        db.session.add_all(flights)
        db.session.commit()
        print("Seeded flights.")
    else:
        print("Flights already exist.")
