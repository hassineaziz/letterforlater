from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_mail import Mail
from os import path
from flask_login import LoginManager
import os
from sqlalchemy import create_engine
from sqlalchemy_utils import database_exists, create_database
from flask_login import current_user

db = SQLAlchemy()
migrate = Migrate(db)
mail = Mail()

def reset_database(app):
    with app.app_context():
        db.drop_all()
        db.create_all()
        print('Database reset complete!')

def create_app():
    app = Flask(__name__)
    
    # File upload configuration - max file size to 100MB
    app.config['MAX_CONTENT_LENGTH'] = 100 * 1024 * 1024  # 100MB max file size
    
    # Database configuration
    app.config['SECRET_KEY'] = 'hjshjhdjah kjshkjdhjs'
    database_url = os.getenv('DATABASE_URL', 'postgresql://postgres:postgres@localhost:5432/legacy_letter')
    app.config['SQLALCHEMY_DATABASE_URI'] = database_url
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    
    # Create database if it doesn't exist
    engine = create_engine(database_url)
    if not database_exists(engine.url):
        create_database(engine.url)
        print('Database created!')
    
    # Email configuration
    app.config['MAIL_SERVER'] = 'smtp.ionos.de'
    app.config['MAIL_PORT'] = 587
    app.config['MAIL_USE_TLS'] = True
    app.config['MAIL_USE_SSL'] = False
    app.config['MAIL_USERNAME'] = os.getenv('MAIL_USERNAME', 'info@itbewertungen.de')
    app.config['MAIL_PASSWORD'] = os.getenv('MAIL_PASSWORD', 'Testtest123*')
    app.config['MAIL_DEFAULT_SENDER'] = os.getenv('MAIL_USERNAME', 'info@itbewertungen.de')
    app.config['MAIL_TIMEOUT'] = 10  # 10 seconds timeout
    app.config['MAIL_MAX_EMAILS'] = 10
    app.config['MAIL_ASCII_ATTACHMENTS'] = False

    # Initialize extensions
    db.init_app(app)
    migrate.init_app(app, db)
    mail.init_app(app)
    
    # Initialize SEO routes (custom sitemap)
    from .sitemap_config import seo_bp

    from .views import views
    from .auth import auth

    app.register_blueprint(views, url_prefix='/')
    app.register_blueprint(auth, url_prefix='/')
    app.register_blueprint(seo_bp, url_prefix='/')

    from .models import User, Letter, DeathVerification, TrustedContact, Notification, MediaAttachment
    
    # Create database tables
    with app.app_context():
        db.create_all()
        print('Database tables created!')

    login_manager = LoginManager()
    login_manager.login_view = 'auth.login'
    login_manager.init_app(app)

    @login_manager.user_loader
    def load_user(id):
        return User.query.get(int(id))

    # Add context processor to make TrustedContact and Letter available to all templates
    @app.context_processor
    def inject_models():
        return dict(TrustedContact=TrustedContact, Letter=Letter)

    # Add context processor to inject pending trusted contact invitations for the current user into all templates as 'pending_trusted_invitations'.
    @app.context_processor
    def inject_pending_trusted_invitations():
        from website.models import TrustedContact
        if current_user.is_authenticated:
            pending_trusted_invitations = TrustedContact.query.filter_by(email=current_user.email, is_confirmed=False).all()
        else:
            pending_trusted_invitations = []
        return dict(pending_trusted_invitations=pending_trusted_invitations)

    # Add context processor to ensure user is always available in templates
    @app.context_processor
    def inject_user():
        return dict(user=current_user)

    # Add custom Jinja filter for status color
    def status_color(status):
        return {
            'pending': 'warning',
            'delivered': 'success',
            'cancelled': 'danger',
            'scheduled': 'info',
            'draft': 'secondary',
            'verified': 'success',
            'rejected': 'danger'
        }.get(status, 'secondary')
    app.jinja_env.filters['status_color'] = status_color

    return app
