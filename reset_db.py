from website import create_app, db
from website.models import User, Letter, DeathVerification, TrustedContact, DeathVerificationConfirmation
from datetime import datetime, timedelta
import sys
from sqlalchemy import text

def reset_database():
    try:
        app = create_app()
        with app.app_context():
            print('Dropping and recreating schema...')
            db.session.execute(text('DROP SCHEMA public CASCADE;'))
            db.session.execute(text('CREATE SCHEMA public;'))
            db.session.commit()
            db.reflect()
            db.drop_all()
            print('All tables dropped!')
            db.create_all()
            print('All tables recreated!')

            from werkzeug.security import generate_password_hash
            print('Creating test user...')
            test_user = User(
                email='test@example.com',
                password=generate_password_hash('password123', method='pbkdf2:sha256'),
                first_name='Test',
                last_name='User',
                notification_preferences={'email_notifications': True},
                delivery_preferences={'delivery_method': 'email'},
                role='main'
            )
            db.session.add(test_user)
            db.session.commit()
            print('Test user created!')

            print('Creating admin user...')
            admin_user = User(
                email='hassineaziz@icloud.com',
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
            print('Admin user created!')

            print('Creating unconfirmed trusted contact...')
            trusted_contact = TrustedContact(
                user_id=test_user.id,
                full_name='Trusted Person',
                email='trusted@example.com',
                phone='1234567890',
                relationship='Friend',
                is_confirmed=False,
                confirmation_code='test-confirm-code'
            )
            db.session.add(trusted_contact)
            db.session.commit()
            print('Test trusted contact created!')

            print('Creating confirmed trusted contact...')
            trusted_contact2 = TrustedContact(
                user_id=test_user.id,
                full_name='Trusted Main',
                email='trustedmain@example.com',
                phone='9876543210',
                relationship='Sibling',
                is_confirmed=True,
                confirmation_code='test-confirm-code-2'
            )
            db.session.add(trusted_contact2)
            db.session.commit()
            print('Test confirmed trusted contact created!')

            print('Creating trusted_main user...')
            trusted_main_user = User(
                email='trustedmain@example.com',
                password=generate_password_hash('password456', method='pbkdf2:sha256'),
                first_name='Trusted',
                last_name='Main',
                notification_preferences={'email_notifications': True},
                delivery_preferences={'delivery_method': 'email'},
                role='trusted_main'
            )
            db.session.add(trusted_main_user)
            db.session.commit()
            print('Trusted main user created!')

            print('Creating letter requiring death verification...')
            letter = Letter(
                title='After Death Letter',
                content='This is a letter to be sent after my death.',
                recipient_name='Recipient',
                recipient_email='recipient@example.com',
                delivery_type='death_verification',
                status='pending_verification',
                user_id=test_user.id,
                delivery_date=None,
                delivery_status=None
            )
            db.session.add(letter)
            db.session.commit()
            print('Test letter created!')

            print('Creating scheduled letter...')
            scheduled_letter = Letter(
                title='Scheduled Letter',
                content='This is a letter to be sent on a specific date.',
                recipient_name='Recipient2',
                recipient_email='recipient2@example.com',
                delivery_type='date',
                status='scheduled',
                user_id=test_user.id,
                scheduled_date=datetime.now() + timedelta(days=7),
                delivery_date=datetime.now() + timedelta(days=7),
                delivery_status='pending'
            )
            db.session.add(scheduled_letter)
            db.session.commit()
            print('Scheduled letter created!')

            print('Creating delivered letter...')
            delivered_letter = Letter(
                title='Delivered Letter',
                content='This letter has already been delivered.',
                recipient_name='Recipient3',
                recipient_email='recipient3@example.com',
                delivery_type='date',
                status='delivered',
                user_id=test_user.id,
                scheduled_date=datetime.now() - timedelta(days=2),
                delivery_date=datetime.now() - timedelta(days=1),
                delivery_status='delivered'
            )
            db.session.add(delivered_letter)
            db.session.commit()
            print('Delivered letter created!')

            print('Creating death verification for the test user...')
            dv = DeathVerification(
                user_id=test_user.id,
                confirmations_count=0,
                status='pending',
                verification_code='test-verification-code'
            )
            db.session.add(dv)
            db.session.commit()
            print('Test death verification created!')

            print('Creating death verification confirmation by trusted_main...')
            dvc = DeathVerificationConfirmation(
                verification_id=dv.id,
                trusted_contact_id=trusted_contact2.id,
                confirmed=True
            )
            db.session.add(dvc)
            db.session.commit()
            print('Test death verification confirmation created!')

            print('Database reset complete!')
            return True
    except Exception as e:
        print(f'Error resetting database: {str(e)}', file=sys.stderr)
        return False

if __name__ == '__main__':
    if reset_database():
        print('Database reset successful!')
    else:
        print('Database reset failed!', file=sys.stderr)
        sys.exit(1) 