#!/usr/bin/env python3
"""
Emergency script to stop emails from being sent.
Blocks email sending for spam IPs and prevents new confirmation emails.
"""

import sys
from website import create_app, db
from website.models import User
from website.blocking import block_ip
from datetime import datetime, timedelta, timezone


def stop_emails_for_spam_ips():
    """Block all spam IPs to prevent emails from being sent"""
    app = create_app()
    
    with app.app_context():
        # Find all IPs with multiple signups (spam)
        seven_days_ago = datetime.now(timezone.utc) - timedelta(days=7)
        
        recent_users = User.query.filter(
            User.created_date >= seven_days_ago
        ).all()
        
        # Group by IP
        ip_users = {}
        for user in recent_users:
            if user.registration_ip:
                if user.registration_ip not in ip_users:
                    ip_users[user.registration_ip] = []
                ip_users[user.registration_ip].append(user)
        
        # Block all IPs with 3+ signups
        spam_ips_to_block = []
        for ip, users in ip_users.items():
            if len(users) >= 3:
                spam_ips_to_block.append((ip, len(users)))
        
        print(f"\n🚨 BLOCKING {len(spam_ips_to_block)} SPAM IP(S) TO STOP EMAILS")
        print("="*60)
        
        blocked_count = 0
        for ip, count in spam_ips_to_block:
            # Check if already blocked
            from website.blocking import is_ip_blocked
            already_blocked, _ = is_ip_blocked(ip)
            
            if not already_blocked:
                success, message, _ = block_ip(ip, reason=f"Spam: {count} signups - blocking to prevent email spam")
                if success:
                    blocked_count += 1
                    print(f"  ✅ Blocked {ip} ({count} accounts) - Emails stopped")
                else:
                    print(f"  ⚠️  Failed to block {ip}: {message}")
            else:
                print(f"  ✓ {ip} already blocked")
        
        print(f"\n✅ Blocked {blocked_count} IP(s)")
        print("   Emails will NOT be sent to these IPs anymore!")


def main():
    print("="*60)
    print("EMERGENCY: STOP EMAILS FOR SPAM IPs")
    print("="*60)
    print("\nThis will block all spam IPs to prevent emails from being sent.")
    print("Already-created accounts won't trigger new emails.")
    
    stop_emails_for_spam_ips()
    
    print("\n" + "="*60)
    print("✅ DONE - Spam IPs blocked, emails stopped")
    print("="*60)
    print("\nNow run cleanup to delete accounts:")
    print("  python cleanup_spam_accounts.py --delete-all-from-ip 49.204.141.33")


if __name__ == "__main__":
    main()

