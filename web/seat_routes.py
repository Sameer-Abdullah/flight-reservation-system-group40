from flask import Blueprint, render_template, jsonify, request
from web.models import Flight, AircraftType, Seat
from web import db
from .state import get_booking_context, update_booking_context

bp = Blueprint("seats", __name__)

@bp.get("/flights/<int:flight_id>/seats")
def seat_page(flight_id):
    # Serve the HTML; the JS fetches the data via the API below.
    ctx = get_booking_context()
    pax_override = request.args.get("pax", type=int)
    if pax_override and pax_override > 0:
        # override previous context when user picked a new passenger count
        selected_seats = (ctx.get("selected_seats") or [])[:pax_override]
        ctx = update_booking_context(
            {
                "flight_id": flight_id,
                "passenger_count": pax_override,
                "selected_seats": selected_seats,
            }
        )
    pax = ctx.get("passenger_count")
    selected = []
    if ctx.get("flight_id") == flight_id:
        selected = (ctx.get("selected_seats") or [])[: (pax or 1)]
    return render_template(
        "seat_select.html",
        passenger_count=pax,
        preselected_seats=selected,
    )

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


@bp.post("/api/booking/selection")
def save_selection():
    payload = request.get_json(silent=True) or {}
    try:
        flight_id = int(payload.get("flight_id") or 0)
    except (TypeError, ValueError):
        flight_id = 0

    if not flight_id:
        return jsonify({"error": "missing_flight_id"}), 400

    flight = db.session.get(Flight, flight_id)
    if not flight:
        return jsonify({"error": "flight_not_found"}), 404

    try:
        passenger_count = max(1, int(payload.get("passenger_count") or 1))
    except (TypeError, ValueError):
        passenger_count = 1

    raw_seats = payload.get("seat_map") or payload.get("seats") or []
    codes = [str(code).upper() if code else None for code in raw_seats]

    authorized = set(
        f"{row}{letter}"
        for row, letter in db.session.query(Seat.row_num, Seat.seat_letter).filter(
            Seat.flight_id == flight_id
        )
    )
    selected = []
    for code in codes[:passenger_count]:
        if code and code in authorized:
            selected.append(code)
        else:
            selected.append(None)

    # pad in case the client sent fewer seats than passengers
    while len(selected) < passenger_count:
        selected.append(None)

    ctx = update_booking_context(
        {
            "flight_id": flight_id,
            "passenger_count": passenger_count,
            "selected_seats": selected,
        }
    )
    return jsonify({"message": "saved", "context": ctx})
