"""
Email validation utilities
- Blocks disposable/temporary email domains
- Validates MX records exist for email domains
"""

import dns.resolver
import socket
from typing import Tuple, Optional
import re

# Comprehensive list of disposable email domains
# This is a curated list - you can expand it or use an API
DISPOSABLE_EMAIL_DOMAINS = {
    # Common temporary email services
    '10minutemail.com', '10minutemail.de', '10minutemail.co.uk',
    'guerrillamail.com', 'guerrillamail.net', 'guerrillamail.org',
    'mailinator.com', 'mailinator.net', 'mailinator.org',
    'tempmail.com', 'tempmail.net', 'tempmail.org',
    'throwaway.email', 'getnada.com', 'mohmal.com', 'fakeinbox.com',
    'trashmail.com', 'temp-mail.org', 'yopmail.com', 'maildrop.cc',
    'sharklasers.com', 'grr.la', 'dispostable.com', 'mintemail.com',
    'meltmail.com', 'melt.li', 'getairmail.com',
    # More disposable email services
    'tempail.com', 'tempr.email', 'tmpmail.org', 'tmpmail.net',
    'tmpmail.com', 'tmpmail.io', 'tmpmail.co', 'tmpmail.me',
    'throwawaymail.com', 'throwawaymail.net', 'throwawaymail.org',
    'throwawaymail.io', 'throwawaymail.co', 'throwawaymail.me',
    'fakemail.net', 'fakemail.org', 'fakemail.io', 'fakemail.co',
    'fakemail.me', 'fakemail.com', 'fakemailgenerator.com',
    'emailondeck.com', 'emailondeck.net', 'emailondeck.org',
    'emailondeck.io', 'emailondeck.co', 'emailondeck.me',
    'mailcatch.com', 'mailcatch.net', 'mailcatch.org',
    'mailcatch.io', 'mailcatch.co', 'mailcatch.me',
    'spamgourmet.com', 'spamgourmet.net', 'spamgourmet.org',
    'spamgourmet.io', 'spamgourmet.co', 'spamgourmet.me',
    'mytemp.email', 'mytemp.net', 'mytemp.org', 'mytemp.io',
    'mytemp.co', 'mytemp.me', 'mytemp.com',
    # Additional common ones
    '33mail.com', '33mail.net', '33mail.org', '33mail.io',
    '33mail.co', '33mail.me', 'emailias.com', 'emailias.net',
    'emailias.org', 'emailias.io', 'emailias.co', 'emailias.me',
    'mailnesia.com', 'mailnesia.net', 'mailnesia.org',
    'mailnesia.io', 'mailnesia.co', 'mailnesia.me',
}


def is_disposable_email(email: str) -> bool:
    """
    Check if email is from a disposable/temporary email service.
    
    Args:
        email: Email address to check
        
    Returns:
        True if email is from a disposable domain, False otherwise
    """
    if not email or '@' not in email:
        return False
    
    # Extract domain
    domain = email.split('@')[-1].lower().strip()
    
    # Check against disposable domains list
    if domain in DISPOSABLE_EMAIL_DOMAINS:
        return True
    
    # Also check for common patterns in disposable email domains
    disposable_patterns = [
        r'^temp.*mail',
        r'^throw.*mail',
        r'^fake.*mail',
        r'^trash.*mail',
        r'^spam.*mail',
        r'^disposable.*mail',
        r'^10min.*mail',
        r'^mint.*mail',
        r'^melt.*mail',
        r'^tmp.*mail',
        r'^nada.*',
        r'^mohmal.*',
        r'^guerrilla.*',
        r'^mailinator.*',
        r'^yopmail.*',
        r'^sharklasers.*',
    ]
    
    for pattern in disposable_patterns:
        if re.match(pattern, domain):
            return True
    
    return False


