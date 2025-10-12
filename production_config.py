"""
Production configuration for the Legacy Letter application.
This file contains production-ready settings for media handling and system optimization.
"""

import os
from datetime import timedelta

class ProductionConfig:
    """Production configuration class"""
    
    # Basic Flask settings
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'your-super-secret-production-key-change-this'
    DEBUG = False
    TESTING = False
    
    # Database settings
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or 'sqlite:///production.db'
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {
        'pool_size': 20,
        'pool_recycle': 3600,
        'pool_pre_ping': True,
        'max_overflow': 30
    }
    
    # Media system settings
    MAX_CONTENT_LENGTH = 100 * 1024 * 1024  # 100MB max file size
    MEDIA_UPLOAD_FOLDER = os.path.join(os.getcwd(), 'website', 'static', 'uploads')
    MEDIA_TEMP_EXPIRY_HOURS = 24  # Temporary media expires after 24 hours
    MEDIA_ALLOWED_EXTENSIONS = {
        'image': {'png', 'jpg', 'jpeg', 'gif', 'webp'},
        'video': {'mp4'},
        'audio': {'mp3', 'wav', 'm4a'}
    }
    
    # File storage settings
    UPLOAD_FOLDER = MEDIA_UPLOAD_FOLDER
    MAX_FILE_SIZE = MAX_CONTENT_LENGTH
    
    # Security settings
    SESSION_COOKIE_SECURE = True
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'
    PERMANENT_SESSION_LIFETIME = timedelta(hours=24)
    
    # Logging settings
    LOG_LEVEL = 'INFO'
    LOG_FILE = 'production.log'
    
    # Performance settings
    SEND_FILE_MAX_AGE_DEFAULT = timedelta(hours=1)  # Cache static files for 1 hour
    
    # Email settings (configure these for production)
    MAIL_SERVER = os.environ.get('MAIL_SERVER') or 'smtp.gmail.com'
    MAIL_PORT = int(os.environ.get('MAIL_PORT') or 587)
    MAIL_USE_TLS = os.environ.get('MAIL_USE_TLS', 'true').lower() in ['true', 'on', '1']
    MAIL_USERNAME = os.environ.get('MAIL_USERNAME')
    MAIL_PASSWORD = os.environ.get('MAIL_PASSWORD')
    
    # Media cleanup settings
    MEDIA_CLEANUP_INTERVAL_HOURS = 6  # Run cleanup every 6 hours
    MEDIA_CLEANUP_BATCH_SIZE = 100  # Process media in batches of 100
    
    # User limits
    MAX_MEDIA_PER_USER = 100  # Maximum media files per user
    MAX_MEDIA_PER_LETTER = 20  # Maximum media files per letter
    MAX_TOTAL_MEDIA_SIZE_MB = 1000  # Maximum total media size per user (1GB)
    
    # CDN settings (for future use)
    CDN_ENABLED = os.environ.get('CDN_ENABLED', 'false').lower() in ['true', 'on', '1']
    CDN_DOMAIN = os.environ.get('CDN_DOMAIN')
    
    # Monitoring settings
    ENABLE_METRICS = True
    METRICS_INTERVAL_SECONDS = 300  # Collect metrics every 5 minutes
    
    @staticmethod
    def init_app(app):
        """Initialize application with production settings"""
        # Create upload directories
        os.makedirs(ProductionConfig.MEDIA_UPLOAD_FOLDER, exist_ok=True)
        
        # Set up logging
        import logging
        from logging.handlers import RotatingFileHandler
        
        if not app.debug and not app.testing:
            if not os.path.exists('logs'):
                os.mkdir('logs')
            
            file_handler = RotatingFileHandler(
                'logs/production.log', 
                maxBytes=10240000, 
                backupCount=10
            )
            file_handler.setFormatter(logging.Formatter(
                '%(asctime)s %(levelname)s: %(message)s [in %(pathname)s:%(lineno)d]'
            ))
            file_handler.setLevel(logging.INFO)
            app.logger.addHandler(file_handler)
            
            app.logger.setLevel(logging.INFO)
            app.logger.info('Legacy Letter production startup')

class DevelopmentConfig:
    """Development configuration class"""
    
    DEBUG = True
    SQLALCHEMY_DATABASE_URI = 'sqlite:///development.db'
    SQLALCHEMY_TRACK_MODIFICATIONS = True
    
    # Development media settings
    MAX_CONTENT_LENGTH = 50 * 1024 * 1024  # 50MB for development
    MEDIA_TEMP_EXPIRY_HOURS = 168  # 1 week for development
    
    @staticmethod
    def init_app(app):
        pass

class TestingConfig:
    """Testing configuration class"""
    
    TESTING = True
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'
    WTF_CSRF_ENABLED = False
    
    @staticmethod
    def init_app(app):
        pass

# Configuration dictionary
config = {
    'development': DevelopmentConfig,
    'testing': TestingConfig,
    'production': ProductionConfig,
    'default': DevelopmentConfig
}

def get_config(config_name=None):
    """Get configuration class by name"""
    if config_name is None:
        config_name = os.environ.get('FLASK_ENV', 'default')
    
    return config.get(config_name, config['default'])
