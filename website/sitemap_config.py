"""
Sitemap and robots.txt configuration for Flask-Sitemap
"""
from flask import Blueprint, request
from flask_sitemap import Sitemap
from datetime import datetime, timezone
from .models import BlogPost

# Initialize sitemap
sitemap = Sitemap()

# Create blueprint for SEO-related routes
seo_bp = Blueprint('seo', __name__)

@sitemap.register_generator
def sitemap_generator():
    """Generate sitemap entries automatically"""
    
    # Static pages
    yield 'views.home', {}, datetime.now(timezone.utc), 'daily', 1.0
    yield 'views.blog_index', {}, datetime.now(timezone.utc), 'daily', 0.8
    yield 'views.privacy_policy', {}, datetime.now(timezone.utc), 'monthly', 0.3
    yield 'views.terms_of_service', {}, datetime.now(timezone.utc), 'monthly', 0.3
    
    # Dynamic blog posts
    blog_posts = BlogPost.query.filter_by(status='published').all()
    for post in blog_posts:
        lastmod = post.updated_at or post.published_at or post.created_at
        yield 'views.blog_post', {'slug': post.slug}, lastmod, 'weekly', 0.6

@seo_bp.route('/robots.txt')
def robots_txt():
    """Generate robots.txt file"""
    base_url = request.url_root.rstrip('/')
    
    robots_content = f"""User-agent: *
Allow: /
Disallow: /admin/
Disallow: /api/
Disallow: /auth/
Disallow: /add-letter
Disallow: /view-letters/
Disallow: /received-letters
Disallow: /settings
Disallow: /trusted-contacts
Disallow: /verify-death
Disallow: /verify-2fa
Disallow: /setup-2fa
Disallow: /forgot-password
Disallow: /reset-password
Disallow: /sign-up-with-invite
Disallow: /confirm-trusted-contact
Disallow: /pending-trusted-contact

# Sitemap
Sitemap: {base_url}/sitemap.xml

# RSS Feed
Sitemap: {base_url}/blog/feed.xml
"""
    
    return robots_content, 200, {'Content-Type': 'text/plain'}
