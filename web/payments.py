from flask import Blueprint, render_template, request, redirect, url_for, flash
from datetime import datetime
from .models import Flight, Customer, Booking, BookingRecord
from . import db

payments = Blueprint("payments", __name__, url_prefix="/payments")

@payments.route("/<int:flight_id>", methods=["GET"])
def payments_page(flight_id: int):
    """
    Render the payment page. No external gateways; just the same UI.
    """
    flight = Flight.query.get_or_404(flight_id)
    pax = request.args.get("pax", type=int) or 1
    passenger_count = max(1, min(pax, 9))

    flash("Saved your traveler details. Continue to payment.", "success")
    return render_template(
        "payments.html",
        flight=flight,
        flight_id=flight_id,
        passenger_count=passenger_count,
        currency_code="CAD",
    )

@payments.route("/submit-card", methods=["POST"])
def submit_card():
    """
    Fake card submission: accept posted form fields and complete instantly.
    """
    flight_id = request.form.get("flight_id", type=int)
    seat_payload = request.form.get("seat_data") or "{}"
    _complete_booking(flight_id, seat_payload)
    # You can read other fields here if you want to validate/save them.
    flash("Payment completed (card).", "success")
    # After payment, send them back to search (or booking confirmation if you have it).
    return redirect(url_for("search.search"))

@payments.route("/mock-paypal/<int:flight_id>", methods=["POST", "GET"])
def mock_paypal(flight_id: int):
    """
    Simulated PayPal flow: just flash and go back to search.
    """
    if request.method == "POST":
        seat_payload = request.form.get("seat_data") or "{}"
        _complete_booking(flight_id, seat_payload)
    flash("Payment completed (PayPal – mock).", "success")
    return redirect(url_for("search.search"))

# Backward-compat alias so "from .payments import payments_bp" still works.
payments_bp = payments


def _complete_booking(flight_id: int | None, seat_payload: str):
    """
    Persist bookings and passengers so My Bookings and staff tools stay in sync.
    """
    if not flight_id:
        return
    flight = Flight.query.get(flight_id)
    if not flight:
        return

    try:
        data = request.get_json(silent=True) or {}
    except Exception:
        data = {}
    # seat_payload from form takes priority
    import json
    try:
        parsed = json.loads(seat_payload) if seat_payload else {}
    except Exception:
        parsed = data if isinstance(data, dict) else {}

    passengers = parsed.get("passengers") or []
    if not passengers:
        pax = max(1, int(parsed.get("pax") or 1))
        passengers = [{"label": f"Passenger {i+1}"} for i in range(pax)]

    # Build a simple booking reference
    stamp = datetime.utcnow().strftime("%Y%m%d%H%M%S")
    booking_ref = f"BK-{flight_id}-{stamp}"

    primary = passengers[0] if passengers else {}
    full_name = primary.get("fullName") or primary.get("name") or primary.get("label") or "Primary Passenger"
    email = primary.get("email")
    phone = primary.get("phone")

    # Find or create a customer for the primary passenger
    cust = None
    if email:
        cust = Customer.query.filter_by(email=email).first()
    if not cust:
        first, *rest = (full_name or "").split(" ", 1)
        last = rest[0] if rest else ""
        cust = Customer(first_name=first or "Guest", last_name=last or "Passenger", email=email or f"guest-{stamp}@example.com", phone=phone)
        db.session.add(cust)
        db.session.flush()

    # Create legacy booking rows for staff view
    for p in passengers:
        seat_code = p.get("seatCode") or ""
        db.session.add(Booking(customer_id=cust.id, flight_id=flight_id, seat_code=seat_code))

    # Store rich record for My Bookings
    total_paid_cents = (flight.price_cents or 0) * max(1, len(passengers))
    record = BookingRecord(
        booking_ref=booking_ref,
        flight_id=flight_id,
        primary_name=full_name,
        primary_email=email,
        primary_phone=phone,
        total_paid_cents=total_paid_cents,
        status=flight.status or "On time",
        passengers=passengers,
    )
    db.session.add(record)
    db.session.commit()
