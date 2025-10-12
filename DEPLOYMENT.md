# Production Deployment Checklist

## Pre-Deployment

### 1. Environment Setup

- [ ] Create `.env` file from `env.example`
- [ ] Set strong SECRET_KEY (use `python -c "import secrets; print(secrets.token_hex(32))"`)
- [ ] Configure DATABASE_URL with production PostgreSQL
- [ ] Set up AWS S3 credentials
- [ ] Configure SMTP email settings
- [ ] Set FLASK_ENV=production
- [ ] **Configure Google OAuth credentials** (see GOOGLE_OAUTH_SETUP.md)

### 2. Database Setup

- [ ] Create production PostgreSQL database
- [ ] Run migrations: `flask db upgrade`
- [ ] Create admin user (use a secure script, not the deleted ensure_admin.py)
- [ ] Set up database backups

### 3. AWS S3 Setup

- [ ] Create S3 bucket
- [ ] Configure bucket permissions
- [ ] Set up CORS policy
- [ ] Enable versioning (optional)
- [ ] Set up lifecycle policies for temp files

### 4. Security

- [ ] Change default SECRET_KEY
- [ ] Remove hardcoded credentials from code
- [ ] Enable HTTPS/SSL
- [ ] Set up firewall rules
- [ ] Configure CORS properly
- [ ] Enable 2FA for admin accounts

## Deployment Steps

### 1. Server Setup

```bash
# Update system
sudo apt update && sudo apt upgrade -y

# Install Python and dependencies
sudo apt install python3-pip python3-venv postgresql-client -y

# Install nginx (if using as reverse proxy)
sudo apt install nginx -y
```

### 2. Application Setup

```bash
# Clone repository
git clone <your-repo-url>
cd legacy-letter

# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Set up environment variables
cp env.example .env
nano .env  # Edit with production values
```

### 3. Database Migration

```bash
# Run migrations
flask db upgrade

# Verify database connection
python -c "from website import create_app; app = create_app(); print('Database connected!')"
```

### 4. Start Application

```bash
# Using gunicorn (recommended)
gunicorn -w 4 -b 0.0.0.0:8000 --timeout 120 wsgi:app

# Or using systemd service (see below)
```

### 5. Set Up Systemd Service

Create `/etc/systemd/system/legacy-letter.service`:

```ini
[Unit]
Description=Legacy Letter Application
After=network.target

[Service]
User=www-data
Group=www-data
WorkingDirectory=/path/to/legacy-letter
Environment="PATH=/path/to/legacy-letter/venv/bin"
ExecStart=/path/to/legacy-letter/venv/bin/gunicorn -w 4 -b 127.0.0.1:8000 --timeout 120 wsgi:app
Restart=always

[Install]
WantedBy=multi-user.target
```

Enable and start:

```bash
sudo systemctl enable legacy-letter
sudo systemctl start legacy-letter
sudo systemctl status legacy-letter
```

### 6. Configure Nginx (Reverse Proxy)

Create `/etc/nginx/sites-available/legacy-letter`:

```nginx
server {
    listen 80;
    server_name your-domain.com;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;

        # Increase timeout for media uploads
        proxy_read_timeout 300;
        proxy_connect_timeout 300;
        proxy_send_timeout 300;
    }

    # Increase max upload size
    client_max_body_size 100M;
}
```

Enable site:

```bash
sudo ln -s /etc/nginx/sites-available/legacy-letter /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl restart nginx
```

### 7. Set Up SSL with Let's Encrypt

```bash
sudo apt install certbot python3-certbot-nginx -y
sudo certbot --nginx -d your-domain.com
```

### 8. Configure Cron Jobs

```bash
crontab -e
```

Add these lines:

```bash
# Send scheduled letters daily at midnight
0 0 * * * cd /path/to/legacy-letter && /path/to/venv/bin/python send_scheduled_letters.py >> /var/log/legacy-letter/cron.log 2>&1

# Cleanup expired media daily at 2 AM
0 2 * * * cd /path/to/legacy-letter && /path/to/venv/bin/python cleanup_expired_media.py >> /var/log/legacy-letter/cleanup.log 2>&1
```

## Post-Deployment

### 1. Testing

- [ ] Test user registration
- [ ] Test login/logout
- [ ] Test 2FA
- [ ] Test letter creation
- [ ] Test media upload to S3
- [ ] Test email sending
- [ ] Test scheduled letters
- [ ] Test death verification workflow
- [ ] **Test Google Sign-In/Sign-Up** (see GOOGLE_OAUTH_SETUP.md)

### 2. Monitoring Setup

- [ ] Set up application logging
- [ ] Configure log rotation
- [ ] Set up uptime monitoring (UptimeRobot, Pingdom)
- [ ] Monitor S3 storage usage
- [ ] Monitor database size
- [ ] Set up error tracking (Sentry, optional)

### 3. Backup Strategy

- [ ] Set up automated database backups
- [ ] Configure S3 bucket versioning
- [ ] Test backup restoration
- [ ] Document backup procedures

### 4. Performance Optimization

- [ ] Enable gzip compression in nginx
- [ ] Set up CDN for static assets (optional)
- [ ] Configure database connection pooling
- [ ] Enable browser caching
- [ ] Optimize media file sizes

## Maintenance

### Regular Tasks

- Weekly: Check application logs
- Weekly: Monitor disk space
- Monthly: Review S3 storage costs
- Monthly: Update dependencies (security patches)
- Quarterly: Test backup restoration
- Quarterly: Review and optimize database

### Updating Application

```bash
# Pull latest changes
git pull origin main

# Activate virtual environment
source venv/bin/activate

# Install/update dependencies
pip install -r requirements.txt

# Run migrations
flask db upgrade

# Restart application
sudo systemctl restart legacy-letter
```

## Troubleshooting

### Application won't start

- Check logs: `sudo journalctl -u legacy-letter -n 50`
- Verify environment variables in `.env`
- Check database connection
- Verify S3 credentials

### Email not sending

- Check SMTP credentials
- Verify firewall allows outbound SMTP
- Check email logs
- Test with a simple email script

### Media upload failing

- Check S3 credentials
- Verify bucket permissions
- Check file size limits
- Review nginx client_max_body_size

### Database connection errors

- Verify DATABASE_URL
- Check PostgreSQL is running
- Verify network connectivity
- Check database user permissions

## Security Best Practices

1. **Never commit sensitive data** to version control
2. **Use strong passwords** for all accounts
3. **Keep dependencies updated** regularly
4. **Monitor logs** for suspicious activity
5. **Enable 2FA** for all admin accounts
6. **Use HTTPS** everywhere
7. **Regular backups** are essential
8. **Limit S3 bucket access** with proper IAM policies
9. **Use environment variables** for all secrets
10. **Regular security audits** of the application

## Support

For issues during deployment, check:

- Application logs: `/var/log/legacy-letter/`
- System logs: `sudo journalctl -u legacy-letter`
- Nginx logs: `/var/log/nginx/error.log`
- Database logs: PostgreSQL logs

## Production URLs

- Application: https://your-domain.com
- Admin Panel: https://your-domain.com/admin (if applicable)
- API Documentation: (if applicable)
