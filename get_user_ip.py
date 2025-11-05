#!/usr/bin/env python3
"""
Get IP address(es) for a user.
Shows registration IP, last login IP, and IPs from newsletter subscriptions.
Usage:
    python get_user_ip.py --user email@example.com
    python get_user_ip.py --user-id 123
    python get_user_ip.py --ip 192.168.1.1  # Find all users with this IP
"""

import sys
import argparse
from website import create_app, db
from website.models import User, NewsletterSubscriber
from website.blocking import get_client_ip


def get_user_ips(user):
    """Get all IP addresses associated with a user"""
    ips = []
    
    # Registration IP
    if user.registration_ip:
        ips.append({
            'ip': user.registration_ip,
            'source': 'Registration',
            'date': user.created_date
        })
    
    # Last login IP
    if user.last_login_ip:
        ips.append({
            'ip': user.last_login_ip,
            'source': 'Last Login',
            'date': None  # We don't track login dates yet
        })
    
    # Newsletter subscription IPs
    newsletter = NewsletterSubscriber.query.filter_by(email=user.email).first()
    if newsletter and newsletter.ip_address:
        ips.append({
            'ip': newsletter.ip_address,
            'source': 'Newsletter Subscription',
            'date': newsletter.created_at
        })
    
    return ips


def find_users_by_ip(ip_address):
    """Find all users associated with an IP address"""
    users = []
    
    # By registration IP
    reg_users = User.query.filter_by(registration_ip=ip_address).all()
    for user in reg_users:
        users.append({
            'user': user,
            'source': 'Registration',
            'date': user.created_date
        })
    
    # By last login IP
    login_users = User.query.filter_by(last_login_ip=ip_address).all()
    for user in login_users:
        if user not in [u['user'] for u in users]:  # Avoid duplicates
            users.append({
                'user': user,
                'source': 'Last Login',
                'date': None
            })
    
    # By newsletter subscription
    newsletter = NewsletterSubscriber.query.filter_by(ip_address=ip_address).all()
    for sub in newsletter:
        user = User.query.filter_by(email=sub.email).first()
        if user and user not in [u['user'] for u in users]:
            users.append({
                'user': user,
                'source': 'Newsletter Subscription',
                'date': sub.created_at
            })
    
    return users


def main():
    parser = argparse.ArgumentParser(description='Get IP addresses for a user or find users by IP')
    parser.add_argument('--user', type=str, help='User email to look up')
    parser.add_argument('--user-id', type=int, help='User ID to look up')
    parser.add_argument('--ip', type=str, help='IP address to find users for')
    
    args = parser.parse_args()
    
    app = create_app()
    
    with app.app_context():
        if args.ip:
            print("\n" + "="*60)
            print(f"USERS ASSOCIATED WITH IP: {args.ip}")
            print("="*60)
            
            users = find_users_by_ip(args.ip)
            if not users:
                print(f"\nNo users found with IP address {args.ip}")
            else:
                print(f"\nFound {len(users)} user(s):")
                for item in users:
                    user = item['user']
                    print(f"\n  User: {user.email} (ID: {user.id})")
                    print(f"  Name: {user.first_name} {user.last_name}")
                    print(f"  Source: {item['source']}")
                    if item['date']:
                        print(f"  Date: {item['date']}")
                    print(f"  Active: {'Yes' if user.is_active else 'No (Blocked)'}")
            
            return
        
        if args.user or args.user_id:
            if args.user:
                user = User.query.filter_by(email=args.user).first()
                if not user:
                    print(f"❌ User with email {args.user} not found")
                    return
            else:
                user = User.query.get(args.user_id)
                if not user:
                    print(f"❌ User with ID {args.user_id} not found")
                    return
            
            print("\n" + "="*60)
            print(f"IP ADDRESSES FOR USER: {user.email}")
            print("="*60)
            print(f"\nUser: {user.email} (ID: {user.id})")
            print(f"Name: {user.first_name} {user.last_name}")
            print(f"Created: {user.created_date}")
            print(f"Active: {'Yes' if user.is_active else 'No (Blocked)'}")
            
            ips = get_user_ips(user)
            
            if not ips:
                print("\n⚠️  No IP addresses found for this user")
                print("   (User may not have logged in yet or IPs weren't tracked)")
            else:
                print(f"\n📡 Found {len(ips)} IP address(es):")
                unique_ips = {}
                for ip_info in ips:
                    ip = ip_info['ip']
                    if ip not in unique_ips:
                        unique_ips[ip] = []
                    unique_ips[ip].append(ip_info)
                
                for ip, sources in unique_ips.items():
                    print(f"\n  IP: {ip}")
                    for source_info in sources:
                        print(f"    - {source_info['source']}", end="")
                        if source_info['date']:
                            print(f" ({source_info['date']})")
                        else:
                            print()
                
                print("\n" + "-"*60)
                print("To block this IP address:")
                for ip in unique_ips.keys():
                    print(f"  python block_ip.py --ip {ip} --reason \"Abuse from user {user.email}\"")
            
            return
        
        # No arguments
        parser.print_help()
        print("\nExamples:")
        print("  python get_user_ip.py --user spammer@example.com")
        print("  python get_user_ip.py --user-id 123")
        print("  python get_user_ip.py --ip 192.168.1.100")


if __name__ == "__main__":
    main()

