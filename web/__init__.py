from flask import Flask
from .search import search_bp


def create_app():
    app = Flask(__name__)

    @app.route("/")
    def home():
        return "CP317 - Grou 40"
    
    app.register_blueprint(search_bp)

    

    return app
