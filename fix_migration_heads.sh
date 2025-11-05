#!/bin/bash
# Script to fix multiple migration heads issue

echo "Checking migration heads..."
flask db heads

echo ""
echo "If you see multiple heads, we need to merge them."
echo "Listing all heads:"
flask db heads

echo ""
echo "To fix this, you can:"
echo "1. Check what the current database revision is:"
echo "   flask db current"
echo ""
echo "2. If there are multiple heads, merge them:"
echo "   flask db merge heads -m 'merge_migration_heads'"
echo ""
echo "3. Then upgrade:"
echo "   flask db upgrade"
echo ""

