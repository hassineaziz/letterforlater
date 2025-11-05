#!/usr/bin/env python3
"""
AGGRESSIVE spam account cleanup script.
Finds and deletes spam accounts, blocks IPs.
Usage:
    python cleanup_spam_accounts.py --auto-cleanup  # Delete spam and block IPs
    python cleanup_spam_accounts.py --list           # Just list spam (dry run)
    python cleanup_spam_accounts.py --delete-all-from-ip 192.168.1.100  # Delete all from specific IP
"""

import sys
import argparse
from website import create_app, db
from website.models import User, TrustedContact, Letter, NewsletterSubscriber
from website.blocking import block_ip, get_blocked_ips
from datetime import datetime, timedelta, timezone
from collections import Counter


def find_spam_accounts():
    """Find all spam accounts based on patterns"""
    app = create_app()
    
    with app.app_context():
        # Find IPs with multiple signups
        one_hour_ago = datetime.now(timezone.utc) - timedelta(hours=1)
        one_day_ago = datetime.now(timezone.utc) - timedelta(days=1)
        
        # Get all recent signups
        recent_users = User.query.filter(
            User.created_date >= one_day_ago
        ).all()
        
        # Group by IP
        ip_users = {}
        for user in recent_users:
            if user.registration_ip:
                if user.registration_ip not in ip_users:
                    ip_users[user.registration_ip] = []
                ip_users[user.registration_ip].append(user)
        
        # Find spam IPs (multiple signups)
        spam_ips = {}
        for ip, users in ip_users.items():
            if len(users) >= 3:  # 3+ signups = spam
                spam_ips[ip] = {
                    'users': users,
                    'count': len(users),
                    'first_signup': min(u.created_date for u in users),
                    'last_signup': max(u.created_date for u in users),
                }
        
        return spam_ips


def delete_user_and_related_data(user):
    """Delete a user and all their related data"""
    deleted_items = {
        'user': 1,
        'letters': 0,
        'trusted_contacts': 0,
        'newsletter': 0
    }
    
    # Delete letters
    letters = Letter.query.filter_by(user_id=user.id).all()
    for letter in letters:
        db.session.delete(letter)
        deleted_items['letters'] += 1
    
    # Delete trusted contacts they created
    contacts = TrustedContact.query.filter_by(user_id=user.id).all()
    for contact in contacts:
        db.session.delete(contact)
        deleted_items['trusted_contacts'] += 1
    
    # Delete newsletter subscription
    newsletter = NewsletterSubscriber.query.filter_by(email=user.email).first()
    if newsletter:
        db.session.delete(newsletter)
        deleted_items['newsletter'] += 1
    
    # Delete the user
    db.session.delete(user)
    
    return deleted_items


