from flask import Blueprint, render_template, request, redirect, url_for, flash
from datetime import datetime
from typing import Any, Dict, List, Tuple
from .models import Flight, Customer, Booking, BookingRecord
from . import db

payments = Blueprint("payments", __name__, url_prefix="/payments")

# tax rates for payment calculations
TAX_TABLE: dict[str, float] = {
    "Canada": 0.13, "United States": 0.08, "Mexico": 0.16, "Bahamas": 0.12, "Bermuda": 0.075,
    "Jamaica": 0.15, "Dominican Republic": 0.18, "Cuba": 0.14, "Puerto Rico": 0.115,
    "Belize": 0.12, "Costa Rica": 0.13, "Panama": 0.07, "Guatemala": 0.12, "Honduras": 0.15,
    "El Salvador": 0.13, "Nicaragua": 0.15, "Trinidad and Tobago": 0.12, "Barbados": 0.175,
    "Aruba": 0.18, "Cayman Islands": 0.0, "Brazil": 0.17, "Argentina": 0.21, "Chile": 0.19,
    "Peru": 0.18, "Colombia": 0.19, "Ecuador": 0.12, "Uruguay": 0.22, "Paraguay": 0.1,
    "Bolivia": 0.13, "Venezuela": 0.16, "United Kingdom": 0.2, "Ireland": 0.23, "France": 0.2,
    "Germany": 0.19, "Spain": 0.21, "Italy": 0.22, "Portugal": 0.23, "Netherlands": 0.21,
    "Switzerland": 0.081, "Greece": 0.24, "Turkey": 0.18, "United Arab Emirates": 0.05,
    "Qatar": 0.05, "Saudi Arabia": 0.15, "Egypt": 0.14, "South Africa": 0.15,
    "Kenya": 0.16, "Morocco": 0.2, "India": 0.18, "China": 0.13, "Japan": 0.1, "South Korea": 0.1,
    "Singapore": 0.09, "Thailand": 0.07, "Vietnam": 0.1, "Malaysia": 0.08, "Indonesia": 0.11,
    "Philippines": 0.12, "Australia": 0.1, "New Zealand": 0.15, "Fiji": 0.15,
}
DEFAULT_TAX_RATE = 0.13

# sets up payment page
@payments.route("/<int:flight_id>", methods=["GET"])
def payments_page(flight_id: int):
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

# Payment support for both card and PayPal (Not real payments)
@payments.route("/submit-card", methods=["POST"])
def submit_card():
    flight_id = request.form.get("flight_id", type=int)
    seat_payload = request.form.get("seat_data") or "{}"
    billing_country = (request.form.get("country") or "").strip() or None
    _complete_booking(flight_id, seat_payload, billing_country=billing_country)
    flash("Payment completed (card).", "success")
    return redirect(url_for("search.search"))

@payments.route("/mock-paypal/<int:flight_id>", methods=["POST", "GET"])
def mock_paypal(flight_id: int):
    if request.method == "POST":
        seat_payload = request.form.get("seat_data") or "{}"
        billing_country = (request.form.get("country") or "").strip() or None
        _complete_booking(flight_id, seat_payload, billing_country=billing_country)
    flash("Payment completed (PayPal – mock).", "success")
    return redirect(url_for("search.search"))

payments_bp = payments

# Gets tax rate based on country selected in billing info
def _tax_rate_for(country: str | None) -> float:
    if not country:
        return DEFAULT_TAX_RATE
    return TAX_TABLE.get(country, DEFAULT_TAX_RATE)

# make sure passenger data is set up so each entry has labels, seat info, class, and contact.
def _parse_passenger_list(raw: Any, fallback_pax: int) -> List[Dict[str, Any]]:
    passengers = raw if isinstance(raw, list) else []
    count = len(passengers) if passengers else max(1, fallback_pax)
    normalized: List[Dict[str, Any]] = []
    for idx in range(count):
        p = passengers[idx] if idx < len(passengers) else {}
        normalized.append(
            {
                "label": p.get("label") or f"Passenger {idx+1}",
                "fullName": p.get("fullName") or p.get("name") or p.get("label") or f"Passenger {idx+1}",
                "seatCode": p.get("seatCode") or "",
                "cabin": p.get("cabin") or "",
                "position": p.get("position") or p.get("seatPreference") or "",
                "seatPreference": p.get("seatPreference") or p.get("position") or "",
                "mealPreference": p.get("mealPreference") or "Standard",
                "classPreference": p.get("classPreference") or p.get("cabin") or "",
                "extraBags": int(p.get("extraBags") or 0),
                "email": p.get("email") or "",
                "phone": p.get("phone") or "",
                "row": p.get("row"),
                "letter": p.get("letter"),
            }
        )
    return normalized

