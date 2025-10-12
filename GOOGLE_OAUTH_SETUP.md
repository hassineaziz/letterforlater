# Google OAuth Setup Guide

## Overview

Your Legacy Letter application supports Google Sign-In/Sign-Up functionality. This guide will help you set up Google OAuth credentials properly.

## Step 1: Create Google OAuth Credentials

### 1. Go to Google Cloud Console

- Visit: https://console.cloud.google.com/
- Sign in with your Google account

### 2. Create a New Project (or select existing)

- Click "Select a project" → "New Project"
- Enter project name: "Legacy Letter"
- Click "Create"

### 3. Enable Google+ API

- Go to "APIs & Services" → "Library"
- Search for "Google+ API" or "Google Identity"
- Click on "Google+ API" → "Enable"

### 4. Create OAuth 2.0 Credentials

- Go to "APIs & Services" → "Credentials"
- Click "Create Credentials" → "OAuth 2.0 Client IDs"
- Choose "Web application"
- Enter name: "Legacy Letter Web Client"

### 5. Configure Authorized URLs

#### For Development:

```
Authorized JavaScript origins:
http://localhost:5001
http://127.0.0.1:5001

Authorized redirect URIs:
http://localhost:5001/auth/google/callback
http://127.0.0.1:5001/auth/google/callback
```

#### For Production:

```
Authorized JavaScript origins:
https://yourdomain.com
https://www.yourdomain.com

Authorized redirect URIs:
https://yourdomain.com/auth/google/callback
https://www.yourdomain.com/auth/google/callback
```

### 6. Get Your Credentials

- After creating, you'll get:
  - **Client ID**: `123456789-abcdefg.apps.googleusercontent.com`
  - **Client Secret**: `GOCSPX-abcdefghijklmnopqrstuvwxyz`

## Step 2: Configure Environment Variables

### Update your `.env` file:

```bash
# Google OAuth (Required for Google Sign-In)
GOOGLE_CLIENT_ID=123456789-abcdefg.apps.googleusercontent.com
GOOGLE_CLIENT_SECRET=GOCSPX-abcdefghijklmnopqrstuvwxyz
```

### For Production Deployment:

```bash
# Set environment variables on your server
export GOOGLE_CLIENT_ID="123456789-abcdefg.apps.googleusercontent.com"
export GOOGLE_CLIENT_SECRET="GOCSPX-abcdefghijklmnopqrstuvwxyz"
```

## Step 3: Test Google Authentication

### 1. Start your application:

```bash
python main.py
```

### 2. Test the flow:

- Go to `/login` or `/sign_up`
- Click "Sign in with Google" or "Sign up with Google"
- You should be redirected to Google's OAuth page
- After authorization, you'll be redirected back to your app

### 3. Check logs:

Look for these messages in your console:

```
🔍 Google OAuth URL: https://accounts.google.com/o/oauth2/v2/auth?...
🚀 Google callback route hit!
🔍 Google callback received code: abc123...
✅ User user@example.com logged in successfully with Google
```

## Step 4: Troubleshooting

### Common Issues:

#### 1. "redirect_uri_mismatch" Error

**Problem**: The redirect URI doesn't match what's configured in Google Console
**Solution**:

- Check your Google Console settings
- Ensure the URL matches exactly (including http/https, port, trailing slashes)
- For development, use `localhost` not `127.0.0.1`

#### 2. "invalid_client" Error

**Problem**: Client ID or Secret is incorrect
**Solution**:

- Double-check your environment variables
- Ensure no extra spaces or quotes
- Verify the credentials in Google Console

#### 3. "access_denied" Error

**Problem**: User denied permission or app not verified
**Solution**:

- For development: This is normal, users can still proceed
- For production: You may need to verify your app with Google

#### 4. Callback URL Not Working

**Problem**: The callback route isn't being hit
**Solution**:

- Check your Flask routes
- Verify the URL pattern matches: `/auth/google/callback`
- Test with: `http://localhost:5001/auth/google/test`

### Debug Mode:

Add this to your `.env` for debugging:

```bash
FLASK_DEBUG=True
```

## Step 5: Production Considerations

### 1. App Verification (Optional but Recommended)

For production apps with many users, consider:

- Submitting your app for Google verification
- This removes the "unverified app" warning
- Required for apps with >100 users

### 2. Security Best Practices

- Never commit credentials to version control
- Use environment variables
- Rotate credentials regularly
- Monitor OAuth usage in Google Console

### 3. Monitoring

- Check Google Cloud Console for usage statistics
- Monitor failed authentication attempts
- Set up alerts for unusual activity

## Step 6: User Experience

### What Users See:

1. **Login/Signup Page**: Google button with proper branding
2. **Google OAuth Page**: Standard Google authorization screen
3. **Return to App**: Automatic login after authorization
4. **Account Creation**: New users are automatically created
5. **Existing Users**: Existing users are logged in

### User Data Retrieved:

- Email address
- Full name
- Profile picture (if available)
- Google ID (for account linking)

## Step 7: Database Schema

The application automatically handles Google users:

```python
# User model includes these fields for Google OAuth:
google_id = db.Column(db.String(100), unique=True, nullable=True)
is_google_user = db.Column(db.Boolean, default=False)
```

### User Flow:

1. **New Google User**: Account created with Google ID
2. **Existing Google User**: Logged in using Google ID
3. **Email Match**: If email exists, account is linked to Google

## Step 8: Testing Checklist

- [ ] Google OAuth credentials created
- [ ] Environment variables set correctly
- [ ] Authorized URLs configured
- [ ] Login page shows Google button
- [ ] Signup page shows Google button
- [ ] Google OAuth flow works
- [ ] Callback redirects properly
- [ ] User account created/logged in
- [ ] No console errors
- [ ] Works in both development and production

## Support

If you encounter issues:

1. Check the Flask console logs
2. Verify Google Console settings
3. Test with a simple OAuth flow
4. Check network connectivity
5. Verify environment variables

## Security Notes

- Google OAuth is secure and handles authentication
- No passwords are stored for Google users
- User data is minimal (email, name, profile)
- All OAuth flows use HTTPS in production
- Tokens are handled securely by Google

---

**Last Updated**: $(date)
**Status**: Production Ready ✅
