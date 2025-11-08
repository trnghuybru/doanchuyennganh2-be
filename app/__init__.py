from flask import Flask
from app.models import db
from flask_migrate import Migrate
from config import Config

migrate = Migrate()

def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    db.init_app(app)
    migrate.init_app(app, db)

    from app.routes.main_routes import main
    app.register_blueprint(main)

    return app
