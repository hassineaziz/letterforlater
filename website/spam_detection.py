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
]


def is_random_email(email):
    """Check if email looks randomly generated"""
    if not email:
        return False
    
    email_lower = email.lower()
    
    # Check for temporary email domains
    domain = email_lower.split('@')[-1] if '@' in email_lower else ''
    if domain in TEMPORARY_EMAIL_DOMAINS:
        return True
    
    # Check for random patterns
    for pattern in RANDOM_EMAIL_PATTERNS:
        if re.match(pattern, email_lower):
            return True
    
    # Check for excessive randomness (many consonants in a row, no vowels)
    local_part = email_lower.split('@')[0] if '@' in email_lower else email_lower
    if len(local_part) >= 10:
        # Check if it has very few vowels (random strings often have few vowels)
        vowels = sum(1 for c in local_part if c in 'aeiou')
        if vowels < len(local_part) * 0.2:  # Less than 20% vowels
            # Check for long consonant sequences
            if re.search(r'[bcdfghjklmnpqrstvwxyz]{5,}', local_part):
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
    
    # If less than 25% vowels, likely random
    if vowel_ratio < 0.25:
        # Check for long consonant sequences (4+ consonants in a row)
        if re.search(r'[bcdfghjklmnpqrstvwxyz]{4,}', name_lower):
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

