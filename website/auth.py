from flask import Blueprint, render_template, request, flash, redirect, url_for, session
from .models import User, TrustedContact, DeathVerification, Letter, NewsletterSubscriber
from werkzeug.security import generate_password_hash, check_password_hash
from . import db   ##means from __init__.py import db
from flask_login import login_user, login_required, logout_user, current_user
from .blocking import get_client_ip
import uuid
from datetime import datetime, timedelta, timezone
from . import mail
from flask_mail import Message
from markupsafe import Markup
from .email_rate_limit import safe_send_email
import pyotp
import qrcode
import base64
import io
import secrets
import os
import requests


auth = Blueprint('auth', __name__)

def verify_turnstile_token(token, client_ip=None):
    """
    Verify Cloudflare Turnstile token with Cloudflare's API
    
    Args:
        token: The Turnstile token from the client
        client_ip: Optional client IP address for verification
    
    Returns:
        tuple: (is_valid: bool, error_message: str)
    """
    # Skip verification if Turnstile site key is not configured or is a placeholder
    turnstile_site_key = os.getenv('TURNSTILE_SITE_KEY')
    if not turnstile_site_key or turnstile_site_key.startswith('your-'):
        # No real site key, assume Turnstile not in use
        return True, None
        
    turnstile_secret = os.getenv('TURNSTILE_SECRET_KEY')
    if not turnstile_secret:
        # If Turnstile is not configured, skip verification (for development)
        print("[TURNSTILE] Warning: TURNSTILE_SECRET_KEY not set, skipping verification")
        return True, None

    # Check if we're in local development
    is_local = False
    if client_ip in ['127.0.0.1', '::1', 'localhost']:
        is_local = True
    elif os.getenv('FLASK_DEBUG') == '1' or os.getenv('FLASK_ENV') == 'development':
        is_local = True

    if not token or token == 'not-configured':
        if is_local:
            print("[TURNSTILE] Local development detected: Skipping verification for missing token.")
            return True, None
        else:
            # In production, a missing token is a security failure (bot attempt or bypassed frontend)
            return False, "Security verification token is missing. Please complete the security check."
    
    try:
        # Cloudflare Turnstile verification endpoint
        verify_url = "https://challenges.cloudflare.com/turnstile/v0/siteverify"
        
        data = {
            'secret': turnstile_secret,
            'response': token
        }
        
        # Include client IP if provided (recommended by Cloudflare)
        if client_ip:
            data['remoteip'] = client_ip
        
        response = requests.post(verify_url, data=data, timeout=10)
        result = response.json()
        
        if result.get('success'):
            return True, None
        else:
            error_codes = result.get('error-codes', [])
            error_msg = f"Turnstile verification failed: {', '.join(error_codes)}"
            print(f"[TURNSTILE] Verification failed: {error_msg}")
            return False, error_msg
            
    except requests.exceptions.RequestException as e:
        print(f"[TURNSTILE] Error verifying token: {str(e)}")
        # On network error, we fail closed in production, but open in development
        if is_local:
            print("[TURNSTILE] Network error on localhost, failing open.")
            return True, None
        return False, f"Error verifying Turnstile token: {str(e)}"
    except Exception as e:
        print(f"[TURNSTILE] Unexpected error: {str(e)}")
        if is_local:
            return True, None
        return False, f"Unexpected error during verification: {str(e)}"

def send_confirmation_email(user):
    """Helper function to send email confirmation email to a user"""
    try:
        # Generate token
        confirm_token = str(uuid.uuid4())
        user.password_reset_token = confirm_token
        user.password_reset_expires = datetime.now(timezone.utc) + timedelta(hours=48)
        db.session.commit()
        
        # Generate new confirmation token
        confirm_token = str(uuid.uuid4())
        user.password_reset_token = confirm_token
        user.password_reset_expires = datetime.now(timezone.utc) + timedelta(hours=48)
        db.session.commit()

        # Send confirmation email
        confirm_link = url_for('auth.confirm_email', token=confirm_token, _external=True)
        msg = Message(
            'Confirm your LetterForLater account',
            recipients=[user.email],
            sender=os.getenv('MAIL_USERNAME', 'support@letterforlater.com')
        )
        
        # Render HTML template
        user_name = user.first_name + (" " + user.last_name if user.last_name else "")
        msg.html = render_template('emails/email_confirmation.html',
            user_name=user_name,
            user_email=user.email,
            confirm_link=confirm_link,
            confirm_url=confirm_link
        )
        
        # Render text template
        msg.body = render_template('emails/email_confirmation.txt',
            user_name=user_name,
            user_email=user.email,
            confirm_link=confirm_link,
            confirm_url=confirm_link
        )
        
        # Use rate-limited email sending
        success = safe_send_email(msg, email_type='confirmation')
        if success:
            print(f"✅ Confirmation email sent successfully to {user.email}")
            return True
        else:
            print(f"❌ Failed to send confirmation email to {user.email} - check logs above for details (rate limited, SMTP error, or blocked)")
            db.session.rollback()
            return False
    except Exception as e:
        print(f"❌ Exception in send_confirmation_email for {user.email}: {str(e)}")
        import traceback
        traceback.print_exc()
        db.session.rollback()
        return False

