"""
Create and configure the Flask application.
"""
from flask import Flask
from flask_cors import CORS

from app.main import Routes

def create_app():
    """Create and configure the Flask application."""
    app = Flask(__name__)
    CORS(app)

    app.register_blueprint(Routes.main_bp)

    return app
