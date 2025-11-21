from datetime import datetime, timezone
from flask import Blueprint, request, render_template, jsonify, redirect, url_for, flash
from flask_login import login_required, current_user
from .models import Flight, Booking
from . import db
from .state import get_booking_context, update_booking_context

booking_bp = Blueprint("booking", __name__, url_prefix="/booking")

CANCELLATION_POLICY = (
    "By canceling this booking, you may incur a cancellation fee based on your fare "
    "type. Refunds (if any) will be processed in 5–10 business days."
)


@booking_bp.route("/new")
def new_booking():
    flight_id = request.args.get("flight_id", type=int)
    flight = Flight.query.get_or_404(flight_id)
    ctx = get_booking_context()
    pax_from_query = request.args.get("pax", type=int)
    passenger_count = pax_from_query or ctx.get("passenger_count") or 1
    passenger_count = max(1, passenger_count)
    selected_seats = (ctx.get("selected_seats") or [])[:passenger_count]
    class_map = flight.aircraft_type.class_map if flight.aircraft_type else []
    layout = flight.aircraft_type.layout if flight.aircraft_type else "ABC DEF"
    rows_total = flight.aircraft_type.total_rows if flight.aircraft_type else 0
    lead_passenger = ctx.get("lead_passenger") or {}
    passengers_ctx = ctx.get("passengers") or []
    prefs_ctx = ctx.get("preferences") or {}

    def cabin_for_row(row_num: int):
        for block in class_map:
            if block.get("from") <= row_num <= block.get("to"):
                return block.get("class")
        return "Economy"

    def seat_pref_from_code(code: str):
        if not code:
            return None
        try:
            row = int("".join(filter(str.isdigit, code)))
        except Exception:
            row = None
        letter = "".join(ch for ch in code if ch.isalpha())
        groups = layout.split()
        if not groups:
            return None
        window_letters = {groups[0][0], groups[-1][-1]}
        aisle_letters = set()
        for i in range(len(groups) - 1):
            aisle_letters.add(groups[i][-1])
            aisle_letters.add(groups[i + 1][0])
        if letter in window_letters:
            return "Window"
        if letter in aisle_letters:
            return "Aisle"
        return "Middle"

    def cabin_for_code(code: str):
        if not code:
            return None
        try:
            row = int("".join(filter(str.isdigit, code)))
        except Exception:
            return None
        return cabin_for_row(row)

    derived_prefs = [seat_pref_from_code(code) for code in selected_seats]
    seat_cabins = [cabin_for_code(code) for code in selected_seats]

    valid_class = {"Economy", "Premium", "Business", "First"}

    if seat_cabins:
        class_default = seat_cabins[0]
    elif ctx.get("class_choice") in valid_class:
        class_default = ctx["class_choice"]
    else:
        class_default = "Economy"

    if derived_prefs:
        seat_pref_default = derived_prefs[0] or prefs_ctx.get("seat") or "Window"
    else:
        seat_pref_default = prefs_ctx.get("seat") or "Window"

    meal_pref_default = prefs_ctx.get("meal") or "Standard"


    passenger_seat_prefs = []
    passenger_class_prefs = []
    passenger_extra_bags = []
    passenger_meal_prefs = []
    passenger_names = []
    passenger_emails = []
    passenger_phones = []
    passenger_dobs = []
    for idx in range(passenger_count):
        pref_from_seat = derived_prefs[idx] if idx < len(derived_prefs) else None
        saved_pref = passengers_ctx[idx].get("seat_pref") if idx < len(passengers_ctx) else None
        if pref_from_seat:
            passenger_seat_prefs.append(pref_from_seat)
        elif saved_pref:
            passenger_seat_prefs.append(saved_pref)
        else:
            passenger_seat_prefs.append(seat_pref_default)

        # class pref per passenger: prefer existing saved pref, else cabin of their seat, else overall default
        this_cabin = seat_cabins[idx] if idx < len(seat_cabins) else None
        if idx < len(passengers_ctx):
            passenger_class_prefs.append(passengers_ctx[idx].get("class_pref") or this_cabin or class_default)
            passenger_extra_bags.append(passengers_ctx[idx].get("extra_bags") or 0)
            passenger_meal_prefs.append(passengers_ctx[idx].get("meal_pref") or meal_pref_default)
            passenger_names.append(passengers_ctx[idx].get("full_name") or "")
            passenger_emails.append(passengers_ctx[idx].get("email") or "")
            passenger_phones.append(passengers_ctx[idx].get("phone") or "")
            passenger_dobs.append(passengers_ctx[idx].get("dob") or "")
        else:
            passenger_class_prefs.append(this_cabin or class_default)
            passenger_extra_bags.append(0)
            passenger_meal_prefs.append(meal_pref_default)
            passenger_names.append("")
            passenger_emails.append("")
            passenger_phones.append("")
            passenger_dobs.append("")

    # keep flight + pax in session for downstream pages
    update_booking_context(
        {
            "flight_id": flight.id,
            "passenger_count": passenger_count,
            "selected_seats": selected_seats[:passenger_count],
            "class_choice": class_default,
        }
    )

    return render_template(
        "booking.html",
        flight=flight,
        passenger_count=passenger_count,
        selected_seats=selected_seats,
        class_map=class_map,
        layout=layout,
        rows_total=rows_total,
        class_default=class_default,
        seat_pref_default=seat_pref_default,
        meal_pref_default=meal_pref_default,
        passenger_seat_prefs=passenger_seat_prefs,
        passenger_class_prefs=passenger_class_prefs,
        passenger_extra_bags=passenger_extra_bags,
        passenger_names=passenger_names,
        passenger_emails=passenger_emails,
        passenger_phones=passenger_phones,
        passenger_dobs=passenger_dobs,
        passenger_meal_prefs=passenger_meal_prefs,
        lead_passenger=lead_passenger,
    )


