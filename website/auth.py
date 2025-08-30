from flask import Blueprint, render_template, request, flash, redirect, url_for, session
from .models import User, TrustedContact, DeathVerification, Letter
from werkzeug.security import generate_password_hash, check_password_hash
from . import db   ##means from __init__.py import db
from flask_login import login_user, login_required, logout_user, current_user
import uuid
from datetime import datetime, timedelta, timezone
from . import mail
from flask_mail import Message
import pyotp
import qrcode
import base64
import io
import secrets


auth = Blueprint('auth', __name__)


@auth.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('views.home'))
    next_page = request.args.get('next')
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        next_page = request.form.get('next') or next_page
        user = User.query.filter_by(email=email).first()
        if user:
            if check_password_hash(user.password, password):
                # Check if user has 2FA enabled
                if user.two_factor_enabled:
                    # Store login info in session for 2FA verification
                    session['pending_2fa_user_id'] = user.id
                    session['pending_2fa_next'] = next_page
                    session['pending_2fa_remember'] = True
                    session['pending_2fa_time'] = datetime.now(timezone.utc).timestamp()
                    return redirect(url_for('auth.login_2fa'))
                else:
                    # No 2FA, proceed with normal login
                    login_user(user, remember=True)
                    # Check for pending trusted contact invitation
                    contact = TrustedContact.query.filter_by(email=user.email, is_confirmed=False).first()
                    if contact:
                        session['pending_trusted_contact_code'] = contact.confirmation_code
                    flash('Logged in successfully!', category='success')
                    return redirect(next_page or url_for('views.home'))
            else:
                flash('Incorrect password, try again.', category='error')
        else:
            flash('Email does not exist.', category='error')
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
                db.session.commit()
                
                # Complete login
                login_user(user, remember=session.get('pending_2fa_remember', True))
                
                # Clear session
                next_page = session.pop('pending_2fa_next', None)
                session.pop('pending_2fa_user_id', None)
                session.pop('pending_2fa_remember', None)
                session.pop('pending_2fa_time', None)
                
                flash('Logged in successfully using backup code!', 'success')
                return redirect(next_page or url_for('views.home'))
            else:
                flash('Invalid backup code.', 'error')
        elif code:
            # Verify TOTP code
            if user.two_factor_secret:
                totp = pyotp.TOTP(user.two_factor_secret)
                if totp.verify(code):
                    # Complete login
                    login_user(user, remember=session.get('pending_2fa_remember', True))
                    
                    # Clear session
                    next_page = session.pop('pending_2fa_next', None)
                    session.pop('pending_2fa_user_id', None)
                    session.pop('pending_2fa_remember', None)
                    session.pop('pending_2fa_time', None)
                    
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
    if current_user.is_authenticated:
        return redirect(url_for('views.home'))
    next_page = request.args.get('next')
    if request.method == 'POST':
        email = request.form.get('email')
        first_name = request.form.get('firstName')
        last_name = request.form.get('lastName')
        password1 = request.form.get('password1')
        password2 = request.form.get('password2')
        next_page = request.form.get('next') or next_page
        user = User.query.filter_by(email=email).first()
        if user:
            flash('Email already exists.', category='error')
        elif len(email) < 4:
            flash('Email must be greater than 3 characters.', category='error')
        elif len(first_name) < 2:
            flash('First name must be greater than 1 character.', category='error')
        elif len(last_name) < 2:
            flash('Last name must be greater than 1 character.', category='error')
        elif password1 != password2:
            flash('Passwords don\'t match.', category='error')
        elif len(password1) < 7:
            flash('Password must be at least 7 characters.', category='error')
        else:
            new_user = User(
                email=email,
                first_name=first_name,
                last_name=last_name,
                password=generate_password_hash(password1, method='pbkdf2:sha256'),
                notification_preferences={'email_notifications': True},
                delivery_preferences={'delivery_method': 'email'}
            )
            db.session.add(new_user)
            db.session.commit()

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

            login_user(new_user, remember=True)
            flash('Account created!', category='success')
            return redirect(next_page or url_for('views.home'))

    # If this is a trusted contact signup, pre-fill the email
    trusted_contact_code = session.get('trusted_contact_code')
    email = None
    if trusted_contact_code:
        contact = TrustedContact.query.filter_by(confirmation_code=trusted_contact_code).first()
        if contact:
            email = contact.email

    return render_template("sign_up.html", user=current_user, email=email, next=next_page)

@auth.route('/forgot-password', methods=['GET', 'POST'])
def forgot_password():
    if current_user.is_authenticated:
        return redirect(url_for('views.home'))
    
    if request.method == 'POST':
        email = request.form.get('email')
        user = User.query.filter_by(email=email).first()
        
        if user:
            # Generate reset token
            reset_token = str(uuid.uuid4())
            user.password_reset_token = reset_token
            user.password_reset_expires = datetime.now(timezone.utc) + timedelta(hours=24)
            db.session.commit()
            
            # Send reset email
            reset_link = url_for('auth.reset_password', token=reset_token, _external=True)
            msg = Message('Password Reset Request',
                        recipients=[email])
            msg.body = f'''Hello {user.first_name},

You have requested a password reset for your Legacy Letter account.

Click the following link to reset your password:
{reset_link}

This link will expire in 24 hours.

If you did not request this reset, please ignore this email.

Best regards,
Legacy Letter Team'''
            
            try:
                mail.send(msg)
                flash('Password reset instructions have been sent to your email.', 'success')
            except Exception as e:
                print(f"Error sending password reset email: {str(e)}")
                flash('Error sending email. Please try again later.', 'error')
        else:
            # Don't reveal if email exists or not for security
            flash('If an account with that email exists, password reset instructions have been sent.', 'info')
        
        return redirect(url_for('auth.forgot_password'))
    
    return render_template('forgot_password.html')

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
            db.session.commit()
            
            flash('Your password has been reset successfully. Please log in with your new password.', 'success')
            return redirect(url_for('auth.login'))
    
    return render_template('reset_password.html', token=token)

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
            issuer_name="Legacy Letter"
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
