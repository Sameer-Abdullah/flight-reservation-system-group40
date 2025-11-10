from datetime import datetime
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from . import db, login_manager

# ---- User model ----
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)

    def set_password(self, plaintext: str):
        self.password_hash = generate_password_hash(plaintext)

    def check_password(self, plaintext: str) -> bool:
        return check_password_hash(self.password_hash, plaintext)

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# ---- Aircraft catalog ----
class AircraftType(db.Model):
    __tablename__ = "aircraft_type"

    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(16), unique=True, nullable=False)
    name = db.Column(db.String(64), nullable=False)
    total_rows = db.Column(db.Integer, nullable=False)
    layout = db.Column(db.String(32), nullable=False)
    class_map = db.Column(db.JSON, nullable=True)

    def __repr__(self):
        return f"<AircraftType {self.code} rows={self.total_rows} layout={self.layout}>"
        
# ---- Flight ----
class Flight(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(16), nullable=True)
    origin = db.Column(db.String(3), nullable=False)
    destination = db.Column(db.String(3), nullable=False)
    depart_time = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    price_cents = db.Column(db.Integer, nullable=False, default=0)

    aircraft_type_id = db.Column(db.Integer, db.ForeignKey('aircraft_type.id'), nullable=True)
    aircraft_type = db.relationship('AircraftType')

    seats = db.relationship('Seat', back_populates='flight', cascade='all, delete-orphan')

    def __repr__(self):
        return f"<Flight {self.origin}->{self.destination} {self.depart_time}>"

# ---- Seat ----
class Seat(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    flight_id = db.Column(db.Integer, db.ForeignKey('flight.id'), nullable=False)
    row_num = db.Column(db.Integer, nullable=False)
    seat_letter = db.Column(db.String(2), nullable=False)
    cabin_class = db.Column(db.String(16), nullable=False)   # Economy/Business/First
    is_blocked = db.Column(db.Boolean, nullable=False, default=False)

    __table_args__ = (
        db.UniqueConstraint('flight_id', 'row_num', 'seat_letter', name='uniq_flight_row_letter'),
    )

    flight = db.relationship('Flight', back_populates='seats')

    def code(self) -> str:
        return f"{self.row_num}{self.seat_letter}"

    def __repr__(self):
        return f"<Seat {self.code()} {self.cabin_class} flight={self.flight_id}>"

# ---- Booking ----
class Booking(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    flight_id = db.Column(db.Integer, db.ForeignKey('flight.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    status = db.Column(db.String(16), nullable=False, default='confirmed')  # confirmed|completed|canceled

    flight = db.relationship('Flight', lazy='joined')

    def __repr__(self):
        return f"<Booking id={self.id} user={self.user_id} flight={self.flight_id} status={self.status}>"