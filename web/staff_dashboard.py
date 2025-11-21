from datetime import datetime, timedelta, UTC
from io import StringIO
import csv
from types import SimpleNamespace

from flask import Blueprint, render_template, request, Response
from flask_login import login_required, current_user

from .models import Flight, Seat, Booking, Customer
from . import db

staff_dashboard_bp = Blueprint("staff_dashboard", __name__, url_prefix="/staff")


def _today_window():
    """Return start and end (UTC) for 'today'."""
    now = datetime.now(UTC)
    start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    end = start + timedelta(days=1)
    return now, start, end


def _to_utc(dt: datetime) -> datetime:
    """Convert naive datetimes from SQLite to UTC-aware."""
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=UTC)
    return dt


def _compute_flight_status(now: datetime, depart_time: datetime) -> str:
    """Simple derived status based on departure time (both UTC-aware)."""
    if depart_time < now - timedelta(minutes=30):
        return "Departed"
    if now - timedelta(minutes=30) <= depart_time <= now + timedelta(minutes=15):
        return "Boarding"
    if now + timedelta(minutes=15) < depart_time <= now + timedelta(hours=2):
        return "On time"
    return "Scheduled"


@staff_dashboard_bp.route("/dashboard")
@login_required
def dashboard():
    if not current_user.is_staff:
        return "Forbidden", 403

    now, today_start, today_end = _today_window()

    # ---- Today’s flights ----
    today_start_naive = today_start.replace(tzinfo=None)
    today_end_naive = today_end.replace(tzinfo=None)

    flights_today = (
        Flight.query
        .order_by(Flight.depart_time.asc())
        .all()
    )



    enriched_flights = []
    for f in flights_today:
        depart_utc = _to_utc(f.depart_time)
        status = _compute_flight_status(now, depart_utc)

        total_seats = (
            db.session.query(Seat.id)
            .filter(Seat.flight_id == f.id)
            .count()
        )

        seats_booked = 0  

        f.code = f"{f.origin}{f.destination}-{f.id}"
        f.status = status
        f.seats_total = total_seats
        f.seats_booked = seats_booked
        enriched_flights.append(f)

    completed = sum(1 for f in enriched_flights if f.status == "Departed")
    upcoming = len(enriched_flights) - completed

    total_capacity = sum(f.seats_total for f in enriched_flights)
    passengers_today = total_capacity

    stats = {
        "flights_today": len(enriched_flights),
        "passengers_today": passengers_today,
        "completed_flights": completed,
        "upcoming_flights": upcoming,
    }

    # ---- Customer lookup ----
    first = (request.args.get("first_name") or "").strip()
    last = (request.args.get("last_name") or "").strip()
    email = (request.args.get("email") or "").strip()
    phone = (request.args.get("phone") or "").strip()
    booking_ref = (request.args.get("booking_ref") or "").strip()

    customers = None

    if any([first, last, email, phone, booking_ref]):
        q = (
            db.session.query(Booking, Customer, Flight)
            .join(Customer, Booking.customer_id == Customer.id)
            .join(Flight, Booking.flight_id == Flight.id)
        )

        if first:
            q = q.filter(Customer.first_name.ilike(f"%{first}%"))
        if last:
            q = q.filter(Customer.last_name.ilike(f"%{last}%"))
        if email:
            q = q.filter(Customer.email.ilike(f"%{email}%"))
        if phone:
            q = q.filter(Customer.phone.ilike(f"%{phone}%"))
        if booking_ref:
            digits = "".join(ch for ch in booking_ref if ch.isdigit())
            if digits:
                try:
                    bid = int(digits)
                    q = q.filter(Booking.id == bid)
                except ValueError:
                    pass

        rows = q.limit(100).all()

        customers = []
        for b, c, f in rows:
            depart_utc = _to_utc(f.depart_time)
            booking_code = f"BK-{b.id:06d}"
            flight_code = f"{f.origin}{f.destination}-{f.id}"

            customers.append(SimpleNamespace(
                full_name=f"{c.first_name} {c.last_name}",
                email=c.email,
                phone=c.phone,
                booking_ref=booking_code,
                flight_code=flight_code,
                origin=f.origin,
                destination=f.destination,
                depart_time=depart_utc.strftime("%Y-%m-%d %H:%M"),
                seat_code=b.seat_code or "-",
            ))

    return render_template(
        "staff_dashboard.html",
        stats=stats,
        flights_today=enriched_flights,
        customers=customers,
    )


@staff_dashboard_bp.route("/download-today-report")
@login_required
def download_today_report():
    if not current_user.is_staff:
        return "Forbidden", 403

    now, today_start, today_end = _today_window()
    today_start_naive = today_start.replace(tzinfo=None)
    today_end_naive = today_end.replace(tzinfo=None)

    flights_today = (
        Flight.query
        .order_by(Flight.depart_time.asc())
        .all()
    )

    output = StringIO()
    writer = csv.writer(output)

    writer.writerow([
        "Flight Code",
        "Origin",
        "Destination",
        "Departure (UTC)",
        "Status",
    ])

    for f in flights_today:
        depart_utc = _to_utc(f.depart_time)
        status = _compute_flight_status(now, depart_utc)
        code = f"{f.origin}{f.destination}-{f.id}"
        writer.writerow([
            code,
            f.origin,
            f.destination,
            depart_utc.isoformat(),
            status,
        ])

    csv_data = output.getvalue()
    output.close()

    resp = Response(csv_data, mimetype="text/csv")
    resp.headers["Content-Disposition"] = "attachment; filename=today_flights.csv"
    return resp


@staff_dashboard_bp.route("/download-today-manifest")
@login_required
def download_today_manifest():
    if not current_user.is_staff:
        return "Forbidden", 403

    now, today_start, today_end = _today_window()

    today_start_naive = today_start.replace(tzinfo=None)
    today_end_naive = today_end.replace(tzinfo=None)

    flights_today = (
        Flight.query
        .order_by(Flight.depart_time.asc())
        .all()
    )

    output = StringIO()
    writer = csv.writer(output)

    writer.writerow([
        "Flight Code",
        "Origin",
        "Destination",
        "Departure Time (UTC)",
        "Booking Ref",
        "Seat",
        "Passenger Name",
        "Email",
        "Phone",
    ])

    for f in flights_today:
        depart_utc = _to_utc(f.depart_time)
        flight_code = f"{f.origin}{f.destination}-{f.id}"

        for b in f.bookings: 
            c = b.customer
            writer.writerow([
                flight_code,
                f.origin,
                f.destination,
                depart_utc.isoformat(),
                f"BK-{b.id:06d}",
                b.seat_code or "-",
                f"{c.first_name} {c.last_name}",
                c.email,
                c.phone,
            ])

    csv_data = output.getvalue()
    output.close()

    resp = Response(csv_data, mimetype="text/csv")
    resp.headers["Content-Disposition"] = "attachment; filename=today_passenger_manifest.csv"
    return resp

