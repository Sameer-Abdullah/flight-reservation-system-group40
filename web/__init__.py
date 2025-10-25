from flask import Flask, render_template


def create_app():
    # point Flask to emplates/ and static/
    app = Flask(__name__, template_folder="../templates", static_folder="../static")

    @app.route("/")
    def home():
        return render_template("index.html")

    from .auth import auth_bp
    app.register_blueprint(auth_bp)

    return app