@auth.context_processor
def utility_processor():
    """Make utility functions available to all templates"""
    def check_trusted_contact_status(user):
        """Check if user has active trusted contact relationships"""
        if not user or not user.is_authenticated:
            return False
        from .views import has_active_trusted_relationships
        return has_active_trusted_relationships(user)
    
    return dict(check_trusted_contact_status=check_trusted_contact_status)


@auth.route('/login', methods=['GET', 'POST'])
def login():
    # Get client IP for logging
    client_ip = get_client_ip()
    
    if current_user.is_authenticated:
        return redirect(url_for('views.home'))
    next_page = request.args.get('next')
    if request.method == 'POST':
        # Rate limit login attempts (prevent brute force)
        from datetime import timedelta
        five_minutes_ago = datetime.now(timezone.utc) - timedelta(minutes=5)
        
        # Count failed login attempts from this IP in last 5 minutes
        # (We'll track this by checking recent login activity - if user doesn't exist or password wrong)
        # For now, we'll add rate limiting after checking credentials
        
        email = request.form.get('email')
        password = request.form.get('password')
        next_page = request.form.get('next') or next_page
        user = User.query.filter_by(email=email).first()
        if user:
            if not user.password:
                if user.is_google_user:
                    flash('This account was created using Google. Please log in using the "Sign in with Google" button.', 'error')
                else:
                    flash('No password set for this account. Please sign in with Google or reset your password.', 'error')
                return render_template("login.html", user=current_user, next=next_page)
                
            # Check password first to provide better feedback for inactive accounts
            if check_password_hash(user.password, password):
                # Check if user account is suspended/deactivated
                if not user.is_active:
                    # Check if it's email confirmation or account suspension
                    if user.password_reset_token and user.password_reset_expires and user.password_reset_expires > datetime.now(timezone.utc):
                        resend_link = url_for('auth.resend_verification')
                        flash(Markup('Please check your email and click the confirmation link to activate your account. If you didn\'t receive the email, <a href="{}" class="underline font-semibold">click here to resend the verification email</a>.'.format(resend_link)), 'error')
                        return render_template("login.html", user=current_user, next=next_page)
                    else:
                        # Offer reactivation for deactivated accounts
                        session['pending_reactivation_user_id'] = user.id
                        return redirect(url_for('auth.reactivate_account'))
                
                # Password is correct and account is active, proceed to login or 2FA
                if user.two_factor_enabled:
                    # Store login info in session for 2FA verification
                    client_ip = get_client_ip()
                    session['pending_2fa_user_id'] = user.id
                    session['pending_2fa_next'] = next_page
                    session['pending_2fa_remember'] = True
                    session['pending_2fa_time'] = datetime.now(timezone.utc).timestamp()
                    session['pending_2fa_ip'] = client_ip
                    return redirect(url_for('auth.login_2fa'))
                else:
                    # No 2FA, proceed with normal login
                    client_ip = get_client_ip()
                    user.last_login_ip = client_ip
                    user.last_login_date = datetime.now(timezone.utc)
                    db.session.commit()
                    
                    login_user(user, remember=True)
                    
                    # Check for pending letter invites
                    from .models import RecipientInvite
                    pending_invites = RecipientInvite.query.filter(
                        RecipientInvite.recipient_email == user.email,
                        RecipientInvite.registered_at.is_(None)
                    ).all()
                    
                    if pending_invites:
                        for invite in pending_invites:
                            invite.recipient_user_id = user.id
                            invite.registered_at = datetime.now(timezone.utc)
                        db.session.commit()
                        flash(f'Welcome back! You have {len(pending_invites)} new letter(s) to read.', 'success')
                    
                    # Check for pending trusted contact invitation
                    contact = TrustedContact.query.filter_by(email=user.email, is_confirmed=False).first()
                    if contact:
                        session['pending_trusted_contact_code'] = contact.confirmation_code
                    
                    # Check for intended plan upgrade
                    intended_plan = session.get('intended_plan')
                    user_email = session.get('user_email')
                    if intended_plan and intended_plan != 'free' and user_email == user.email:
                        session.pop('intended_plan', None)
                        session.pop('intended_cycle', None)
                        session.pop('user_email', None)
                        flash(f'Welcome! You signed up for {intended_plan.title()} plan. Complete your upgrade to unlock all features!', 'info')
                        return redirect(url_for('pricing.pricing_page'))
                    
                    flash('Logged in successfully!', category='success')
                    return redirect(next_page or url_for('views.home'))
            else:
                # Incorrect password
                flash('Incorrect password, try again.', 'error')
                return render_template("login.html", user=current_user, next=next_page)
        else:
            flash('Email does not exist.', 'error')
            return render_template("login.html", user=current_user, next=next_page)
    return render_template("login.html", user=current_user, next=next_page)

