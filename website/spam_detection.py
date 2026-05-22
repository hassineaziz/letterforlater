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
    r'^[a-z0-9]{6,}[._-][a-z0-9]{4,}@',  # Random chars with separator (like j9u3mp95bi0bwmi8cp)
    r'^[a-z0-9]{5,}_[a-z0-9]{4,}@',  # Underscore separator pattern
    r'^[a-z0-9]{4,}\.[a-z0-9]{4,}@',  # Dot separator pattern (like o7mbb9k5u.r)
    r'^[a-z]\d+[a-z]+\d+@',  # Letter-digit-letter-digit pattern
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


def check_recent_spam_activity(registration_ip):
    """
    Check if this IP or its Subnet has been creating too many accounts recently.
    Real-looking data bypasses string patterns, so we enforce hard rate limits per subnet.
    Returns (is_spam_ip, spam_count, reason)
    """
    if not registration_ip:
        return False, 0, None
    
    # Check last 30 minutes
    thirty_minutes_ago = datetime.now(timezone.utc) - timedelta(minutes=30)
    
    try:
        parts = registration_ip.split('.')
        if len(parts) == 4:
            subnet = f"{parts[0]}.{parts[1]}.{parts[2]}."
        else:
            subnet = registration_ip
    except:
        subnet = registration_ip

    # Get all users from the same exact IP in the last 30 mins
    recent_exact_ip = User.query.filter(
        User.registration_ip == registration_ip,
        User.created_date >= thirty_minutes_ago
    ).count()

    if recent_exact_ip >= 3:
        return True, recent_exact_ip, f"Strict rate limit: {recent_exact_ip} signups from exact IP in 30 minutes"
        
    # Get all users from the same Subnet (e.g. 192.101.255.*) in the last 30 mins
    recent_subnet_users = User.query.filter(
        User.registration_ip.like(f"{subnet}%"),
        User.created_date >= thirty_minutes_ago
    ).count()
    
    if recent_subnet_users >= 3:
        return True, recent_subnet_users, f"Strict subnet rate limit: {recent_subnet_users} signups from subnet {subnet}* in 30 minutes"
    
    return False, 0, None


def check_timing_pattern(registration_ip, email, first_name, last_name):
    """
    Detect if signup follows a suspicious timing pattern (like every 5 minutes).
    This catches automated bots that create accounts at regular intervals.
    
    Returns (is_suspicious, reason, confidence)
    """
    if not registration_ip:
        return False, None, 0
    
    now = datetime.now(timezone.utc)
    
    # Check for accounts created at regular intervals from different IPs
    # This catches the pattern where a bot rotates IPs but maintains timing
    one_hour_ago = now - timedelta(hours=1)
    
    # Get recent signups with similar patterns (random email/name)
    recent_spam_signups = User.query.filter(
        User.created_date >= one_hour_ago
    ).order_by(User.created_date.desc()).limit(20).all()
    
    # Filter to only spam-like accounts
    spam_like_signups = [
        u for u in recent_spam_signups
        if (is_random_email(u.email) or is_random_name(u.first_name) or is_random_name(u.last_name))
        and u.registration_ip != registration_ip  # Different IPs
    ]
    
    if len(spam_like_signups) >= 3:
        # Check if they follow a regular interval pattern
        intervals = []
        for i in range(len(spam_like_signups) - 1):
            diff = (spam_like_signups[i].created_date - spam_like_signups[i+1].created_date).total_seconds()
            intervals.append(diff)
        
        if intervals:
            # Check if intervals are consistent (within 1 minute of each other)
            avg_interval = sum(intervals) / len(intervals)
            
            # Check if this signup would fit the pattern (4-6 minute intervals)
            if 240 <= avg_interval <= 360:  # 4-6 minutes
                # Check if current signup fits the pattern
                if spam_like_signups:
                    time_since_last = (now - spam_like_signups[0].created_date).total_seconds()
                    # If it's been 4-6 minutes since last spam signup, it's suspicious
                    if 240 <= time_since_last <= 360:
                        return True, f"Matches automated timing pattern (every ~5 minutes from different IPs)", 60
    
    # Check for regular intervals from same IP pattern
    recent_same_ip = User.query.filter(
        User.registration_ip == registration_ip,
        User.created_date >= one_hour_ago
    ).order_by(User.created_date.desc()).limit(10).all()
    
    if len(recent_same_ip) >= 3:
        intervals = []
        for i in range(len(recent_same_ip) - 1):
            diff = (recent_same_ip[i].created_date - recent_same_ip[i+1].created_date).total_seconds()
            intervals.append(diff)
        
        if intervals:
            avg_interval = sum(intervals) / len(intervals)
            # Check if intervals are very consistent (within 30 seconds)
            interval_variance = sum(abs(i - avg_interval) for i in intervals) / len(intervals)
            
            if 240 <= avg_interval <= 360 and interval_variance < 60:  # Consistent 4-6 minute intervals
                return True, f"Regular timing pattern detected: {avg_interval/60:.1f} minute intervals from same IP", 70
    
    return False, None, 0


def check_aws_ip_range(ip_address):
    """
    Check if IP is from AWS ranges (common for bots).
    Returns (is_aws, subnet_info)
    """
    if not ip_address:
        return False, None
    
    try:
        parts = ip_address.split('.')
        if len(parts) != 4:
            return False, None
        
        first_octet = int(parts[0])
        second_octet = int(parts[1])
        
        # AWS IP ranges (common ones)
        # 3.x.x.x - AWS
        # 18.x.x.x - AWS
        # 52.x.x.x - AWS
        # 54.x.x.x - AWS
        # 13.x.x.x - AWS
        
        if first_octet == 3:
            return True, "AWS (3.x.x.x)"
        elif first_octet == 18:
            return True, "AWS (18.x.x.x)"
        elif first_octet == 52:
            return True, "AWS (52.x.x.x)"
        elif first_octet == 54:
            return True, "AWS (54.x.x.x)"
        elif first_octet == 13:
            return True, "AWS (13.x.x.x)"
        elif first_octet == 63 and second_octet == 178:
            return True, "AWS (63.178.x.x)"
        
        return False, None
    except:
        return False, None


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
    
    # Check timing pattern (NEW)
    if registration_ip:
        timing_suspicious, timing_reason, timing_confidence = check_timing_pattern(registration_ip, email, first_name, last_name)
        if timing_suspicious:
            reasons.append(timing_reason)
            confidence += timing_confidence
            
    # STRICT IP & SUBNET RATE LIMITING (OVERRIDE)
    if registration_ip:
        rate_limited, count, limit_reason = check_recent_spam_activity(registration_ip)
        if rate_limited:
            reasons.append(limit_reason)
            confidence += 100  # Instant flag as spam
    
    # Check for AWS IP (NEW - lower weight, just a flag)
    if registration_ip:
        is_aws, aws_info = check_aws_ip_range(registration_ip)
        if is_aws:
            # Only add to confidence if combined with other spam indicators
            if confidence >= 50:
                reasons.append(f"from AWS IP range ({aws_info})")
                confidence += 10
    
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
    is_spam = confidence >= 80
    
    reason = ", ".join(reasons) if reasons else "pattern detection"
    
    return is_spam, reason, confidence

