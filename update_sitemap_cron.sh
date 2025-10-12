#!/bin/bash
# Cron job to automatically update sitemap every hour
# Add this to your crontab: 0 * * * * /path/to/update_sitemap_cron.sh

cd /Users/aziz/Desktop/legacy-letter
SITE_DOMAIN=https://letterforlater.com python update_sitemap.py >> /var/log/sitemap_update.log 2>&1
