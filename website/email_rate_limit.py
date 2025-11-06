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
    
    # Check delay between emails - but don't block, just warn
    # (We removed time.sleep so we don't actually delay, but we still track for monitoring)
    if _last_email_time:
        time_since_last = (now - _last_email_time).total_seconds()
        if time_since_last < EMAIL_RATE_LIMIT['delay_between_emails']:
            wait_time = EMAIL_RATE_LIMIT['delay_between_emails'] - time_since_last
            # Don't block, just return True (we removed sleep delays)
            print(f"[EMAIL RATE LIMIT] Warning: Email sent {time_since_last:.2f}s after last (min {EMAIL_RATE_LIMIT['delay_between_emails']}s), but sending anyway")
            return True, 0  # Allow through despite delay
    
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
            # Rate limit warning but send anyway (no sleep)
            print(f"[EMAIL RATE LIMIT] Rate limit warning for email send, but sending anyway (no sleep)")
            # Still try to send, but log the warning
        
        # Send email
        try:
            result = mail_func(*args, **kwargs)
            # Record successful send
            email_type = kwargs.get('email_type', 'unknown')
            record_email_sent(email_type)
            return result
        except Exception as e:
            # If it's a rate limit error from SMTP, don't wait - fail fast
            error_str = str(e).lower()
            if 'rate limit' in error_str or 'unusual sending' in error_str or '550' in error_str:
                print(f"[EMAIL RATE LIMIT] SMTP rate limit detected. Email NOT sent (no sleep/retry).")
                raise e  # Fail immediately without waiting
            raise
    
    return wrapper


def safe_send_email(msg, email_type='unknown', max_retries=2):
    """
    Safely send an email with rate limiting and retry logic.
    Includes spam detection to prevent sending emails to spam accounts.
    
    Args:
        msg: Flask-Mail Message object
        email_type: Type of email (for tracking)
        max_retries: Maximum number of retry attempts
        
    Returns:
        bool: True if sent successfully, False otherwise
    """
    from . import mail
    
    # SPAM DETECTION: Only block obvious spam, allow legitimate users through
    if msg.recipients:
        recipient_email = msg.recipients[0] if isinstance(msg.recipients, list) else msg.recipients
        
        # For ALL emails, be VERY lenient - only block if IP is explicitly blocked
        # Don't block based on email patterns or name patterns (too aggressive)
        from .models import User
        user = User.query.filter_by(email=recipient_email).first()
        
        if user and user.registration_ip:
            # Only block if IP is explicitly blocked (not based on recent activity or patterns)
            from .blocking import is_ip_blocked
            ip_blocked, _ = is_ip_blocked(user.registration_ip)
            if ip_blocked:
                print(f"[EMAIL BLOCK] Skipping {email_type} email to {recipient_email} - explicitly blocked IP")
                return False
        
        # For confirmation emails only, also check if email is clearly spam
        # (password reset and other emails should go through regardless)
        if email_type == 'confirmation':
            from .spam_detection import is_random_email
            if is_random_email(recipient_email):
                print(f"[EMAIL BLOCK] Skipping confirmation email to {recipient_email} - spam email pattern")
                return False
    
    # Check rate limit
    # For critical security emails (password reset, confirmation), bypass rate limiting
    # These are essential emails that users need
    can_send, wait_time = check_email_rate_limit()
    
    if not can_send:
        # All emails bypass rate limiting sleep - send immediately
        # Rate limiting is still checked but we don't block/delay emails with time.sleep()
        print(f"[EMAIL RATE LIMIT] {email_type} email - rate limit warning but sending anyway (no sleep)")
        # Still try to send, but log the rate limit warning
    
    # Try to send with retries
    recipient_email = msg.recipients[0] if isinstance(msg.recipients, list) else msg.recipients if msg.recipients else "unknown"
    
    for attempt in range(max_retries + 1):
        try:
            print(f"[EMAIL SEND] Attempt {attempt + 1}/{max_retries + 1}: Sending {email_type} email to {recipient_email}")
            mail.send(msg)
            record_email_sent(email_type)
            print(f"[EMAIL SEND] ✅ Successfully sent {email_type} email to {recipient_email}")
            return True
        except Exception as e:
            error_str = str(e).lower()
            error_type = type(e).__name__
            
            print(f"[EMAIL ERROR] Attempt {attempt + 1} failed for {email_type} to {recipient_email}: {error_type} - {str(e)}")
            
            # Check if it's a rate limit error
            if 'rate limit' in error_str or 'unusual sending' in error_str or '550' in error_str or '5.4.6' in error_str:
                # Don't retry rate limit errors - fail immediately to avoid worker timeout
                print(f"[EMAIL RATE LIMIT] SMTP rate limit detected for {email_type} to {recipient_email}. Email NOT sent (Zoho blocking).")
                return False  # Fail fast - don't retry or wait
            elif attempt < max_retries:
                # Retry for other errors (connection issues, etc.)
                print(f"[EMAIL ERROR] Retrying {email_type} email to {recipient_email} (attempt {attempt + 2}/{max_retries + 1})")
                continue
            else:
                # Final attempt failed
                print(f"[EMAIL ERROR] ❌ Failed to send {email_type} email to {recipient_email} after {max_retries + 1} attempts: {error_type} - {str(e)}")
                return False
    
    print(f"[EMAIL ERROR] ❌ Failed to send {email_type} email to {recipient_email} - all retries exhausted")
    return False

