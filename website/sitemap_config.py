"""
Sitemap and robots.txt configuration for Flask-Sitemap
"""
import os
from flask import Blueprint, request
from flask_sitemap import Sitemap
from datetime import datetime, timezone
from .models import BlogPost

# Initialize sitemap (disabled - using custom route instead)
# sitemap = Sitemap()

# Configure sitemap settings (disabled - using custom route instead)
# sitemap.config = {
#     'SITEMAP_INCLUDE_RULES_WITHOUT_PARAMS': True,
#     'SITEMAP_URL_SCHEME': 'https',
#     'SITEMAP_FORCE_HTTPS': True,
#     'SITEMAP_URL_SCHEME': 'https'
# }

# Create blueprint for SEO-related routes
seo_bp = Blueprint('seo', __name__)

def sitemap_generator():
    """Generate sitemap entries automatically"""
    from .auto_sitemap import generate_auto_sitemap
    
    # Use automatic discovery for all routes
    for entry in generate_auto_sitemap():
        yield entry

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
Disallow: /admin-cms/
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

# Block test routes
Disallow: /test/

# Allow important public pages
Allow: /blog
Allow: /privacy
Allow: /terms
Allow: /robots.txt
Allow: /sitemap.xml
Allow: /sitemap-manual.xml
Allow: /static/sitemap.xml

# Sitemap location
Sitemap: {base_url}/sitemap.xml

# RSS Feed
Sitemap: {base_url}/blog/feed.xml
"""
    
    return robots_content, 200, {'Content-Type': 'text/plain'}

# Debug route removed for production

@seo_bp.route('/sitemap.xml')
def sitemap_xml():
    """Dynamic sitemap generation with HTTPS support"""
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
                # Use SITE_DOMAIN environment variable for HTTPS
                if os.getenv('SITE_DOMAIN'):
                    base_domain = os.getenv('SITE_DOMAIN').rstrip('/')
                    path = url_for(entry[0], **entry[1])
                    url = f"{base_domain}{path}"
                else:
                    # Fallback to Flask's url_for with HTTPS conversion
                    url = url_for(entry[0], **entry[1], _external=True)
                    if url.startswith('http://'):
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
                # Log error but continue with other entries
                continue
        
        # Convert to string
        xml_str = ET.tostring(urlset, encoding='unicode', method='xml')
        xml_str = '<?xml version="1.0" encoding="UTF-8"?>\n' + xml_str
        
        return Response(xml_str, mimetype='application/xml')
        
    except Exception as e:
        return f"Error generating sitemap: {str(e)}", 500

# Manual sitemap route removed - using Flask-Sitemap only
