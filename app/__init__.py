"""
Create and configure the Flask application.
"""
from flask import Flask
from flask_cors import CORS

from app.main import RestAPIRoutes

def create_app():
    """Create and configure the Flask application."""
    app = Flask(__name__)
    CORS(app)

    app.register_blueprint(RestAPIRoutes.main_bp)

    return app