@auth.route('/login-2fa', methods=['GET', 'POST'])
def login_2fa():
    # Check if we have a pending 2FA login
    pending_user_id = session.get('pending_2fa_user_id')
    pending_2fa_time = session.get('pending_2fa_time')
    
    if not pending_user_id or not pending_2fa_time:
        flash('No pending login found.', 'error')
        return redirect(url_for('auth.login'))
    
    # Check if 2FA session has expired (15 minutes)
    if datetime.now(timezone.utc).timestamp() - pending_2fa_time > 900:  # 15 minutes
        session.pop('pending_2fa_user_id', None)
        session.pop('pending_2fa_next', None)
        session.pop('pending_2fa_remember', None)
        session.pop('pending_2fa_time', None)
        flash('2FA session expired. Please login again.', 'error')
        return redirect(url_for('auth.login'))
    
    user = User.query.get(pending_user_id)
    if not user or not user.two_factor_enabled:
        flash('Invalid 2FA login request.', 'error')
        session.pop('pending_2fa_user_id', None)
        session.pop('pending_2fa_next', None)
        session.pop('pending_2fa_remember', None)
        session.pop('pending_2fa_time', None)
        return redirect(url_for('auth.login'))
    
    if request.method == 'POST':
        code = request.form.get('code')
        backup_code = request.form.get('backup_code')
        
        if backup_code:
            # Verify backup code
            if user.backup_codes and backup_code in user.backup_codes:
                # Remove used backup code
                user.backup_codes.remove(backup_code)
                
                # Log IP address and login date
                client_ip = session.get('pending_2fa_ip') or get_client_ip()
                user.last_login_ip = client_ip
                user.last_login_date = datetime.now(timezone.utc)
                db.session.commit()
                
                # Complete login
                login_user(user, remember=session.get('pending_2fa_remember', True))
                
                # Check for pending letter invites for this email
                from .models import RecipientInvite
                pending_invites = RecipientInvite.query.filter(
                    RecipientInvite.recipient_email == user.email,
                    RecipientInvite.registered_at.is_(None)
                ).all()
                
                if pending_invites:
                    # Link all pending invites to this user
                    for invite in pending_invites:
                        invite.recipient_user_id = user.id
                        invite.registered_at = datetime.now(timezone.utc)
                    db.session.commit()
                    flash(f'Welcome back! You have {len(pending_invites)} new letter(s) to read.', 'success')
                
                # Clear session
                next_page = session.pop('pending_2fa_next', None)
                session.pop('pending_2fa_user_id', None)
                session.pop('pending_2fa_remember', None)
                session.pop('pending_2fa_time', None)
                
                if not pending_invites:
                    flash('Logged in successfully using backup code!', 'success')
                return redirect(next_page or url_for('views.home'))
            else:
                flash('Invalid backup code.', 'error')
        elif code:
            # Verify TOTP code
            if user.two_factor_secret:
                totp = pyotp.TOTP(user.two_factor_secret)
                if totp.verify(code):
                    # Log IP address and login date
                    client_ip = session.get('pending_2fa_ip') or get_client_ip()
                    user.last_login_ip = client_ip
                    user.last_login_date = datetime.now(timezone.utc)
                    db.session.commit()
                    
                    # Complete login
                    login_user(user, remember=session.get('pending_2fa_remember', True))
                    
                    # Check for pending letter invites for this email
                    from .models import RecipientInvite
                    pending_invites = RecipientInvite.query.filter(
                        RecipientInvite.recipient_email == user.email,
                        RecipientInvite.registered_at.is_(None)
                    ).all()
                    
                    if pending_invites:
                        # Link all pending invites to this user
                        for invite in pending_invites:
                            invite.recipient_user_id = user.id
                            invite.registered_at = datetime.now(timezone.utc)
                        db.session.commit()
                        flash(f'Welcome back! You have {len(pending_invites)} new letter(s) to read.', 'success')
                    
                    # Clear session
                    next_page = session.pop('pending_2fa_next', None)
                    session.pop('pending_2fa_user_id', None)
                    session.pop('pending_2fa_remember', None)
                    session.pop('pending_2fa_time', None)
                    
                    if not pending_invites:
                        flash('Logged in successfully!', 'success')
                    return redirect(next_page or url_for('views.home'))
                else:
                    flash('Invalid verification code.', 'error')
            else:
                flash('Two-factor authentication is not properly configured.', 'error')
        else:
            flash('Please enter a verification code or backup code.', 'error')
    
    return render_template('login_2fa.html', user=user)


@auth.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('auth.login'))


