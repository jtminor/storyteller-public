"""
Create and configure the Flask application.
"""
from flask import Flask
from app import main
from flask_cors import CORS

def create_app():
    """Create and configure the Dotes Flask application."""
    app = Flask(__name__)
    CORS(app)

    return app
