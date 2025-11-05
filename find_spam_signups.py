#!/usr/bin/env python3
"""
Find and block spam signups.
Usage:
    python find_spam_signups.py --auto-block  # Auto-block IPs with spam signups
    python find_spam_signups.py --list         # Just list spam IPs
"""

import sys
import argparse
from website import create_app, db
from website.models import User
from website.blocking import block_ip, get_blocked_ips
from datetime import datetime, timedelta, timezone


def find_spam_signups():
    """Find IPs with suspicious signup patterns"""
    app = create_app()
    
    with app.app_context():
        # Find IPs with multiple signups in short time
        one_hour_ago = datetime.now(timezone.utc) - timedelta(hours=1)
        five_minutes_ago = datetime.now(timezone.utc) - timedelta(minutes=5)
        
        # Get all signups in last hour
        recent_signups = User.query.filter(
            User.created_date >= one_hour_ago
        ).all()
        
        # Group by IP
        ip_signups = {}
        for user in recent_signups:
            if user.registration_ip:
                if user.registration_ip not in ip_signups:
                    ip_signups[user.registration_ip] = []
                ip_signups[user.registration_ip].append(user)
        
        spam_ips = []
        for ip, users in ip_signups.items():
            # Check rapid signups (5 minutes)
            rapid = [u for u in users if u.created_date >= five_minutes_ago]
            
            if len(rapid) >= 3:
                spam_ips.append({
                    'ip': ip,
                    'rapid_count': len(rapid),
                    'total_count': len(users),
                    'users': users,
                    'severity': 'CRITICAL'
                })
            elif len(users) >= 10:
                spam_ips.append({
                    'ip': ip,
                    'rapid_count': len(rapid),
                    'total_count': len(users),
                    'users': users,
                    'severity': 'HIGH'
                })
            elif len(users) >= 5:
                spam_ips.append({
                    'ip': ip,
                    'rapid_count': len(rapid),
                    'total_count': len(users),
                    'users': users,
                    'severity': 'MEDIUM'
                })
        
        return spam_ips


def main():
    parser = argparse.ArgumentParser(description='Find and block spam signups')
    parser.add_argument('--auto-block', action='store_true', help='Automatically block spam IPs')
    parser.add_argument('--list', action='store_true', help='List spam IPs without blocking')
    parser.add_argument('--delete-users', action='store_true', help='Delete spam user accounts')
    
    args = parser.parse_args()
    
    spam_ips = find_spam_signups()
    
    if not spam_ips:
        print("✅ No spam signups detected!")
        return
    
    print("\n" + "="*60)
    print(f"🚨 FOUND {len(spam_ips)} SPAM IP(S)")
    print("="*60)
    
    for item in spam_ips:
        ip = item['ip']
        print(f"\nIP: {ip}")
        print(f"  Severity: {item['severity']}")
        print(f"  Rapid signups (5 min): {item['rapid_count']}")
        print(f"  Total signups (1 hour): {item['total_count']}")
        print(f"  User emails:")
        for user in item['users'][:5]:  # Show first 5
            print(f"    - {user.email} ({user.created_date})")
        if len(item['users']) > 5:
            print(f"    ... and {len(item['users']) - 5} more")
    
    if args.list:
        return
    
    if args.auto_block:
        print("\n" + "="*60)
        print("AUTO-BLOCKING SPAM IPs...")
        print("="*60)
        
        for item in spam_ips:
            ip = item['ip']
            reason = f"Spam signups: {item['rapid_count']} rapid, {item['total_count']} total in 1 hour"
            
            # Check if already blocked
            from website.blocking import is_ip_blocked
            already_blocked, _ = is_ip_blocked(ip)
            
            if already_blocked:
                print(f"  ✓ {ip} already blocked")
            else:
                success, message, _ = block_ip(ip, reason=reason)
                if success:
                    print(f"  ✅ {ip} blocked: {message}")
                else:
                    print(f"  ❌ {ip} failed: {message}")
            
            # Delete spam users if requested
            if args.delete_users:
                deleted = 0
                for user in item['users']:
                    db.session.delete(user)
                    deleted += 1
                db.session.commit()
                print(f"  🗑️  Deleted {deleted} spam user accounts")
        
        print("\n✅ Auto-blocking complete!")


if __name__ == "__main__":
    main()

