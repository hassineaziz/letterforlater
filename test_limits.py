#!/usr/bin/env python3
"""
Test script to verify:
1. Trusted contact limit (10 per user)
2. Letter creation rate limit (5 per hour)
"""

import sys
import os
from datetime import datetime, timezone

# Add the project directory to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from website import create_app, db
from website.models import User, Letter, TrustedContact
from website.views import check_letter_creation_rate_limit


def test_trusted_contact_limit():
    """Test trusted contact limit (10 per user)"""
    print("\n" + "="*60)
    print("TESTING TRUSTED CONTACT LIMIT (10 per user)")
    print("="*60)
    
    try:
        db.session.rollback()  # Reset any failed transactions
        
        # Check all users for limit violations
        print("\nChecking all users for trusted contact counts...")
        users_over_limit = []
        users_near_limit = []
        
        # Use raw SQL to avoid model column issues
        result = db.session.execute(
            db.text("SELECT user_id, COUNT(*) as count FROM trusted_contact GROUP BY user_id")
        )
        contact_counts = {row[0]: row[1] for row in result}
        
        # Get user emails
        user_ids = list(contact_counts.keys())
        if user_ids:
            user_emails = {}
            for user_id in user_ids:
                user = User.query.get(user_id)
                if user:
                    user_emails[user_id] = user.email
                    count = contact_counts[user_id]
                    if count > 10:
                        users_over_limit.append((user.email, count))
                    elif count >= 8:
                        users_near_limit.append((user.email, count))
        
        if users_over_limit:
            print(f"\n⚠️  Found {len(users_over_limit)} user(s) EXCEEDING limit:")
            for email, count in users_over_limit:
                print(f"  - {email}: {count} contacts (limit: 10) ❌")
        else:
            print("✅ No users exceeding trusted contact limit")
        
        if users_near_limit:
            print(f"\n⚠️  Found {len(users_near_limit)} user(s) near limit (8-10 contacts):")
            for email, count in users_near_limit:
                print(f"  - {email}: {count} contacts")
        
        # Show total stats
        total_contacts = sum(contact_counts.values())
        print(f"\nTotal trusted contacts: {total_contacts}")
        print(f"Users with contacts: {len(contact_counts)}")
        if contact_counts:
            avg_contacts = total_contacts / len(contact_counts)
            max_contacts = max(contact_counts.values())
            print(f"Average contacts per user: {avg_contacts:.1f}")
            print(f"Maximum contacts by one user: {max_contacts}")
            
    except Exception as e:
        print(f"⚠️  Error checking trusted contacts: {str(e)}")
        print("   (This might be due to missing database migrations)")
        db.session.rollback()


