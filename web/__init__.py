import os
from datetime import datetime, date, timedelta
from flask import Flask, render_template, request, redirect, url_for, flash
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, current_user, login_required
from dotenv import load_dotenv

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
    
    @app.route("/account", methods=["GET", "POST"])
    @login_required
    def account():
        from .models import UserProfile, BookingRecord, Flight, Traveler

        profile = UserProfile.query.filter_by(user_id=current_user.id).first()
        if not profile:
            profile = UserProfile(user_id=current_user.id, member_since=date.today())
            db.session.add(profile)
            db.session.commit()

        if request.method == "POST":
            form_type = request.form.get("form_type") or "profile"

            if form_type == "profile":
                title = (request.form.get("title") or "").strip() or None
                first_name = (request.form.get("first_name") or "").strip() or None
                middle_name = (request.form.get("middle_name") or "").strip() or None
                last_name = (request.form.get("last_name") or "").strip() or None
                phone = (request.form.get("phone") or "").strip() or None
                nationality = (request.form.get("nationality") or "").strip() or None
                dob_raw = (request.form.get("dob") or "").strip()

                if dob_raw:
                    try:
                        profile.dob = datetime.strptime(dob_raw, "%Y-%m-%d").date()
                    except ValueError:
                        flash("Please enter date of birth as YYYY-MM-DD.", "warning")
                        return redirect(url_for("account"))
                else:
                    profile.dob = None

                profile.title = title
                profile.first_name = first_name
                profile.middle_name = middle_name
                profile.last_name = last_name
                profile.phone = phone
                profile.nationality = nationality
                if not profile.member_since:
                    profile.member_since = date.today()

                db.session.add(profile)
                db.session.commit()
                flash("Profile updated.", "success")
                return redirect(url_for("account"))

            if form_type == "traveler":
                t_title = (request.form.get("traveler_title") or "").strip() or None
                t_first = (request.form.get("traveler_first_name") or "").strip()
                t_middle = (request.form.get("traveler_middle_name") or "").strip() or None
                t_last = (request.form.get("traveler_last_name") or "").strip()
                relation_choice = (request.form.get("traveler_relation_select") or "").strip()
                relation_other = (request.form.get("traveler_relation_other") or "").strip()
                t_relation = relation_other if relation_choice == "Other" and relation_other else relation_choice or None
                t_email = (request.form.get("traveler_email") or "").strip() or None
                t_phone = (request.form.get("traveler_phone") or "").strip() or None
                t_nationality = (request.form.get("traveler_nationality") or "").strip() or None
                t_dob_raw = (request.form.get("traveler_dob") or "").strip()

                if not t_first or not t_last:
                    flash("Please provide first and last name for the traveler.", "warning")
                    return redirect(url_for("account"))

                t_dob = None
                if t_dob_raw:
                    try:
                        t_dob = datetime.strptime(t_dob_raw, "%Y-%m-%d").date()
                    except ValueError:
                        flash("Traveler date of birth must be YYYY-MM-DD.", "warning")
                        return redirect(url_for("account"))

                traveler = Traveler(
                    user_id=current_user.id,
                    title=t_title,
                    first_name=t_first,
                    middle_name=t_middle,
                    last_name=t_last,
                    relation=t_relation,
                    email=t_email,
                    phone=t_phone,
                    nationality=t_nationality,
                    dob=t_dob,
                )
                db.session.add(traveler)
                db.session.commit()
                flash("Traveler added.", "success")
                return redirect(url_for("account"))

        # Stored datetimes are naive UTC; use utcnow for consistent categorization.
        now = datetime.utcnow()
        records = (
            db.session.query(BookingRecord, Flight)
            .join(Flight, BookingRecord.flight_id == Flight.id)
            .order_by(BookingRecord.created_at.desc())
            .all()
        )

        trips = []
        upcoming = completed = cancelled = 0
        total_paid = 0.0
        touched = False
        for rec, flight in records:
            depart = flight.depart_time
            status_text = rec.status or flight.status or "On time"
            if flight.depart_time and flight.depart_time <= now and "cancel" not in status_text.lower():
                status_text = "Departed"
                if rec.status != status_text:
                    rec.status = status_text
                    db.session.add(rec)
                    touched = True
            ticket_type = "Economy"
            if rec.passengers:
                p0 = rec.passengers[0]
                ticket_type = (
                    p0.get("class")
                    or p0.get("cabin")
                    or p0.get("classPreference")
                    or p0.get("ticketType")
                    or "Economy"
                )

            is_cancelled = "cancel" in status_text.lower()
            is_upcoming = depart and depart > now and not is_cancelled
            is_completed = depart and depart <= now and not is_cancelled

            if is_upcoming:
                upcoming += 1
            elif is_completed:
                completed += 1
            elif is_cancelled:
                cancelled += 1

            arrival_guess = depart + timedelta(hours=3) if depart else None
            trips.append(
                {
                    "origin": flight.origin,
                    "destination": flight.destination,
                    "ticket_type": ticket_type,
                    "depart": depart,
                    "arrival": arrival_guess,
                    "status": status_text,
                    "booking_ref": rec.booking_ref,
                    "flight_number": f"SW{flight.id:04d}",
                    "total_paid": (rec.total_paid_cents or 0) / 100,
                }
            )
            total_paid += (rec.total_paid_cents or 0) / 100

        if touched:
            db.session.commit()

        if not trips:
            fallback_date = datetime(2025, 11, 29, 7, 30)
            trips = [
                {
                    "origin": "YYZ",
                    "destination": "LAX",
                    "ticket_type": "First",
                    "depart": fallback_date,
                    "arrival": fallback_date + timedelta(hours=3),
                    "status": "On time",
                    "booking_ref": "SW7481041540",
                    "flight_number": "SW7481",
                    "total_paid": 3672.12,
                },
                {
                    "origin": "YYZ",
                    "destination": "DXB",
                    "ticket_type": "First",
                    "depart": fallback_date,
                    "arrival": fallback_date + timedelta(hours=3),
                    "status": "On time",
                    "booking_ref": "SW7481041541",
                    "flight_number": "SW7482",
                    "total_paid": 3672.12,
                },
            ]
            upcoming = len(trips)
            cancelled = completed = 0

        saved_amount = total_paid if total_paid else 3102
        status_overview = (trips[0]["status"] if trips else "") or "On time"

        title_options = ["Mr", "Ms", "Mrs", "Mx", "Dr", "Prof"]
        nationality_options = [
            "Afghanistan", "Albania", "Algeria", "Andorra", "Angola", "Antigua and Barbuda",
            "Argentina", "Armenia", "Australia", "Austria", "Azerbaijan", "Bahamas", "Bahrain",
            "Bangladesh", "Barbados", "Belarus", "Belgium", "Belize", "Benin", "Bhutan",
            "Bolivia", "Bosnia and Herzegovina", "Botswana", "Brazil", "Brunei", "Bulgaria",
            "Burkina Faso", "Burundi", "Cambodia", "Cameroon", "Canada", "Cape Verde",
            "Central African Republic", "Chad", "Chile", "China", "Colombia", "Comoros",
            "Congo (Congo-Brazzaville)", "Costa Rica", "Cote d'Ivoire", "Croatia", "Cuba", "Cyprus",
            "Czechia", "Democratic Republic of the Congo", "Denmark", "Djibouti", "Dominica",
            "Dominican Republic", "Ecuador", "Egypt", "El Salvador", "Equatorial Guinea",
            "Eritrea", "Estonia", "Eswatini", "Ethiopia", "Fiji", "Finland", "France", "Gabon",
            "Gambia", "Georgia", "Germany", "Ghana", "Greece", "Grenada", "Guatemala", "Guinea",
            "Guinea-Bissau", "Guyana", "Haiti", "Honduras", "Hungary", "Iceland", "India",
            "Indonesia", "Iran", "Iraq", "Ireland", "Italy", "Jamaica", "Japan",
            "Jordan", "Kazakhstan", "Kenya", "Kiribati", "Kosovo", "Kuwait", "Kyrgyzstan", "Laos",
            "Latvia", "Lebanon", "Lesotho", "Liberia", "Libya", "Liechtenstein", "Lithuania",
            "Luxembourg", "Madagascar", "Malawi", "Malaysia", "Maldives", "Mali", "Malta",
            "Marshall Islands", "Mauritania", "Mauritius", "Mexico", "Micronesia", "Moldova",
            "Monaco", "Mongolia", "Montenegro", "Morocco", "Mozambique", "Myanmar", "Namibia",
            "Nauru", "Nepal", "Netherlands", "New Zealand", "Nicaragua", "Niger", "Nigeria",
            "North Korea", "North Macedonia", "Norway", "Oman", "Pakistan", "Palau", "Panama",
            "Papua New Guinea", "Paraguay", "Peru", "Philippines", "Poland", "Portugal", "Qatar",
            "Romania", "Russia", "Rwanda", "Saint Kitts and Nevis", "Saint Lucia",
            "Saint Vincent and the Grenadines", "Samoa", "San Marino", "Sao Tome and Principe",
            "Saudi Arabia", "Senegal", "Serbia", "Seychelles", "Sierra Leone", "Singapore",
            "Slovakia", "Slovenia", "Solomon Islands", "Somalia", "South Africa", "South Korea",
            "South Sudan", "Spain", "Sri Lanka", "Sudan", "Suriname", "Sweden", "Switzerland",
            "Syria", "Taiwan", "Tajikistan", "Tanzania", "Thailand", "Timor-Leste", "Togo",
            "Tonga", "Trinidad and Tobago", "Tunisia", "Turkey", "Turkmenistan", "Tuvalu",
            "Uganda", "Ukraine", "United Arab Emirates", "United Kingdom", "United States",
            "Uruguay", "Uzbekistan", "Vanuatu", "Vatican City", "Venezuela", "Vietnam", "Yemen",
            "Zambia", "Zimbabwe", "Other",
        ]

        display_name = current_user.full_name or current_user.email
        initials = current_user.initials or (current_user.email.split("@")[0][:2].upper() if current_user.email else "YO")

        stats = {
            # Total trips should reflect flown + scheduled, not cancellations
            "trip_count": upcoming + completed if trips else upcoming,
            "upcoming": upcoming,
            "completed": completed,
            "cancelled": cancelled,
            "saved": saved_amount,
            "alerts": 0,
            "status": status_overview,
        }

        # Only show upcoming flights in the “Recent bookings” list
        upcoming_trips = [t for t in trips if t.get("depart") and t["depart"] > now and "cancel" not in (t["status"] or "").lower()]

        return render_template(
            "account.html",
            profile=profile,
            stats=stats,
            bookings=upcoming_trips,
            display_name=display_name,
            initials=initials,
            member_since=profile.member_since,
            user_email=current_user.email,
            title_options=title_options,
            nationality_options=nationality_options,
            travelers=Traveler.query.filter_by(user_id=current_user.id).order_by(Traveler.last_name.asc()).all(),
        )

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

    from .my_bookings import bookings_bp
    app.register_blueprint(bookings_bp)

    # NEW: Staff dashboard blueprint
    from .staff_dashboard import staff_dashboard_bp
    app.register_blueprint(staff_dashboard_bp)
    
    from .staff_update import staff_update_bp
    app.register_blueprint(staff_update_bp)

    from .contact import general_bp
    app.register_blueprint(general_bp)




    from .search import search_bp   

    # create tables
    with app.app_context():
        from . import models
        db.create_all()

    return app
