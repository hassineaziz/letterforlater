# Setting Up Cron Job for Scheduled Letters

This document explains how to set up automated delivery of scheduled letters after death verification delays.

## Overview

When a user creates a letter with "after death verification" delivery and sets a delay (e.g., 1 week), the letter is scheduled for delivery after that delay period expires. A cron job needs to run periodically to check for and send these scheduled letters.

## Option 1: Using Cron (Linux/Mac)

### 1. Make the script executable

```bash
chmod +x send_scheduled_letters.py
```

### 2. Set up a cron job

Edit your crontab:

```bash
crontab -e
```

Add one of these lines depending on how frequently you want to check:

**Check every hour:**

```bash
0 * * * * cd /path/to/your/project && python3 send_scheduled_letters.py >> /var/log/scheduled_letters.log 2>&1
```

**Check every 15 minutes:**

```bash
*/15 * * * * cd /path/to/your/project && python3 send_scheduled_letters.py >> /var/log/scheduled_letters.log 2>&1
```

**Check daily at 9 AM:**

```bash
0 9 * * * cd /path/to/your/project && python3 send_scheduled_letters.py >> /var/log/scheduled_letters.log 2>&1
```

### 3. Monitor the logs

```bash
tail -f /var/log/scheduled_letters.log
```

## Option 2: Using Windows Task Scheduler

1. Open Task Scheduler
2. Create a new Basic Task
3. Set the trigger (e.g., daily at 9 AM)
4. Set the action to start a program: `python.exe`
5. Add arguments: `C:\path\to\your\project\send_scheduled_letters.py`
6. Set the start in: `C:\path\to\your\project`

## Option 3: Using Python Schedule Library

If you prefer to keep the task running within your Flask app, you can use the `schedule` library:

```bash
pip install schedule
```

Then add this to your main Flask app:

```python
import schedule
import time
import threading

def run_schedule():
    while True:
        schedule.run_pending()
        time.sleep(60)  # Check every minute

# Schedule the task to run every hour
schedule.every().hour.do(send_scheduled_letters_task)

# Start the scheduler in a separate thread
scheduler_thread = threading.Thread(target=run_schedule)
scheduler_thread.daemon = True
scheduler_thread.start()
```

## Testing

To test if the script works:

1. Create a letter with a 1-minute delay
2. Verify death (triggering the scheduling)
3. Wait for the delay to expire
4. Run the script manually:
   ```bash
   python3 send_scheduled_letters.py
   ```

## Troubleshooting

### Common Issues:

1. **Permission denied**: Make sure the script is executable
2. **Import errors**: Check that the project path is correct
3. **Database connection**: Ensure the database is accessible
4. **Email errors**: Check your email configuration

### Debug Mode:

You can add more verbose logging by modifying the script to include debug information:

```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

## Security Notes

- The cron job runs with the same permissions as the user who owns the crontab
- Ensure the script can't be modified by unauthorized users
- Consider running the cron job as a dedicated service user
- Log all activities for audit purposes

## Performance Considerations

- For high-volume systems, consider running the task less frequently
- Monitor database performance during letter processing
- Consider batching letters if you have many scheduled at once
- Monitor email sending limits from your email provider



