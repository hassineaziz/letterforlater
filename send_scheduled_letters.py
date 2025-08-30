#!/usr/bin/env python3
"""
Script to send scheduled letters that are waiting for their delay period to expire.
This can be run by a cron job (e.g., every hour) to process scheduled letters.
"""

import sys
import os
from datetime import datetime, timedelta

# Add the project directory to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from website import create_app
from website.models import Letter
from website.views import send_scheduled_letters_task
from flask_mail import Message

def main():
    """Main function to send scheduled letters"""
    print(f"Starting scheduled letter processing at {datetime.now()}")
    
    try:
        # Create Flask app context
        app = create_app()
        
        with app.app_context():
            # Find letters that are scheduled and past their delivery date
            now = datetime.now()
            scheduled_letters = Letter.query.filter(
                Letter.status == 'scheduled',
                Letter.delivery_status == 'scheduled',
                Letter.delivery_date <= now,
                Letter.delivery_type == 'death_verification'
            ).all()
            
            if not scheduled_letters:
                print("No scheduled letters to process")
                return
            
            print(f"Found {len(scheduled_letters)} scheduled letters to process")
            
            sent_count = 0
            for letter in scheduled_letters:
                try:
                    from website import mail
                    msg = Message(
                        f'Legacy Letter: {letter.title}',
                        recipients=[letter.recipient_email]
                    )
                    msg.body = f"""
Dear {letter.recipient_name},

This is a legacy letter from {letter.author.first_name} {letter.author.last_name}.

{letter.content}

---
This letter was delivered through the Legacy Letter service.
"""
                    mail.send(msg)
                    letter.status = 'delivered'
                    letter.delivery_status = 'delivered'
                    sent_count += 1
                    print(f"Sent scheduled letter {letter.id} to {letter.recipient_email}")
                except Exception as e:
                    print(f"Error sending scheduled letter {letter.id}: {str(e)}")
                    # Keep the letter as scheduled if there's an error
            
            # Commit all changes
            from website import db
            try:
                db.session.commit()
                print(f"Successfully processed {sent_count} out of {len(scheduled_letters)} letters")
            except Exception as e:
                db.session.rollback()
                print(f"Error committing changes: {str(e)}")
                
    except Exception as e:
        print(f"Error in main function: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    main()



