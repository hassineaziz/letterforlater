"""
Advanced spam detection for signups.
Detects patterns in emails, names, and cross-IP behavior.
"""

import re
from collections import Counter
from datetime import datetime, timedelta, timezone
from website.models import User, db


# Common temporary/disposable email domains
TEMPORARY_EMAIL_DOMAINS = {
    '10minutemail.com', 'guerrillamail.com', 'mailinator.com', 'tempmail.com',
    'throwaway.email', 'getnada.com', 'mohmal.com', 'fakeinbox.com',
    'trashmail.com', 'temp-mail.org', 'yopmail.com', 'maildrop.cc',
    'sharklasers.com', 'grr.la', 'dispostable.com', 'mintemail.com'
}

# Patterns for random/spam emails
RANDOM_EMAIL_PATTERNS = [
    r'^[a-z0-9]{8,}\d{4,}@',  # 8+ random chars + 4+ digits (like 6z01zpukw9b72411)
    r'^\d+[a-z]+\d+@',  # Starts with digits, has letters, ends with digits
    r'^[a-z]{6,}\d{5,}@',  # 6+ letters followed by 5+ digits
    r'\.@',  # Dot immediately before @ (like kel4z5iqdkke.@outlook.com)
    r'^[a-z0-9]{10,}@',  # 10+ random alphanumeric chars before @
    r'^[a-z]{3,}\d{3,}[a-z]{3,}@',  # Pattern like "ecrx7dr8mg" (letters-digits-letters)
    r'^\d+\.',  # Starts with digit followed by dot (like 6.gxt8@proton.me)
    r'^[a-z]{1,2}\.',  # 1-2 letters followed by dot (like sp.kt0n904f7@outlook.com)
    r'_\d+[a-z]+\d+@',  # Underscore followed by random pattern (like t6ida_eb4l@yahoo.com)
    r'^\d+[a-z]+\d+_',  # Starts with digits, letters, digits, underscore (like 97d9vuob_xtz5@hotmail.com)
]


def is_random_email(email):
    """Check if email looks randomly generated"""
    if not email:
        return False
    
    email_lower = email.lower().strip()
    
    # Check for temporary email domains
    domain = email_lower.split('@')[-1] if '@' in email_lower else ''
    if domain in TEMPORARY_EMAIL_DOMAINS:
        return True
    
    # Check for dot immediately before @ (suspicious pattern like "kel4z5iqdkke.@outlook.com")
    if '.@' in email_lower or email_lower.endswith('.@'):
        return True
    
    # Check for random patterns
    for pattern in RANDOM_EMAIL_PATTERNS:
        if re.search(pattern, email_lower):
            return True
    
    # Check for excessive randomness (many consonants in a row, no vowels)
    local_part = email_lower.split('@')[0] if '@' in email_lower else email_lower
    # Remove dots from local part for analysis
    local_part_clean = local_part.replace('.', '')
    
    if len(local_part_clean) >= 6:  # Lowered from 8 to catch shorter spam emails
        # Check if it has very few vowels (random strings often have few vowels)
        vowels = sum(1 for c in local_part_clean if c in 'aeiou')
        vowel_ratio = vowels / len(local_part_clean) if local_part_clean else 0
        
        # For shorter emails (6-7 chars), be more strict
        if len(local_part_clean) <= 7:
            if vowel_ratio < 0.25:  # Less than 25% vowels for short emails
                # Check for long consonant sequences (4+ for short emails)
                if re.search(r'[bcdfghjklmnpqrstvwxyz]{4,}', local_part_clean):
                    return True
        else:
            # For longer emails (8+ chars), original logic
            if vowel_ratio < 0.2:  # Less than 20% vowels
                # Check for long consonant sequences
                if re.search(r'[bcdfghjklmnpqrstvwxyz]{5,}', local_part_clean):
                    return True
        
        # Check for patterns like "ecrx7dr8mg" - alternating letters and digits
        if re.match(r'^[a-z]{3,}\d{2,}[a-z]{2,}\d{1,}[a-z]{1,}$', local_part_clean):
            return True
        
        # Check for patterns like "frqond" - 6 chars with very few vowels
        # "frqond" has only 1 vowel (16.7%), which is suspicious
        if len(local_part_clean) == 6 and vowel_ratio < 0.2:
            # If it has very few vowels, check for consonant sequences (3+ for 6-char emails)
            if re.search(r'[bcdfghjklmnpqrstvwxyz]{3,}', local_part_clean):
                return True
    
    return False


