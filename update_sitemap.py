#!/usr/bin/env python3
"""
Auto-update static sitemap when new content is added
Run this script whenever you add new blog posts or pages
"""

import os
import sys
from datetime import datetime, timezone
import xml.etree.ElementTree as ET

# Add the project root to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from website import create_app
from website.models import BlogPost

def update_static_sitemap():
    """Update the static sitemap with current content"""
    app = create_app()
    
    with app.app_context():
        # Create XML sitemap
        urlset = ET.Element('urlset')
        urlset.set('xmlns', 'http://www.sitemaps.org/schemas/sitemap/0.9')
        
        # Get current timestamp
        now_iso = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace('+00:00', 'Z')
        
        # Static pages
        static_pages = [
            ('/', 'daily', 1.0),
            ('/blog', 'daily', 0.8),
            ('/privacy', 'monthly', 0.3),
            ('/terms', 'monthly', 0.3),
        ]
        
        # Add static pages
        for path, changefreq, priority in static_pages:
            url_elem = ET.SubElement(urlset, 'url')
            
            loc_elem = ET.SubElement(url_elem, 'loc')
            loc_elem.text = f'https://yourdomain.com{path}'
            
            lastmod_elem = ET.SubElement(url_elem, 'lastmod')
            lastmod_elem.text = now_iso
            
            changefreq_elem = ET.SubElement(url_elem, 'changefreq')
            changefreq_elem.text = changefreq
            
            priority_elem = ET.SubElement(url_elem, 'priority')
            priority_elem.text = str(priority)
        
        # Add blog posts
        blog_posts = BlogPost.query.filter_by(status='published').all()
        for post in blog_posts:
            url_elem = ET.SubElement(urlset, 'url')
            
            loc_elem = ET.SubElement(url_elem, 'loc')
            loc_elem.text = f'https://yourdomain.com/blog/{post.slug}'
            
            # Use post's last modified date
            lastmod = post.updated_at or post.published_at or post.created_at
            lastmod_iso = lastmod.astimezone(timezone.utc).replace(microsecond=0).isoformat().replace('+00:00', 'Z')
            
            lastmod_elem = ET.SubElement(url_elem, 'lastmod')
            lastmod_elem.text = lastmod_iso
            
            changefreq_elem = ET.SubElement(url_elem, 'changefreq')
            changefreq_elem.text = 'weekly'
            
            priority_elem = ET.SubElement(url_elem, 'priority')
            priority_elem.text = '0.6'
        
        # Convert to string
        xml_str = ET.tostring(urlset, encoding='unicode', method='xml')
        xml_str = '<?xml version="1.0" encoding="UTF-8"?>\n' + xml_str
        
        # Write to static file
        static_path = os.path.join('website', 'static', 'sitemap.xml')
        with open(static_path, 'w', encoding='utf-8') as f:
            f.write(xml_str)
        
        print(f"✅ Updated static sitemap with {len(static_pages)} static pages and {len(blog_posts)} blog posts")
        print(f"📁 Saved to: {static_path}")

if __name__ == '__main__':
    update_static_sitemap()
