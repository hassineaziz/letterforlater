"""
Email sending rate limiting to prevent SMTP provider throttling.
Limits how many emails can be sent per time period.
"""

from datetime import datetime, timedelta, timezone
from .models import db
import time
from functools import wraps


# Rate limit configuration
# Global limits removed - only per-user limits for password_reset and confirmation
EMAIL_RATE_LIMIT = {
    'max_emails_per_minute': 1000,  # Very high limit (effectively no limit)
    'max_emails_per_hour': 10000,   # Very high limit (effectively no limit)
}

# Per-user email limits (for password_reset and confirmation only)
PER_USER_EMAIL_LIMIT = {
    'password_reset': 5,  # Max 5 password reset emails per user per hour
    'confirmation': 5,    # Max 5 confirmation emails per user per hour
}

# Track email sending times (global - for monitoring only)
_last_email_time = None
_email_send_times = []  # List of (timestamp, email_type) tuples

# Track per-user email sending (for password_reset and confirmation)
_user_email_times = {}  # Dict: {email: [(timestamp, email_type), ...]}


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
    
    return True, 0


def check_per_user_email_limit(email, email_type):
    """
    Check if user has exceeded per-user email limits.
    Only applies to password_reset and confirmation emails.
    Returns (can_send: bool, count: int)
    """
    global _user_email_times
    
    # Only check limits for password_reset and confirmation
    if email_type not in PER_USER_EMAIL_LIMIT:
        return True, 0  # No limit for other email types
    
    now = datetime.now(timezone.utc)
    one_hour_ago = now - timedelta(hours=1)
    
    # Initialize if needed
    if email not in _user_email_times:
        _user_email_times[email] = []
    
    # Clean old entries for this user
    _user_email_times[email] = [
        (ts, et) for ts, et in _user_email_times[email] 
        if ts > one_hour_ago and et == email_type
    ]
    
    # Count emails of this type in last hour
    count = len(_user_email_times[email])
    max_allowed = PER_USER_EMAIL_LIMIT[email_type]
    
    if count >= max_allowed:
        return False, count
    
    return True, count


def record_email_sent(email_type='unknown', recipient_email=None):
    """Record that an email was sent"""
    global _last_email_time, _email_send_times, _user_email_times
    now = datetime.now(timezone.utc)
    _last_email_time = now
    _email_send_times.append((now, email_type))
    
    # Track per-user for password_reset and confirmation
    if recipient_email and email_type in PER_USER_EMAIL_LIMIT:
        if recipient_email not in _user_email_times:
            _user_email_times[recipient_email] = []
        _user_email_times[recipient_email].append((now, email_type))
        
        # Clean old entries for this user
        one_hour_ago = now - timedelta(hours=1)
        _user_email_times[recipient_email] = [
            (ts, et) for ts, et in _user_email_times[recipient_email] 
            if ts > one_hour_ago
        ]
    
    # Keep only last hour of global records
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
    
    # Get recipient email
    recipient_email = None
    if msg.recipients:
        recipient_email = msg.recipients[0] if isinstance(msg.recipients, list) else msg.recipients
    

    
    # Check per-user email limit (only for password_reset and confirmation)
    if recipient_email and email_type in PER_USER_EMAIL_LIMIT:
        can_send, count = check_per_user_email_limit(recipient_email, email_type)
        if not can_send:
            max_allowed = PER_USER_EMAIL_LIMIT[email_type]
            print(f"[EMAIL RATE LIMIT] Per-user limit exceeded for {email_type}: {count}/{max_allowed} emails sent to {recipient_email} in last hour")
            return False
    
    # Check global rate limit (very high limits - effectively no limit for most emails)
    can_send, wait_time = check_email_rate_limit()
    
    if not can_send:
        print(f"[EMAIL RATE LIMIT] Global limit reached. Waiting {wait_time:.2f} seconds...")
        time.sleep(wait_time)
        can_send, wait_time = check_email_rate_limit()
        if not can_send:
            print(f"[EMAIL RATE LIMIT] Global rate limit exceeded for {email_type}. Email will be queued/skipped.")
            return False
    
    # Try to send with retries
    for attempt in range(max_retries + 1):
        try:
            mail.send(msg)
            record_email_sent(email_type, recipient_email)
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

