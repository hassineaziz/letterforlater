#!/usr/bin/env python3
"""
Simple script to block/unblock IP addresses and users.
Usage:
    python block_ip.py --ip 192.168.1.1 --reason "Spam activity"
    python block_ip.py --ip 192.168.1.1 --unblock
    python block_ip.py --user email@example.com --reason "Violation"
    python block_ip.py --user-id 123 --unblock
"""

import sys
import argparse
from website import create_app, db
from website.blocking import block_ip, unblock_ip, block_user, unblock_user, get_blocked_ips, get_blocked_users
from website.models import User, BlockedIP


def main():
    parser = argparse.ArgumentParser(description='Block or unblock IP addresses and users')
    parser.add_argument('--ip', type=str, help='IP address to block/unblock')
    parser.add_argument('--user', type=str, help='User email to block/unblock')
    parser.add_argument('--user-id', type=int, help='User ID to block/unblock')
    parser.add_argument('--reason', type=str, help='Reason for blocking')
    parser.add_argument('--unblock', action='store_true', help='Unblock instead of block')
    parser.add_argument('--list-ips', action='store_true', help='List all blocked IPs')
    parser.add_argument('--list-users', action='store_true', help='List all blocked users')
    
    args = parser.parse_args()
    
    app = create_app()
    
    with app.app_context():
        if args.list_ips:
            print("\n" + "="*60)
            print("BLOCKED IP ADDRESSES")
            print("="*60)
            blocked_ips = get_blocked_ips()
            if not blocked_ips:
                print("No blocked IP addresses found.")
            else:
                for blocked in blocked_ips:
                    print(f"\nIP: {blocked.ip_address}")
                    print(f"  Blocked at: {blocked.blocked_at}")
                    print(f"  Reason: {blocked.reason or 'No reason provided'}")
                    if blocked.blocked_by:
                        admin = User.query.get(blocked.blocked_by)
                        if admin:
                            print(f"  Blocked by: {admin.email}")
            return
        
        if args.list_users:
            print("\n" + "="*60)
            print("BLOCKED USERS")
            print("="*60)
            blocked_users = get_blocked_users()
            if not blocked_users:
                print("No blocked users found.")
            else:
                for user in blocked_users:
                    print(f"\nUser: {user.email} (ID: {user.id})")
                    print(f"  Created: {user.created_date}")
            return
        
        if args.ip:
            if args.unblock:
                success, message = unblock_ip(args.ip)
                if success:
                    print(f"✅ {message}")
                else:
                    print(f"❌ {message}")
            else:
                success, message, block_record = block_ip(args.ip, reason=args.reason)
                if success:
                    print(f"✅ {message}")
                else:
                    print(f"❌ {message}")
            return
        
        if args.user or args.user_id:
            if args.user:
                user = User.query.filter_by(email=args.user).first()
                if not user:
                    print(f"❌ User with email {args.user} not found")
                    return
                user_id = user.id
            else:
                user_id = args.user_id
                user = User.query.get(user_id)
                if not user:
                    print(f"❌ User with ID {user_id} not found")
                    return
            
            if args.unblock:
                success, message, user_obj = unblock_user(user_id)
                if success:
                    print(f"✅ {message}")
                else:
                    print(f"❌ {message}")
            else:
                success, message, user_obj = block_user(user_id, reason=args.reason)
                if success:
                    print(f"✅ {message}")
                else:
                    print(f"❌ {message}")
            return
        
        # No action specified
        parser.print_help()


if __name__ == "__main__":
    main()

