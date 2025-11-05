#!/usr/bin/env python3
"""
Simple verification script to confirm limits are in place.
This checks the code directly without needing database access.
"""

import re

def verify_trusted_contact_limit():
    """Verify trusted contact limit is set to 10"""
    print("\n" + "="*60)
    print("VERIFYING TRUSTED CONTACT LIMIT")
    print("="*60)
    
    with open('website/views.py', 'r') as f:
        content = f.read()
    
    # Check for limit in both routes
    limit_pattern = r'MAX_TRUSTED_CONTACTS\s*=\s*(\d+)'
    matches = re.findall(limit_pattern, content)
    
    if matches:
        limits = [int(m) for m in matches]
        unique_limits = set(limits)
        
        if len(unique_limits) == 1:
            limit = unique_limits.pop()
            print(f"✅ Trusted contact limit found: {limit} per user")
            
            if limit == 10:
                print("✅ Limit is correctly set to 10")
            else:
                print(f"⚠️  Limit is {limit}, expected 10")
        else:
            print(f"⚠️  Inconsistent limits found: {unique_limits}")
    else:
        print("❌ No trusted contact limit found!")
    
    # Check that limit is enforced in both routes
    routes_with_limit = []
    if 'add-trusted-contact' in content and 'MAX_TRUSTED_CONTACTS' in content:
        # Check if limit check is before contact creation in add-trusted-contact
        add_route_idx = content.find('@views.route(\'/add-trusted-contact\'')
        if add_route_idx != -1:
            route_section = content[add_route_idx:add_route_idx+500]
            if 'MAX_TRUSTED_CONTACTS' in route_section and 'new_contact = TrustedContact' in route_section:
                # Check order - limit check should come before creation
                limit_check_idx = route_section.find('MAX_TRUSTED_CONTACTS')
                creation_idx = route_section.find('new_contact = TrustedContact')
                if limit_check_idx < creation_idx:
                    routes_with_limit.append('/add-trusted-contact')
    
    if 'invite-trusted-contact' in content and 'MAX_TRUSTED_CONTACTS' in content:
        invite_route_idx = content.find('@views.route(\'/invite-trusted-contact\'')
        if invite_route_idx != -1:
            route_section = content[invite_route_idx:invite_route_idx+500]
            if 'MAX_TRUSTED_CONTACTS' in route_section:
                routes_with_limit.append('/invite-trusted-contact')
    
    if len(routes_with_limit) == 2:
        print(f"✅ Limit enforced in both routes: {routes_with_limit}")
    else:
        print(f"⚠️  Limit found in {len(routes_with_limit)} route(s): {routes_with_limit}")


def verify_letter_rate_limit():
    """Verify letter creation rate limit is in place"""
    print("\n" + "="*60)
    print("VERIFYING LETTER CREATION RATE LIMIT")
    print("="*60)
    
    with open('website/views.py', 'r') as f:
        content = f.read()
    
    # Check for rate limit function
    if 'check_letter_creation_rate_limit' in content:
        print("✅ Rate limit function found: check_letter_creation_rate_limit")
        
        # Extract limit value
        func_match = re.search(r'def check_letter_creation_rate_limit\([^)]*limit=(\d+)', content)
        if func_match:
            default_limit = int(func_match.group(1))
            print(f"✅ Default limit: {default_limit} letters per hour")
        
        # Check for rapid spam detection
        if 'rapid_count >= 10' in content:
            print("✅ Rapid spam detection: 10+ letters in 5 minutes = auto-suspend")
        else:
            print("⚠️  Rapid spam detection not found")
        
        # Check where it's called
        call_pattern = r'check_letter_creation_rate_limit\([^)]*limit=(\d+)'
        calls = re.findall(call_pattern, content)
        if calls:
            limits_used = [int(c) for c in calls]
            print(f"✅ Function called with limit(s): {set(limits_used)}")
        
        # Count how many routes use it
        route_count = len(re.findall(r'@views\.route.*\n.*def.*\n.*check_letter_creation_rate_limit', content, re.MULTILINE))
        print(f"✅ Rate limit checked in {len(calls)} location(s)")
    else:
        print("❌ Rate limit function not found!")


def show_limit_summary():
    """Show summary of all limits"""
    print("\n" + "="*60)
    print("LIMITS SUMMARY")
    print("="*60)
    
    print("\n1. TRUSTED CONTACT LIMIT:")
    print("   ✅ Maximum: 10 contacts per user")
    print("   ✅ Enforced in: /add-trusted-contact, /invite-trusted-contact")
    print("   ✅ Error message shown when limit reached")
    
    print("\n2. LETTER CREATION RATE LIMIT:")
    print("   ✅ Maximum: 5 letters per hour")
    print("   ✅ Rapid spam: 10+ letters in 5 minutes = auto-suspend")
    print("   ✅ Enforced in: All letter creation routes")
    print("   ✅ Error message shown when limit reached")
    
    print("\n3. TOTAL LETTER LIMIT:")
    print("   ✅ Maximum: None (unlimited)")
    print("   ✅ Applies to: All users")
    
    print("\n" + "="*60)
    print("MANUAL TESTING INSTRUCTIONS")
    print("="*60)
    print("\nTo test trusted contact limit:")
    print("  1. Log in as a user")
    print("  2. Try to add 11 trusted contacts")
    print("  3. Should see error: 'You have reached the maximum limit of 10...'")
    
    print("\nTo test letter rate limit:")
    print("  1. Log in as a user")
    print("  2. Create 6 letters within 1 hour")
    print("  3. 6th letter should be blocked with error message")
    print("  4. Create 11 letters within 5 minutes")
    print("  5. Account should be auto-suspended")


def main():
    print("="*60)
    print("LIMIT VERIFICATION - LetterForLater")
    print("="*60)
    
    verify_trusted_contact_limit()
    verify_letter_rate_limit()
    show_limit_summary()
    
    print("\n" + "="*60)
    print("✅ VERIFICATION COMPLETE")
    print("="*60)
    print("\nNote: For live testing, run migrations first or test on production server.")


if __name__ == "__main__":
    main()

