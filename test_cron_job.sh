#!/bin/bash
# Quick test script for cron job
# Run this on your production server

echo "============================================"
echo "Testing Scheduled Letter Cron Job"
echo "============================================"

echo ""
echo "1. Checking cron job setup..."
crontab -l | grep send_scheduled_letters

echo ""
echo "2. Checking log directory..."
mkdir -p /var/log/letterforlater
ls -la /var/log/letterforlater/ 2>/dev/null || echo "Log directory doesn't exist yet"

echo ""
echo "3. Checking cron service..."
systemctl is-active cron > /dev/null 2>&1 && echo "✓ Cron service is running" || echo "✗ Cron service is not running"

echo ""
echo "4. Testing script execution..."
cd /root/letterforlater && /root/letterforlater/venv/bin/python send_scheduled_letters.py

echo ""
echo "5. Checking log file..."
if [ -f /var/log/letterforlater/cron.log ]; then
    echo "✓ Log file exists"
    echo "Last 10 lines of log:"
    tail -n 10 /var/log/letterforlater/cron.log
else
    echo "✗ Log file doesn't exist yet (will be created when cron runs)"
fi

echo ""
echo "6. Next cron execution times (next 3 runs):"
for i in {0..2}; do
    minute=$((($(date +%M) / 15 + 1 + $i) * 15 % 60))
    hour=$(date +%H)
    if [ $minute -ge 60 ]; then
        minute=0
        hour=$((hour + 1))
    fi
    printf "  Run %d: At %02d:%02d\n" $((i+1)) $hour $minute
done

echo ""
echo "============================================"
echo "To monitor in real-time:"
echo "  tail -f /var/log/letterforlater/cron.log"
echo "============================================"

