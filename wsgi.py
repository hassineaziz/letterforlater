"""
WSGI entry point for production deployment
Use with gunicorn: gunicorn -w 4 wsgi:app
"""
from website import create_app
import os

# Set production environment
os.environ.setdefault('FLASK_ENV', 'production')

# Create application instance
app = create_app()

if __name__ == '__main__':
    # This is only for development/testing
    # In production, use gunicorn or another WSGI server
    app.run(host='0.0.0.0', port=8000)

