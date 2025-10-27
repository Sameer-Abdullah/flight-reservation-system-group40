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

    # secrets + DB
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
    def account():
        return render_template("account.html")

    # register blueprints
    from .auth import auth_bp
    app.register_blueprint(auth_bp)

    from .booking import booking_bp
    app.register_blueprint(booking_bp)

    from .search import search_bp
    app.register_blueprint(search_bp)

    from .payments import payments_bp
    app.register_blueprint(payments_bp)



    from .search import search_bp   

    # create tables
    with app.app_context():
        from . import models
        db.create_all()

    return app