@auth.route('/sign-up', methods=['GET', 'POST'])
def sign_up():

    
    # Get client IP for logging
    client_ip = get_client_ip()
    
    # Get Turnstile site key for template
    turnstile_site_key = os.getenv('TURNSTILE_SITE_KEY', '')
    
    # Spam prevention checks
    if request.method == 'POST':
        # Verify Cloudflare Turnstile token
        turnstile_token = request.form.get('cf-turnstile-response', '')
        is_turnstile_valid, turnstile_error = verify_turnstile_token(turnstile_token, client_ip)
        if not is_turnstile_valid:
            print(f"[TURNSTILE] BLOCKED signup attempt - Turnstile verification failed. IP: {client_ip}, Error: {turnstile_error}")
            flash('Security verification failed. Please try again.', 'error')
            return render_template("sign_up.html", user=current_user, turnstile_site_key=turnstile_site_key)

    
    if current_user.is_authenticated:
        return redirect(url_for('views.home'))
    
    # Get plan parameter from URL
    selected_plan = request.args.get('plan', 'free')
    cycle = request.args.get('cycle', 'month')
    
    # Validate plan parameter
    if selected_plan not in ['free', 'premium', 'lifetime']:
        selected_plan = 'free'
    
    next_page = request.args.get('next')
    if request.method == 'POST':
        email = request.form.get('email')
        first_name = request.form.get('firstName')
        last_name = request.form.get('lastName', '').strip()  # Get last name, default to empty string and strip whitespace
        password1 = request.form.get('password1')
        intended_plan = request.form.get('intended_plan', 'free')
        intended_cycle = request.form.get('intended_cycle', 'month')
        next_page = request.form.get('next') or next_page
        user = User.query.filter_by(email=email).first()
        if user:
            flash('Email already exists.', category='error')
        elif len(email) < 4:
            flash('Email must be greater than 3 characters.', category='error')
        elif len(first_name) < 2:
            flash('First name must be greater than 1 character.', category='error')
        elif last_name and len(last_name) < 2:
            flash('Last name must be greater than 1 character if provided.', category='error')
        elif len(password1) < 7:
            flash('Password must be at least 7 characters.', category='error')
        else:
            # Validate email: check disposable domains and MX records
            from .email_validation import validate_email
            email_valid, email_error = validate_email(email, check_mx=True)
            if not email_valid:
                print(f"[EMAIL VALIDATION] Rejected email {email}: {email_error}")
                flash(email_error or 'Invalid email address. Please use a valid email address.', category='error')
                return render_template("sign_up.html", user=current_user, turnstile_site_key=turnstile_site_key)
            
            # Continue with signup
            # Get IP address for registration
            client_ip = get_client_ip()
            
            # AUTOMATIC SPAM PATTERN DETECTION & SUBNET BLOCKING
            from .spam_detection import detect_spam_pattern
            from .blocking import block_ip_subnet
            
            is_spam, spam_reason, confidence = detect_spam_pattern(email, first_name, last_name, client_ip)
            if is_spam:
                print(f"[AUTOMATIC SPAM BLOCK] Blocked registration. Email: {email}, Name: {first_name} {last_name}, IP: {client_ip}, Reason: {spam_reason} (confidence: {confidence})")
                
                # Automatically block their entire IP subnet
                block_ip_subnet(client_ip, reason=f"Automatic spam blocking: {spam_reason} (Email: {email}, Name: {first_name} {last_name})")
                
                # Render the sign-up page with a generic security failure to not leak detection details
                flash('Security verification failed. Please try again.', 'error')
                return render_template("sign_up.html", user=current_user, turnstile_site_key=turnstile_site_key)
            

            

            
            new_user = User(
                email=email,
                first_name=first_name,
                last_name=last_name,
                password=generate_password_hash(password1, method='pbkdf2:sha256'),
                plan='free',  # Always start with free plan
                subscription_cycle=intended_cycle if intended_plan == 'premium' else None,
                notification_preferences={'email_notifications': True},
                delivery_preferences={'delivery_method': 'email'},
                is_active=False,
                marketing_consent=(request.form.get('marketing_consent') == 'yes'),
                registration_ip=client_ip
            )
            db.session.add(new_user)
            db.session.commit()
            


            # If marketing consent given, add/update newsletter subscriber
            if new_user.marketing_consent:
                subscriber = NewsletterSubscriber.query.filter_by(email=email).first()
                if not subscriber:
                    subscriber = NewsletterSubscriber(
                        email=email,
                        status='subscribed',
                        source='signup_form'
                    )
                    db.session.add(subscriber)
                else:
                    subscriber.status = 'subscribed'
                    if not subscriber.source:
                        subscriber.source = 'signup_form'
                db.session.commit()

            # Store intended plan in session for post-signup upgrade flow
            session['intended_plan'] = intended_plan
            session['intended_cycle'] = intended_cycle
            session['user_email'] = email
            
            # Check for pending letter data from landing page hero section
            # The letter data is stored with the email as key
            pending_letter_data = session.get(f'pending_hero_letter_data_{email}')
            if pending_letter_data:
                # Store with user email for later retrieval after email confirmation
                session[f'pending_hero_letter_data_for_user_{email}'] = pending_letter_data
                session.pop(f'pending_hero_letter_data_{email}', None)

            # Check if this is a trusted contact signup
            trusted_contact_code = session.get('trusted_contact_code')
            if trusted_contact_code:
                contact = TrustedContact.query.filter_by(confirmation_code=trusted_contact_code).first()
                if contact and contact.email == email:
                    # Confirm the trusted contact
                    contact.is_confirmed = True
                    
                    # Create death verification record for pending letters
                    pending_letters = Letter.query.filter(
                        Letter.user_id == contact.user_id,
                        Letter.status == 'pending_verification'
                    ).all()
                    
                    for letter in pending_letters:
                        # Check if death verification record already exists
                        existing_verification = DeathVerification.query.filter_by(
                            user_id=contact.user_id,
                            status='pending'
                        ).first()
                        
                        if not existing_verification:
                            death_verification = DeathVerification(
                                user_id=contact.user_id,
                                confirmations_count=0,
                                status='pending',
                                verification_code=str(uuid.uuid4())
                            )
                            db.session.add(death_verification)
                    
                    db.session.commit()
                    session.pop('trusted_contact_code', None)
                    # Don't auto-login trusted contacts, let them login manually
                    flash('Account created successfully! Your trusted contact role has been confirmed. Please login to access your features.', category='success')
                    return redirect(url_for('auth.login'))

            # Send confirmation email using helper function
            send_confirmation_email(new_user)
            
            flash("Account created! Please check your email to confirm your account (don't forget to check your spam folder).", category='success')
            return redirect(url_for('auth.login', next=next_page))

    # If this is a trusted contact signup, pre-fill the email
    trusted_contact_code = session.get('trusted_contact_code')
    email = request.args.get('email')  # Get email from URL if coming from landing page
    is_trusted_contact_signup = False
    from_landing = request.args.get('from_landing') == 'true' or bool(email and not trusted_contact_code)
    
    if trusted_contact_code:
        contact = TrustedContact.query.filter_by(confirmation_code=trusted_contact_code).first()
        if contact:
            email = contact.email
            is_trusted_contact_signup = True

    return render_template("sign_up.html", user=current_user, email=email, next=next_page, selected_plan=selected_plan, cycle=cycle, turnstile_site_key=turnstile_site_key, is_trusted_contact_signup=is_trusted_contact_signup, from_landing=from_landing)

