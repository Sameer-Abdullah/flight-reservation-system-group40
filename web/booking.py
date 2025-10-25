from flask import Blueprint, request, render_template
from .models import Flight

booking_bp = Blueprint("booking", __name__, url_prefix="/booking")

@booking_bp.route("/new")
def new_booking():
    flight_id = request.args.get("flight_id", type=int)
    flight = Flight.query.get_or_404(flight_id)
    # For Sprint 01 demo: just show a simple confirmation page
    return render_template("booking.html", flight=flight)
