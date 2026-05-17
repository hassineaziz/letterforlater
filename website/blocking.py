"""
IP address utilities for the website.
"""

from flask import request

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

def get_ip_subnet(ip_address):
    """
    Get the subnet (first 3 octets) of an IP address.
    
    Args:
        ip_address: IP address (e.g., "89.33.8.58")
        
    Returns:
        str: Subnet pattern (e.g., "89.33.8") or None if invalid
    """
    if not ip_address:
        return None
    
    try:
        parts = ip_address.split('.')
        if len(parts) == 4:
            return '.'.join(parts[:3])
    except:
        pass
    
    return None
