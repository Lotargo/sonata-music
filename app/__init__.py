import os
from flask import Flask
from app.models import db

def create_app():
    app = Flask(__name__)

    # Configuration
    basedir = os.path.abspath(os.path.dirname(os.path.dirname(__file__)))
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(basedir, 'project.db')
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    app.config['UPLOAD_FOLDER'] = os.path.join(basedir, 'uploads')
    app.config['PROCESSED_FOLDER'] = os.path.join(basedir, 'library')

    # Ensure directories exist
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
    os.makedirs(app.config['PROCESSED_FOLDER'], exist_ok=True)

    db.init_app(app)

    with app.app_context():
        # Create tables
        db.create_all()

    # Register blueprints
    # We will import main blueprint here.
    # To avoid ImportErrors before routes.py is created, we do it inside create_app or just expect it to exist.
    from app.routes import main
    app.register_blueprint(main)

    return app
