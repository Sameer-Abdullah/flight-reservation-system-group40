from flask import Blueprint, render_template
from .models import Flight
from sqlalchemy import func

reports_bp = Blueprint("reports", __name__, url_prefix="/reports")

@reports_bp.route("/route-popularity")
def route_popularity():
    """
    Displays the most popular airline routes (origin → destination)
    based on number of scheduled flights.
    """

    # Query: count how many flights exist per route
    results = (
        Flight.query
        .with_entities(
            Flight.origin.label("origin"),
            Flight.destination.label("destination"),
            func.count().label("count")
        )
        .group_by(Flight.origin, Flight.destination)
        .order_by(func.count().desc())
        .all()
    )

    # Convert SQL result rows into list of dictionaries
    route_data = [
        {
            "origin": row.origin,
            "destination": row.destination,
            "count": row.count
        }
        for row in results
    ]

    return render_template("route_popularity.html", route_data=route_data)