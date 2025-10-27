import os
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from dotenv import load_dotenv

load_dotenv()

db = SQLAlchemy()
login_manager = LoginManager()
login_manager.login_view = "auth.login"

# Paths that match your screenshot: templates/ and static/ are at the repo root
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
TEMPLATES_DIR = os.path.join(PROJECT_ROOT, "templates")
STATIC_DIR    = os.path.join(PROJECT_ROOT, "static")

def create_app():
    app = Flask(
        __name__,
        instance_relative_config=True,
        template_folder=TEMPLATES_DIR,
        static_folder=STATIC_DIR,
    )

    app.config.update(
        SECRET_KEY=os.getenv("SECRET_KEY", "dev-secret-key"),
        SQLALCHEMY_DATABASE_URI=os.getenv("DATABASE_URL", "sqlite:///app.db"),
        SQLALCHEMY_TRACK_MODIFICATIONS=False,
    )

    db.init_app(app)
    login_manager.init_app(app)

    from .models import User  # ensure models loaded

    @login_manager.user_loader
    def load_user(user_id):
        from .models import User
        return User.query.get(int(user_id))

    # Blueprints
    from .auth import auth_bp
    from .search import search_bp
    from .booking import booking_bp
    from .payments import payments_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(search_bp)
    app.register_blueprint(booking_bp)
    app.register_blueprint(payments_bp)

    with app.app_context():
        db.create_all()

    return app