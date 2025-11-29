from flask import Blueprint, request, render_template
from .models import Flight

booking_bp = Blueprint("booking", __name__, url_prefix="/booking")

@booking_bp.route("/new")
def new_booking():
    flight_id = request.args.get("flight_id", type=int)
    pax = request.args.get("pax", default=1, type=int) or 1
    passenger_count = max(1, min(pax, 9))
    flight = Flight.query.get_or_404(flight_id)
    return render_template("booking.html", flight=flight, passenger_count=passenger_count)
