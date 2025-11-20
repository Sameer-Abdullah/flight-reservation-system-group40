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

    @property
    def is_staff(self) -> bool:
        return self.email.lower().endswith("@skywing.com")


@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


# ---- Aircraft catalog (NEW) ----
class AircraftType(db.Model):
    __tablename__ = "aircraft_type"

    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(16), unique=True, nullable=False)   
    name = db.Column(db.String(64), nullable=False)               
    total_rows = db.Column(db.Integer, nullable=False)             
    layout = db.Column(db.String(32), nullable=False)             
    class_map = db.Column(db.JSON, nullable=False)

    def __repr__(self):
        return f"<AircraftType {self.code} rows={self.total_rows} layout={self.layout}>"


# ---- Flight model ----
class Flight(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    origin = db.Column(db.String(3), nullable=False)
    destination = db.Column(db.String(3), nullable=False)
    depart_time = db.Column(db.DateTime, nullable=False)
    price_cents = db.Column(db.Integer, nullable=False, default=0)

    aircraft_type_id = db.Column(db.Integer, nullable=True, index=True)
    aircraft_type = db.relationship(
        "AircraftType",
        primaryjoin="foreign(Flight.aircraft_type_id)==AircraftType.id",
        lazy="joined",
    )

    # Seats backref
    seats = db.relationship(
        "Seat",
        back_populates="flight",
        lazy="dynamic",
        cascade="all, delete-orphan",
    )

    def __repr__(self):
        return f"<Flight {self.origin}->{self.destination} {self.depart_time}>"


class Seat(db.Model):
    __tablename__ = "seats"

    id = db.Column(db.Integer, primary_key=True)
    flight_id = db.Column(db.Integer, db.ForeignKey("flight.id"), nullable=False, index=True)
    row_num = db.Column(db.Integer, nullable=False)
    seat_letter = db.Column(db.String(1), nullable=False)
    cabin_class = db.Column(db.String(16), nullable=False)
    is_blocked = db.Column(db.Boolean, nullable=False, default=False)

    __table_args__ = (
        db.UniqueConstraint("flight_id", "row_num", "seat_letter", name="uniq_flight_row_letter"),
    )

    flight = db.relationship("Flight", back_populates="seats")

    def code(self) -> str:
        return f"{self.row_num}{self.seat_letter}"

    def __repr__(self):
        return f"<Seat {self.code()} {self.cabin_class} flight={self.flight_id}>"

class Customer(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    first_name = db.Column(db.String(64), nullable=False)
    last_name = db.Column(db.String(64), nullable=False)
    email = db.Column(db.String(120), nullable=False, index=True)
    phone = db.Column(db.String(32), nullable=True)

    bookings = db.relationship("Booking", back_populates="customer")

    def full_name(self):
        return f"{self.first_name} {self.last_name}"


class Booking(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    customer_id = db.Column(db.Integer, db.ForeignKey("customer.id"))
    flight_id = db.Column(db.Integer, db.ForeignKey("flight.id"))
    seat_code = db.Column(db.String(8))    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    customer = db.relationship("Customer", back_populates="bookings")
    flight = db.relationship("Flight", backref="bookings")
