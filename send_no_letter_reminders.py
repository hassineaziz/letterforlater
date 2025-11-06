#!/usr/bin/env python3
"""
Script to send reminders to:
1. Users who created accounts but haven't written any letters
2. Users who have draft letters but haven't finished them
3. Users who have created letters (to encourage upgrades and more usage)

Reminder schedule:
- First reminder: 2 days after account/draft creation
- Second reminder: 7 days after account/draft creation
- Weekly reminders: Every 7 days after the last reminder sent (for no letters/drafts)
- Pricing reminders: Every 14 days after first letter creation (for users with letters)

This can be run by a cron job (e.g., daily) to process reminders.
"""

import sys
import os
from datetime import datetime, timedelta, timezone

# Add the project directory to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from website import create_app, db, mail
from website.models import User, Letter
from website.email_rate_limit import safe_send_email
from flask_mail import Message
from flask import render_template, url_for


def send_pricing_reminder(user):
    """Send pricing/upsell reminder to users with letters (every 14 days)"""
    try:
        dashboard_url = os.getenv('SITE_DOMAIN', 'https://letterforlater.com').rstrip('/')
        pricing_url = f"{dashboard_url}/pricing"
        
        # Count non-draft letters
        letter_count = Letter.query.filter(
            Letter.user_id == user.id,
            Letter.status != 'draft'
        ).count()
        
        if letter_count == 0:
            return False  # No letters to count
        
        msg = Message(
            'Unlock Premium Features - LetterForLater',
            recipients=[user.email],
            sender=os.getenv('MAIL_USERNAME', 'support@letterforlater.com')
        )
        
        # Render HTML template
        msg.html = render_template('emails/pricing_reminder.html',
            user_name=f"{user.first_name} {user.last_name}",
            user_email=user.email,
            dashboard_url=dashboard_url,
            pricing_url=pricing_url,
            letter_count=letter_count
        )
        
        # Render text template
        msg.body = render_template('emails/pricing_reminder.txt',
            user_name=f"{user.first_name} {user.last_name}",
            user_email=user.email,
            dashboard_url=dashboard_url,
            pricing_url=pricing_url,
            letter_count=letter_count
        )
        
        safe_send_email(msg, email_type='pricing_reminder')
        user.last_pricing_reminder_sent_at = datetime.now(timezone.utc)
        db.session.commit()
        print(f"✓ Sent pricing reminder to {user.email} ({letter_count} letters)")
        return True
        
    except Exception as e:
        print(f"✗ Error sending pricing reminder to {user.email}: {str(e)}")
        db.session.rollback()
        return False


def send_first_draft_reminder(user, letter):
    """Send first reminder for draft letter (2 days after draft creation)"""
    try:
        dashboard_url = os.getenv('SITE_DOMAIN', 'https://letterforlater.com').rstrip('/')
        edit_url = f"{dashboard_url}/add-letter?letter_id={letter.id}"
        
        # Get decrypted title
        letter_title = letter.decrypted_title or "Untitled Letter"
        days_since_draft = (datetime.now(timezone.utc) - letter.created_date).days
        
        msg = Message(
            'Continue Where You Left Off',
            recipients=[user.email],
            sender=os.getenv('MAIL_USERNAME', 'support@letterforlater.com')
        )
        
        # Render HTML template
        msg.html = render_template('emails/first_draft_reminder.html',
            user_name=f"{user.first_name} {user.last_name}",
            user_email=user.email,
            dashboard_url=dashboard_url,
            edit_url=edit_url,
            letter_title=letter_title,
            days_since_draft=days_since_draft
        )
        
        # Render text template
        msg.body = render_template('emails/first_draft_reminder.txt',
            user_name=f"{user.first_name} {user.last_name}",
            user_email=user.email,
            dashboard_url=dashboard_url,
            edit_url=edit_url,
            letter_title=letter_title,
            days_since_draft=days_since_draft
        )
        
        safe_send_email(msg, email_type='draft_reminder')
        letter.last_draft_reminder_sent_at = datetime.now(timezone.utc)
        db.session.commit()
        print(f"✓ Sent first draft reminder to {user.email} for letter {letter.id}")
        return True
        
    except Exception as e:
        print(f"✗ Error sending first draft reminder to {user.email} for letter {letter.id}: {str(e)}")
        db.session.rollback()
        return False


