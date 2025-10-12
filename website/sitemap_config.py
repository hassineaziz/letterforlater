"""
Sitemap and robots.txt configuration for Flask-Sitemap
"""
import os
from flask import Blueprint, request
from flask_sitemap import Sitemap
from datetime import datetime, timezone
from .models import BlogPost

# Initialize sitemap
sitemap = Sitemap()

# Configure sitemap settings
sitemap.config = {
    'SITEMAP_INCLUDE_RULES_WITHOUT_PARAMS': True,
    'SITEMAP_URL_SCHEME': 'https',
    'SITEMAP_FORCE_HTTPS': True
}

# Create blueprint for SEO-related routes
seo_bp = Blueprint('seo', __name__)

@sitemap.register_generator
def sitemap_generator():
    """Generate sitemap entries automatically"""
    
    # Static pages - using proper ISO 8601 format
    now_iso = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace('+00:00', 'Z')
    yield 'views.home', {}, now_iso, 'daily', 1.0
    yield 'views.blog_index', {}, now_iso, 'daily', 0.8
    yield 'views.privacy_policy', {}, now_iso, 'monthly', 0.3
    yield 'views.terms_of_service', {}, now_iso, 'monthly', 0.3
    
    # Dynamic blog posts - using proper ISO 8601 format
    blog_posts = BlogPost.query.filter_by(status='published').all()
    for post in blog_posts:
        lastmod = post.updated_at or post.published_at or post.created_at
        # Convert to ISO 8601 without microseconds
        lastmod_iso = lastmod.astimezone(timezone.utc).replace(microsecond=0).isoformat().replace('+00:00', 'Z')
        yield 'views.blog_post', {'slug': post.slug}, lastmod_iso, 'weekly', 0.6

@seo_bp.route('/robots.txt')
def robots_txt():
    """Generate robots.txt file"""
    # Force HTTPS for production
    base_url = os.getenv('SITE_DOMAIN', request.url_root.rstrip('/'))
    if not base_url.startswith('https://'):
        base_url = base_url.replace('http://', 'https://')
    
    robots_content = f"""User-agent: *
Allow: /

# Block private user areas
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

# Block media files (they're served via S3)
Disallow: /media/
Disallow: /download-media/

# Block debug and test routes
Disallow: /sitemap-debug
Disallow: /test/

# Allow important public pages
Allow: /blog
Allow: /privacy
Allow: /terms
Allow: /robots.txt
Allow: /sitemap.xml
Allow: /sitemap-manual.xml
Allow: /static/sitemap.xml

# Sitemap locations
Sitemap: {base_url}/sitemap.xml
Sitemap: {base_url}/sitemap-manual.xml
Sitemap: {base_url}/static/sitemap.xml

# RSS Feed
Sitemap: {base_url}/blog/feed.xml
"""
    
    return robots_content, 200, {'Content-Type': 'text/plain'}

@seo_bp.route('/sitemap-debug')
def sitemap_debug():
    """Debug sitemap generation"""
    try:
        entries = list(sitemap_generator())
        debug_info = {
            'total_entries': len(entries),
            'entries': []
        }
        
        for entry in entries:
            debug_info['entries'].append({
                'endpoint': entry[0],
                'params': entry[1],
                'lastmod': entry[2],
                'changefreq': entry[3],
                'priority': entry[4]
            })
        
        from flask import jsonify
        return jsonify(debug_info)
    except Exception as e:
        from flask import jsonify
        return jsonify({'error': str(e)}), 500

@seo_bp.route('/sitemap-manual.xml')
def sitemap_manual():
    """Manual sitemap generation as fallback"""
    from flask import Response, url_for
    import xml.etree.ElementTree as ET
    
    try:
        # Create XML sitemap
        urlset = ET.Element('urlset')
        urlset.set('xmlns', 'http://www.sitemaps.org/schemas/sitemap/0.9')
        
        entries = list(sitemap_generator())
        
        for entry in entries:
            url_elem = ET.SubElement(urlset, 'url')
            
            # Generate URL with HTTPS
            try:
                url = url_for(entry[0], **entry[1], _external=True)
                # Force HTTPS - use SITE_DOMAIN if available
                if os.getenv('SITE_DOMAIN'):
                    base_domain = os.getenv('SITE_DOMAIN').rstrip('/')
                    path = url_for(entry[0], **entry[1])
                    url = f"{base_domain}{path}"
                elif url.startswith('http://'):
                    url = url.replace('http://', 'https://')
                loc_elem = ET.SubElement(url_elem, 'loc')
                loc_elem.text = url
                
                # Add lastmod
                if entry[2]:
                    lastmod_elem = ET.SubElement(url_elem, 'lastmod')
                    lastmod_elem.text = entry[2]
                
                # Add changefreq
                if entry[3]:
                    changefreq_elem = ET.SubElement(url_elem, 'changefreq')
                    changefreq_elem.text = entry[3]
                
                # Add priority
                if entry[4]:
                    priority_elem = ET.SubElement(url_elem, 'priority')
                    priority_elem.text = str(entry[4])
                    
            except Exception as e:
                print(f"Error generating URL for {entry[0]}: {e}")
                continue
        
        # Convert to string
        xml_str = ET.tostring(urlset, encoding='unicode', method='xml')
        xml_str = '<?xml version="1.0" encoding="UTF-8"?>\n' + xml_str
        
        return Response(xml_str, mimetype='application/xml')
        
    except Exception as e:
        return f"Error generating sitemap: {str(e)}", 500
