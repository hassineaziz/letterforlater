#!/usr/bin/env python3
"""
Check if spam accounts share the same device fingerprint.
This helps identify if it's the same bot/device creating multiple accounts.
"""

import sys
from website import create_app, db
from website.models import User
from collections import Counter

def check_fingerprints(user_ids):
    """Check fingerprints for a list of user IDs"""
    app = create_app()
    
    with app.app_context():
        print("="*70)
        print("CHECKING FINGERPRINTS FOR SPAM ACCOUNTS")
        print("="*70)
        print()
        
        users = User.query.filter(User.id.in_(user_ids)).all()
        
        if not users:
            print("No users found with those IDs")
            return
        
        print(f"Found {len(users)} users to check\n")
        
        # Group by fingerprint
        fingerprint_groups = {}
        no_fingerprint = []
        
        for user in users:
            fp = user.device_fingerprint
            if fp:
                if fp not in fingerprint_groups:
                    fingerprint_groups[fp] = []
                fingerprint_groups[fp].append(user)
            else:
                no_fingerprint.append(user)
        
        # Display results
        print("="*70)
        print("FINGERPRINT ANALYSIS")
        print("="*70)
        print()
        
        if fingerprint_groups:
            print(f"Found {len(fingerprint_groups)} unique fingerprints\n")
            
            # Sort by number of accounts (most suspicious first)
            sorted_groups = sorted(fingerprint_groups.items(), key=lambda x: len(x[1]), reverse=True)
            
            for idx, (fingerprint, user_list) in enumerate(sorted_groups, 1):
                print(f"\n{'='*70}")
                print(f"FINGERPRINT GROUP #{idx}: {fingerprint[:32]}...")
                print(f"Number of accounts: {len(user_list)}")
                print(f"{'='*70}")
                
                for user in user_list:
                    print(f"  ID: {user.id}")
                    print(f"  Email: {user.email}")
                    print(f"  Name: {user.first_name} {user.last_name}")
                    print(f"  IP: {user.registration_ip}")
                    print(f"  Created: {user.created_date}")
                    print()
        else:
            print("⚠️  No fingerprints found for these accounts")
            print("   (They may have been created before fingerprinting was added)")
            print()
        
        if no_fingerprint:
            print(f"\n{'='*70}")
            print(f"ACCOUNTS WITHOUT FINGERPRINTS: {len(no_fingerprint)}")
            print(f"{'='*70}")
            for user in no_fingerprint:
                print(f"  ID: {user.id} | Email: {user.email} | IP: {user.registration_ip}")
            print()
        
        # IP analysis
        print(f"\n{'='*70}")
        print("IP ADDRESS ANALYSIS")
        print(f"{'='*70}")
        ip_counts = Counter(user.registration_ip for user in users if user.registration_ip)
        print(f"Unique IPs: {len(ip_counts)}")
        print(f"Total accounts: {len(users)}")
        print()
        
        if len(ip_counts) < len(users):
            print("⚠️  Some IPs are reused:")
            for ip, count in ip_counts.most_common():
                if count > 1:
                    print(f"  {ip}: {count} accounts")
        else:
            print("✓ All accounts have unique IPs")
        
        # Check for fingerprint-IP correlation
        print(f"\n{'='*70}")
        print("FINGERPRINT-IP CORRELATION")
        print(f"{'='*70}")
        
        if fingerprint_groups:
            for fingerprint, user_list in sorted_groups:
                if len(user_list) > 1:
                    unique_ips = set(u.registration_ip for u in user_list if u.registration_ip)
                    print(f"\nFingerprint: {fingerprint[:32]}...")
                    print(f"  Accounts: {len(user_list)}")
                    print(f"  Unique IPs: {len(unique_ips)}")
                    
                    if len(unique_ips) > 1:
                        print(f"  ⚠️  SAME FINGERPRINT FROM {len(unique_ips)} DIFFERENT IPs!")
                        print(f"     This is a STRONG indicator of bot/spam activity")
                        for ip in unique_ips:
                            accounts_with_ip = [u for u in user_list if u.registration_ip == ip]
                            print(f"     - {ip}: {len(accounts_with_ip)} account(s)")
                    else:
                        print(f"  ✓ Same IP for all accounts (less suspicious)")
        
        # Summary
        print(f"\n{'='*70}")
        print("SUMMARY")
        print(f"{'='*70}")
        
        if fingerprint_groups:
            max_group_size = max(len(users) for users in fingerprint_groups.values())
            if max_group_size > 1:
                print(f"🚨 SUSPICIOUS: Found {max_group_size} accounts with the same fingerprint!")
                print(f"   This indicates the same device/bot is creating multiple accounts")
            else:
                print(f"✓ All accounts have unique fingerprints")
        else:
            print(f"⚠️  No fingerprint data available")
        
        # Check timing pattern
        print(f"\n{'='*70}")
        print("TIMING PATTERN ANALYSIS")
        print(f"{'='*70}")
        
        sorted_users = sorted(users, key=lambda u: u.created_date)
        time_diffs = []
        for i in range(1, len(sorted_users)):
            diff = (sorted_users[i].created_date - sorted_users[i-1].created_date).total_seconds()
            time_diffs.append(diff)
            print(f"  {sorted_users[i-1].id} -> {sorted_users[i].id}: {diff:.0f} seconds ({diff/60:.1f} minutes)")
        
        if time_diffs:
            avg_diff = sum(time_diffs) / len(time_diffs)
            print(f"\n  Average time between accounts: {avg_diff:.0f} seconds ({avg_diff/60:.1f} minutes)")
            
            if 240 <= avg_diff <= 360:  # 4-6 minutes
                print(f"  🚨 SUSPICIOUS: Consistent ~5 minute intervals detected!")
                print(f"     This matches automated bot behavior")


def main():
    if len(sys.argv) < 2:
        print("Usage: python check_spammer_fingerprints.py <user_id1> <user_id2> ...")
        print("Example: python check_spammer_fingerprints.py 2172 2171 2170 2169 2168")
        sys.exit(1)
    
    try:
        user_ids = [int(uid) for uid in sys.argv[1:]]
        check_fingerprints(user_ids)
    except ValueError:
        print("Error: All user IDs must be integers")
        sys.exit(1)
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()

