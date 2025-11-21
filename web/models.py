from datetime import datetime, date, timezone
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from . import db, login_manager


# ---- User model ----
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    title = db.Column(db.String(16))
    first_name = db.Column(db.String(60))
    last_name = db.Column(db.String(60))
    phone = db.Column(db.String(32))
    dob = db.Column(db.Date)
    nationality = db.Column(db.String(64))

    bookings = db.relationship(
        "Booking",
        back_populates="user",
        cascade="all, delete-orphan",
        lazy="dynamic",
    )
    travelers = db.relationship(
        "Traveler",
        back_populates="user",
        cascade="all, delete-orphan",
        lazy="dynamic",
    )

    def set_password(self, plaintext: str):
        self.password_hash = generate_password_hash(plaintext)

    def check_password(self, plaintext: str) -> bool:
        return check_password_hash(self.password_hash, plaintext)

    @property
    def display_name(self) -> str:
        parts = [self.first_name or "", self.last_name or ""]
        name = " ".join(p for p in parts if p).strip() or self.email
        if self.title:
            return f"{self.title} {name}".strip()
        return name

    @property
    def initials(self) -> str:
        if self.first_name or self.last_name:
            return f"{(self.first_name or ' ')[0]}{(self.last_name or ' ')[0]}".upper()
        return (self.email[:2] if self.email else "AA").upper()

    def is_staff(self) -> bool:
        return bool(self.email) and self.email.lower().endswith("@skywing.com")


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
    flight_id = db.Column(
        db.Integer,
        db.ForeignKey("flight.id"),
        nullable=False,
        index=True,
    )
    row_num = db.Column(db.Integer, nullable=False)
    seat_letter = db.Column(db.String(1), nullable=False)
    cabin_class = db.Column(db.String(16), nullable=False)
    is_blocked = db.Column(db.Boolean, nullable=False, default=False)

    __table_args__ = (
        db.UniqueConstraint(
            "flight_id",
            "row_num",
            "seat_letter",
            name="uniq_flight_row_letter",
        ),
    )

    flight = db.relationship("Flight", back_populates="seats")

    def code(self) -> str:
        return f"{self.row_num}{self.seat_letter}"

    def __repr__(self):
        return f"<Seat {self.code()} {self.cabin_class} flight={self.flight_id}>"


# ---- Booking & Traveler ----
class Booking(db.Model):
    __tablename__ = "booking"

    STATUS_UPCOMING = "UPCOMING"
    STATUS_COMPLETED = "COMPLETED"
    STATUS_CANCELED = "CANCELED"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(
        db.Integer,
        db.ForeignKey("user.id"),
        nullable=False,
        index=True,
    )
    airline = db.Column(db.String(80), nullable=False)
    flight_number = db.Column(db.String(12), nullable=False)
    origin = db.Column(db.String(3), nullable=False)
    destination = db.Column(db.String(3), nullable=False)
    departure_time = db.Column(db.DateTime, nullable=False)
    arrival_time = db.Column(db.DateTime, nullable=False)
    ticket_type = db.Column(db.String(24), nullable=False, default="Economy")
    booking_reference = db.Column(db.String(20), nullable=False, unique=True)
    status = db.Column(
        db.String(16),
        nullable=False,
        default=STATUS_UPCOMING,
    )
    total_paid_cents = db.Column(db.Integer, nullable=False, default=0)
    cancellation_reason = db.Column(db.String(160))
    cancellation_ack = db.Column(db.Boolean, nullable=False, default=False)
    canceled_at = db.Column(db.DateTime)
    extras = db.Column(db.JSON)
    created_at = db.Column(
        db.DateTime,
        nullable=False,
        default=datetime.utcnow,
    )
    updated_at = db.Column(
        db.DateTime,
        nullable=False,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
    )

    user = db.relationship("User", back_populates="bookings")

    def can_cancel(self) -> bool:
        if self.status == self.STATUS_CANCELED or not self.departure_time:
            return False

        depart = self.departure_time
        if depart.tzinfo:
            depart = depart.astimezone(timezone.utc).replace(tzinfo=None)
        return depart > datetime.utcnow()

    def formatted_total(self) -> str:
        dollars = (self.total_paid_cents or 0) / 100
        return f"${dollars:,.2f}"

    def __repr__(self):
        return f"<Booking {self.booking_reference} {self.status}>"


class Traveler(db.Model):
    __tablename__ = "traveler"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(
        db.Integer,
        db.ForeignKey("user.id"),
        nullable=False,
        index=True,
    )
    title = db.Column(db.String(16))
    full_name = db.Column(db.String(120), nullable=False)
    dob = db.Column(db.Date)
    gender = db.Column(db.String(24))
    contact_info = db.Column(db.String(80))
    relationship = db.Column(db.String(32))
    created_at = db.Column(
        db.DateTime,
        nullable=False,
        default=datetime.utcnow,
    )

    user = db.relationship("User", back_populates="travelers")

    def to_dict(self):
        return {
            "id": self.id,
            "title": self.title,
            "full_name": self.full_name,
            "dob": self.dob.isoformat() if self.dob else None,
            "gender": self.gender,
            "contact_info": self.contact_info,
            "relationship": self.relationship,
        }

    def __repr__(self):
        return f"<Traveler {self.full_name} ({self.relationship})>"
