# Legacy Letter - Production Ready

A Flask-based SaaS application for creating and scheduling legacy letters to be delivered after death verification.

## Features

- 📧 Email-based letter delivery system
- 🔐 Two-factor authentication (2FA)
- 👥 Trusted contact management
- 📁 Media attachments (images, videos, audio) via AWS S3
- 📝 Rich text editor for letter composition
- 🔔 Notification system
- 📰 Blog functionality
- 🔒 Death verification workflow

## Tech Stack

- **Backend**: Flask (Python)
- **Database**: PostgreSQL
- **Storage**: AWS S3
- **Authentication**: Flask-Login, PyOTP
- **Email**: Flask-Mail
- **Media Processing**: Pillow, OpenCV, MoviePy

## Production Setup

### Prerequisites

- Python 3.8+
- PostgreSQL database
- AWS S3 bucket
- SMTP email server

### Environment Variables

Create a `.env` file with the following variables:

```bash
# Flask
SECRET_KEY=your-secret-key-here
FLASK_ENV=production

# Database
DATABASE_URL=postgresql://user:password@host:port/database

# AWS S3
AWS_ACCESS_KEY_ID=your-aws-access-key
AWS_SECRET_ACCESS_KEY=your-aws-secret-key
AWS_REGION=your-region
S3_BUCKET=your-bucket-name

# Email
MAIL_SERVER=smtp.your-provider.com
MAIL_PORT=587
MAIL_USERNAME=your-email@domain.com
MAIL_PASSWORD=your-email-password

# Google OAuth (optional)
GOOGLE_CLIENT_ID=your-google-client-id
GOOGLE_CLIENT_SECRET=your-google-client-secret
```

### Installation

1. Clone the repository
2. Create a virtual environment:

   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. Install dependencies:

   ```bash
   pip install -r requirements.txt
   ```

4. Set up the database:

   ```bash
   flask db upgrade
   ```

5. Run the application:
   ```bash
   gunicorn -w 4 -b 0.0.0.0:8000 main:app
   ```

## Production Deployment

### Using Gunicorn (Recommended)

```bash
gunicorn -w 4 -b 0.0.0.0:8000 --timeout 120 main:app
```

### Using Docker (Optional)

```dockerfile
FROM python:3.9-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY . .
CMD ["gunicorn", "-w", "4", "-b", "0.0.0.0:8000", "main:app"]
```

## Scheduled Tasks

The application includes scheduled tasks that should be run via cron:

1. **Send Scheduled Letters**: `send_scheduled_letters.py`

   - Run daily to check and send scheduled letters

2. **Cleanup Expired Media**: `cleanup_expired_media.py`
   - Run daily to clean up temporary media files

Example crontab:

```bash
0 0 * * * cd /path/to/app && /path/to/venv/bin/python send_scheduled_letters.py
0 2 * * * cd /path/to/app && /path/to/venv/bin/python cleanup_expired_media.py
```

## Security Considerations

- Always use HTTPS in production
- Keep SECRET_KEY secure and random
- Use environment variables for sensitive data
- Enable 2FA for admin accounts
- Regularly update dependencies
- Monitor application logs
- Set up database backups
- Use AWS S3 bucket policies to restrict access

## Monitoring

- Check application logs regularly
- Monitor S3 storage usage
- Track email delivery rates
- Monitor database performance
- Set up uptime monitoring

## Support

For issues or questions, please contact the development team.

## License

Proprietary - All rights reserved