def main():
    parser = argparse.ArgumentParser(description='AGGRESSIVE spam account cleanup')
    parser.add_argument('--auto-cleanup', action='store_true', help='Auto-delete spam and block IPs')
    parser.add_argument('--list', action='store_true', help='List spam accounts (dry run)')
    parser.add_argument('--delete-all-from-ip', type=str, help='Delete ALL accounts from specific IP')
    parser.add_argument('--min-signups', type=int, default=3, help='Minimum signups to consider spam (default: 3)')
    parser.add_argument('--block-threshold', type=int, default=5, help='Auto-block IPs with this many signups (default: 5)')
    
    args = parser.parse_args()
    
    app = create_app()
    
    with app.app_context():
        if args.delete_all_from_ip:
            print(f"\n🚨 DELETING ALL ACCOUNTS FROM IP: {args.delete_all_from_ip}")
            print("="*60)
            
            users_from_ip = User.query.filter_by(registration_ip=args.delete_all_from_ip).all()
            
            if not users_from_ip:
                print(f"No accounts found with IP {args.delete_all_from_ip}")
                return
            
            print(f"Found {len(users_from_ip)} account(s) from this IP")
            
            total_deleted = {'user': 0, 'letters': 0, 'trusted_contacts': 0, 'newsletter': 0}
            
            for user in users_from_ip:
                deleted = delete_user_and_related_data(user)
                for key, value in deleted.items():
                    total_deleted[key] += value
            
            db.session.commit()
            
            # Block the IP
            block_ip(args.delete_all_from_ip, reason=f"Spam cleanup: {len(users_from_ip)} accounts deleted")
            
            print(f"\n✅ Deleted {total_deleted['user']} users")
            print(f"   - {total_deleted['letters']} letters")
            print(f"   - {total_deleted['trusted_contacts']} trusted contacts")
            print(f"   - {total_deleted['newsletter']} newsletter subscriptions")
            print(f"✅ IP {args.delete_all_from_ip} blocked")
            return
        
        # Find spam accounts
        print("\n" + "="*60)
        print("SCANNING FOR SPAM ACCOUNTS...")
        print("="*60)
        
        spam_ips = find_spam_accounts()
        
        if not spam_ips:
            print("✅ No spam accounts detected!")
            return
        
        # Sort by count (most spam first)
        sorted_spam = sorted(spam_ips.items(), key=lambda x: x[1]['count'], reverse=True)
        
        total_spam_accounts = sum(item['count'] for _, item in spam_ips.items())
        
        print(f"\n🚨 FOUND {len(spam_ips)} SPAM IP(S) WITH {total_spam_accounts} TOTAL ACCOUNTS")
        print("="*60)
        
        for ip, data in sorted_spam:
            print(f"\nIP: {ip}")
            print(f"  Accounts: {data['count']}")
            print(f"  First signup: {data['first_signup']}")
            print(f"  Last signup: {data['last_signup']}")
            print(f"  Sample emails:")
            for user in data['users'][:5]:
                print(f"    - {user.email}")
            if len(data['users']) > 5:
                print(f"    ... and {len(data['users']) - 5} more")
        
        if args.list:
            print("\n" + "="*60)
            print("DRY RUN - No accounts deleted")
            print("Run with --auto-cleanup to delete and block")
            return
        
        if args.auto_cleanup:
            print("\n" + "="*60)
            print("🚨 AUTO-CLEANUP STARTING...")
            print("="*60)
            
            total_deleted = {'user': 0, 'letters': 0, 'trusted_contacts': 0, 'newsletter': 0}
            blocked_ips = []
            
            for ip, data in sorted_spam:
                print(f"\nProcessing IP: {ip} ({data['count']} accounts)...")
                
                # Delete all accounts from this IP
                for user in data['users']:
                    deleted = delete_user_and_related_data(user)
                    for key, value in deleted.items():
                        total_deleted[key] += value
                
                # Block IP if it meets threshold
                if data['count'] >= args.block_threshold:
                    success, message, _ = block_ip(ip, reason=f"Spam cleanup: {data['count']} spam accounts deleted")
                    if success:
                        blocked_ips.append(ip)
                        print(f"  ✅ Blocked IP: {ip}")
                
                db.session.commit()
                print(f"  ✅ Deleted {data['count']} accounts from {ip}")
            
            print("\n" + "="*60)
            print("✅ CLEANUP COMPLETE!")
            print("="*60)
            print(f"\nDeleted:")
            print(f"  - {total_deleted['user']} spam user accounts")
            print(f"  - {total_deleted['letters']} letters")
            print(f"  - {total_deleted['trusted_contacts']} trusted contacts")
            print(f"  - {total_deleted['newsletter']} newsletter subscriptions")
            print(f"\nBlocked {len(blocked_ips)} IP address(es):")
            for ip in blocked_ips:
                print(f"  - {ip}")
            
            print("\n🎯 Database cleaned!")
        else:
            print("\n⚠️  Run with --auto-cleanup to delete spam accounts")
            print("   Or use --delete-all-from-ip <IP> to clean specific IP")


if __name__ == "__main__":
    main()

