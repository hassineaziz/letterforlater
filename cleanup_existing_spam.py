#!/usr/bin/env python3
"""
Emergency script to clean up existing spam accounts.
Deletes accounts with random email/name patterns and blocks their IPs.
"""

import sys
from website import create_app, db
from website.models import User, TrustedContact, Letter, NewsletterSubscriber
from website.blocking import block_ip_subnet
from website.spam_detection import is_random_email, is_random_name
from datetime import datetime, timedelta, timezone
from collections import Counter


def delete_user_and_related_data(user):
    """Delete a user and all their related data"""
    try:
        # Delete trusted contacts
        TrustedContact.query.filter_by(user_id=user.id).delete()
        
        # Delete letters
        Letter.query.filter_by(user_id=user.id).delete()
        
        # Delete newsletter subscription
        NewsletterSubscriber.query.filter_by(email=user.email).delete()
        
        # Delete the user
        db.session.delete(user)
        return True
    except Exception as e:
        print(f"Error deleting user {user.id}: {e}")
        return False


def cleanup_spam_accounts():
    """Find and delete spam accounts based on patterns"""
    app = create_app()
    
    with app.app_context():
        print("🔍 Scanning for spam accounts...")
        print("="*60)
        
        # Get all users (or recent users if you want to limit)
        # For emergency cleanup, check all users
        all_users = User.query.all()
        
        spam_users = []
        spam_ips = Counter()
        
        for user in all_users:
            # Check for spam patterns
            if is_random_email(user.email) or is_random_name(user.first_name) or is_random_name(user.last_name):
                spam_users.append(user)
                if user.registration_ip:
                    spam_ips[user.registration_ip] += 1
        
        print(f"\n📊 Found {len(spam_users)} spam accounts")
        print(f"📊 Found {len(spam_ips)} unique spam IPs")
        print("\n" + "="*60)
        
        if not spam_users:
            print("✅ No spam accounts found!")
            return
        
        # Show top spam IPs
        print("\n🔴 Top 10 Spam IPs:")
        for ip, count in spam_ips.most_common(10):
            print(f"   {ip}: {count} accounts")
        
        # Ask for confirmation
        print(f"\n⚠️  About to delete {len(spam_users)} spam accounts and block {len(spam_ips)} IPs")
        response = input("Continue? (yes/no): ")
        
        if response.lower() != 'yes':
            print("❌ Cancelled")
            return
        
        # Delete spam accounts
        deleted_count = 0
        for user in spam_users:
            if delete_user_and_related_data(user):
                deleted_count += 1
                if deleted_count % 50 == 0:
                    print(f"   Deleted {deleted_count}/{len(spam_users)} accounts...")
        
        db.session.commit()
        print(f"\n✅ Deleted {deleted_count} spam accounts")
        
        # Block all spam IPs
        blocked_count = 0
        for ip, count in spam_ips.items():
            try:
                block_ip_subnet(ip, reason=f"Spam cleanup: {count} spam accounts deleted", blocked_by_user_id=None)
                blocked_count += 1
            except Exception as e:
                print(f"   Error blocking IP {ip}: {e}")
        
        print(f"✅ Blocked {blocked_count} spam IPs (entire subnets)")
        print(f"\n🎯 Cleanup complete! Deleted {deleted_count} accounts, blocked {blocked_count} IPs")


if __name__ == '__main__':
    cleanup_spam_accounts()