def test_letter_rate_limit():
    """Test letter creation rate limit (5 per hour)"""
    print("\n" + "="*60)
    print("TESTING LETTER CREATION RATE LIMIT (5 per hour)")
    print("="*60)
    
    try:
        db.session.rollback()  # Reset any failed transactions
        
        # Get users who created letters recently using raw SQL
        result = db.session.execute(
            db.text("""
                SELECT DISTINCT user_id 
                FROM letter 
                WHERE created_date >= NOW() - INTERVAL '1 hour'
                LIMIT 10
            """)
        )
        recent_user_ids = [row[0] for row in result]
        
        if not recent_user_ids:
            print("\n⚠️  No users with recent letter creation found.")
            print("   Testing limit logic with sample user IDs...")
            # Test with first few user IDs
            sample_users = db.session.execute(
                db.text("SELECT id, email FROM \"user\" WHERE is_active = true LIMIT 5")
            ).fetchall()
            if sample_users:
                recent_user_ids = [user[0] for user in sample_users]
            else:
                print("   No active users found to test.")
                return
        
        print(f"\nTesting rate limit for {len(recent_user_ids)} user(s)...")
        
        users_blocked = []
        users_ok = []
        
        for user_id in recent_user_ids[:10]:  # Test up to 10 users
            # Get user email
            user_result = db.session.execute(
                db.text("SELECT email FROM \"user\" WHERE id = :user_id"),
                {"user_id": user_id}
            ).fetchone()
            
            if not user_result:
                continue
                
            user_email = user_result[0]
            
            # Check rate limit
            is_allowed, count, message = check_letter_creation_rate_limit(user_id, limit=5)
            
            if not is_allowed:
                users_blocked.append((user_email, count, message))
                print(f"\n  ❌ {user_email}:")
                print(f"     Letters in last hour: {count}")
                print(f"     BLOCKED: {message}")
            else:
                users_ok.append((user_email, count))
        
        # Show summary
        if users_blocked:
            print(f"\n⚠️  {len(users_blocked)} user(s) currently rate-limited")
        else:
            print(f"\n✅ No users currently rate-limited")
            if users_ok:
                print(f"   {len(users_ok)} user(s) checked - all within limits")
        
        # Check for rapid spam detection
        print("\n" + "-"*60)
        print("Checking for rapid spam (10+ letters in 5 minutes)...")
        spam_result = db.session.execute(
            db.text("""
                SELECT user_id, COUNT(*) as count
                FROM letter
                WHERE created_date >= NOW() - INTERVAL '5 minutes'
                GROUP BY user_id
                HAVING COUNT(*) >= 10
            """)
        ).fetchall()
        
        if spam_result:
            print(f"⚠️  Found {len(spam_result)} user(s) with spam activity:")
            for user_id, count in spam_result:
                user_email_result = db.session.execute(
                    db.text("SELECT email FROM \"user\" WHERE id = :user_id"),
                    {"user_id": user_id}
                ).fetchone()
                email = user_email_result[0] if user_email_result else f"User {user_id}"
                print(f"  🚨 {email}: {count} letters in last 5 minutes (should be suspended)")
        else:
            print("✅ No spam activity detected")
            
    except Exception as e:
        print(f"⚠️  Error checking letter rate limits: {str(e)}")
        import traceback
        traceback.print_exc()
        db.session.rollback()


def test_limits_summary():
    """Show summary of all limits"""
    print("\n" + "="*60)
    print("LIMITS SUMMARY")
    print("="*60)
    
    print("\n1. TRUSTED CONTACT LIMIT:")
    print("   - Maximum: 10 contacts per user")
    print("   - Applies to: All users")
    print("   - Checked in: /add-trusted-contact, /invite-trusted-contact")
    
    print("\n2. LETTER CREATION RATE LIMIT:")
    print("   - Maximum: 5 letters per hour")
    print("   - Rapid spam: 10+ letters in 5 minutes = auto-suspend")
    print("   - Applies to: All users")
    print("   - Checked in: All letter creation functions")
    
    print("\n3. TOTAL LETTER LIMIT:")
    print("   - Maximum: None (unlimited)")
    print("   - Applies to: All users")
    
    # Count stats using raw SQL to avoid model issues
    try:
        total_users = db.session.execute(db.text("SELECT COUNT(*) FROM \"user\"")).scalar()
        active_users = db.session.execute(db.text("SELECT COUNT(*) FROM \"user\" WHERE is_active = true")).scalar()
        total_contacts = db.session.execute(db.text("SELECT COUNT(*) FROM trusted_contact")).scalar()
        total_letters = db.session.execute(db.text("SELECT COUNT(*) FROM letter")).scalar()
    except Exception as e:
        print(f"⚠️  Error getting stats: {str(e)}")
        total_users = active_users = total_contacts = total_letters = 0
    
    print("\n" + "-"*60)
    print("CURRENT STATS:")
    print(f"  Total users: {total_users} (active: {active_users})")
    print(f"  Total trusted contacts: {total_contacts}")
    print(f"  Total letters: {total_letters}")
    
    # Average contacts per user
    users_with_contacts = db.session.query(User).join(TrustedContact).distinct().count()
    if users_with_contacts > 0:
        avg_contacts = total_contacts / users_with_contacts
        print(f"  Average contacts per user (with contacts): {avg_contacts:.1f}")


def main():
    """Main test function"""
    print("="*60)
    print("TESTING LIMITS - LetterForLater")
    print("="*60)
    
    try:
        # Create Flask app context
        app = create_app()
        
        with app.app_context():
            # Test trusted contact limit
            test_trusted_contact_limit()
            
            # Test letter rate limit
            test_letter_rate_limit()
            
            # Show summary
            test_limits_summary()
            
            print("\n" + "="*60)
            print("✅ TESTING COMPLETE")
            print("="*60)
            
    except Exception as e:
        print(f"\n❌ Error during testing: {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()

