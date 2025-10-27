from flask import Blueprint, render_template, request
from datetime import datetime
from .models import Flight

search_bp = Blueprint("search", __name__)

@search_bp.route("/search", methods=["GET"])
def search():
    q_origin = (request.args.get("origin") or "").upper().strip()
    q_dest   = (request.args.get("destination") or "").upper().strip()
    q_depart = request.args.get("depart")

    query = Flight.query
    if q_origin:
        query = query.filter(Flight.origin == q_origin)
    if q_dest:
        query = query.filter(Flight.destination == q_dest)
    if q_depart:
        try:
            d = datetime.fromisoformat(q_depart)
            end = d.replace(hour=23, minute=59, second=59)
            query = query.filter(Flight.depart_time >= d, Flight.depart_time <= end)
        except Exception:
            pass

    flights = None
    if q_origin or q_dest or q_depart:
        flights = query.order_by(Flight.depart_time.asc()).all()

    return render_template("flight_search.html", flights=flights)
