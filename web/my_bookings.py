from datetime import datetime, timedelta
from flask import Blueprint, render_template, request, jsonify
from flask_login import login_required
from .models import BookingRecord, Flight
from . import db

bookings_bp = Blueprint("bookings", __name__, url_prefix="/bookings")


# builds the My Bookings page from stored records, with demo fallback if none exist
@bookings_bp.route("/")
@login_required
def my_bookings():
    now = datetime.utcnow()
    touched = False
    records = (
        db.session.query(BookingRecord, Flight)
        .join(Flight, BookingRecord.flight_id == Flight.id)
        .order_by(BookingRecord.created_at.desc())
        .all()
    )

    trips = []
    for rec, flight in records:
        passengers = rec.passengers or []
        pax_list = []
        for idx, p in enumerate(passengers):
            chip = p.get("label") or f"P{idx+1}"
            if chip.lower().startswith("passenger"):
                chip = f"P{idx+1}"
            pax_list.append({
                "label": p.get("label") or f"P{idx+1}",
                "chip": chip,
                "name": p.get("fullName") or p.get("name") or p.get("label") or f"Passenger {idx+1}",
                "class": p.get("classPreference") or p.get("cabin") or "Economy",
                "seat_pref": p.get("seatPreference") or p.get("position") or "",
                "meal": p.get("mealPreference") or "Standard",
                "extra_bags": int(p.get("extraBags") or 0),
                "seat": p.get("seatCode") or "",
            })

        extra_bags = sum(p.get("extra_bags", 0) for p in pax_list)
        included_bags = len(pax_list) * 1
        total_bags = included_bags + extra_bags

        status_text = rec.status or flight.status or "On time"
        if flight.depart_time and flight.depart_time <= now and "cancel" not in status_text.lower():
            status_text = "Departed"
            if rec.status != status_text:
                rec.status = status_text
                db.session.add(rec)
                touched = True

        is_future = bool(flight.depart_time and flight.depart_time > now)
        flight_available = is_future and not ((flight.status or "").lower().startswith("cancel"))

        arrival_time = flight.depart_time + timedelta(hours=3) if flight.depart_time else None

        trips.append({
            "origin": flight.origin,
            "destination": flight.destination,
            "airline": "SkyWings",
            "flight_number": f"SW{flight.id:04d}",
            "departure": flight.depart_time,
            "arrival": arrival_time,
            "booking_ref": rec.booking_ref,
            "ticket_type": pax_list[0]["class"] if pax_list else "Economy",
            "total_paid": (rec.total_paid_cents or 0) / 100,
            "price": (flight.price_cents or 0) / 100,
            "status": status_text,
            "pax": pax_list,
            "baggage": {"total": total_bags, "included": included_bags, "extras": extra_bags},
            "fare_terms": "Free online cancellation up to 2 hours before departure.",
            "available": flight_available,
        })

    if touched:
        db.session.commit()

    upcoming, past, cancelled = [], [], []
    for t in trips:
        status_text = (t["status"] or "").lower()
        if "cancel" in status_text:
            cancelled.append(t)
        elif t["departure"] and t["departure"] <= now:
            past.append(t)
        elif "depart" in status_text:
            past.append(t)
        else:
            upcoming.append(t)

    if not upcoming and not past and not cancelled:
        sample_trip = {
            "origin": "YYZ",
            "destination": "DXB",
            "airline": "SkyWings",
            "flight_number": "SW7481",
            "departure": datetime(2025, 11, 29, 7, 30),
            "arrival": datetime(2025, 11, 29, 10, 30),
            "booking_ref": "SW7481041540",
            "ticket_type": "First",
            "total_paid": 3672.12,
            "status": "On time",
            "pax": [
                {
                    "label": "P1",
                    "name": "Yaman Al-Eryani",
                    "class": "First",
                    "seat_pref": "Window Seat",
                    "meal": "Standard",
                    "extra_bags": 0,
                    "seat": "1A",
                },
                {
                    "label": "P2",
                    "name": "Yaman Al-Eryani",
                    "class": "Business",
                    "seat_pref": "Aisle Seat",
                    "meal": "Standard",
                    "extra_bags": 1,
                    "seat": "6D",
                },
            ],
            "baggage": {"total": 3, "included": 2, "extras": 1},
            "fare_terms": "Free online cancellation up to 2 hours before departure.",
        }
        upcoming.append(sample_trip)

    bookings = {
        "upcoming": upcoming,
        "past": past,
        "cancelled": cancelled,
    }

    return render_template("bookings.html", bookings=bookings)


# marks a booking as cancelled and optionally records the reason
@bookings_bp.route("/cancel", methods=["POST"])
@login_required
def cancel_booking():
    data = request.get_json(silent=True) or request.form or {}
    booking_ref = (data.get("booking_ref") or "").strip()
    reason = (data.get("reason") or "").strip()
    if not booking_ref:
        return jsonify({"ok": False, "error": "Missing booking_ref"}), 400

    rec = BookingRecord.query.filter_by(booking_ref=booking_ref).first()
    if not rec:
        return jsonify({"ok": False, "error": "Booking not found"}), 404

    rec.status = "Cancelled"
    if rec.passengers and reason:
        pax = rec.passengers
        if isinstance(pax, list):
            for p in pax:
                if isinstance(p, dict):
                    p.setdefault("notes", [])
                    p["notes"].append(f"Cancellation reason: {reason}")
        rec.passengers = pax
    db.session.add(rec)
    db.session.commit()
    return jsonify({"ok": True})


# reactivates a cancelled booking if its flight is still available
@bookings_bp.route("/rebook", methods=["POST"])
@login_required
def rebook_booking():
    data = request.get_json(silent=True) or request.form or {}
    booking_ref = (data.get("booking_ref") or "").strip()
    if not booking_ref:
        return jsonify({"ok": False, "error": "Missing booking_ref"}), 400

    rec = BookingRecord.query.filter_by(booking_ref=booking_ref).first()
    if not rec:
        return jsonify({"ok": False, "error": "Booking not found"}), 404

    flight = Flight.query.get(rec.flight_id)
    now = datetime.utcnow()
    if not flight or not flight.depart_time or flight.depart_time <= now:
        return jsonify({"ok": False, "error": "Flight no longer available"}), 400
    if flight.status and "cancel" in flight.status.lower():
        return jsonify({"ok": False, "error": "Flight no longer available"}), 400

    rec.status = "On time"
    db.session.add(rec)
    db.session.commit()
    return jsonify({
        "ok": True,
        "price": (flight.price_cents or 0) / 100,
        "depart": flight.depart_time.isoformat() if flight.depart_time else None,
        "origin": flight.origin,
        "destination": flight.destination,
    })