#!/usr/bin/env python3
"""
Script to send scheduled letters and weekly reminders for unregistered recipients.
This can be run by a cron job (e.g., every hour) to process scheduled letters and reminders.
"""

import sys
import os
from datetime import datetime, timedelta, timezone

# Add the project directory to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from website import create_app
from website.models import Letter, DeathVerification, RecipientInvite
from website.views import send_letter_invite
from website.email_rate_limit import safe_send_email
from flask_mail import Message
from flask import render_template
import os

def send_weekly_reminders():
    """Send weekly reminders to recipients who haven't registered yet"""
    from website import db, mail
    from flask import url_for
    
    print("Checking for weekly reminders...")
    
    # Find invites that need reminders
    invites_needing_reminders = RecipientInvite.query.filter(
        RecipientInvite.registered_at.is_(None),
        RecipientInvite.last_reminder_sent_at < datetime.now(timezone.utc) - timedelta(days=7)
    ).all()
    
    if not invites_needing_reminders:
        print("No reminders needed")
        return
    
    print(f"Found {len(invites_needing_reminders)} invites needing reminders")
    
    reminder_count = 0
    for invite in invites_needing_reminders:
        try:
            # Build invite URL (works with SERVER_NAME configured in main())
            invite_url = url_for('auth.sign_up_with_invite', token=invite.invite_token, _external=True)
            
            # Create reminder email
            msg = Message(
                f'Friendly Reminder: You have a letter waiting from {invite.letter.author.first_name} {invite.letter.author.last_name}',
                recipients=[invite.recipient_email],
                sender=os.getenv('MAIL_USERNAME', 'support@letterforlater.com')
            )
            
            # Render HTML template
            # Decrypt letter title for email
            letter_title = invite.letter.decrypted_title
            
            msg.html = render_template('emails/letter_reminder.html',
                recipient_name=invite.recipient_name,
                author_name=f"{invite.letter.author.first_name} {invite.letter.author.last_name}",
                sent_date=invite.sent_at.strftime('%B %d, %Y'),
                letter_title=letter_title,
                invite_url=invite_url
            )
            
            # Render text template
            msg.body = render_template('emails/letter_reminder.txt',
                recipient_name=invite.recipient_name,
                author_name=f"{invite.letter.author.first_name} {invite.letter.author.last_name}",
                sent_date=invite.sent_at.strftime('%B %d, %Y'),
                letter_title=letter_title,
                invite_url=invite_url
            )
            
            # Send the reminder with spam checking
            safe_send_email(msg, email_type='letter_reminder')
            
            # Update the reminder timestamp
            invite.last_reminder_sent_at = datetime.now(timezone.utc)
            reminder_count += 1
            
            print(f"Sent reminder for invite {invite.id} to {invite.recipient_email}")
            
        except Exception as e:
            print(f"Error sending reminder for invite {invite.id}: {str(e)}")
    
    try:
        db.session.commit()
        print(f"Successfully sent {reminder_count} reminders")
    except Exception as e:
        db.session.rollback()
        print(f"Error committing reminder updates: {str(e)}")

def main():
    """Main function to send scheduled letters and reminders"""
    print(f"Starting scheduled letter processing at {datetime.now(timezone.utc)} (UTC)")
    
    try:
        # Create Flask app context
        app = create_app()
        
        # Configure Flask for URL generation outside request context (needed for cron)
        # These settings allow url_for() to work without an active HTTP request
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
            # Process scheduled letters
            now = datetime.now(timezone.utc)
            print(f"Current UTC time: {now}")
            
            # Find letters that are scheduled and due for delivery
            scheduled_letters = Letter.query.filter(
                Letter.status == 'scheduled',
                Letter.delivery_status.in_(['scheduled', 'pending']),
                Letter.delivery_date <= now
            ).all()
            
            sent_count = 0
            failed_count = 0
            
            if scheduled_letters:
                print(f"Found {len(scheduled_letters)} scheduled letters to process")
                
                for letter in scheduled_letters:
                    try:
                        print(f"Processing letter {letter.id} - Scheduled for: {letter.delivery_date}, Recipient: {letter.recipient_email}")
                        success = send_letter_invite(
                            letter, 
                            letter.recipient_email, 
                            letter.recipient_name, 
                            f"{letter.author.first_name} {letter.author.last_name}"
                        )
                        if success:
                            letter.status = 'delivered'
                            letter.delivery_status = 'delivered'
                            letter.delivery_date = datetime.now(timezone.utc)
                            sent_count += 1
                            print(f"✓ Successfully sent scheduled letter {letter.id} to {letter.recipient_email}")
                        else:
                            failed_count += 1
                            print(f"✗ Failed to send scheduled letter {letter.id} to {letter.recipient_email} - will retry on next run")
                    except Exception as e:
                        failed_count += 1
                        print(f"✗ Error sending scheduled letter {letter.id}: {str(e)}")
                        import traceback
                        traceback.print_exc()
            else:
                print("No scheduled letters to process")
            
            # Send weekly reminders
            send_weekly_reminders()
            
            # Commit all changes
            from website import db
            try:
                db.session.commit()
                print(f"✓ Successfully processed {sent_count} letters ({failed_count} failed), sent reminders")
            except Exception as e:
                db.session.rollback()
                print(f"✗ Error committing changes: {str(e)}")
                import traceback
                traceback.print_exc()
                
    except Exception as e:
        print(f"Error in main function: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    main()