def send_weekly_draft_reminder(user, letter):
    """Send weekly reminder for draft letter"""
    try:
        dashboard_url = os.getenv('SITE_DOMAIN', 'https://letterforlater.com').rstrip('/')
        edit_url = f"{dashboard_url}/add-letter?letter_id={letter.id}"
        
        # Get decrypted title
        letter_title = letter.decrypted_title or "Untitled Letter"
        days_since_draft = (datetime.now(timezone.utc) - letter.created_date).days
        
        msg = Message(
            "Finish Your Letter - Don't Leave It Unfinished",
            recipients=[user.email],
            sender=os.getenv('MAIL_USERNAME', 'support@letterforlater.com')
        )
        
        # Render HTML template
        msg.html = render_template('emails/weekly_draft_reminder.html',
            user_name=f"{user.first_name} {user.last_name}",
            user_email=user.email,
            dashboard_url=dashboard_url,
            edit_url=edit_url,
            letter_title=letter_title,
            days_since_draft=days_since_draft
        )
        
        # Render text template
        msg.body = render_template('emails/weekly_draft_reminder.txt',
            user_name=f"{user.first_name} {user.last_name}",
            user_email=user.email,
            dashboard_url=dashboard_url,
            edit_url=edit_url,
            letter_title=letter_title,
            days_since_draft=days_since_draft
        )
        
        safe_send_email(msg, email_type='draft_reminder')
        letter.last_draft_reminder_sent_at = datetime.now(timezone.utc)
        db.session.commit()
        print(f"✓ Sent weekly draft reminder to {user.email} for letter {letter.id}")
        return True
        
    except Exception as e:
        print(f"✗ Error sending weekly draft reminder to {user.email} for letter {letter.id}: {str(e)}")
        db.session.rollback()
        return False


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
        
        safe_send_email(msg, email_type='no_letter_reminder')
        user.last_no_letter_reminder_sent_at = datetime.now(timezone.utc)
        db.session.commit()
        print(f"✓ Sent first reminder to {user.email}")
        return True
        
    except Exception as e:
        print(f"✗ Error sending first reminder to {user.email}: {str(e)}")
        db.session.rollback()
        return False


def send_weekly_reminder(user):
    """Send weekly reminder"""
    try:
        dashboard_url = os.getenv('SITE_DOMAIN', 'https://letterforlater.com').rstrip('/')
        
        # Calculate days since signup
        days_since_signup = (datetime.now(timezone.utc) - user.created_date).days
        
        msg = Message(
            "Don't Forget - Create Your First Letter",
            recipients=[user.email],
            sender=os.getenv('MAIL_USERNAME', 'support@letterforlater.com')
        )
        
        # Render HTML template
        msg.html = render_template('emails/weekly_letter_reminder.html',
            user_name=f"{user.first_name} {user.last_name}",
            user_email=user.email,
            dashboard_url=dashboard_url,
            days_since_signup=days_since_signup
        )
        
        # Render text template
        msg.body = render_template('emails/weekly_letter_reminder.txt',
            user_name=f"{user.first_name} {user.last_name}",
            user_email=user.email,
            dashboard_url=dashboard_url,
            days_since_signup=days_since_signup
        )
        
        safe_send_email(msg, email_type='no_letter_reminder')
        user.last_no_letter_reminder_sent_at = datetime.now(timezone.utc)
        db.session.commit()
        print(f"✓ Sent weekly reminder to {user.email}")
        return True
        
    except Exception as e:
        print(f"✗ Error sending weekly reminder to {user.email}: {str(e)}")
        db.session.rollback()
        return False


