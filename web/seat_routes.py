from flask import Blueprint, render_template, jsonify
from web.models import Flight, AircraftType, Seat
from web import db

bp = Blueprint("seats", __name__)

@bp.get("/flights/<int:flight_id>/seats")
def seat_page(flight_id):
    # Serve the HTML; the JS fetches the data via the API below.
    return render_template("seat_select.html")

@bp.get("/api/flights/<int:flight_id>/seats")
def seats_api(flight_id):
    f = db.session.get(Flight, flight_id)
    if not f or not f.aircraft_type_id:
        return jsonify({"error": "flight_not_found"}), 404

    at = db.session.get(AircraftType, f.aircraft_type_id)
    if not at:
        return jsonify({"error": "aircraft_not_found"}), 404

    # Blocked seats from DB
    blocked = []
    rows = (
        db.session.query(Seat.row_num, Seat.seat_letter, Seat.is_blocked)
        .filter(Seat.flight_id == flight_id)
        .all()
    )
    for r, ch, is_blocked in rows:
        if is_blocked:
            blocked.append(f"{r}{ch}")

    return jsonify({
        "flight_id": flight_id,
        "origin": f.origin,
        "destination": f.destination,
        "depart_time": f.depart_time.isoformat(),
        "rows": at.total_rows,
        "layout": at.layout,       
        "classes": at.class_map,   
        "occupied": [],             
        "held": [],                 
        "blocked": blocked,
        "prices": {}                
    })
