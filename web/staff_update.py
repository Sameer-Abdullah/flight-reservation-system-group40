from flask import Blueprint, render_template, request, redirect, url_for
from flask_login import login_required
from web.models import Flight
from web import db

staff_update_bp = Blueprint("staff_update", __name__, url_prefix="/staff/update")


@staff_update_bp.route("/", methods=["GET", "POST"])
@login_required
def update_status():
    flights = Flight.query.order_by(Flight.depart_time.asc()).all()

    if request.method == "POST":
        flight_id = request.form.get("flight_id")
        status = request.form.get("status")
        note = request.form.get("note", "")

        f = Flight.query.get(flight_id)
        if not f:
            return render_template(
                "staff_update.html",
                flights=flights,
                message="Flight not found."
            )

        # Save the update
        f.status = status
        f.status_note = note
        db.session.commit()

        return render_template(
            "staff_update.html",
            flights=flights,
            message="Flight status updated successfully"
        )

    return render_template("staff_update.html", flights=flights)