def send_reminders():
    """Send reminders to users without letters, users with draft letters, and users with letters (pricing)"""
    now = datetime.now(timezone.utc)
    print(f"Checking for users needing reminders at {now} (UTC)")
    
    # Get all active users
    active_users = User.query.filter(User.is_active == True).all()
    
    first_reminder_count = 0
    weekly_reminder_count = 0
    first_draft_reminder_count = 0
    weekly_draft_reminder_count = 0
    pricing_reminder_count = 0
    
    # First, handle users with draft letters
    draft_letters = Letter.query.filter(Letter.status == 'draft').all()
    
    for letter in draft_letters:
        # Skip if letter's user is not active
        user = User.query.get(letter.user_id)
        if not user or not user.is_active:
            continue
        
        days_since_draft = (now - letter.created_date).days
        
        # First draft reminder: 2 days after draft creation (and no reminder sent yet)
        if days_since_draft >= 2 and letter.last_draft_reminder_sent_at is None:
            if send_first_draft_reminder(user, letter):
                first_draft_reminder_count += 1
            continue
        
        # Weekly draft reminders: 7 days after draft creation, then every 7 days after last reminder
        if days_since_draft >= 7:
            if letter.last_draft_reminder_sent_at is None:
                # Should have sent first reminder but didn't - send first reminder now
                if send_first_draft_reminder(user, letter):
                    first_draft_reminder_count += 1
                    continue
            
            # Check if it's time for weekly reminder (7 days since last reminder)
            days_since_last_reminder = (now - letter.last_draft_reminder_sent_at).days
            if days_since_last_reminder >= 7:
                if send_weekly_draft_reminder(user, letter):
                    weekly_draft_reminder_count += 1
    
    # Then, handle users without any letters
    for user in active_users:
        # Skip if user has any letters (non-draft)
        letter_count = Letter.query.filter(
            Letter.user_id == user.id,
            Letter.status != 'draft'
        ).count()
        if letter_count > 0:
            continue  # User has completed letters, skip
        
        # Check if user has draft letters (already handled above)
        has_draft = Letter.query.filter(
            Letter.user_id == user.id,
            Letter.status == 'draft'
        ).count() > 0
        if has_draft:
            continue  # User has draft letters, already handled above
        
        days_since_signup = (now - user.created_date).days
        
        # First reminder: 2 days after signup (and no reminder sent yet)
        if days_since_signup >= 2 and user.last_no_letter_reminder_sent_at is None:
            if send_first_reminder(user):
                first_reminder_count += 1
            continue
        
        # Weekly reminders: 7 days after signup, then every 7 days after last reminder
        if days_since_signup >= 7:
            if user.last_no_letter_reminder_sent_at is None:
                # Should have sent first reminder but didn't - send first reminder now
                if send_first_reminder(user):
                    first_reminder_count += 1
                    continue
            
            # Check if it's time for weekly reminder (7 days since last reminder)
            # This handles both the second reminder at day 7 and subsequent weekly reminders
            days_since_last_reminder = (now - user.last_no_letter_reminder_sent_at).days
            if days_since_last_reminder >= 7:
                if send_weekly_reminder(user):
                    weekly_reminder_count += 1
    
    # Finally, handle pricing reminders for users with letters (every 14 days)
    # Only send to free plan users who have at least one non-draft letter
    for user in active_users:
        # Skip if user is already on premium or lifetime
        if user.plan and user.plan != 'free':
            continue
        
        # Check if user has at least one non-draft letter
        letter_count = Letter.query.filter(
            Letter.user_id == user.id,
            Letter.status != 'draft'
        ).count()
        
        if letter_count == 0:
            continue  # No letters, skip
        
        # Check if we need to send pricing reminder
        # First pricing reminder: 14 days after first letter creation
        first_letter = Letter.query.filter(
            Letter.user_id == user.id,
            Letter.status != 'draft'
        ).order_by(Letter.created_date.asc()).first()
        
        if not first_letter:
            continue
        
        days_since_first_letter = (now - first_letter.created_date).days
        
        # First pricing reminder: 14 days after first letter creation (and no reminder sent yet)
        if days_since_first_letter >= 14 and user.last_pricing_reminder_sent_at is None:
            if send_pricing_reminder(user):
                pricing_reminder_count += 1
            continue
        
        # Subsequent pricing reminders: Every 14 days after last reminder
        if days_since_first_letter >= 14 and user.last_pricing_reminder_sent_at:
            days_since_last_reminder = (now - user.last_pricing_reminder_sent_at).days
            if days_since_last_reminder >= 14:
                if send_pricing_reminder(user):
                    pricing_reminder_count += 1
    
    total_count = first_reminder_count + weekly_reminder_count + first_draft_reminder_count + weekly_draft_reminder_count + pricing_reminder_count
    print(f"✓ Sent {first_reminder_count} first reminders and {weekly_reminder_count} weekly reminders")
    print(f"✓ Sent {first_draft_reminder_count} first draft reminders and {weekly_draft_reminder_count} weekly draft reminders")
    print(f"✓ Sent {pricing_reminder_count} pricing reminders")
    return total_count


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

