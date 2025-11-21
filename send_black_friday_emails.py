#!/usr/bin/env python3
"""
Script to send Black Friday sale emails to all free users
Usage: python send_black_friday_emails.py
"""

import sys
import os

# Add the project root to the path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from website import create_app, db
from website.models import User
from website.email_service import send_black_friday_sale_email

def send_black_friday_emails():
    """Send Black Friday sale emails to all free users"""
    app = create_app()
    
    with app.app_context():
        # Get all free users (users with plan='free' or plan=None)
        free_users = User.query.filter(
            (User.plan == 'free') | (User.plan.is_(None))
        ).filter(
            User.is_active == True
        ).all()
        
        total_users = len(free_users)
        print(f"Found {total_users} free users to send emails to")
        
        if total_users == 0:
            print("No free users found. Exiting.")
            return
        
        # Ask for confirmation
        response = input(f"\nAre you sure you want to send Black Friday sale emails to {total_users} users? (yes/no): ")
        if response.lower() != 'yes':
            print("Cancelled.")
            return
        
        # Send emails
        success_count = 0
        failed_count = 0
        
        for i, user in enumerate(free_users, 1):
            print(f"\n[{i}/{total_users}] Sending to {user.email}...")
            
            try:
                success = send_black_friday_sale_email(user)
                if success:
                    success_count += 1
                    print(f"✅ Sent successfully")
                else:
                    failed_count += 1
                    print(f"❌ Failed to send")
            except Exception as e:
                failed_count += 1
                print(f"❌ Error: {str(e)}")
        
        # Summary
        print("\n" + "="*50)
        print("EMAIL SENDING SUMMARY")
        print("="*50)
        print(f"Total users: {total_users}")
        print(f"✅ Successfully sent: {success_count}")
        print(f"❌ Failed: {failed_count}")
        print("="*50)

if __name__ == '__main__':
    send_black_friday_emails()

