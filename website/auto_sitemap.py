"""
Automatic sitemap discovery system
This module automatically discovers all routes and generates sitemap entries
"""

import os
from flask import current_app, url_for
from datetime import datetime, timezone
from .models import BlogPost

def discover_routes():
    """Automatically discover all public routes for sitemap"""
    routes = []
    
    # Get all registered routes
    for rule in current_app.url_map.iter_rules():
        # Skip private/admin routes
        if any(skip in rule.rule for skip in [
            '/admin', '/api', '/auth', '/add-letter', '/view-letters',
            '/received-letters', '/settings', '/trusted-contacts', '/verify-',
            '/setup-2fa', '/forgot-password', '/reset-password', '/sign-up-with-invite',
            '/confirm-trusted-contact', '/pending-trusted-contact', '/media/',
            '/download-media/', '/sitemap-debug', '/test/', '/webhook', '/newsletter',
            '/debug', '/get-draft', '/confirm-trust', '/stripe', '/payment'
        ]):
            continue
            
        # Skip routes with parameters (except blog posts)
        if '<' in rule.rule and not rule.rule.startswith('/blog/'):
            continue
            
        # Skip POST/PUT/DELETE methods
        if rule.methods and not any(method in ['GET', 'HEAD'] for method in rule.methods):
            continue
            
        # Only include specific public pages
        public_pages = [
            '/', '/blog', '/pricing', '/privacy', '/terms', '/robots.txt', '/sitemap.xml'
        ]
        
        if rule.rule in public_pages or rule.rule.startswith('/blog/'):
            routes.append(rule)
    
    return routes

def get_route_priority(rule):
    """Determine priority based on route path"""
    path = rule.rule
    
    if path == '/':
        return 1.0
    elif path == '/blog':
        return 0.8
    elif path == '/pricing':
        return 0.7
    elif path.startswith('/blog/'):
        return 0.6
    elif path in ['/privacy', '/terms']:
        return 0.3
    else:
        return 0.5  # Default priority for other pages

def get_route_changefreq(rule):
    """Determine changefreq based on route path"""
    path = rule.rule
    
    if path == '/':
        return 'daily'
    elif path == '/blog':
        return 'daily'
    elif path.startswith('/blog/'):
        return 'weekly'
    elif path == '/pricing':
        return 'weekly'
    elif path in ['/privacy', '/terms']:
        return 'monthly'
    else:
        return 'weekly'  # Default changefreq for other pages

def generate_auto_sitemap():
    """Generate sitemap entries automatically from configured pages and discovered routes"""
    now_iso = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace('+00:00', 'Z')
    
    # First, add configured pages
    from .sitemap_pages import get_sitemap_pages
    for endpoint, params, changefreq, priority in get_sitemap_pages():
        yield endpoint, params, now_iso, changefreq, priority
    
    # Then add blog posts
    try:
        blog_posts = BlogPost.query.filter_by(status='published').all()
        for post in blog_posts:
            lastmod = post.updated_at or post.published_at or post.created_at
            lastmod_iso = lastmod.astimezone(timezone.utc).replace(microsecond=0).isoformat().replace('+00:00', 'Z')
            yield 'views.blog_post', {'slug': post.slug}, lastmod_iso, 'weekly', 0.6
    except Exception as e:
        # Log error but don't break sitemap generation
        pass

def get_manual_pages():
    """Get manually configured pages that might not be auto-discovered"""
    return [
        ('views.home', {}, 'daily', 1.0),
        ('views.blog_index', {}, 'daily', 0.8),
        ('pricing.pricing_page', {}, 'weekly', 0.7),
        ('views.privacy_policy', {}, 'monthly', 0.3),
        ('views.terms_of_service', {}, 'monthly', 0.3),
    ]