@auth.route('/sign-up-with-invite/<token>', methods=['GET', 'POST'])
def sign_up_with_invite(token):
    """Sign up using an invite token from a letter delivery"""
    # Get client IP for logging
    client_ip = get_client_ip()
    
    if current_user.is_authenticated:
        return redirect(url_for('views.received_letters'))
    
    # Validate the invite token
    from .models import RecipientInvite
    invite = RecipientInvite.query.filter_by(invite_token=token).first()
    
    if not invite:
        flash('Invalid or expired invite link.', 'error')
        return redirect(url_for('auth.sign_up'))
    
    if invite.is_registered():
        flash('This invite has already been used.', 'error')
        return redirect(url_for('auth.login'))
    
    if request.method == 'POST':
        email = request.form.get('email')
        first_name = request.form.get('firstName')
        last_name = request.form.get('lastName', '').strip()  # Get last name, default to empty string and strip whitespace
        password1 = request.form.get('password1')
        
        # Validate email matches invite
        if email != invite.recipient_email:
            flash('Email must match the invite recipient.', 'error')
            return render_template("sign_up_with_invite.html", invite=invite, token=token)
        
        user = User.query.filter_by(email=email).first()
        if user:
            flash('Email already exists. Please log in instead.', 'error')
            return redirect(url_for('auth.login'))
        elif len(email) < 4:
            flash('Email must be greater than 3 characters.', 'error')
        elif len(first_name) < 2:
            flash('First name must be greater than 1 character.', 'error')
        elif last_name and len(last_name) < 2:
            flash('Last name must be greater than 1 character if provided.', 'error')
        elif len(password1) < 7:
            flash('Password must be at least 7 characters.', 'error')
        else:
            # Validate email: check disposable domains and MX records
            from .email_validation import validate_email
            email_valid, email_error = validate_email(email, check_mx=True)
            if not email_valid:
                print(f"[EMAIL VALIDATION] Rejected email {email} (invite signup): {email_error}")
                flash(email_error or 'Invalid email address. Please use a valid email address.', 'error')
                return render_template("sign_up_with_invite.html", invite=invite, token=token)
            
            # Continue with signup
            # Get IP address for registration
            client_ip = get_client_ip()
            
            # Get device fingerprint
            device_fingerprint = request.form.get('device_fingerprint', '').strip()
            if device_fingerprint and len(device_fingerprint) > 64:
                device_fingerprint = device_fingerprint[:64]  # Limit to 64 chars
            

            
            new_user = User(
                email=email,
                first_name=first_name,
                last_name=last_name,
                password=generate_password_hash(password1, method='pbkdf2:sha256'),
                notification_preferences={'email_notifications': True},
                delivery_preferences={'delivery_method': 'email'},
                is_active=True,  # Auto-activate for invite signups
                registration_ip=client_ip,
                device_fingerprint=device_fingerprint if device_fingerprint else None
            )
            db.session.add(new_user)
            db.session.flush()
            
            # Link ALL invites for this email to the user
            all_invites_for_email = RecipientInvite.query.filter_by(
                recipient_email=email,
                registered_at=None
            ).all()
            
            for invite_to_link in all_invites_for_email:
                invite_to_link.recipient_user_id = new_user.id
                invite_to_link.registered_at = datetime.now(timezone.utc)
            
            db.session.commit()
            
            # Log the user in automatically
            login_user(new_user, remember=True)
            
            # Count how many letters they now have access to
            letter_count = len(all_invites_for_email)
            if letter_count == 1:
                flash(f'Welcome! You can now read your letter from {invite.letter.author.first_name} {invite.letter.author.last_name}.', 'success')
            else:
                flash(f'Welcome! You can now read {letter_count} letters that were sent to you.', 'success')
            
            return redirect(url_for('views.received_letters'))
    
    return render_template("sign_up_with_invite.html", invite=invite, token=token)

