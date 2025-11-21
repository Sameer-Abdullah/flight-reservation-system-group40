import os
import json
from datetime import datetime, timezone
from flask import Flask, render_template, request, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, login_required, current_user
from dotenv import load_dotenv
from sqlalchemy import text

db = SQLAlchemy()
login_manager = LoginManager()

def create_app():
    load_dotenv()

    app = Flask(
        __name__,
        template_folder="../templates",
        static_folder="../static",
    )

    app.config["SECRET_KEY"] = os.getenv("SECRET_KEY", "dev-secret")
    app.config["SQLALCHEMY_DATABASE_URI"] = os.getenv("DATABASE_URL", "sqlite:///app.sqlite3")
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

    db.init_app(app)
    login_manager.init_app(app)
    login_manager.login_view = "auth.login"

    @app.route("/")
    def home():
        return render_template("index.html")
    
    @app.route("/account")
    @login_required
    def account():
        from .models import Booking, Traveler

        # booking counts for stats
        bookings_all = Booking.query.filter_by(user_id=current_user.id).all()
        now = datetime.now(timezone.utc)
        upcoming_count = 0
        completed_count = 0
        for b in bookings_all:
            depart = b.departure_time
            dep_cmp = depart
            if depart and depart.tzinfo is None:
                dep_cmp = depart.replace(tzinfo=timezone.utc)
            if b.status == Booking.STATUS_CANCELED:
                continue
            if b.status == Booking.STATUS_COMPLETED or (dep_cmp and dep_cmp < now):
                completed_count += 1
            else:
                upcoming_count += 1
        trips_total = upcoming_count + completed_count

        recent_bookings = (
            Booking.query.filter_by(user_id=current_user.id)
            .order_by(Booking.departure_time.desc())
            .limit(3)
            .all()
        )
        travelers = (
            Traveler.query.filter_by(user_id=current_user.id)
            .order_by(Traveler.created_at.desc())
            .all()
        )
        traveler_payload = [t.to_dict() for t in travelers]
        traveler_payload_json = json.dumps(traveler_payload)

        return render_template(
            "account.html",
            recent_bookings=recent_bookings,
            travelers=travelers,
            traveler_payload=traveler_payload,
            traveler_payload_json=traveler_payload_json,
            trips_total=trips_total,
            upcoming_count=upcoming_count,
            completed_count=completed_count,
        )

    @app.route("/account/profile", methods=["POST"])
    @login_required
    def update_profile():
        payload = request.get_json() or request.form
        allowed = ("title", "first_name", "last_name", "email", "phone", "dob", "nationality")

        dob_value = payload.get("dob")
        if dob_value:
            try:
                dob_parsed = datetime.strptime(dob_value, "%Y-%m-%d").date()
            except ValueError:
                return jsonify({"error": "Invalid date format."}), 400
        else:
            dob_parsed = None

        for field in allowed:
            if field == "dob":
                setattr(current_user, field, dob_parsed)
            elif field in payload:
                setattr(current_user, field, (payload.get(field) or "").strip() or None)
        db.session.commit()
        return jsonify(
            {
                "message": "Profile updated.",
                "user": {
                    "title": current_user.title,
                    "first_name": current_user.first_name,
                    "last_name": current_user.last_name,
                    "email": current_user.email,
                    "phone": current_user.phone,
                    "dob": current_user.dob.isoformat() if current_user.dob else None,
                    "nationality": current_user.nationality,
                    "display_name": current_user.display_name,
                },
            }
        )

    @app.route("/account/travelers", methods=["POST"])
    @login_required
    def add_traveler():
        from .models import Traveler

        payload = request.get_json() or {}
        full_name = (payload.get("full_name") or "").strip()
        if not full_name:
            return jsonify({"error": "Full name is required."}), 400

        dob_value = payload.get("dob")
        dob_parsed = None
        if dob_value:
            try:
                dob_parsed = datetime.strptime(dob_value, "%Y-%m-%d").date()
            except ValueError:
                return jsonify({"error": "Invalid date format."}), 400

        traveler = Traveler(
            user_id=current_user.id,
            title=(payload.get("title") or "").strip() or None,
            full_name=full_name,
            dob=dob_parsed,
            gender=(payload.get("gender") or "").strip() or None,
            contact_info=(payload.get("contact_info") or "").strip() or None,
            relationship=(payload.get("relationship") or "").strip() or None,
        )
        db.session.add(traveler)
        db.session.commit()
        return jsonify({"message": "Traveler added.", "traveler": traveler.to_dict()})

    # register blueprints
    from .auth import auth_bp
    app.register_blueprint(auth_bp)

    from .booking import booking_bp
    app.register_blueprint(booking_bp)

    from .search import search_bp
    app.register_blueprint(search_bp)

    from .notifications import notifications_bp
    app.register_blueprint(notifications_bp)

    from .payments import payments_bp
    app.register_blueprint(payments_bp)

    from .seat_routes import bp as seats_bp
    app.register_blueprint(seats_bp)

    # NEW: Staff dashboard blueprint
    from .staff_dashboard import staff_dashboard_bp
    app.register_blueprint(staff_dashboard_bp)



    from .search import search_bp   

    # create tables
    with app.app_context():
        from . import models
        db.create_all()
        ensure_booking_columns()

    return app


def ensure_booking_columns():
    """
    Lightweight schema guard to add optional columns without Alembic.
    Ensures booking.extras exists for storing seats/preferences/baggage.
    """
    cols = db.session.execute(text("PRAGMA table_info('booking')")).fetchall()
    names = {row[1] for row in cols}
    if "extras" not in names:
        db.session.execute(text("ALTER TABLE booking ADD COLUMN extras JSON"))
        db.session.commit()
