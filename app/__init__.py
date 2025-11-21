from flask import Flask
from app.models import db
from flask_migrate import Migrate
from flask_jwt_extended import JWTManager
from config import Config
from flask_cors import CORS

migrate = Migrate()
jwt = JWTManager()

def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)
    CORS(app, resources={r"/*": {"origins": "*"}}, supports_credentials=True)

    # Initialize extensions
    db.init_app(app)
    migrate.init_app(app, db)
    jwt.init_app(app)

    # Register blueprints
    from app.routes.main_routes import main
    from app.routes.auth_routes import auth_bp
    from app.routes.user_routes import api_bp
    from app.routes.image_routes import image_bp
    from app.routes.set_routes import set_routes

    app.register_blueprint(main)
    app.register_blueprint(auth_bp, url_prefix='/auth')
    app.register_blueprint(api_bp, url_prefix='/api')
    app.register_blueprint(image_bp, url_prefix='/image')
    app.register_blueprint(set_routes)

    return app