@auth.route('/forgot-password', methods=['GET', 'POST'])
def forgot_password():
    if current_user.is_authenticated:
        return redirect(url_for('views.home'))
    
    # Get Turnstile site key for template
    turnstile_site_key = os.getenv('TURNSTILE_SITE_KEY', '')
    
    if request.method == 'POST':
        # Verify Cloudflare Turnstile token
        turnstile_token = request.form.get('cf-turnstile-response', '')
        client_ip = get_client_ip()
        is_turnstile_valid, turnstile_error = verify_turnstile_token(turnstile_token, client_ip)
        if not is_turnstile_valid:
            print(f"[TURNSTILE] BLOCKED forgot password attempt - Turnstile verification failed. IP: {client_ip}, Error: {turnstile_error}")
            flash('Security verification failed. Please try again.', 'error')
            return render_template('forgot_password.html', turnstile_site_key=turnstile_site_key)
        
        email = request.form.get('email')
        user = User.query.filter_by(email=email).first()
        
        if user:
            # Check for 5-minute cooldown
            if user.password_reset_expires and user.password_reset_expires > datetime.now(timezone.utc):
                time_left = user.password_reset_expires - datetime.now(timezone.utc)
                total_seconds_left = time_left.total_seconds()
                
                minutes_since = None
                if 23 * 3600 < total_seconds_left <= 24 * 3600:
                    minutes_since = (24 * 3600 - total_seconds_left) / 60
                elif 47 * 3600 < total_seconds_left <= 48 * 3600:
                    minutes_since = (48 * 3600 - total_seconds_left) / 60
                    
                if minutes_since is not None and minutes_since < 5:
                    minutes_left = 5 - int(minutes_since)
                    flash(f'Please wait {minutes_left} minute(s) before requesting another email.', 'warning')
                    return redirect(url_for('auth.forgot_password'))

            # Generate reset token
            reset_token = str(uuid.uuid4())
            user.password_reset_token = reset_token
            user.password_reset_expires = datetime.now(timezone.utc) + timedelta(hours=24)
            db.session.commit()
            
            # Send reset email
            reset_link = url_for('auth.reset_password', token=reset_token, _external=True)
            msg = Message('Reset Your Password - LetterForLater',
                        recipients=[email],
                        sender=os.getenv('MAIL_USERNAME', 'support@letterforlater.com'))
            
            # Render HTML template
            user_name = user.first_name + (" " + user.last_name if user.last_name else "")
            msg.html = render_template('emails/password_reset.html',
                user_name=user_name,
                user_email=user.email,
                reset_link=reset_link,
                reset_url=reset_link
            )
            
            # Render text template
            msg.body = render_template('emails/password_reset.txt',
                user_name=user_name,
                user_email=user.email,
                reset_link=reset_link,
                reset_url=reset_link
            )
            
            # Use rate-limited email sending (fails fast - no waiting to avoid timeout)
            success = safe_send_email(msg, email_type='password_reset', max_retries=0)
            if success:
                flash("Password reset instructions have been sent to your email (don't forget to check your spam folder).", 'success')
            else:
                # Rate limited or failed - show user-friendly message
                flash('Email service is temporarily unavailable. Please try again in a few minutes.', 'info')
        else:
            # Don't reveal if email exists or not for security
            flash("If an account with that email exists and is verified, password reset instructions have been sent (don't forget to check your spam folder).", 'info')
        
        return redirect(url_for('auth.forgot_password'))
    
    return render_template('forgot_password.html', turnstile_site_key=turnstile_site_key)

@auth.route('/resend-verification', methods=['GET', 'POST'])
def resend_verification():
    """Resend email verification link"""
    if current_user.is_authenticated:
        return redirect(url_for('views.home'))
    
    # Get Turnstile site key for template
    turnstile_site_key = os.getenv('TURNSTILE_SITE_KEY', '')
    
    if request.method == 'POST':
        # Verify Cloudflare Turnstile token
        turnstile_token = request.form.get('cf-turnstile-response', '')
        client_ip = get_client_ip()
        is_turnstile_valid, turnstile_error = verify_turnstile_token(turnstile_token, client_ip)
        if not is_turnstile_valid:
            print(f"[TURNSTILE] BLOCKED resend verification attempt - Turnstile verification failed. IP: {client_ip}, Error: {turnstile_error}")
            flash('Security verification failed. Please try again.', 'error')
            return render_template('resend_verification.html', turnstile_site_key=turnstile_site_key)
        
        email = request.form.get('email')
        user = User.query.filter_by(email=email).first()
        
        if user:
            # Check if user is already active
            if user.is_active:
                flash('Your account is already verified. You can log in normally.', 'info')
                return redirect(url_for('auth.login'))
            
            # Check if user has a valid confirmation token (pending verification)
            if user.password_reset_token and user.password_reset_expires and user.password_reset_expires > datetime.now(timezone.utc):
                # Rate limit: max once every 5 minutes
                last_sent_time = user.password_reset_expires - timedelta(hours=48)
                time_since_last_sent = datetime.now(timezone.utc) - last_sent_time
                if time_since_last_sent < timedelta(minutes=5):
                    minutes_left = 5 - int(time_since_last_sent.total_seconds() / 60)
                    flash(f'Please wait {minutes_left} minute(s) before requesting another verification email.', 'warning')
                    return redirect(url_for('auth.login'))
                    
                # Resend the confirmation email
                if send_confirmation_email(user):
                    flash('Verification email sent! Please check your email (and spam folder) and click the confirmation link.', 'success')
                else:
                    flash('Error sending verification email. Please try again later or contact support.', 'error')
            else:
                # Token expired or doesn't exist, generate new one
                if send_confirmation_email(user):
                    flash('New verification email sent! Please check your email (and spam folder) and click the confirmation link.', 'success')
                else:
                    flash('Error sending verification email. Please try again later or contact support.', 'error')
        else:
            # Don't reveal if email exists or not for security
            flash('If an account with that email exists and is unverified, a verification email has been sent.', 'info')
        
        return redirect(url_for('auth.login'))
    
    # GET request - show form
    return render_template('resend_verification.html', turnstile_site_key=turnstile_site_key)