# calculates total price based on base price, num of passengers, upgrades, extra bags, and tax
def _compute_total_cents(base_price_cents: int, passengers: List[Dict[str, Any]], country: str | None) -> Tuple[int, Dict[str, Any]]:
    pax_count = max(1, len(passengers))
    base_fare_cents = (base_price_cents or 0) * pax_count

    upgrade_cents = 0
    extra_bags = 0
    for p in passengers:
        cls = (p.get("classPreference") or p.get("cabin") or "").lower()
        if "first" in cls:
            upgrade_cents += 90000  # $900 upgrade for First
        elif "business" in cls:
            upgrade_cents += 45000  # $450 upgrade for Business
        try:
            bags = int(p.get("extraBags") or 0)
        except (TypeError, ValueError):
            bags = 0
        extra_bags += max(0, bags)
    baggage_cents = extra_bags * 5000  # $50 per extra bag

    subtotal_cents = base_fare_cents + upgrade_cents + baggage_cents
    tax_rate = _tax_rate_for(country)
    tax_cents = round(subtotal_cents * tax_rate)
    total_cents = subtotal_cents + tax_cents

    return total_cents, {
        "pax": pax_count,
        "base_fare_cents": base_fare_cents,
        "upgrade_cents": upgrade_cents,
        "extra_bags": extra_bags,
        "baggage_cents": baggage_cents,
        "tax_rate": tax_rate,
        "tax_cents": tax_cents,
    }

# Finalizes booking after payment and stores booking details for a booking reference 
def _complete_booking(flight_id: int | None, seat_payload: str, billing_country: str | None = None):
    if not flight_id:
        return
    flight = Flight.query.get(flight_id)
    if not flight:
        return

    try:
        data = request.get_json(silent=True) or {}
    except Exception:
        data = {}
    import json
    try:
        parsed = json.loads(seat_payload) if seat_payload else {}
    except Exception:
        parsed = data if isinstance(data, dict) else {}

    try:
        pax_requested = int(parsed.get("pax") or 1)
    except (TypeError, ValueError):
        pax_requested = 1
    passengers = _parse_passenger_list(parsed.get("passengers"), pax_requested)

    # Build a simple booking reference
    stamp = datetime.utcnow().strftime("%Y%m%d%H%M%S")
    booking_ref = f"BK-{flight_id}-{stamp}"

    primary = passengers[0] if passengers else {}
    full_name = primary.get("fullName") or primary.get("name") or primary.get("label") or "Primary Passenger"
    email = primary.get("email") or None
    phone = primary.get("phone") or None

    # Finds or creates a customer for the primary passenger
    cust = None
    if email:
        cust = Customer.query.filter_by(email=email).first()
    if not cust:
        first, *rest = (full_name or "").split(" ", 1)
        last = rest[0] if rest else ""
        cust = Customer(first_name=first or "Guest", last_name=last or "Passenger", email=email or f"guest-{stamp}@example.com", phone=phone)
        db.session.add(cust)
        db.session.flush()

    # Support for staff view
    for p in passengers:
        seat_code = p.get("seatCode") or ""
        db.session.add(Booking(customer_id=cust.id, flight_id=flight_id, seat_code=seat_code))

    total_paid_cents, _fare_details = _compute_total_cents(flight.price_cents or 0, passengers, billing_country)

    status_text = flight.status or "On time"
    if flight.depart_time and flight.depart_time <= datetime.utcnow() and "cancel" not in (status_text or "").lower():
        status_text = "Departed"

    # Details for booking reference
    record = BookingRecord(
        booking_ref=booking_ref,
        flight_id=flight_id,
        primary_name=full_name,
        primary_email=email,
        primary_phone=phone,
        total_paid_cents=total_paid_cents,
        status=status_text,
        passengers=passengers,
    )
    db.session.add(record)
    db.session.commit()
