#!/usr/bin/env python3
"""
Script to send first-time reminders to:
1. Users who created accounts but haven't written any letters

Reminder schedule:
- First reminder: 2 days after account creation

This can be run by a cron job (e.g., daily) to process reminders.
"""

import sys
import os
from datetime import datetime, timedelta, timezone

# Add the project directory to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from website import create_app, db, mail
from website.models import User, Letter
from flask_mail import Message
from flask import render_template, url_for


def send_first_reminder(user):
    """Send first reminder (2 days after signup)"""
    try:
        dashboard_url = os.getenv('SITE_DOMAIN', 'https://letterforlater.com').rstrip('/')
        
        msg = Message(
            'Ready to Write Your First Letter?',
            recipients=[user.email],
            sender=os.getenv('MAIL_USERNAME', 'support@letterforlater.com')
        )
        
        # Render HTML template
        msg.html = render_template('emails/first_letter_reminder.html',
            user_name=f"{user.first_name} {user.last_name}",
            user_email=user.email,
            dashboard_url=dashboard_url
        )
        
        # Render text template
        msg.body = render_template('emails/first_letter_reminder.txt',
            user_name=f"{user.first_name} {user.last_name}",
            user_email=user.email,
            dashboard_url=dashboard_url
        )
        
        mail.send(msg)
        user.last_no_letter_reminder_sent_at = datetime.now(timezone.utc)
        db.session.commit()
        print(f"✓ Sent first reminder to {user.email}")
        return True
        
    except Exception as e:
        print(f"✗ Error sending first reminder to {user.email}: {str(e)}")
        db.session.rollback()
        return False


def send_reminders():
    """Send reminders to users without letters"""
    now = datetime.now(timezone.utc)
    print(f"Checking for users needing reminders at {now} (UTC)")
    
    # Get all active users
    active_users = User.query.filter(User.is_active == True).all()
    
    first_reminder_count = 0
    
    # Handle users without any letters
    for user in active_users:
        # Skip if user has any letters (non-draft)
        letter_count = Letter.query.filter(
            Letter.user_id == user.id,
            Letter.status != 'draft'
        ).count()
        if letter_count > 0:
            continue  # User has completed letters, skip
        
        # Check if user has draft letters
        has_draft = Letter.query.filter(
            Letter.user_id == user.id,
            Letter.status == 'draft'
        ).count() > 0
        if has_draft:
            continue  # User has draft letters, skip
        
        days_since_signup = (now - user.created_date).days
        
        # First reminder: 2 days after signup (and no reminder sent yet)
        if days_since_signup >= 2 and user.last_no_letter_reminder_sent_at is None:
            if send_first_reminder(user):
                first_reminder_count += 1
    
    print(f"✓ Sent {first_reminder_count} first reminders")
    return first_reminder_count


def main():
    """Main function to send reminders"""
    print(f"Starting no-letter reminder processing at {datetime.now(timezone.utc)} (UTC)")
    
    try:
        # Create Flask app context
        app = create_app()
        
        # Configure Flask for URL generation outside request context (needed for cron)
        site_domain = os.getenv('SITE_DOMAIN', 'https://letterforlater.com')
        if site_domain.startswith('https://'):
            server_name = site_domain.replace('https://', '').replace('http://', '').split('/')[0]
            app.config['SERVER_NAME'] = server_name
            app.config['PREFERRED_URL_SCHEME'] = 'https'
        elif site_domain.startswith('http://'):
            server_name = site_domain.replace('http://', '').split('/')[0]
            app.config['SERVER_NAME'] = server_name
            app.config['PREFERRED_URL_SCHEME'] = 'http'
        else:
            # Default to letterforlater.com
            app.config['SERVER_NAME'] = 'letterforlater.com'
            app.config['PREFERRED_URL_SCHEME'] = 'https'
        
        app.config['APPLICATION_ROOT'] = '/'
        
        with app.app_context():
            # Send reminders
            total_sent = send_reminders()
            
            # Commit all changes
            try:
                db.session.commit()
                print(f"✓ Successfully processed reminders ({total_sent} total reminders sent)")
            except Exception as e:
                db.session.rollback()
                print(f"✗ Error committing changes: {str(e)}")
                import traceback
                traceback.print_exc()
                
    except Exception as e:
        print(f"Error in main function: {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