def has_mx_record(domain: str, timeout: int = 5) -> Tuple[bool, Optional[str]]:
    """
    Check if a domain has valid MX (Mail Exchange) records.
    
    Args:
        domain: Domain name to check (without @)
        timeout: DNS query timeout in seconds
        
    Returns:
        Tuple of (has_mx: bool, error_message: Optional[str])
    """
    if not domain:
        return False, "Domain is empty"
    
    # Clean domain
    domain = domain.lower().strip()
    
    # Remove @ if present
    if domain.startswith('@'):
        domain = domain[1:]
    
    try:
        # Try to resolve MX records
        try:
            mx_records = dns.resolver.resolve(domain, 'MX', lifetime=timeout)
            if len(mx_records) > 0:
                return True, None
            else:
                return False, "No MX records found"
        except dns.resolver.NoAnswer:
            # No MX records, but domain might exist
            # Check if domain exists at all
            try:
                # Try A record as fallback - some domains use A records for mail
                dns.resolver.resolve(domain, 'A', lifetime=timeout)
                # Domain exists but no MX - this is suspicious but might be valid
                # Some small domains might not have MX records
                return False, "Domain exists but has no MX records (domain may not accept email)"
            except dns.resolver.NXDOMAIN:
                return False, "Domain does not exist"
            except Exception:
                return False, "Domain validation failed"
        except dns.resolver.NXDOMAIN:
            return False, "Domain does not exist"
        except dns.resolver.Timeout:
            # DNS timeout - be lenient, don't block if DNS is slow
            # Log warning but allow (might be temporary DNS issue)
            print(f"[EMAIL VALIDATION] DNS timeout for {domain} - allowing (may be temporary)")
            return True, "DNS timeout (allowed, may be temporary)"
        except dns.resolver.NoNameservers:
            # No nameservers - domain likely doesn't exist
            return False, "Domain does not exist (no nameservers)"
        except Exception as e:
            # Other DNS errors - be lenient for temporary issues
            error_str = str(e).lower()
            if 'timeout' in error_str or 'timed out' in error_str:
                print(f"[EMAIL VALIDATION] DNS error for {domain}: {e} - allowing (may be temporary)")
                return True, "DNS error (allowed, may be temporary)"
            return False, f"DNS error: {str(e)}"
            
    except Exception as e:
        # Fallback: try socket lookup if DNS library fails completely
        try:
            socket.gethostbyname(domain)
            # Domain exists but we couldn't check MX - be lenient
            print(f"[EMAIL VALIDATION] Could not verify MX for {domain} (DNS library error) - allowing")
            return True, "Could not verify MX records (DNS error), but domain exists"
        except socket.gaierror:
            return False, "Domain does not exist"
        except Exception as e:
            # If even socket lookup fails, be lenient - might be network issue
            print(f"[EMAIL VALIDATION] Error checking {domain}: {e} - allowing (may be network issue)")
            return True, f"Error checking domain (allowed, may be network issue): {str(e)}"


def validate_email(email: str, check_mx: bool = True) -> Tuple[bool, Optional[str]]:
    """
    Comprehensive email validation:
    1. Check if email is from a disposable domain
    2. Check if domain has MX records (if check_mx is True)
    
    Args:
        email: Email address to validate
        check_mx: Whether to check MX records (default: True)
        
    Returns:
        Tuple of (is_valid: bool, error_message: Optional[str])
    """
    if not email:
        return False, "Email is required"
    
    # Basic email format check
    email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    if not re.match(email_pattern, email):
        return False, "Invalid email format"
    
    # Extract domain
    if '@' not in email:
        return False, "Invalid email format"
    
    domain = email.split('@')[-1].lower().strip()
    
    # Check if disposable
    if is_disposable_email(email):
        return False, "Disposable email addresses are not allowed. Please use a permanent email address."
    
    # Check MX records if requested
    if check_mx:
        has_mx, mx_error = has_mx_record(domain)
        if not has_mx:
            return False, f"Email domain is invalid or does not accept emails: {mx_error}"
    
    return True, None


def validate_email_domain(domain: str, check_mx: bool = True) -> Tuple[bool, Optional[str]]:
    """
    Validate just the domain part of an email.
    
    Args:
        domain: Domain name to validate (without @)
        check_mx: Whether to check MX records (default: True)
        
    Returns:
        Tuple of (is_valid: bool, error_message: Optional[str])
    """
    if not domain:
        return False, "Domain is required"
    
    # Check if disposable
    test_email = f"test@{domain}"
    if is_disposable_email(test_email):
        return False, "Disposable email domains are not allowed"
    
    # Check MX records if requested
    if check_mx:
        has_mx, mx_error = has_mx_record(domain)
        if not has_mx:
            return False, f"Domain is invalid or does not accept emails: {mx_error}"
    
    return True, None

