#!/bin/bash
# Quick script to nuke the spammer

echo "🚨 NUKE SPAMMER SCRIPT"
echo "======================"
echo ""
echo "This will delete ALL 1396 spam accounts from IP 49.204.141.33"
echo ""

read -p "Are you sure? Type 'YES' to continue: " confirm

if [ "$confirm" != "YES" ]; then
    echo "Cancelled."
    exit 1
fi

echo ""
echo "Starting cleanup..."
cd ~/letterforlater
source venv/bin/activate

# Delete all accounts from the spammer IP
python cleanup_spam_accounts.py --delete-all-from-ip 49.204.141.33

echo ""
echo "✅ Done! Spammer accounts deleted and IP blocked."

