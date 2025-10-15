"""
Configuration for sitemap pages
Add new pages here to automatically include them in the sitemap
"""

# Define your public pages here
# Format: (endpoint, params, changefreq, priority)
SITEMAP_PAGES = [
    ('views.home', {}, 'daily', 1.0),
    ('views.blog_index', {}, 'daily', 0.8),
    ('pricing.pricing_page', {}, 'weekly', 0.7),
    ('views.privacy_policy', {}, 'monthly', 0.3),
    ('views.terms_of_service', {}, 'monthly', 0.3),
    # Add new pages here:
    # ('your_blueprint.your_route', {}, 'weekly', 0.6),
]

def get_sitemap_pages():
    """Get configured sitemap pages"""
    return SITEMAP_PAGES
