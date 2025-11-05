"""
Email sending rate limiting to prevent SMTP provider throttling.
Limits how many emails can be sent per time period.
"""

from datetime import datetime, timedelta, timezone
from .models import db
import time
from functools import wraps


# Rate limit configuration
EMAIL_RATE_LIMIT = {
    'max_emails_per_minute': 10,  # Max 10 emails per minute
    'max_emails_per_hour': 100,   # Max 100 emails per hour
    'delay_between_emails': 0.5  # Minimum 0.5 seconds between emails
}

# Track email sending times
_last_email_time = None
_email_send_times = []  # List of (timestamp, email_type) tuples


def check_email_rate_limit():
    """
    Check if we can send an email based on rate limits.
    Returns (can_send: bool, wait_time: float)
    """
    global _last_email_time, _email_send_times
    
    now = datetime.now(timezone.utc)
    one_minute_ago = now - timedelta(minutes=1)
    one_hour_ago = now - timedelta(hours=1)
    
    # Clean old entries
    _email_send_times = [(ts, email_type) for ts, email_type in _email_send_times if ts > one_hour_ago]
    
    # Count emails in last minute
    recent_count = len([ts for ts, _ in _email_send_times if ts > one_minute_ago])
    
    # Count emails in last hour
    hourly_count = len(_email_send_times)
    
    # Check limits
    if recent_count >= EMAIL_RATE_LIMIT['max_emails_per_minute']:
        wait_time = 60 - (now - _email_send_times[-EMAIL_RATE_LIMIT['max_emails_per_minute']][0]).total_seconds()
        return False, max(0, wait_time)
    
    if hourly_count >= EMAIL_RATE_LIMIT['max_emails_per_hour']:
        wait_time = 3600 - (now - _email_send_times[0][0]).total_seconds()
        return False, max(0, wait_time)
    
    # Check delay between emails
    if _last_email_time:
        time_since_last = (now - _last_email_time).total_seconds()
        if time_since_last < EMAIL_RATE_LIMIT['delay_between_emails']:
            wait_time = EMAIL_RATE_LIMIT['delay_between_emails'] - time_since_last
            return False, wait_time
    
    return True, 0


def record_email_sent(email_type='unknown'):
    """Record that an email was sent"""
    global _last_email_time, _email_send_times
    now = datetime.now(timezone.utc)
    _last_email_time = now
    _email_send_times.append((now, email_type))
    
    # Keep only last hour of records
    one_hour_ago = now - timedelta(hours=1)
    _email_send_times = [(ts, et) for ts, et in _email_send_times if ts > one_hour_ago]


def rate_limited_email_send(mail_func):
    """
    Decorator to rate limit email sending.
    Adds delay between emails and checks rate limits.
    """
    @wraps(mail_func)
    def wrapper(*args, **kwargs):
        # Check rate limit
        can_send, wait_time = check_email_rate_limit()
        
        if not can_send:
            print(f"[EMAIL RATE LIMIT] Throttling email send. Waiting {wait_time:.2f} seconds...")
            time.sleep(wait_time)
            # Re-check after waiting
            can_send, wait_time = check_email_rate_limit()
            if not can_send:
                print(f"[EMAIL RATE LIMIT] Email rate limit exceeded. Skipping email send.")
                raise Exception(f"Email rate limit exceeded. Please try again later.")
        
        # Send email
        try:
            result = mail_func(*args, **kwargs)
            # Record successful send
            email_type = kwargs.get('email_type', 'unknown')
            record_email_sent(email_type)
            return result
        except Exception as e:
            # If it's a rate limit error from SMTP, wait longer
            error_str = str(e).lower()
            if 'rate limit' in error_str or 'unusual sending' in error_str or '550' in error_str:
                print(f"[EMAIL RATE LIMIT] SMTP rate limit detected. Waiting 60 seconds...")
                time.sleep(60)
                # Try once more
                try:
                    result = mail_func(*args, **kwargs)
                    record_email_sent(kwargs.get('email_type', 'unknown'))
                    return result
                except Exception as e2:
                    print(f"[EMAIL RATE LIMIT] Retry failed: {str(e2)}")
                    raise e2
            raise
    
    return wrapper


def safe_send_email(msg, email_type='unknown', max_retries=2):
    """
    Safely send an email with rate limiting and retry logic.
    
    Args:
        msg: Flask-Mail Message object
        email_type: Type of email (for tracking)
        max_retries: Maximum number of retry attempts
        
    Returns:
        bool: True if sent successfully, False otherwise
    """
    from . import mail
    
    # EMERGENCY: Check if recipient email is from spam account
    if msg.recipients:
        recipient_email = msg.recipients[0] if isinstance(msg.recipients, list) else msg.recipients
        from .models import User
        user = User.query.filter_by(email=recipient_email).first()
        if user and user.registration_ip:
            # Check if this IP is spam
            from datetime import datetime, timedelta, timezone
            five_minutes_ago = datetime.now(timezone.utc) - timedelta(minutes=5)
            spam_count = User.query.filter(
                User.registration_ip == user.registration_ip,
                User.created_date >= five_minutes_ago
            ).count()
            
            if spam_count >= 3:
                print(f"[EMAIL BLOCK] Skipping email to {recipient_email} - spam IP {user.registration_ip}")
                return False
            
            # Check if IP is blocked
            from .blocking import is_ip_blocked
            ip_blocked, _ = is_ip_blocked(user.registration_ip)
            if ip_blocked:
                print(f"[EMAIL BLOCK] Skipping email to {recipient_email} - blocked IP")
                return False
    
    # Check rate limit
    can_send, wait_time = check_email_rate_limit()
    
    if not can_send:
        print(f"[EMAIL RATE LIMIT] Throttling {email_type} email. Waiting {wait_time:.2f} seconds...")
        time.sleep(wait_time)
        can_send, wait_time = check_email_rate_limit()
        if not can_send:
            print(f"[EMAIL RATE LIMIT] Rate limit exceeded for {email_type}. Email will be queued/skipped.")
            return False
    
    # Try to send with retries
    for attempt in range(max_retries + 1):
        try:
            mail.send(msg)
            record_email_sent(email_type)
            return True
        except Exception as e:
            error_str = str(e).lower()
            
            # Check if it's a rate limit error
            if 'rate limit' in error_str or 'unusual sending' in error_str or '550' in error_str or '5.4.6' in error_str:
                # Don't retry rate limit errors - fail immediately to avoid worker timeout
                print(f"[EMAIL RATE LIMIT] SMTP rate limit detected for {email_type}. Email NOT sent (Zoho blocking).")
                return False  # Fail fast - don't retry or wait
            else:
                # Other error, don't retry
                print(f"[EMAIL ERROR] Error sending {email_type} email: {str(e)}")
                return False
    
    return False