def is_random_name(name):
    """Check if name looks randomly generated"""
    if not name or len(name) < 3:
        return False
    
    name_lower = name.lower()
    
    # Random names often have:
    # 1. No vowels or very few vowels
    # 2. Long consonant sequences
    # 3. Patterns like "Cvxpoz" (consonant-heavy)
    
    vowels = sum(1 for c in name_lower if c in 'aeiou')
    vowel_ratio = vowels / len(name_lower) if name_lower else 0
    
    # For very short names (3-4 chars), be more strict
    if len(name_lower) <= 4:
        # For 3-char names, if it has 1 or fewer vowels, it's likely spam
        if len(name_lower) == 3:
            if vowels <= 1:  # 0 or 1 vowel in 3 chars is suspicious
                return True
        elif len(name_lower) == 4:
            if vowel_ratio < 0.3:  # Less than 30% vowels for 4-char names
                # Check for consonant sequences (3+ for short names)
                if re.search(r'[bcdfghjklmnpqrstvwxyz]{3,}', name_lower):
                    return True
    else:
        # For longer names (5+ chars), original logic
        # If less than 30% vowels (slightly more lenient for longer names), likely random
        if vowel_ratio < 0.30:
            # Check for long consonant sequences (4+ consonants in a row)
            if re.search(r'[bcdfghjklmnpqrstvwxyz]{4,}', name_lower):
                return True
            # Also check for names with very few vowels (less than 25%) even without long sequences
            if vowel_ratio < 0.25:
                # Check for any consonant sequence of 3+ chars
                if re.search(r'[bcdfghjklmnpqrstvwxyz]{3,}', name_lower):
                    return True
    
    # Check for patterns like "Cvxpoz" - alternating consonant-heavy
    if re.match(r'^[bcdfghjklmnpqrstvwxyz]{2,}[aeiou]?[bcdfghjklmnpqrstvwxyz]{2,}[aeiou]?[bcdfghjklmnpqrstvwxyz]{2,}', name_lower):
        return True
    
    return False


def detect_spam_pattern(email, first_name, last_name, registration_ip):
    """
    Detect if signup is spam based on patterns.
    Returns (is_spam, reason, confidence)
    """
    reasons = []
    confidence = 0
    
    # Check email
    if is_random_email(email):
        reasons.append("random email pattern")
        confidence += 50
    
    # Check names
    if is_random_name(first_name):
        reasons.append("random first name")
        confidence += 30
    
    if is_random_name(last_name):
        reasons.append("random last name")
        confidence += 30
    
    # Check for cross-IP pattern (same email pattern from different IPs)
    if registration_ip:
        # Look for similar emails from different IPs in last hour
        one_hour_ago = datetime.now(timezone.utc) - timedelta(hours=1)
        
        # Extract email pattern (first 8 chars + domain)
        email_pattern = email[:8].lower() if len(email) >= 8 else email.lower()
        domain = email.split('@')[-1].lower() if '@' in email else ''
        
        # Find similar emails (same pattern) from different IPs
        similar_emails = User.query.filter(
            User.created_date >= one_hour_ago,
            User.email.like(f"{email_pattern}%@{domain}")
        ).all()
        
        if len(similar_emails) >= 3:
            unique_ips = set(u.registration_ip for u in similar_emails if u.registration_ip)
            if len(unique_ips) >= 2:  # Same pattern from multiple IPs = spam
                reasons.append("cross-IP spam pattern")
                confidence += 40
    
    # High confidence = spam
    is_spam = confidence >= 50
    
    reason = ", ".join(reasons) if reasons else "pattern detection"
    
    return is_spam, reason, confidence


def check_recent_spam_activity(registration_ip):
    """
    Check if this IP has been creating spam accounts recently.
    Returns (is_spam_ip, spam_count, reason)
    """
    if not registration_ip:
        return False, 0, None
    
    # Check last 5 minutes
    five_minutes_ago = datetime.now(timezone.utc) - timedelta(minutes=5)
    recent_users = User.query.filter(
        User.registration_ip == registration_ip,
        User.created_date >= five_minutes_ago
    ).all()
    
    if len(recent_users) >= 1:  # Even 1 signup in 5 minutes is suspicious if pattern matches
        # Check if any of them have spam patterns
        spam_count = 0
        for user in recent_users:
            if is_random_email(user.email) or is_random_name(user.first_name) or is_random_name(user.last_name):
                spam_count += 1
        
        if spam_count > 0:
            return True, len(recent_users), f"{spam_count} spam accounts in 5 minutes"
    
    return False, 0, None

