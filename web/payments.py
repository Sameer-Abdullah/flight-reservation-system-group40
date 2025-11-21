from datetime import datetime, timedelta
from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import current_user
from .models import Flight, Booking, Traveler
from . import db
from .state import get_booking_context, update_booking_context, clear_booking_context

payments = Blueprint("payments", __name__, url_prefix="/payments")

COUNTRY_TAX_RATES = {
    # All set to 13% per request for consistent calculation
    "Antigua and Barbuda": 0.13,
    "Bahamas": 0.13,
    "Barbados": 0.13,
    "Belize": 0.13,
    "Canada": 0.13,
    "Costa Rica": 0.13,
    "Cuba": 0.13,
    "Dominica": 0.13,
    "Dominican Republic": 0.13,
    "El Salvador": 0.13,
    "Grenada": 0.13,
    "Guatemala": 0.13,
    "Haiti": 0.13,
    "Honduras": 0.13,
    "Jamaica": 0.13,
    "Mexico": 0.13,
    "Nicaragua": 0.13,
    "Panama": 0.13,
    "Saint Kitts and Nevis": 0.13,
    "Saint Lucia": 0.13,
    "Saint Vincent and the Grenadines": 0.13,
    "Trinidad and Tobago": 0.13,
    "United States": 0.13,
    "Argentina": 0.13,
    "Bolivia": 0.13,
    "Brazil": 0.13,
    "Chile": 0.13,
    "Colombia": 0.13,
    "Ecuador": 0.13,
    "Guyana": 0.13,
    "Paraguay": 0.13,
    "Peru": 0.13,
    "Suriname": 0.13,
    "Uruguay": 0.13,
    "Venezuela": 0.13,
    "United Kingdom": 0.13,
    "France": 0.13,
    "Germany": 0.13,
    "Spain": 0.13,
    "Italy": 0.13,
    "Portugal": 0.13,
    "Japan": 0.13,
    "Australia": 0.13,
    "New Zealand": 0.13,
    "Singapore": 0.13,
    "United Arab Emirates": 0.13,
}


def fmt(cents: int) -> str:
    dollars = (cents or 0) / 100
    return f"${dollars:,.2f}"


def build_pricing(flight: Flight, passenger_count: int, class_choice: str, passengers: list, included_bags: int, extra_bags: int, country: str):
    base_cents = (flight.price_cents or 0) * passenger_count

    def upgrade_for_class(cpref: str) -> int:
        if cpref == "Business":
            return 45000
        if cpref == "First":
            return 90000
        return 0

    upgrade_cents = 0
    if passengers:
        for idx in range(passenger_count):
            pref = None
            if idx < len(passengers):
                pref = passengers[idx].get("class_pref") or class_choice
            else:
                pref = class_choice
            upgrade_cents += upgrade_for_class(pref)
    else:
        upgrade_cents = upgrade_for_class(class_choice) * passenger_count

    included_bags = included_bags if included_bags is not None else passenger_count
    extra_bags = extra_bags if extra_bags is not None else 0
    baggage_cents = max(extra_bags, 0) * 5000  # $50 per overage

    subtotal = base_cents + upgrade_cents + baggage_cents
    tax_rate = COUNTRY_TAX_RATES.get(country, 0.13)
    tax_cents = int(round(subtotal * tax_rate))
    total_cents = subtotal + tax_cents

    return {
        "base_cents": base_cents,
        "upgrade_cents": upgrade_cents,
        "baggage_cents": baggage_cents,
        "tax_cents": tax_cents,
        "total_cents": total_cents,
        "tax_rate": tax_rate,
        "country": country,
        "included_bags": included_bags,
        "additional_bags": extra_bags,
        "formatted": {
            "base": fmt(base_cents),
            "upgrade": fmt(upgrade_cents),
            "baggage": fmt(baggage_cents),
            "tax": fmt(tax_cents),
        "total": fmt(total_cents),
        },
    }