@auth.route('/reset-password/<token>', methods=['GET', 'POST'])
def reset_password(token):
    if current_user.is_authenticated:
        return redirect(url_for('views.home'))
    
    user = User.query.filter_by(password_reset_token=token).first()
    
    if not user or user.password_reset_expires < datetime.now(timezone.utc):
        flash('Invalid or expired reset token.', 'error')
        return redirect(url_for('auth.forgot_password'))
    
    if request.method == 'POST':
        password1 = request.form.get('password1')
        password2 = request.form.get('password2')
        
        if password1 != password2:
            flash('Passwords do not match.', 'error')
        elif len(password1) < 7:
            flash('Password must be at least 7 characters.', 'error')
        else:
            # Update password and clear reset token
            user.password = generate_password_hash(password1, method='pbkdf2:sha256')
            user.password_reset_token = None
            user.password_reset_expires = None
            user.is_active = True  # Activate account on password reset
            db.session.commit()
            
            flash('Your password has been reset successfully. Please log in with your new password.', 'success')
            return redirect(url_for('auth.login'))
    
    return render_template('reset_password.html', token=token)

@auth.route('/confirm-email/<token>')
def confirm_email(token):
    if current_user.is_authenticated and current_user.is_active:
        return redirect(url_for('views.home'))
    user = User.query.filter_by(password_reset_token=token).first()
    if not user or not user.password_reset_expires or user.password_reset_expires < datetime.now(timezone.utc):
        flash('Invalid or expired confirmation link.', 'error')
        return redirect(url_for('auth.login'))
    # Activate account and clear token
    user.is_active = True
    user.password_reset_token = None
    user.password_reset_expires = None
    db.session.commit()
    
    # Check for pending letter data from landing page hero section
    pending_letter_data = session.get(f'pending_hero_letter_data_for_user_{user.email}')
    if pending_letter_data:
        try:
            from .models import Letter
            
            letter_data = pending_letter_data
            new_letter = Letter(
                title=letter_data.get('title', 'Untitled Letter'),
                content=letter_data.get('content', ''),
                recipient_name=letter_data.get('recipient_name', ''),
                recipient_email=letter_data.get('recipient_email', ''),
                delivery_type=letter_data.get('delivery_type', 'date'),
                user_id=user.id,
                is_send_to_myself=letter_data.get('send_to_myself') == 'on',
                status='scheduled'  # Save as scheduled per user request
            )
            
            # Encrypt title and content before saving
            new_letter.encrypt_fields()
            
            if letter_data.get('delivery_type') == 'date' and letter_data.get('scheduled_date'):
                scheduled_date = datetime.strptime(letter_data['scheduled_date'], '%Y-%m-%d').replace(hour=20, minute=0, second=0, tzinfo=timezone.utc)
                new_letter.delivery_date = scheduled_date
                new_letter.delivery_status = 'pending'
            
            db.session.add(new_letter)
            db.session.commit()
            session.pop(f'pending_hero_letter_data_for_user_{user.email}', None)
            
            # Log user in automatically after email confirmation
            login_user(user, remember=True)
            
            # Send welcome email after successful confirmation
            try:
                from .email_service import send_welcome_email
                send_welcome_email(user)
            except Exception as e:
                print(f"Error sending welcome email: {str(e)}")
            
            flash('Your email has been confirmed!', 'success')
            return redirect(url_for('views.add_letter', letter_id=new_letter.id))
        except Exception as e:
            db.session.rollback()
            print(f"Error creating letter from landing page data: {str(e)}")
            import traceback
            traceback.print_exc()
            session.pop(f'pending_hero_letter_data_for_user_{user.email}', None)
    
    # Log user in automatically after email confirmation
    login_user(user, remember=True)
    
    # Send welcome email after successful confirmation
    try:
        from .email_service import send_welcome_email
        send_welcome_email(user)
    except Exception as e:
        print(f"Error sending welcome email: {str(e)}")
    
    flash('Your email has been confirmed. You can now access your account.', 'success')
    return redirect(url_for('views.home'))

