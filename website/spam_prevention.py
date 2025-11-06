"""
Web form spam prevention utilities
Implements multiple layers of spam protection:
1. Honeypot fields (hidden fields bots fill)
2. Time-based validation (forms submitted too quickly are likely bots)
3. Rate limiting per IP
"""

from flask import request, session, flash
from datetime import datetime, timedelta
from functools import wraps
import time
import hashlib

# Store form submission timestamps and rates in memory (in production, use Redis)
_form_submissions = {}
_form_timestamps = {}

# Configuration
MIN_FORM_TIME = 3  # Minimum seconds to fill a form (human-like)
MAX_FORM_TIME = 3600  # Maximum seconds (1 hour) - forms abandoned too long
MAX_SUBMISSIONS_PER_HOUR = 10  # Max form submissions per IP per hour
MAX_SUBMISSIONS_PER_MINUTE = 3  # Max form submissions per IP per minute


def check_honeypot(form_data):
    """
    Check if honeypot fields were filled (bots often fill hidden fields)
    Returns (is_spam, error_message)
    """
    honeypot_fields = [
        'website',      # Common honeypot name
        'url',          # Another common one
        'phone',        # Some bots fill this
        'company',      # Business spam
        'homepage',     # Common bot field
        'website_url',  # Variant
        'home_page',    # Variant
        'business_url', # Business spam
        'site_url',     # Variant
        'contact_url',  # Contact form spam
    ]
    
    for field in honeypot_fields:
        if field in form_data and form_data[field] and form_data[field].strip():
            return True, "Spam detected: Invalid form submission."
    
    return False, None


def check_form_timing(form_id, form_start_time_key='form_start_time'):
    """
    Check if form was submitted too quickly (bot-like) or too slowly (stale)
    Returns (is_spam, error_message)
    """
    if form_start_time_key not in session:
        # No start time recorded, might be a direct POST or bot
        return True, "Form submission timing validation failed. Please refresh and try again."
    
    start_time = session.get(form_start_time_key)
    if not start_time:
        return True, "Form submission timing validation failed. Please refresh and try again."
    
    elapsed = time.time() - start_time
    
    if elapsed < MIN_FORM_TIME:
        return True, f"Form submitted too quickly. Please take at least {MIN_FORM_TIME} seconds to fill the form."
    
    if elapsed > MAX_FORM_TIME:
        return True, "Form submission expired. Please refresh and try again."
    
    return False, None


def check_rate_limit(ip_address, form_type='general'):
    """
    Check if IP has exceeded rate limits
    Returns (is_allowed, error_message, count)
    """
    now = time.time()
    key = f"{ip_address}:{form_type}"
    
    # Clean old entries (older than 1 hour)
    if key in _form_submissions:
        _form_submissions[key] = [
            timestamp for timestamp in _form_submissions[key]
            if now - timestamp < 3600
        ]
    else:
        _form_submissions[key] = []
    
    # Check per-minute limit
    recent_minute = [
        timestamp for timestamp in _form_submissions.get(key, [])
        if now - timestamp < 60
    ]
    
    if len(recent_minute) >= MAX_SUBMISSIONS_PER_MINUTE:
        return False, f"Too many submissions. Please wait before trying again.", len(recent_minute)
    
    # Check per-hour limit
    recent_hour = [
        timestamp for timestamp in _form_submissions.get(key, [])
        if now - timestamp < 3600
    ]
    
    if len(recent_hour) >= MAX_SUBMISSIONS_PER_HOUR:
        return False, f"Rate limit exceeded. Maximum {MAX_SUBMISSIONS_PER_HOUR} submissions per hour.", len(recent_hour)
    
    # Record this submission
    _form_submissions[key].append(now)
    
    return True, None, len(recent_hour) + 1


def get_client_ip():
    """Get client IP address, handling proxies"""
    if request.headers.get('X-Forwarded-For'):
        ip = request.headers.get('X-Forwarded-For').split(',')[0].strip()
    elif request.headers.get('X-Real-IP'):
        ip = request.headers.get('X-Real-IP')
    else:
        ip = request.remote_addr
    return ip


def validate_form_submission(form_id='default', form_type='general', check_honeypot_fields=True, check_timing=True):
    """
    Comprehensive form spam validation
    Returns (is_valid, error_message)
    """
    ip_address = get_client_ip()
    
    # 1. Check rate limiting
    is_allowed, rate_error, count = check_rate_limit(ip_address, form_type)
    if not is_allowed:
        return False, rate_error
    
    # 2. Check honeypot fields
    if check_honeypot_fields:
        is_spam, honeypot_error = check_honeypot(request.form)
        if is_spam:
            return False, honeypot_error
    
    # 3. Check form timing
    if check_timing:
        form_start_key = f'{form_id}_start_time'
        is_spam, timing_error = check_form_timing(form_id, form_start_key)
        if is_spam:
            return False, timing_error
    
    return True, None


def record_form_start(form_id='default'):
    """Record when a form page was loaded (for timing validation)"""
    session[f'{form_id}_start_time'] = time.time()


def spam_prevention(form_id='default', form_type='general', check_honeypot=True, check_timing=True):
    """
    Decorator for route handlers to add spam prevention
    Usage:
        @spam_prevention(form_id='signup', form_type='signup')
        def sign_up():
            ...
    """
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if request.method == 'POST':
                is_valid, error = validate_form_submission(
                    form_id=form_id,
                    form_type=form_type,
                    check_honeypot_fields=check_honeypot,
                    check_timing=check_timing
                )
                
                if not is_valid:
                    flash(error, 'error')
                    # Return to GET view or redirect
                    from flask import redirect, url_for
                    return redirect(request.url)
            
            # Record form start time for GET requests
            if request.method == 'GET':
                record_form_start(form_id)
            
            return f(*args, **kwargs)
        return decorated_function
    return decorator


def add_honeypot_fields_to_template():
    """
    Returns HTML for honeypot fields to add to forms
    These should be hidden with CSS but present in the HTML
    Bots will fill these fields, real users won't see or fill them
    """
    return """
    <!-- Honeypot fields - hidden from users but visible to bots -->
    <!-- These fields are positioned off-screen and made invisible -->
    <!-- Real users never see or fill these, but bots often auto-fill all inputs -->
    <div style="position: absolute; left: -9999px; opacity: 0; pointer-events: none; width: 0; height: 0; overflow: hidden;" aria-hidden="true">
        <input type="text" name="website" id="website" tabindex="-1" autocomplete="off" value="" style="display: none;">
        <input type="text" name="url" id="url" tabindex="-1" autocomplete="off" value="" style="display: none;">
        <input type="text" name="company" id="company" tabindex="-1" autocomplete="off" value="" style="display: none;">
        <input type="text" name="homepage" id="homepage" tabindex="-1" autocomplete="off" value="" style="display: none;">
        <input type="text" name="website_url" id="website_url" tabindex="-1" autocomplete="off" value="" style="display: none;">
        <!-- Additional honeypot: email field that looks like it should be filled -->
        <input type="email" name="email_confirm" id="email_confirm" tabindex="-1" autocomplete="off" value="" style="display: none;" placeholder="Leave this field empty">
    </div>
    """