def build_upgrade_labels(passengers: list, fallback_class: str):
    labels = []
    for idx, pax in enumerate(passengers or []):
        pref = pax.get("class_pref") or fallback_class
        if pref in ("Business", "First"):
            labels.append(pref)
    # fallback if no passengers list
    if not passengers and fallback_class in ("Business", "First"):
        labels.append(fallback_class)

    counts = {}
    for lbl in labels:
        counts[lbl] = counts.get(lbl, 0) + 1
    parts = []
    for lbl, cnt in counts.items():
        if cnt > 1:
            parts.append(f"{lbl} ({cnt})")
        else:
            parts.append(lbl)
    return parts


def save_additional_travelers(user_id: int, passengers: list):
    """
    Persist additional travelers to the Traveler list on account page.
    Skips the lead passenger (index 0) and avoids duplicates by full name.
    """
    if not user_id or not passengers or len(passengers) < 2:
        return
    existing = {
        t.full_name.lower()
        for t in Traveler.query.filter_by(user_id=user_id).all()
        if t.full_name
    }
    new_entries = []
    for pax in passengers[1:]:
        full_name = (pax.get("full_name") or "").strip()
        if not full_name:
            continue
        key = full_name.lower()
        if key in existing:
            continue
        contact = pax.get("email") or pax.get("phone") or ""
        traveler = Traveler(
            user_id=user_id,
            full_name=full_name,
            contact_info=contact,
            relationship="Travel Companion",
        )
        new_entries.append(traveler)
        existing.add(key)
    if new_entries:
        db.session.add_all(new_entries)
        db.session.commit()


def generate_reference(flight_id: int) -> str:
    now = datetime.utcnow().strftime("%H%M%S")
    return f"SW{flight_id}{now}"


def persist_booking(flight: Flight, class_choice: str, pricing: dict, extras: dict):
    if not current_user.is_authenticated:
        return None

    arrival_time = flight.depart_time + timedelta(hours=3) if flight.depart_time else None
    booking = Booking(
        user_id=current_user.id,
        airline="SkyWings",
        flight_number=f"SW{flight.id}",
        origin=flight.origin,
        destination=flight.destination,
        departure_time=flight.depart_time,
        arrival_time=arrival_time,
        ticket_type=class_choice,
        booking_reference=generate_reference(flight.id),
        total_paid_cents=pricing.get("total_cents", 0),
        extras=extras,
    )
    db.session.add(booking)
    db.session.commit()
    return booking


def available_countries():
    return sorted(COUNTRY_TAX_RATES.keys())


@payments.route("/<int:flight_id>", methods=["GET"])
def payments_page(flight_id: int):
    flight = Flight.query.get_or_404(flight_id)
    ctx = get_booking_context()
    passenger_count = ctx.get("passenger_count") or 1
    seat_map = ctx.get("selected_seats") or [None for _ in range(passenger_count)]
    prefs = ctx.get("preferences") or {}
    baggage_total = ctx.get("baggage_total") or passenger_count
    class_choice = ctx.get("class_choice") or "Economy"
    lead_passenger = ctx.get("lead_passenger") or {}
    passengers = ctx.get("passengers") or []
    extra_bags = ctx.get("extra_bags") or max(baggage_total - passenger_count, 0)
    country = ctx.get("billing_country") or "Canada"

    if not passengers or len(passengers) < passenger_count:
        flash("Please add passenger details on the booking step before paying.", "warning")
        return redirect(url_for("booking.new_booking", flight_id=flight_id))

    pricing = build_pricing(
        flight,
        passenger_count,
        class_choice,
        passengers,
        passenger_count,
        extra_bags,
        country,
    )
    upgrade_labels = build_upgrade_labels(passengers, class_choice)
    update_booking_context(
        {
            "flight_id": flight_id,
            "passenger_count": passenger_count,
            "baggage_total": baggage_total,
            "class_choice": class_choice,
            "selected_seats": seat_map,
        }
    )

    return render_template(
        "payments.html",
        flight=flight,
        flight_id=flight_id,
        passenger_count=passenger_count,
        seat_map=seat_map,
        prefs=prefs,
        baggage_total=baggage_total,
        pricing=pricing,
        country_rates=available_countries(),
        tax_rates=COUNTRY_TAX_RATES,
        selected_country=country,
        class_choice=class_choice,
        lead_passenger=lead_passenger,
        passengers=passengers,
        extra_bags=extra_bags,
        upgrade_labels=upgrade_labels,
    )


