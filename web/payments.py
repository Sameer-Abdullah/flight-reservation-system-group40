# Still needs to be conneted to a payment method like stripe or paypal. Just a base/template to get started

from flask import Blueprint, render_template, request, redirect, url_for, flash
from .models import Flight  
from . import db

payments_bp = Blueprint("payments", __name__, url_prefix="/payments")

@payments_bp.route("/", methods=["GET", "POST"])
def payments_page():
    flight_id = request.args.get("flight_id", type=int)
    if not flight_id:
        flash("Missing flight information.", "warning")
        return redirect(url_for("search.search"))

    flight = Flight.query.get(flight_id)
    if not flight:
        flash("Flight not found.", "danger")
        return redirect(url_for("search.search"))

    if request.method == "POST":
        # process payment here later…
        flash("Payment processed successfully!", "success")
        return redirect(url_for("search.search"))

    return render_template("payments.html", flight=flight)

