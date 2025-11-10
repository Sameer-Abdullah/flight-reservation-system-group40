from flask import Blueprint, request, render_template, redirect, url_for, flash, abort
from flask_login import login_required, current_user
from .models import Flight, Booking
from . import db

booking_bp = Blueprint("booking", __name__, url_prefix="/booking")

@booking_bp.route("/new")
def new_booking():
    flight_id = request.args.get("flight_id", type=int)
    flight = Flight.query.get_or_404(flight_id)
    return render_template("booking.html", flight=flight)

# === My Bookings list ===
@booking_bp.route("/mine")
@login_required
def my_bookings():
    upcoming = (
        Booking.query
        .filter_by(user_id=current_user.id, status='confirmed')
        .join(Flight, Booking.flight_id == Flight.id)
        .order_by(Flight.depart_time.asc())
        .all()
    )
    past = (
        Booking.query
        .filter_by(user_id=current_user.id, status='completed')
        .join(Flight, Booking.flight_id == Flight.id)
        .order_by(Flight.depart_time.desc())
        .all()
    )
    cancelled = (
        Booking.query
        .filter_by(user_id=current_user.id, status='canceled')
        .join(Flight, Booking.flight_id == Flight.id)
        .order_by(Flight.depart_time.desc())
        .all()
    )
    return render_template("my_bookings.html", upcoming=upcoming, past=past, cancelled=cancelled)

# === Cancel an upcoming booking ===
@booking_bp.post("/<int:booking_id>/cancel")
@login_required
def cancel_booking(booking_id: int):
    b = Booking.query.get_or_404(booking_id)
    if b.user_id != current_user.id:
        abort(403)

    if b.status != 'confirmed':
        flash("This booking cannot be canceled.", "warning")
        return redirect(url_for("booking.my_bookings"))

    # Only allow cancel if the flight hasn't departed yet
    if b.flight and b.flight.depart_time:
        from datetime import datetime
        if b.flight.depart_time <= datetime.utcnow():
            flash("Flight already departed and cannot be canceled.", "warning")
            return redirect(url_for("booking.my_bookings"))

    b.status = "canceled"
    db.session.commit()
    flash("Booking canceled.", "success")
    return redirect(url_for("booking.my_bookings"))