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


if __name__ == "__main__":
    app = create_app()
    app.run(host='0.0.0.0', port=8080, debug=True) # Explicitly set host