@auth.route('/setup-2fa', methods=['GET', 'POST'])
@login_required
def setup_2fa():
    if current_user.two_factor_enabled:
        flash('Two-factor authentication is already enabled.', 'info')
        return redirect(url_for('views.settings'))
    
    if request.method == 'POST':
        # Generate new secret
        secret = pyotp.random_base32()
        current_user.two_factor_secret = secret
        
        # Generate backup codes
        backup_codes = [secrets.token_hex(4).upper() for _ in range(8)]
        current_user.backup_codes = backup_codes
        
        db.session.commit()
        
        # Generate QR code
        totp = pyotp.TOTP(secret)
        provisioning_uri = totp.provisioning_uri(
            name=current_user.email,
            issuer_name="LetterForLater"
        )
        
        qr = qrcode.QRCode(version=1, box_size=10, border=5)
        qr.add_data(provisioning_uri)
        qr.make(fit=True)
        
        img = qr.make_image(fill_color="black", back_color="white")
        
        # Convert to base64 for display
        buffer = io.BytesIO()
        img.save(buffer, format='PNG')
        qr_code_base64 = base64.b64encode(buffer.getvalue()).decode()
        
        return render_template('setup_2fa.html', 
                            user=current_user,
                            secret=secret, 
                            qr_code=qr_code_base64, 
                            backup_codes=backup_codes)
    
    return render_template('setup_2fa.html', user=current_user)

@auth.route('/verify-2fa', methods=['GET', 'POST'])
@login_required
def verify_2fa():
    if request.method == 'POST':
        code = request.form.get('code')
        backup_code = request.form.get('backup_code')
        
        if backup_code:
            # Verify backup code
            if current_user.backup_codes and backup_code in current_user.backup_codes:
                # Remove used backup code
                current_user.backup_codes.remove(backup_code)
                db.session.commit()
                flash('Backup code used successfully. Please generate new backup codes.', 'success')
                return redirect(url_for('views.settings'))
            else:
                flash('Invalid backup code.', 'error')
        elif code:
            # Verify TOTP code
            if current_user.two_factor_secret:
                totp = pyotp.TOTP(current_user.two_factor_secret)
                if totp.verify(code):
                    # Enable 2FA if not already enabled
                    if not current_user.two_factor_enabled:
                        current_user.two_factor_enabled = True
                        db.session.commit()
                        flash('Two-factor authentication enabled successfully!', 'success')
                    else:
                        flash('Two-factor authentication verified successfully!', 'success')
                    return redirect(url_for('views.settings'))
                else:
                    flash('Invalid verification code.', 'error')
            else:
                flash('Two-factor authentication is not set up.', 'error')
        else:
            flash('Please enter a verification code or backup code.', 'error')
    
    # Check if user is setting up 2FA for the first time
    if not current_user.two_factor_enabled and current_user.two_factor_secret:
        return render_template('verify_2fa.html', user=current_user, setup_mode=True)
    elif current_user.two_factor_enabled:
        return render_template('verify_2fa.html', user=current_user, setup_mode=False)
    else:
        flash('Two-factor authentication is not set up.', 'error')
        return redirect(url_for('views.settings'))

@auth.route('/disable-2fa', methods=['POST'])
@login_required
def disable_2fa():
    if not current_user.two_factor_enabled:
        flash('Two-factor authentication is not enabled.', 'error')
        return redirect(url_for('views.settings'))
    
    password = request.form.get('password')
    if not check_password_hash(current_user.password, password):
        flash('Incorrect password.', 'error')
        return redirect(url_for('views.settings'))
    
    current_user.two_factor_enabled = False
    current_user.two_factor_secret = None
    current_user.backup_codes = None
    db.session.commit()
    
    flash('Two-factor authentication has been disabled.', 'success')
    return redirect(url_for('views.settings'))

@auth.route('/generate-backup-codes', methods=['POST'])
@login_required
def generate_backup_codes():
    if not current_user.two_factor_enabled:
        flash('Two-factor authentication must be enabled first.', 'error')
        return redirect(url_for('views.settings'))
    
    password = request.form.get('password')
    if not check_password_hash(current_user.password, password):
        flash('Incorrect password.', 'error')
        return redirect(url_for('views.settings'))
    
    # Generate new backup codes
    backup_codes = [secrets.token_hex(4).upper() for _ in range(8)]
    current_user.backup_codes = backup_codes
    db.session.commit()
    
    flash('New backup codes generated successfully. Please save them securely.', 'success')
    return redirect(url_for('views.settings'))
@auth.route('/reactivate-account', methods=['GET', 'POST'])
def reactivate_account():
    user_id = session.get('pending_reactivation_user_id')
    if not user_id:
        return redirect(url_for('auth.login'))
    
    user = User.query.get(user_id)
    if not user or user.is_active:
        session.pop('pending_reactivation_user_id', None)
        return redirect(url_for('auth.login'))
        
    if request.method == 'POST':
        user.is_active = True
        db.session.commit()
        session.pop('pending_reactivation_user_id', None)
        login_user(user, remember=True)
        flash('Welcome back! Your account and digital estate have been reactivated.', 'success')
        return redirect(url_for('views.home'))
        
    return render_template("reactivate.html", user=user)
