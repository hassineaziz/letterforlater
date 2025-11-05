from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_mail import Mail
from os import path
from flask_login import LoginManager
import os
import warnings
from sqlalchemy import create_engine
from sqlalchemy_utils import database_exists, create_database
from flask_login import current_user
from flask_admin import Admin, AdminIndexView
from flask_admin.contrib.sqla import ModelView

# Suppress flask_admin pkg_resources deprecation warnings
warnings.filterwarnings('ignore', message='.*pkg_resources is deprecated.*', category=UserWarning)

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
    app.config['MAIL_SERVER'] = os.getenv('MAIL_SERVER', 'smtp.gmail.com')
    app.config['MAIL_PORT'] = int(os.getenv('MAIL_PORT', 587))
    app.config['MAIL_USE_TLS'] = os.getenv('MAIL_USE_TLS', 'true').lower() in ['true', 'on', '1']
    app.config['MAIL_USE_SSL'] = os.getenv('MAIL_USE_SSL', 'false').lower() in ['true', 'on', '1']
    app.config['MAIL_USERNAME'] = os.getenv('MAIL_USERNAME')
    app.config['MAIL_PASSWORD'] = os.getenv('MAIL_PASSWORD')
    app.config['MAIL_DEFAULT_SENDER'] = os.getenv('MAIL_USERNAME')
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
    from .pricing import pricing_bp
    from .stripe_routes import stripe_bp
    from .webhook_handler import webhook_bp

    app.register_blueprint(views, url_prefix='/')
    app.register_blueprint(auth, url_prefix='/')
    app.register_blueprint(seo_bp, url_prefix='/')
    app.register_blueprint(pricing_bp, url_prefix='/')
    app.register_blueprint(stripe_bp, url_prefix='/')
    app.register_blueprint(webhook_bp, url_prefix='/')

    from .models import User, Letter, DeathVerification, TrustedContact, Notification, MediaAttachment, BlogPost, RecipientInvite, DeathVerificationConfirmation, NewsletterSubscriber, Payment, BlockedIP
    
    # Create database tables
    with app.app_context():
        db.create_all()
        print('Database tables created!')

    login_manager = LoginManager()
    login_manager.login_view = 'auth.login'
    login_manager.init_app(app)

    @login_manager.user_loader
    def load_user(id):
        user = User.query.get(int(id))
        # Don't allow blocked/suspended users to login
        if user and not user.is_active:
            return None  # This will force re-login and show error
        
        # Also check IP blocking if user is loaded (for security)
        if user:
            from flask import request
            from .blocking import get_client_ip, is_ip_blocked
            client_ip = get_client_ip()
            ip_blocked, _ = is_ip_blocked(client_ip)
            if ip_blocked:
                print(f"[BLOCK] User {user.email} (ID: {id}) attempted access from blocked IP: {client_ip}")
                return None  # Block access even if user exists
        
        return user
    
    # Configure Flask-Admin (after login manager is set up)
    class AdminAuthMixin:
        def is_accessible(self):
            return current_user.is_authenticated and current_user.role == 'admin'
        
        def inaccessible_callback(self, name, **kwargs):
            from flask import redirect, url_for, flash
            flash('You need admin privileges to access this page.', 'error')
            return redirect(url_for('auth.login'))
    
    class AdminModelView(AdminAuthMixin, ModelView):
        pass
    
    class CustomAdminIndexView(AdminAuthMixin, AdminIndexView):
        pass
    
    # Initialize Flask-Admin at default /admin URL
    admin = Admin(app, name='Database Admin', index_view=CustomAdminIndexView())
    
    # Add model views
    admin.add_view(AdminModelView(User, db.session, name='Users'))
    admin.add_view(AdminModelView(Letter, db.session, name='Letters'))
    admin.add_view(AdminModelView(DeathVerification, db.session, name='Death Verifications'))
    admin.add_view(AdminModelView(TrustedContact, db.session, name='Trusted Contacts'))
    admin.add_view(AdminModelView(Notification, db.session, name='Notifications'))
    admin.add_view(AdminModelView(MediaAttachment, db.session, name='Media Attachments'))
    admin.add_view(AdminModelView(BlogPost, db.session, name='Blog Posts'))
    admin.add_view(AdminModelView(RecipientInvite, db.session, name='Recipient Invites'))
    admin.add_view(AdminModelView(DeathVerificationConfirmation, db.session, name='Death Confirmations'))
    admin.add_view(AdminModelView(NewsletterSubscriber, db.session, name='Newsletter Subscribers'))
    admin.add_view(AdminModelView(Payment, db.session, name='Payments'))

    # Add context processor to make TrustedContact and Letter available to all templates
    @app.context_processor
    def inject_models():
        return dict(TrustedContact=TrustedContact, Letter=Letter)

    # Add context processor to inject pending trusted contact invitations for the current user into all templates as 'pending_trusted_invitations'.
    @app.context_processor
    def inject_pending_trusted_invitations():
        from website.models import TrustedContact
        try:
            if current_user.is_authenticated:
                pending_trusted_invitations = TrustedContact.query.filter_by(email=current_user.email, is_confirmed=False).all()
            else:
                pending_trusted_invitations = []
        except:
            pending_trusted_invitations = []
        return dict(pending_trusted_invitations=pending_trusted_invitations)

    # Add context processor to ensure user is always available in templates
    @app.context_processor
    def inject_user():
        try:
            return dict(user=current_user if current_user.is_authenticated else None)
        except:
            return dict(user=None)

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

    @app.context_processor
    def utility_processor():
        def check_trusted_contact_status(user):
            if not user or not user.is_authenticated:
                return False
            from website.models import TrustedContact
            return TrustedContact.query.filter_by(email=user.email, is_confirmed=True).count() > 0
        def has_received_letters(user):
            if not user or not user.is_authenticated:
                return False
            from website.models import RecipientInvite
            return RecipientInvite.query.filter(
                RecipientInvite.recipient_user_id == user.id,
                RecipientInvite.registered_at.isnot(None)
            ).count() > 0
        return dict(check_trusted_contact_status=check_trusted_contact_status, has_received_letters=has_received_letters)

    @app.context_processor
    def inject_now():
        from datetime import datetime, timezone
        def now():
            # ISO 8601 date-time for SEO/JSON-LD usage
            return datetime.now(timezone.utc).isoformat()
        return dict(now=now)

    # Add plan utilities to context
    @app.context_processor
    def inject_plan_utils():
        from website.plan_utils import (
            get_user_plan, is_premium_user, is_lifetime_user,
            can_create_unlimited_letters, can_upload_media, can_schedule_letters,
            can_use_scheduled_delivery, can_use_death_verification,
            can_add_unlimited_contacts, get_max_letters, get_max_contacts,
            get_storage_limit, get_plan_features, get_upgrade_message,
            get_plan_comparison, check_feature_access, get_upgrade_cta_text
        )
        return dict(
            get_user_plan=get_user_plan,
            is_premium_user=is_premium_user,
            is_lifetime_user=is_lifetime_user,
            can_create_unlimited_letters=can_create_unlimited_letters,
            can_upload_media=can_upload_media,
            can_schedule_letters=can_schedule_letters,
            can_use_scheduled_delivery=can_use_scheduled_delivery,
            can_use_death_verification=can_use_death_verification,
            can_add_unlimited_contacts=can_add_unlimited_contacts,
            get_max_letters=get_max_letters,
            get_max_contacts=get_max_contacts,
            get_storage_limit=get_storage_limit,
            get_plan_features=get_plan_features,
            get_upgrade_message=get_upgrade_message,
            get_plan_comparison=get_plan_comparison,
            check_feature_access=check_feature_access,
            get_upgrade_cta_text=get_upgrade_cta_text
        )

    return app
