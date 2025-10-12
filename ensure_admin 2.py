#!/usr/bin/env python3
"""
Script to ensure admin user exists.
Run this script anytime to make sure hassineaziz@icloud.com is an admin.
This is useful after database resets or migrations.
"""

from website import create_app, db
from website.models import User
from werkzeug.security import generate_password_hash
import sys

def ensure_admin_user():
    """Ensure admin user exists with correct permissions"""
    try:
        app = create_app()
        with app.app_context():
            admin_email = 'hassineaziz@icloud.com'
            
            # Check if admin user already exists
            admin_user = User.query.filter_by(email=admin_email).first()
            
            if admin_user:
                # Update existing user to admin role if needed
                if admin_user.role != 'admin':
                    admin_user.role = 'admin'
                    admin_user.is_active = True
                    db.session.commit()
                    print(f'✅ Updated existing user {admin_email} to admin role')
                else:
                    print(f'✅ Admin user {admin_email} already exists with correct role')
            else:
                # Create new admin user
                admin_user = User(
                    email=admin_email,
                    password=generate_password_hash('admin123!', method='pbkdf2:sha256'),
                    first_name='Hassine',
                    last_name='Aziz',
                    notification_preferences={'email_notifications': True},
                    delivery_preferences={'delivery_method': 'email'},
                    role='admin',
                    is_active=True
                )
                db.session.add(admin_user)
                db.session.commit()
                print(f'✅ Created new admin user: {admin_email}')
            
            print(f'📧 Email: {admin_email}')
            print(f'🔑 Password: admin123!')
            print(f'👑 Role: {admin_user.role}')
            print(f'✅ Active: {admin_user.is_active}')
            print('\n🎉 Admin access is ready!')
            return True
            
    except Exception as e:
        print(f'❌ Error ensuring admin user: {str(e)}', file=sys.stderr)
        return False

if __name__ == '__main__':
    if ensure_admin_user():
        print('Admin setup successful!')
    else:
        print('Admin setup failed!', file=sys.stderr)
        sys.exit(1)
