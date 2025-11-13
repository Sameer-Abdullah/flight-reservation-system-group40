from datetime import datetime, timezone
from flask import Blueprint, request, render_template, jsonify
from flask_login import login_required, current_user
from .models import Flight, Booking
from . import db

booking_bp = Blueprint("booking", __name__, url_prefix="/booking")

CANCELLATION_POLICY = (
    "By canceling this booking, you may incur a cancellation fee based on your fare "
    "type. Refunds (if any) will be processed in 5–10 business days."
)


@booking_bp.route("/new")
def new_booking():
    flight_id = request.args.get("flight_id", type=int)
    flight = Flight.query.get_or_404(flight_id)
    return render_template("booking.html", flight=flight)


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
