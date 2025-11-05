#!/usr/bin/env python3
"""
Check Zoho Mail SMTP status by attempting to send a test email.
This will show if the rate limit is still active.
"""

import sys
from website import create_app, mail
from flask_mail import Message
import os


def test_zoho_smtp():
    """Test if Zoho SMTP is working"""
    app = create_app()
    
    with app.app_context():
        print("="*60)
        print("TESTING ZOHO MAIL SMTP STATUS")
        print("="*60)
        
        # Get test email from environment or use a safe test
        test_email = os.getenv('TEST_EMAIL', 'test@example.com')
        
        print(f"\nAttempting to send test email to: {test_email}")
        print("(This will show if Zoho is still rate limiting)")
        
        try:
            msg = Message(
                'Zoho SMTP Test - LetterForLater',
                recipients=[test_email],
                sender=os.getenv('MAIL_USERNAME', 'noreply@letterforlater.com'),
                body='This is a test email to check Zoho SMTP status.'
            )
            
            # Try to send (with short timeout)
            mail.send(msg)
            print("\n✅ SUCCESS: Zoho SMTP is working!")
            print("   Rate limit has been lifted.")
            print("   Emails should work normally now.")
            
        except Exception as e:
            error_str = str(e).lower()
            
            if '550' in error_str or '5.4.6' in error_str or 'unusual sending' in error_str:
                print("\n❌ RATE LIMITED: Zoho is still blocking emails")
                print(f"   Error: {str(e)}")
                print("\n   Status: Rate limit is ACTIVE")
                print("   Action: Wait 1-2 hours for the limit to reset")
                print("   Zoho usually blocks for 1-2 hours after detecting spam")
                
            elif 'authentication' in error_str or '535' in error_str:
                print("\n⚠️  AUTHENTICATION ERROR")
                print(f"   Error: {str(e)}")
                print("   This is not a rate limit - check your SMTP credentials")
                
            elif 'timeout' in error_str or 'connection' in error_str:
                print("\n⚠️  CONNECTION ERROR")
                print(f"   Error: {str(e)}")
                print("   Check your network connection or Zoho SMTP server")
                
            else:
                print(f"\n⚠️  ERROR: {str(e)}")
                print("   Check the error message above")
        
        print("\n" + "="*60)
        print("Note: Zoho Mail rate limits typically reset after 1-2 hours")
        print("="*60)


def check_zoho_account():
    """Provide instructions for checking Zoho account"""
    print("\n" + "="*60)
    print("HOW TO CHECK ZOHO MAIL STATUS")
    print("="*60)
    print("\n1. Log into Zoho Mail Admin Console:")
    print("   https://mailadmin.zoho.eu/ (for .eu domain)")
    print("   or https://mailadmin.zoho.com/ (for .com domain)")
    print("\n2. Check Activity Logs:")
    print("   - Go to Reports > Mail Activity")
    print("   - Look for failed sends or rate limit warnings")
    print("\n3. Check Sending Limits:")
    print("   - Go to Settings > Mail Settings")
    print("   - Check your sending quota/limits")
    print("\n4. Contact Zoho Support:")
    print("   - If rate limit persists > 2 hours")
    print("   - They can manually lift restrictions")
    print("\n" + "="*60)


def main():
    import argparse
    parser = argparse.ArgumentParser(description='Check Zoho Mail SMTP status')
    parser.add_argument('--test', action='store_true', help='Test SMTP by sending email')
    parser.add_argument('--info', action='store_true', help='Show info on checking Zoho account')
    parser.add_argument('--email', type=str, help='Email address to test with')
    
    args = parser.parse_args()
    
    if args.email:
        os.environ['TEST_EMAIL'] = args.email
    
    if args.info:
        check_zoho_account()
    elif args.test:
        test_zoho_smtp()
    else:
        # Default: run both
        test_zoho_smtp()
        check_zoho_account()


if __name__ == "__main__":
    main()