@booking_bp.route("/capture", methods=["POST"])
def capture_booking_details():
    """Persist passenger preferences + baggage so the payment step can price them."""
    flight_id = request.form.get("flight_id", type=int)
    if not flight_id:
        flash("Missing flight when saving booking details.", "danger")
        return redirect(url_for("search.search"))

    passenger_count = request.form.get("passenger_count", type=int) or 1
    lead = {
        "full_name": (request.form.get("fullname") or "").strip(),
        "email": (request.form.get("email") or "").strip(),
        "phone": (request.form.get("phone") or "").strip(),
        "dob": (request.form.get("lead_dob") or "").strip(),
    }
    prefs = {
        "seat": request.form.get("seat") or "Window",
        "meal": request.form.get("meal_pref") or "Standard",
    }
    class_choice = request.form.get("class") or "Economy"

    passengers = []
    extra_bags_total = 0
    seat_map = get_booking_context().get("selected_seats") or []

    # lead passenger
    lead_extra = request.form.get("lead_extra_bags", type=int) or 0
    passengers.append(
        {
            "full_name": lead["full_name"],
            "email": lead["email"],
            "phone": lead["phone"],
            "dob": lead["dob"],
            "seat_pref": prefs["seat"],
            "meal_pref": prefs["meal"],
            "seat": seat_map[0] if seat_map else None,
            "extra_bags": lead_extra,
            "class_pref": class_choice,
        }
    )
    extra_bags_total += lead_extra

    # additional passengers
    for idx in range(2, passenger_count + 1):
        pax = {
            "full_name": (request.form.get(f"pax{idx}_name") or "").strip(),
            "dob": (request.form.get(f"pax{idx}_dob") or "").strip(),
            "email": (request.form.get(f"pax{idx}_email") or "").strip(),
            "phone": (request.form.get(f"pax{idx}_phone") or "").strip(),
            "seat_pref": request.form.get(f"pax{idx}_seat_pref") or prefs["seat"],
            "meal_pref": request.form.get(f"pax{idx}_meal_pref") or prefs["meal"],
            "seat": seat_map[idx - 1] if len(seat_map) >= idx else None,
            "class_pref": request.form.get(f"pax{idx}_class_pref") or class_choice,
        }
        extra_bags = request.form.get(f"pax{idx}_extra_bags", type=int)
        pax["extra_bags"] = extra_bags if extra_bags and extra_bags > 0 else 0
        extra_bags_total += pax["extra_bags"]
        passengers.append(pax)

    # total baggage includes 1 per traveler + any extras supplied
    baggage_total = passenger_count + extra_bags_total

    ctx = update_booking_context(
        {
            "flight_id": flight_id,
            "passenger_count": passenger_count,
            "lead_passenger": lead,
            "preferences": prefs,
            "baggage_total": max(baggage_total, passenger_count),
            "class_choice": class_choice,
            "passengers": passengers,
            "extra_bags": extra_bags_total,
        }
    )

    flash("Saved your traveler details. Continue to payment.", "success")
    return redirect(url_for("payments.payments_page", flight_id=flight_id))


@booking_bp.route("/my", methods=["GET"])
@login_required
def my_bookings():
    bookings = (
        Booking.query.filter_by(user_id=current_user.id)
        .order_by(Booking.departure_time.asc())
        .all()
    )

    now = datetime.now(timezone.utc)
    upcoming, past, canceled = [], [], []
    for booking in bookings:
        depart = booking.departure_time
        dep_cmp = depart
        if depart and depart.tzinfo is None:
            dep_cmp = depart.replace(tzinfo=timezone.utc)

        if booking.status == Booking.STATUS_CANCELED:
            canceled.append(booking)
        elif booking.status == Booking.STATUS_COMPLETED or (dep_cmp and dep_cmp < now):
            past.append(booking)
        else:
            upcoming.append(booking)

    latest_booking = None
    if bookings:
        latest_booking = max(
            bookings,
            key=lambda b: (
                b.departure_time or datetime.min.replace(tzinfo=timezone.utc),
                b.updated_at or b.created_at,
            ),
        )

    return render_template(
        "my_bookings.html",
        upcoming=upcoming,
        past=past,
        canceled=canceled,
        policy_text=CANCELLATION_POLICY,
        show_cancel_banner=bool(latest_booking and latest_booking.status == Booking.STATUS_CANCELED),
        extras_map={b.id: (b.extras or {}) for b in bookings},
    )


@booking_bp.route("/<int:booking_id>/cancel", methods=["POST"])
@login_required
def cancel_booking(booking_id: int):
    booking = (
        Booking.query.filter_by(id=booking_id, user_id=current_user.id)
        .first_or_404()
    )

    if not booking.can_cancel():
        return (
            jsonify({"error": "This flight can no longer be canceled online."}),
            400,
        )

    payload = request.get_json(silent=True) or {}
    if not payload.get("acknowledged"):
        return (
            jsonify({"error": "You must acknowledge the cancellation policy."}),
            400,
        )

    reason = payload.get("reason")
    booking.status = Booking.STATUS_CANCELED
    booking.cancellation_reason = reason.strip() if isinstance(reason, str) else None
    booking.cancellation_ack = True
    booking.canceled_at = datetime.utcnow()
    db.session.commit()

    return jsonify(
        {
            "message": "Flight canceled successfully.",
            "booking": {
                "id": booking.id,
                "status": booking.status,
                "formatted_total": booking.formatted_total(),
                "cancellation_reason": booking.cancellation_reason,
            },
        }
    )
