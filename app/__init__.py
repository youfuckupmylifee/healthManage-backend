from flask import Flask
from flask_cors import CORS
from .extensions import db, jwt
from .config import Config
from .routes import bp as routes_bp

def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    db.init_app(app)
    jwt.init_app(app)

    CORS(app, resources={r"/*": {"origins": "http://localhost:3000"}})

    with app.app_context():
        db.create_all()

    app.register_blueprint(routes_bp)

    return app
