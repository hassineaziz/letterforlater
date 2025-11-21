#!/usr/bin/env python3
"""
Script to send Black Friday sale emails to all free users
Usage: python send_black_friday_emails.py
"""

import sys
import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Add the project root to the path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from website import create_app, db
from website.models import User
from website.email_service import send_black_friday_sale_email

def send_black_friday_emails():
    """Send Black Friday sale emails to all free users"""
    app = create_app()
    
    with app.app_context():
        # Verify email configuration is loaded
        mail_server = os.getenv('MAIL_SERVER', 'Not set')
        mail_username = os.getenv('MAIL_USERNAME', 'Not set')
        mail_password = os.getenv('MAIL_PASSWORD', 'Not set')
        
        print("="*60)
        print("EMAIL CONFIGURATION CHECK")
        print("="*60)
        print(f"MAIL_SERVER: {mail_server}")
        print(f"MAIL_USERNAME: {mail_username}")
        print(f"MAIL_PASSWORD: {'***' if mail_password and mail_password != 'Not set' else '❌ NOT SET (This will cause authentication errors!)'}")
        print("="*60)
        
        if not mail_password or mail_password == 'Not set':
            print("\n⚠️  WARNING: MAIL_PASSWORD is not set in your .env file!")
            print("   This will cause authentication errors when sending emails.")
            print("   Please add your Zoho Mail password to the .env file:")
            print("   MAIL_PASSWORD=your_zoho_password_here\n")
            response = input("Continue anyway? (yes/no): ")
            if response.lower() != 'yes':
                print("Cancelled. Please set MAIL_PASSWORD in your .env file first.")
                return
        
        print()
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
        
        # Send emails with delays to avoid rate limiting
        success_count = 0
        failed_count = 0
        import time
        
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
            except KeyboardInterrupt:
                print("\n\n⚠️  Interrupted by user. Stopping email sending...")
                break
            except Exception as e:
                failed_count += 1
                print(f"❌ Error: {str(e)}")
            
            # Add delay between emails to avoid rate limiting (2 seconds)
            if i < total_users:
                time.sleep(2)
        
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

