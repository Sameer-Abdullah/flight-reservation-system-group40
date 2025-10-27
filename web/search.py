# web/search.py
from datetime import datetime
from flask import Blueprint, render_template, request
from .models import Flight

search_bp = Blueprint("search", __name__)

@search_bp.route("/")
def index():
    return render_template("index.html")

# 👇 add endpoint="search" so url_for('search.search') is valid
@search_bp.route("/search", methods=["GET"], endpoint="search")
def search_page():
    origin = (request.args.get("origin") or "").strip().upper()
    destination = (request.args.get("destination") or "").strip().upper()
    depart_str = request.args.get("depart")

    q = Flight.query
    if origin:
        q = q.filter(Flight.origin.ilike(f"%{origin}%"))
    if destination:
        q = q.filter(Flight.destination.ilike(f"%{destination}%"))
    if depart_str:
        try:
            d = datetime.fromisoformat(depart_str)
            q = q.filter(Flight.depart_time.between(
                d.replace(hour=0, minute=0, second=0),
                d.replace(hour=23, minute=59, second=59)
            ))
        except Exception:
            pass

    flights = None
    if origin or destination or depart_str:
        flights = q.order_by(Flight.depart_time.asc()).all()

    return render_template("flight_search.html", flights=flights)