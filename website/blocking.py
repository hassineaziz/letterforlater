"""
Blocking system for IP addresses and users.
Provides functions to check and manage blocks.
"""

from flask import request, abort
from functools import wraps
from .models import BlockedIP, User, db


def get_client_ip():
    """
    Get the client's real IP address, handling proxies and load balancers.
    Checks common headers for forwarded IP addresses.
    """
    # Check for forwarded IP headers (common in production with proxies/load balancers)
    if request.headers.get('X-Forwarded-For'):
        # X-Forwarded-For can contain multiple IPs, get the first one (original client)
        forwarded_ips = request.headers.get('X-Forwarded-For').split(',')
        ip = forwarded_ips[0].strip()
        if ip:
            return ip
    
    if request.headers.get('X-Real-IP'):
        return request.headers.get('X-Real-IP').strip()
    
    # Fallback to direct connection IP
    return request.remote_addr or '0.0.0.0'


def is_ip_blocked(ip_address):
    """
    Check if an IP address is blocked.
    
    Args:
        ip_address: IP address to check
        
    Returns:
        tuple: (is_blocked: bool, block_record: BlockedIP or None)
    """
    if not ip_address:
        return False, None
    
    blocked = BlockedIP.query.filter_by(
        ip_address=ip_address,
        is_active=True
    ).first()
    
    return (blocked is not None, blocked)


def is_user_blocked(user_id):
    """
    Check if a user is blocked/suspended.
    
    Args:
        user_id: User ID to check
        
    Returns:
        tuple: (is_blocked: bool, user: User or None)
    """
    user = User.query.get(user_id)
    if user and not user.is_active:
        return True, user
    return False, None


def check_blocked(func):
    """
    Decorator to check if IP or user is blocked before allowing access to a route.
    Blocks the request if IP is blocked or user is not active.
    """
    @wraps(func)
    def decorated_function(*args, **kwargs):
        # Check IP blocking
        client_ip = get_client_ip()
        ip_blocked, block_record = is_ip_blocked(client_ip)
        
        if ip_blocked:
            print(f"[BLOCK] Access denied for blocked IP: {client_ip} (reason: {block_record.reason or 'No reason provided'})")
            abort(403)  # Forbidden
        
        # Check user blocking (if user is logged in)
        from flask_login import current_user
        if current_user.is_authenticated:
            user_blocked, user = is_user_blocked(current_user.id)
            if user_blocked:
                print(f"[BLOCK] Access denied for blocked user: {current_user.email} (ID: {current_user.id})")
                abort(403)  # Forbidden
        
        return func(*args, **kwargs)
    
    return decorated_function


def block_ip(ip_address, reason=None, blocked_by_user_id=None):
    """
    Block an IP address permanently.
    
    Args:
        ip_address: IP address to block
        reason: Reason for blocking (optional)
        blocked_by_user_id: ID of admin user who is blocking (optional)
        
    Returns:
        tuple: (success: bool, message: str, block_record: BlockedIP or None)
    """
    if not ip_address:
        return False, "IP address is required", None
    
    # Check if already blocked
    existing = BlockedIP.query.filter_by(ip_address=ip_address).first()
    if existing:
        if existing.is_active:
            return False, f"IP {ip_address} is already blocked", existing
        else:
            # Re-activate existing block
            existing.is_active = True
            existing.reason = reason or existing.reason
            existing.blocked_by = blocked_by_user_id or existing.blocked_by
            db.session.commit()
            return True, f"IP {ip_address} block re-activated", existing
    
    # Create new block
    new_block = BlockedIP(
        ip_address=ip_address,
        reason=reason,
        blocked_by=blocked_by_user_id
    )
    db.session.add(new_block)
    db.session.commit()
    
    print(f"[BLOCK] IP {ip_address} blocked permanently (reason: {reason or 'No reason provided'})")
    return True, f"IP {ip_address} blocked successfully", new_block


def unblock_ip(ip_address):
    """
    Unblock an IP address.
    
    Args:
        ip_address: IP address to unblock
        
    Returns:
        tuple: (success: bool, message: str)
    """
    if not ip_address:
        return False, "IP address is required"
    
    blocked = BlockedIP.query.filter_by(ip_address=ip_address).first()
    if not blocked:
        return False, f"IP {ip_address} is not blocked"
    
    if not blocked.is_active:
        return False, f"IP {ip_address} is already unblocked"
    
    blocked.is_active = False
    db.session.commit()
    
    print(f"[BLOCK] IP {ip_address} unblocked")
    return True, f"IP {ip_address} unblocked successfully"


def block_user(user_id, reason=None, blocked_by_user_id=None):
    """
    Block a user account permanently.
    
    Args:
        user_id: User ID to block
        reason: Reason for blocking (optional, stored in logs)
        blocked_by_user_id: ID of admin user who is blocking (optional)
        
    Returns:
        tuple: (success: bool, message: str, user: User or None)
    """
    user = User.query.get(user_id)
    if not user:
        return False, f"User with ID {user_id} not found", None
    
    if not user.is_active:
        return False, f"User {user.email} is already blocked", user
    
    user.is_active = False
    db.session.commit()
    
    print(f"[BLOCK] User {user.email} (ID: {user_id}) blocked permanently (reason: {reason or 'No reason provided'})")
    if blocked_by_user_id:
        admin = User.query.get(blocked_by_user_id)
        if admin:
            print(f"[BLOCK] Blocked by admin: {admin.email}")
    
    return True, f"User {user.email} blocked successfully", user


def unblock_user(user_id):
    """
    Unblock a user account.
    
    Args:
        user_id: User ID to unblock
        
    Returns:
        tuple: (success: bool, message: str, user: User or None)
    """
    user = User.query.get(user_id)
    if not user:
        return False, f"User with ID {user_id} not found", None
    
    if user.is_active:
        return False, f"User {user.email} is already active", user
    
    user.is_active = True
    db.session.commit()
    
    print(f"[BLOCK] User {user.email} (ID: {user_id}) unblocked")
    return True, f"User {user.email} unblocked successfully", user


def get_blocked_ips():
    """Get all active blocked IPs."""
    return BlockedIP.query.filter_by(is_active=True).all()


def get_blocked_users():
    """Get all blocked/inactive users."""
    return User.query.filter_by(is_active=False).all()

