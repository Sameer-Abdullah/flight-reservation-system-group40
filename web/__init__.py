import os
from flask import Flask, render_template
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
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

    instance_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "instance"))
    os.makedirs(instance_dir, exist_ok=True)
    db_file = os.path.join(instance_dir, "airline.db")
    app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///" + db_file
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

    db.init_app(app)
    login_manager.init_app(app)

    from .auth import auth_bp
    app.register_blueprint(auth_bp, url_prefix="/auth")

    from .search import search_bp
    app.register_blueprint(search_bp)

    from .booking import booking_bp
    app.register_blueprint(booking_bp)

    from .payments import payments_bp
    app.register_blueprint(payments_bp)

    from .seat_routes import bp as seats_bp
    app.register_blueprint(seats_bp)

    from .notifications import notifications_bp
    app.register_blueprint(notifications_bp, url_prefix="/notifications")

    from .account import account_bp
    app.register_blueprint(account_bp)

    @app.route("/")
    def index():
        return render_template("index.html")

    with app.app_context():
        from . import models
        db.create_all()

    return app