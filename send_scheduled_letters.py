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
from flask_mail import Message

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
            # Build invite URL
            invite_url = f"https://letterforlater.com{url_for('auth.sign_up_with_invite', token=invite.invite_token)}"
            
            # Create reminder email
            msg = Message(
                f'Reminder: You have a letter waiting from {invite.letter.author.first_name} {invite.letter.author.last_name}',
                recipients=[invite.recipient_email]
            )
            
            body = f"""Dear {invite.recipient_name},

This is a friendly reminder that you have a special legacy letter waiting for you from {invite.letter.author.first_name} {invite.letter.author.last_name}.

The letter was sent to you on {invite.sent_at.strftime('%B %d, %Y')} and is ready to be read.

To access your letter, simply create a free account using the link below:

{invite_url}

This link is unique to you and will remain active. Once you create your account, you'll be able to read the letter and access any photos, videos, or audio recordings that were included.

If you have any questions or need assistance, please don't hesitate to reach out to our support team.

With warm regards,
The LetterForLater Team

---
This reminder was sent through LetterForLater.com
If you have already registered, please ignore this email.
"""
            
            msg.body = body
            
            # Send the reminder
            mail.send(msg)
            
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
    print(f"Starting scheduled letter processing at {datetime.now()}")
    
    try:
        # Create Flask app context
        app = create_app()
        
        with app.app_context():
            # Process scheduled letters
            now = datetime.now(timezone.utc)
            scheduled_letters = Letter.query.filter(
                Letter.status == 'scheduled',
                Letter.delivery_status.in_(['scheduled', 'pending']),
                Letter.delivery_date <= now
            ).all()
            
            sent_count = 0
            if scheduled_letters:
                print(f"Found {len(scheduled_letters)} scheduled letters to process")
                
                for letter in scheduled_letters:
                    try:
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
                            print(f"Sent scheduled letter {letter.id} to {letter.recipient_email}")
                        else:
                            print(f"Failed to send scheduled letter {letter.id} to {letter.recipient_email}")
                    except Exception as e:
                        print(f"Error sending scheduled letter {letter.id}: {str(e)}")
            else:
                print("No scheduled letters to process")
            
            # Send weekly reminders
            send_weekly_reminders()
            
            # Commit all changes
            from website import db
            try:
                db.session.commit()
                print(f"Successfully processed {sent_count} letters and sent reminders")
            except Exception as e:
                db.session.rollback()
                print(f"Error committing changes: {str(e)}")
                
    except Exception as e:
        print(f"Error in main function: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    main()



