#!/bin/bash
# Set your domain for sitemap generation
# Run this once to configure your domain

echo "Setting up sitemap for letterforlater.com..."

# Create a simple config file
cat > sitemap_config.txt << EOF
SITE_DOMAIN=https://letterforlater.com
EOF

echo "✅ Domain configured!"
echo "📁 Configuration saved to: sitemap_config.txt"
echo ""
echo "🚀 To update sitemap with your domain:"
echo "   SITE_DOMAIN=https://letterforlater.com python update_sitemap.py"
echo ""
echo "🔧 Or add to your .env file:"
echo "   SITE_DOMAIN=https://letterforlater.com"
