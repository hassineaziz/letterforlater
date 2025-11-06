"""
Device fingerprinting and IP velocity detection for spam prevention.
Detects:
- Multiple signups with same fingerprint
- Same fingerprint from different IPs (impossible velocity)
- High velocity signups from same IP
"""

from datetime import datetime, timedelta, timezone
from website.models import User, db
from typing import Tuple, Optional, List


def check_fingerprint_velocity(fingerprint: str, registration_ip: str) -> Tuple[bool, Optional[str], int]:
    """
    Check if a device fingerprint shows suspicious velocity patterns.
    
    Args:
        fingerprint: Device fingerprint hash
        registration_ip: IP address of registration
        
    Returns:
        Tuple of (is_suspicious: bool, reason: Optional[str], count: int)
    """
    if not fingerprint:
        return False, None, 0
    
    now = datetime.now(timezone.utc)
    
    # Check 1: Multiple signups with same fingerprint (last hour)
    one_hour_ago = now - timedelta(hours=1)
    same_fingerprint_users = User.query.filter(
        User.device_fingerprint == fingerprint,
        User.created_date >= one_hour_ago
    ).all()
    
    if len(same_fingerprint_users) >= 3:
        return True, f"Same device fingerprint used for {len(same_fingerprint_users)} signups in last hour", len(same_fingerprint_users)
    
    # Check 2: Same fingerprint from different IPs (impossible velocity)
    # If same fingerprint appears from different IPs within short time, it's suspicious
    if same_fingerprint_users:
        unique_ips = set(u.registration_ip for u in same_fingerprint_users if u.registration_ip)
        if len(unique_ips) >= 2:
            # Check time span - if different IPs within 5 minutes, it's impossible
            five_minutes_ago = now - timedelta(minutes=5)
            recent_multi_ip = [u for u in same_fingerprint_users 
                              if u.created_date >= five_minutes_ago and u.registration_ip]
            if len(recent_multi_ip) >= 2:
                unique_ips_recent = set(u.registration_ip for u in recent_multi_ip)
                if len(unique_ips_recent) >= 2:
                    return True, f"Same fingerprint from {len(unique_ips_recent)} different IPs in 5 minutes (impossible velocity)", len(recent_multi_ip)
    
    # Check 3: Same fingerprint from different IPs in last hour (still suspicious)
    if len(unique_ips) >= 3:
        return True, f"Same fingerprint from {len(unique_ips)} different IPs in last hour", len(same_fingerprint_users)
    
    return False, None, len(same_fingerprint_users)


def check_ip_velocity(registration_ip: str) -> Tuple[bool, Optional[str], int]:
    """
    Check if an IP address shows high velocity signup patterns.
    
    Args:
        registration_ip: IP address to check
        
    Returns:
        Tuple of (is_suspicious: bool, reason: Optional[str], count: int)
    """
    if not registration_ip:
        return False, None, 0
    
    now = datetime.now(timezone.utc)
    
    # Check 1: Multiple signups from same IP in short time
    five_minutes_ago = now - timedelta(minutes=5)
    recent_ip_signups = User.query.filter(
        User.registration_ip == registration_ip,
        User.created_date >= five_minutes_ago
    ).count()
    
    if recent_ip_signups >= 3:
        return True, f"{recent_ip_signups} signups from same IP in 5 minutes", recent_ip_signups
    
    # Check 2: Multiple signups from same IP in last hour
    one_hour_ago = now - timedelta(hours=1)
    hourly_ip_signups = User.query.filter(
        User.registration_ip == registration_ip,
        User.created_date >= one_hour_ago
    ).count()
    
    if hourly_ip_signups >= 10:
        return True, f"{hourly_ip_signups} signups from same IP in last hour", hourly_ip_signups
    
    # Check 3: Multiple signups from same IP in last 24 hours
    one_day_ago = now - timedelta(hours=24)
    daily_ip_signups = User.query.filter(
        User.registration_ip == registration_ip,
        User.created_date >= one_day_ago
    ).count()
    
    if daily_ip_signups >= 50:
        return True, f"{daily_ip_signups} signups from same IP in last 24 hours", daily_ip_signups
    
    return False, None, hourly_ip_signups


def check_fingerprint_ip_correlation(fingerprint: str, registration_ip: str) -> Tuple[bool, Optional[str]]:
    """
    Check for suspicious correlation between fingerprint and IP.
    Detects patterns like:
    - Many different fingerprints from same IP (bot farm)
    - Same fingerprint from many different IPs (VPN/proxy abuse)
    
    Args:
        fingerprint: Device fingerprint hash
        registration_ip: IP address of registration
        
    Returns:
        Tuple of (is_suspicious: bool, reason: Optional[str])
    """
    if not fingerprint or not registration_ip:
        return False, None
    
    now = datetime.now(timezone.utc)
    one_hour_ago = now - timedelta(hours=1)
    
    # Check: Many different fingerprints from same IP (bot farm pattern)
    same_ip_users = User.query.filter(
        User.registration_ip == registration_ip,
        User.created_date >= one_hour_ago
    ).all()
    
    if len(same_ip_users) >= 5:
        unique_fingerprints = set(u.device_fingerprint for u in same_ip_users if u.device_fingerprint)
        if len(unique_fingerprints) >= 5:
            return True, f"IP {registration_ip} has {len(unique_fingerprints)} different fingerprints in last hour (bot farm pattern)"
    
    # Check: Same fingerprint from many different IPs (VPN/proxy abuse)
    same_fingerprint_users = User.query.filter(
        User.device_fingerprint == fingerprint,
        User.created_date >= one_hour_ago
    ).all()
    
    if len(same_fingerprint_users) >= 5:
        unique_ips = set(u.registration_ip for u in same_fingerprint_users if u.registration_ip)
        if len(unique_ips) >= 5:
            return True, f"Fingerprint {fingerprint[:16]}... used from {len(unique_ips)} different IPs in last hour (VPN/proxy abuse)"
    
    return False, None


def validate_fingerprint_and_ip(fingerprint: Optional[str], registration_ip: Optional[str]) -> Tuple[bool, Optional[str], dict]:
    """
    Comprehensive validation of fingerprint and IP velocity.
    
    Args:
        fingerprint: Device fingerprint hash (can be None)
        registration_ip: IP address (can be None)
        
    Returns:
        Tuple of (is_valid: bool, error_message: Optional[str], details: dict)
    """
    details = {
        'fingerprint_checks': {},
        'ip_checks': {},
        'correlation_checks': {}
    }
    
    # Check fingerprint velocity
    if fingerprint:
        fp_suspicious, fp_reason, fp_count = check_fingerprint_velocity(fingerprint, registration_ip or '')
        details['fingerprint_checks'] = {
            'suspicious': fp_suspicious,
            'reason': fp_reason,
            'count': fp_count
        }
        if fp_suspicious:
            return False, fp_reason, details
    
    # Check IP velocity
    if registration_ip:
        ip_suspicious, ip_reason, ip_count = check_ip_velocity(registration_ip)
        details['ip_checks'] = {
            'suspicious': ip_suspicious,
            'reason': ip_reason,
            'count': ip_count
        }
        if ip_suspicious:
            return False, ip_reason, details
    
    # Check fingerprint-IP correlation
    if fingerprint and registration_ip:
        corr_suspicious, corr_reason = check_fingerprint_ip_correlation(fingerprint, registration_ip)
        details['correlation_checks'] = {
            'suspicious': corr_suspicious,
            'reason': corr_reason
        }
        if corr_suspicious:
            return False, corr_reason, details
    
    return True, None, details