@payments.route("/submit-card", methods=["POST"])
def submit_card():
    flight_id = request.form.get("flight_id", type=int)
    if not flight_id:
        flash("Missing flight for payment.", "danger")
        return redirect(url_for("search.search"))

    flight = Flight.query.get_or_404(flight_id)
    ctx = get_booking_context()
    passenger_count = ctx.get("passenger_count") or 1
    class_choice = ctx.get("class_choice") or "Economy"
    baggage_total = ctx.get("baggage_total") or passenger_count
    seats = ctx.get("selected_seats") or []
    prefs = ctx.get("preferences") or {}
    lead = ctx.get("lead_passenger") or {}
    passengers = ctx.get("passengers") or []
    extra_bags = ctx.get("extra_bags") or max(baggage_total - passenger_count, 0)

    name_on_card = (request.form.get("card_name") or "").strip()
    street = (request.form.get("street") or "").strip()
    city = (request.form.get("city") or "").strip()
    country = (request.form.get("country") or "").strip() or "Canada"
    postal = (request.form.get("postal") or "").strip()

    if not name_on_card or not street or not city or not country or not postal:
        flash("Name on card and billing address are required to continue.", "danger")
        return redirect(url_for("payments.payments_page", flight_id=flight_id))

    if not passengers or len(passengers) < passenger_count:
        flash("Please add passenger details on the booking step before paying.", "warning")
        return redirect(url_for("booking.new_booking", flight_id=flight_id))

    billing = {
        "name": name_on_card,
        "street": street,
        "city": city,
        "country": country,
        "postal": postal,
    }

    pricing = build_pricing(
        flight,
        passenger_count,
        class_choice,
        passengers,
        passenger_count,
        extra_bags,
        country,
    )
    upgrade_labels = build_upgrade_labels(passengers, class_choice)
    extras = {
        "passenger_count": passenger_count,
        "selected_seats": seats,
        "preferences": prefs,
        "baggage_total": baggage_total,
        "class_choice": class_choice,
        "passengers": passengers,
        "billing": billing,
        "pricing": pricing,
        "payment_method": "Card",
    }
    update_booking_context({"billing_country": country, "upgrade_labels": upgrade_labels, **extras})

    booking = persist_booking(flight, class_choice, pricing, extras)
    if booking and current_user.is_authenticated:
        save_additional_travelers(current_user.id, passengers)
    clear_booking_context()
    if booking:
        flash("Payment completed. Your booking was saved.", "success")
    else:
        flash("Payment completed. Sign in to keep this booking in My Bookings.", "info")

    return redirect(url_for("booking.my_bookings"))


@payments.route("/mock-paypal/<int:flight_id>", methods=["GET"])
def mock_paypal(flight_id: int):
    flight = Flight.query.get_or_404(flight_id)
    ctx = get_booking_context()
    passenger_count = ctx.get("passenger_count") or 1
    class_choice = ctx.get("class_choice") or "Economy"
    baggage_total = ctx.get("baggage_total") or passenger_count
    seats = ctx.get("selected_seats") or []
    prefs = ctx.get("preferences") or {}
    passengers = ctx.get("passengers") or []
    extra_bags = ctx.get("extra_bags") or max(baggage_total - passenger_count, 0)
    country = ctx.get("billing_country") or "Canada"

    pricing = build_pricing(
        flight,
        passenger_count,
        class_choice,
        passengers,
        passenger_count,
        extra_bags,
        country,
    )
    upgrade_labels = build_upgrade_labels(passengers, class_choice)
    extras = {
        "passenger_count": passenger_count,
        "selected_seats": seats,
        "preferences": prefs,
        "baggage_total": baggage_total,
        "class_choice": class_choice,
        "passengers": passengers,
        "billing": {"country": country, "provider": "PayPal"},
        "pricing": pricing,
        "payment_method": "PayPal (mock)",
    }
    update_booking_context({**extras, "upgrade_labels": upgrade_labels})

    booking = persist_booking(flight, class_choice, pricing, extras)
    if booking and current_user.is_authenticated:
        save_additional_travelers(current_user.id, passengers)
    flash("Payment completed (PayPal – mock).", "success")
    clear_booking_context()
    return redirect(url_for("booking.my_bookings"))


# Backward-compat alias so "from .payments import payments_bp" still works.
payments_bp = payments
