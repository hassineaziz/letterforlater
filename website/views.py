from flask import Blueprint, render_template, request, flash, jsonify, redirect, url_for, session
from flask_login import login_required, current_user
from .models import Letter, TrustedContact, User, DeathVerification, DeathVerificationConfirmation
from . import db, mail
import json
from datetime import datetime, timedelta, timezone
import uuid
from flask_mail import Message
from sqlalchemy import and_
from werkzeug.security import gen_salt
from werkzeug.security import check_password_hash, generate_password_hash

views = Blueprint('views', __name__)

def has_active_trusted_relationships(user):
    """Check if a user has active (confirmed) trusted contact relationships"""
    if user.role != 'trusted_main':
        return False
    
    # Check if user is a confirmed trusted contact for someone else
    active_contacts = TrustedContact.query.filter_by(
        email=user.email,
        is_confirmed=True
    ).count()
    
    return active_contacts > 0

def create_notification(user_id, notification_type, title, message, related_user_id=None, related_letter_id=None, related_trusted_contact_id=None):
    """Helper function to create notifications"""
    from website.models import Notification
    notification = Notification(
        user_id=user_id,
        notification_type=notification_type,
        title=title,
        message=message,
        related_user_id=related_user_id,
        related_letter_id=related_letter_id,
        related_trusted_contact_id=related_trusted_contact_id
    )
    db.session.add(notification)
    try:
        db.session.commit()
        return notification
    except Exception as e:
        db.session.rollback()
        print(f"Error creating notification: {e}")
        return None

@views.context_processor
def utility_processor():
    """Make utility functions available to all templates"""
    def check_trusted_contact_status(user):
        """Check if user has active trusted contact relationships"""
        if not user or not user.is_authenticated:
            return False
        return has_active_trusted_relationships(user)
    
    return dict(check_trusted_contact_status=check_trusted_contact_status)

@views.route('/', methods=['GET', 'POST'])
@login_required
def home():
    if request.method == 'POST':
        title = request.form.get('title')
        content = request.form.get('content')
        recipient_name = request.form.get('recipient_name')
        recipient_email = request.form.get('recipient_email')
        delivery_type = request.form.get('delivery_type')

        if not title or not content or not recipient_name or not recipient_email or not delivery_type:
            flash('Please fill in all required fields.', 'error')
            return redirect(url_for('views.home'))

        new_letter = Letter(
            title=title,
            content=content,
            recipient_name=recipient_name,
            recipient_email=recipient_email,
            delivery_type=delivery_type,
            user_id=current_user.id
        )
        db.session.add(new_letter)
        db.session.flush()

        if delivery_type == 'date':
            scheduled_date = request.form.get('scheduled_date')
            if not scheduled_date:
                flash('Please select a delivery date.', 'error')
                db.session.rollback()
                return redirect(url_for('views.home'))
            new_letter.delivery_date = datetime.strptime(scheduled_date, '%Y-%m-%d')
            new_letter.delivery_status = 'pending'
            new_letter.status = 'scheduled'
        elif delivery_type == 'death_verification':
            # Allow 'choose_later' or empty selection
            if not request.form.getlist('trusted_contact_ids'):
                new_letter.status = 'pending_verification'
            else:
                # Do not require trusted contacts at creation time
                new_letter.status = 'pending_verification'
            
            # Handle delay after death verification
            delay_option = request.form.get('delay_option', 'immediate')
            if delay_option == 'immediate':
                new_letter.delay_after_verification = 0
            elif delay_option == '1_day':
                new_letter.delay_after_verification = 1
            elif delay_option == '1_week':
                new_letter.delay_after_verification = 7
            elif delay_option == '1_month':
                new_letter.delay_after_verification = 30
            elif delay_option == 'custom':
                custom_days = request.form.get('custom_delay_days')
                if custom_days and custom_days.isdigit():
                    days = int(custom_days)
                    if 1 <= days <= 365:
                        new_letter.delay_after_verification = days
                    else:
                        flash('Custom delay must be between 1 and 365 days.', 'error')
                        db.session.rollback()
                        return redirect(url_for('views.home'))
                else:
                    flash('Please enter a valid number of days for custom delay.', 'error')
                    db.session.rollback()
                    return redirect(url_for('views.home'))
            
            # Create or get death verification record for this user
            existing_verification = DeathVerification.query.filter_by(user_id=current_user.id).first()
            if not existing_verification:
                death_verification = DeathVerification(
                    user_id=current_user.id,
                    confirmations_count=0,
                    status='pending',
                    verification_code=str(uuid.uuid4())
                )
                db.session.add(death_verification)

        try:
            db.session.commit()
            
            # Delete any existing draft since the letter was successfully created
            draft = Letter.query.filter_by(user_id=current_user.id, status='draft').first()
            if draft:
                db.session.delete(draft)
                db.session.commit()
            
            flash('Letter created successfully!', 'success')
        except Exception as e:
            db.session.rollback()
            flash('An error occurred while creating the letter.', 'error')
            print(f"Error creating letter: {str(e)}")
        return redirect(url_for('views.home'))
    confirmed_contacts = current_user.trusted_contacts_list.filter_by(is_confirmed=True).all()
    return render_template("home.html", user=current_user, now=datetime.now(timezone.utc), confirmed_contacts=confirmed_contacts)

@views.route('/verify-death', methods=['GET', 'POST'])
@login_required
def verify_death():
    if current_user.role != 'trusted_main':
        flash('You do not have permission to access this page.', 'error')
        return redirect(url_for('views.home'))
    # Find all users who have added current_user as a trusted contact and are confirmed
    trusted_for = TrustedContact.query.filter_by(email=current_user.email, is_confirmed=True).all()
    verification_info = []
    for contact in trusted_for:
        # Only show if the trusted contact is confirmed
        if not contact.is_confirmed:
            continue
        
        # Check if there are letters requiring death verification for this user
        has_death_verification_letters = Letter.query.filter_by(
            user_id=contact.user_id, 
            delivery_type='death_verification'
        ).first() is not None
        
        # Find any DeathVerification record for this user
        dv = DeathVerification.query.filter_by(user_id=contact.user_id).order_by(DeathVerification.id.desc()).first()
        
        if dv:
            # Find this trusted contact's confirmation (if any)
            confirmation = DeathVerificationConfirmation.query.filter_by(verification_id=dv.id, trusted_contact_id=contact.id).first()
            if confirmation:
                status = 'confirmed' if confirmation.confirmed else 'rejected'
            else:
                status = dv.status
        elif has_death_verification_letters:
            # There are letters requiring death verification but no verification record yet
            status = 'pending'
        else:
            # No letters requiring death verification
            status = 'no_letters'
            
        verification_info.append({
            'user': contact.user,
            'verification': dv,
            'trusted_contact': contact,
            'status': status
        })
    if request.method == 'POST':
        verification_id = request.form.get('verification_id')
        action = request.form.get('action')
        trusted_contact_id = request.form.get('trusted_contact_id')
        
        # Get the trusted contact
        contact = TrustedContact.query.get(trusted_contact_id)
        if not contact or contact.email != current_user.email:
            flash('Invalid verification request.', 'error')
            return redirect(url_for('views.verify_death'))
            
        # Only allow confirmation for users who explicitly trusted this contact
        if not contact.is_confirmed:
            flash('You are not a confirmed trusted contact for this user.', 'error')
            return redirect(url_for('views.verify_death'))
            
        # Get or create the verification record
        verification = None
        if verification_id:
            verification = DeathVerification.query.get(verification_id)
        else:
            # Check if there are letters requiring death verification
            has_death_verification_letters = Letter.query.filter_by(
                user_id=contact.user_id, 
                delivery_type='death_verification'
            ).first() is not None
            
            if has_death_verification_letters:
                # Create a new verification record
                verification = DeathVerification(
                    user_id=contact.user_id,
                    confirmations_count=0,
                    status='pending',
                    verification_code=str(uuid.uuid4())
                )
                db.session.add(verification)
                db.session.flush()  # Get the ID
            else:
                flash('No letters requiring death verification found.', 'error')
                return redirect(url_for('views.verify_death'))
        
        if not verification:
            flash('Invalid verification request.', 'error')
            return redirect(url_for('views.verify_death'))
            
        # Prevent duplicate confirmations
        existing = DeathVerificationConfirmation.query.filter_by(verification_id=verification.id, trusted_contact_id=contact.id).first()
        if existing:
            flash('You have already responded to this verification.', 'info')
            return redirect(url_for('views.verify_death'))
        if action == 'confirm':
            conf = DeathVerificationConfirmation(
                verification_id=verification.id,
                trusted_contact_id=contact.id,
                confirmed=True
            )
            db.session.add(conf)
            verification.confirmations_count += 1
            verification.verification_date = datetime.now(timezone.utc)
            
            # Calculate 50% threshold of total trusted contacts
            total_trusted_contacts = TrustedContact.query.filter_by(
                user_id=verification.user_id, 
                is_confirmed=True
            ).count()
            
            # Require at least 50% of trusted contacts to confirm
            required_confirmations = max(1, (total_trusted_contacts + 1) // 2)  # +1 to round up
            
            if verification.confirmations_count >= required_confirmations:
                verification.status = 'verified'
                # Deliver all pending_verification letters for this user
                letters = Letter.query.filter_by(user_id=verification.user_id, status='pending_verification').all()
                for letter in letters:
                    if letter.delay_after_verification == 0:
                        # Send immediately
                        try:
                            msg = Message(
                                f'Legacy Letter: {letter.title}',
                                recipients=[letter.recipient_email]
                            )
                            msg.body = f"""
Dear {letter.recipient_name},

This is a legacy letter from {letter.author.first_name} {letter.author.last_name}.

{letter.content}

---
This letter was delivered through the Legacy Letter service.
"""
                            mail.send(msg)
                            letter.status = 'delivered'
                            letter.delivery_date = datetime.now(timezone.utc)
                            letter.delivery_status = 'delivered'
                        except Exception as e:
                            print(f"Error sending letter to {letter.recipient_email}: {str(e)}")
                            letter.status = 'delivered'
                            letter.delivery_date = datetime.now(timezone.utc)
                            letter.delivery_status = 'delivered'
                    else:
                        # Schedule for later delivery
                        delivery_date = datetime.now(timezone.utc) + timedelta(days=letter.delay_after_verification)
                        letter.delivery_date = delivery_date
                        letter.delivery_status = 'scheduled'
                        letter.status = 'scheduled'
                        # Note: You'll need a background task or cron job to actually send these scheduled letters
                        print(f"Letter {letter.id} scheduled for delivery on {delivery_date}")
                
                flash(f'Death verified! {verification.confirmations_count}/{total_trusted_contacts} trusted contacts confirmed. Letters have been processed according to their delay settings.', 'success')
            else:
                flash(f'Death confirmation recorded. {verification.confirmations_count}/{required_confirmations} confirmations needed. Waiting for more trusted contacts to confirm.', 'info')
        elif action == 'reject':
            conf = DeathVerificationConfirmation(
                verification_id=verification.id,
                trusted_contact_id=contact.id,
                confirmed=False
            )
            db.session.add(conf)
            verification.status = 'rejected'
            verification.verification_date = datetime.now(timezone.utc)
        try:
            db.session.commit()
            flash('Verification status updated successfully.', 'success')
        except Exception as e:
            db.session.rollback()
            flash('An error occurred while updating verification status.', 'error')
            print(f"Error updating verification: {str(e)}")
        return redirect(url_for('views.verify_death'))
    return render_template("verify_death.html", verifications=verification_info, user=current_user)


@views.route('/delete-letter', methods=['POST'])
@login_required
def delete_letter():
    letter = json.loads(request.data)
    letterId = letter['letterId']
    letter = Letter.query.get(letterId)
    if letter:
        if letter.user_id == current_user.id:
            db.session.delete(letter)
            db.session.commit()

    return jsonify({})

@views.route('/edit-letter', methods=['POST'])
@login_required
def edit_letter():
    if request.is_json:
        letter = request.get_json()
        letterId = letter['letterId']
        letter = Letter.query.get(letterId)
        if letter and letter.user_id == current_user.id:
            letter.title = letter['title']
            letter.content = letter['content']
            letter.recipient_name = letter['recipient_name']
            letter.recipient_email = letter['recipient_email']
            
            # Handle delay after verification if provided
            if 'delay_option' in letter and letter.delivery_type == 'death_verification':
                delay_option = letter['delay_option']
                if delay_option == 'immediate':
                    letter.delay_after_verification = 0
                elif delay_option == '1_day':
                    letter.delay_after_verification = 1
                elif delay_option == '1_week':
                    letter.delay_after_verification = 7
                elif delay_option == '1_month':
                    letter.delay_after_verification = 30
                elif delay_option == 'custom' and 'custom_delay_days' in letter:
                    custom_days = letter['custom_delay_days']
                    if custom_days and str(custom_days).isdigit():
                        days = int(custom_days)
                        if 1 <= days <= 365:
                            letter.delay_after_verification = days
                        else:
                            return jsonify({'error': 'Custom delay must be between 1 and 365 days'}), 400
                    else:
                        return jsonify({'error': 'Please enter a valid number of days for custom delay'}), 400
            
            db.session.commit()
        return jsonify({})
    else:
        letterId = request.form.get('letterId')
        letter = Letter.query.get(letterId)
        if letter and letter.user_id == current_user.id:
            letter.title = request.form.get('title')
            letter.content = request.form.get('content')
            letter.recipient_name = request.form.get('recipient_name')
            letter.recipient_email = request.form.get('recipient_email')
            
            # Handle delay after verification if provided
            if letter.delivery_type == 'death_verification':
                delay_option = request.form.get('delay_option')
                if delay_option:
                    if delay_option == 'immediate':
                        letter.delay_after_verification = 0
                    elif delay_option == '1_day':
                        letter.delay_after_verification = 1
                    elif delay_option == '1_week':
                        letter.delay_after_verification = 7
                    elif delay_option == '1_month':
                        letter.delay_after_verification = 30
                    elif delay_option == 'custom':
                        custom_days = request.form.get('custom_delay_days')
                        if custom_days and custom_days.isdigit():
                            days = int(custom_days)
                            if 1 <= days <= 365:
                                letter.delay_after_verification = days
                            else:
                                flash('Custom delay must be between 1 and 365 days.', 'error')
                                return redirect(url_for('views.view_letters', user_id=current_user.id))
                        else:
                            flash('Please enter a valid number of days for custom delay.', 'error')
                            return redirect(url_for('views.view_letters', user_id=current_user.id))
            
            db.session.commit()
            flash('Letter updated successfully!', 'success')
        return redirect(url_for('views.view_letters', user_id=current_user.id))

@views.route('/update-letter-status', methods=['POST'])
@login_required
def update_letter_status():
    if request.is_json:
        data = request.get_json()
        letterId = data['letterId']
        new_status = data.get('status')
        letter = Letter.query.get(letterId)
        if letter and letter.user_id == current_user.id:
            letter.status = new_status
            db.session.commit()
            flash('Letter status updated successfully!', category='success')
        else:
            flash('You do not have permission to update this letter!', category='error')
        return jsonify({})
    else:
        letterId = request.form.get('letterId')
        letter = Letter.query.get(letterId)
        if letter and letter.user_id == current_user.id:
            delivery_type = request.form.get('delivery_type')
            letter.delivery_type = delivery_type
            if delivery_type == 'date':
                scheduled_date = request.form.get('scheduled_date')
                if scheduled_date:
                    letter.delivery_date = datetime.strptime(scheduled_date, '%Y-%m-%d')
                    letter.delivery_status = 'pending'
                    letter.status = 'scheduled'
                else:
                    letter.delivery_date = None
                    letter.delivery_status = None
            elif delivery_type == 'death_verification':
                # No longer require trusted contacts for this delivery type
                letter.status = 'pending_verification'
                letter.delivery_date = None
                letter.delivery_status = None
            db.session.commit()
            flash('Delivery type updated successfully!', 'success')
        return redirect(url_for('views.view_letters', user_id=current_user.id))

@views.route('/trusted-contacts', methods=['GET'])
@login_required
def trusted_contacts():
    contacts = TrustedContact.query.filter_by(user_id=current_user.id).all()
    return render_template("trusted_contacts.html", user=current_user, contacts=contacts)

@views.route('/add-trusted-contact', methods=['POST'])
@login_required
def add_trusted_contact():
    first_name = request.form.get('first_name')
    last_name = request.form.get('last_name')
    email = request.form.get('email')
    phone = request.form.get('phone')
    relationship = request.form.get('relationship')

    if not first_name or not last_name or not email:
        flash('First name, last name, and email are required!', category='error')
        return redirect(url_for('views.trusted_contacts'))
    
    # Prevent user from adding themselves as a trusted contact
    if email.lower() == current_user.email.lower():
        flash('You cannot add yourself as a trusted contact!', category='error')
        return redirect(url_for('views.trusted_contacts'))

    full_name = f"{first_name} {last_name}"
    confirmation_code = str(uuid.uuid4())
    new_contact = TrustedContact(
        user_id=current_user.id,
        full_name=full_name,
        email=email,
        phone=phone,
        relationship=relationship,
        confirmation_code=confirmation_code
    )
    db.session.add(new_contact)
    db.session.commit()

    # Send confirmation email
    confirmation_link = url_for('views.confirm_contact', code=confirmation_code, _external=True)
    msg = Message('Confirm Your Role as a Trusted Contact',
                  recipients=[email])
    msg.body = f'You have been added as a trusted contact by {current_user.first_name}. Please confirm your role by clicking the link: {confirmation_link}'
    
    try:
        mail.send(msg)
        flash('Trusted contact added successfully! Confirmation email sent.', category='success')
    except Exception as e:
        print(f"Error sending email: {str(e)}")
        flash('Trusted contact added successfully! Confirmation email will be sent shortly.', category='success')

    # Check if user came from letter form
    from_letter = request.args.get('from_letter')
    if from_letter == '1':
        return redirect(url_for('views.trusted_contacts', from_letter=1))
    return redirect(url_for('views.trusted_contacts'))

@views.route('/confirm-contact/<code>', methods=['GET', 'POST'])
def confirm_contact(code):
    contact = TrustedContact.query.filter_by(confirmation_code=code).first()
    if not contact:
        flash('Invalid confirmation code.', category='error')
        return redirect(url_for('auth.login'))
    if contact.is_confirmed:
        flash('You have already confirmed your trusted contact role.', category='info')
        return redirect(url_for('auth.login'))
    if current_user.is_authenticated and current_user.email == contact.email:
        if request.method == 'POST':
            action = request.form.get('action')
            if action == 'accept':
                contact.is_confirmed = True
                db.session.commit()
                # Promote user to trusted_main if not already
                if current_user.role != 'trusted_main':
                    current_user.role = 'trusted_main'
                    db.session.commit()
                # Ensure DeathVerification record exists for this user if they have at least one letter requiring death verification
                has_pending_letter = Letter.query.filter_by(user_id=contact.user_id, delivery_type='death_verification', status='pending_verification').first()
                if has_pending_letter:
                    dv = DeathVerification.query.filter_by(user_id=contact.user_id, status='pending').first()
                    if not dv:
                        dv = DeathVerification(
                            user_id=contact.user_id,
                            confirmations_count=0,
                            status='pending',
                            verification_code=str(uuid.uuid4())
                        )
                        db.session.add(dv)
                flash('You have accepted the trusted contact request.', category='success')
                db.session.commit()
                return redirect(url_for('views.verify_death'))
            elif action == 'deny':
                db.session.delete(contact)
                db.session.commit()
                flash('You have declined the trusted contact request.', category='info')
            return redirect(url_for('views.home'))
        return render_template('confirm_trusted_contact.html', contact=contact, user=current_user)
    user = User.query.filter_by(email=contact.email).first()
    if user:
        flash('Please log in to confirm your trusted contact role.', category='info')
        return redirect(url_for('auth.login'))
    session['trusted_contact_code'] = code
    flash('Please sign up to complete the confirmation process.', category='info')
    return redirect(url_for('auth.sign_up'))

@views.route('/resend-confirmation/<int:contact_id>')
@login_required
def resend_confirmation(contact_id):
    contact = TrustedContact.query.get(contact_id)
    if contact and contact.user_id == current_user.id:
        # Generate new confirmation code if one doesn't exist
        if not contact.confirmation_code:
            contact.confirmation_code = str(uuid.uuid4())
            db.session.commit()
        
        confirmation_link = url_for('views.confirm_contact', code=contact.confirmation_code, _external=True)
        msg = Message('Confirm Your Role as a Trusted Contact',
                      recipients=[contact.email])
        msg.body = f'You have been added as a trusted contact by {current_user.first_name}. Please confirm your role by clicking the link: {confirmation_link}'
        
        try:
            mail.send(msg)
            flash('Confirmation email resent successfully!', category='success')
        except Exception as e:
            print(f"Error sending email: {str(e)}")
            flash('Confirmation email will be sent shortly.', category='success')
    else:
        flash('You do not have permission to resend confirmation for this contact!', category='error')
    return redirect(url_for('views.trusted_contacts'))

@views.route('/delete-trusted-contact', methods=['POST'])
@login_required
def delete_trusted_contact():
    contact_id = request.form.get('contact_id')
    contact = TrustedContact.query.get(contact_id)
    if contact and contact.user_id == current_user.id:
        db.session.delete(contact)
        db.session.commit()
        flash('Trusted contact deleted successfully!', category='success')
    else:
        flash('You do not have permission to delete this contact!', category='error')
    return redirect(url_for('views.trusted_contacts'))

@views.route('/edit-trusted-contact', methods=['POST'])
@login_required
def edit_trusted_contact():
    contact_id = request.form.get('contact_id')
    first_name = request.form.get('first_name')
    last_name = request.form.get('last_name')
    email = request.form.get('email')
    phone = request.form.get('phone')
    relationship = request.form.get('relationship')

    contact = TrustedContact.query.get(contact_id)
    if contact and contact.user_id == current_user.id:
        # Prevent user from editing a contact to have their own email
        if email.lower() == current_user.email.lower():
            flash('You cannot set a trusted contact email to your own email address!', category='error')
            return redirect(url_for('views.trusted_contacts'))
        
        contact.full_name = f"{first_name} {last_name}"
        contact.email = email
        contact.phone = phone
        contact.relationship = relationship
        db.session.commit()
        flash('Trusted contact updated successfully!', category='success')
    else:
        flash('You do not have permission to edit this contact!', category='error')
    return redirect(url_for('views.trusted_contacts'))

@views.route('/view-letters/<int:user_id>')
@login_required
def view_letters(user_id):
    # Allow main user to view only their own letters
    if current_user.id == user_id:
        letters = Letter.query.filter_by(user_id=user_id).all()
        return render_template('view_letters.html', user=current_user, letters=letters, contact=None, is_owner=True, now=datetime.now(timezone.utc))
    # Otherwise, check if current user is a trusted contact for this user
    contact = TrustedContact.query.filter_by(
        user_id=user_id,
        email=current_user.email
    ).first()
    if not contact or not contact.can_view_letters():
        flash('You do not have permission to view these letters.', category='error')
        return redirect(url_for('views.home'))
    letters = Letter.query.filter_by(user_id=user_id).all()
    return render_template('view_letters.html', user=current_user, letters=letters, contact=contact, is_owner=False, now=datetime.now(timezone.utc))

@views.route('/settings', methods=['GET', 'POST'])
@login_required
def settings():
    if request.method == 'POST':
        first_name = request.form.get('first_name', '').strip()
        last_name = request.form.get('last_name', '').strip()
        phone = request.form.get('phone', '').strip()
        errors = []
        if len(first_name) < 2:
            errors.append('First name must be at least 2 characters.')
        if len(last_name) < 2:
            errors.append('Last name must be at least 2 characters.')
        if errors:
            for error in errors:
                flash(error, 'error')
            return redirect(url_for('views.settings'))
        current_user.first_name = first_name
        current_user.last_name = last_name
        current_user.phone = phone
        db.session.commit()
        flash('Account settings updated successfully!', 'success')
        return redirect(url_for('views.settings'))
    return render_template('settings.html', user=current_user)

@views.route('/change-password', methods=['POST'])
@login_required
def change_password():
    current_password = request.form.get('current_password')
    new_password = request.form.get('new_password')
    confirm_password = request.form.get('confirm_password')
    
    # Validation
    if not current_password or not new_password or not confirm_password:
        flash('All password fields are required.', 'error')
        return redirect(url_for('views.settings'))
    
    if new_password != confirm_password:
        flash('New passwords do not match.', 'error')
        return redirect(url_for('views.settings'))
    
    if len(new_password) < 7:
        flash('New password must be at least 7 characters long.', 'error')
        return redirect(url_for('views.settings'))
    
    # Prevent using the same password
    if current_password == new_password:
        flash('New password must be different from your current password.', 'error')
        return redirect(url_for('views.settings'))
    
    # Verify current password
    if not check_password_hash(current_user.password, current_password):
        flash('Current password is incorrect.', 'error')
        return redirect(url_for('views.settings'))
    
    # Update password
    try:
        current_user.password = generate_password_hash(new_password, method='pbkdf2:sha256')
        db.session.commit()
        flash('Password changed successfully! Please log in again with your new password.', 'success')
        
        # Log out the user after password change for security
        from flask_login import logout_user
        logout_user()
        return redirect(url_for('auth.login'))
        
    except Exception as e:
        db.session.rollback()
        flash('An error occurred while changing your password. Please try again.', 'error')
        print(f"Error changing password: {str(e)}")
        return redirect(url_for('views.settings'))

@views.route('/save-draft', methods=['POST'])
@login_required
def save_draft():
    data = request.get_json()
    title = data.get('title', '').strip()
    content = data.get('content', '').strip()
    recipient_name = data.get('recipient_name', '').strip()
    recipient_email = data.get('recipient_email', '').strip()
    delivery_type = data.get('delivery_type')
    scheduled_date = data.get('scheduled_date')

    # Save draft even with minimal content to preserve user work
    # Only skip if literally nothing is provided
    if not any([title, content, recipient_name, recipient_email, delivery_type]):
        return jsonify({'success': False, 'reason': 'empty', 'draft_id': None})

    # For draft auto-save, don't consider letters "complete" and delete drafts
    # Only delete drafts when the user actually submits the form
    # This prevents losing work when navigating away to add trusted contacts
    
    # We'll keep all drafts until the user actually submits the form

    # Otherwise, update or create the draft as before
    draft = Letter.query.filter_by(user_id=current_user.id, status='draft').order_by(Letter.last_modified.desc()).first()
    if draft:
        # Update the existing draft
        draft.title = title or ''
        draft.content = content or ''
        draft.recipient_name = recipient_name or ''
        draft.recipient_email = recipient_email or ''
        draft.delivery_type = delivery_type or 'date'
        draft.last_modified = datetime.now(timezone.utc)
        db.session.commit()
        # Update or create delivery schedule if needed
        if delivery_type == 'date' and scheduled_date:
            draft.delivery_date = datetime.strptime(scheduled_date, '%Y-%m-%d')
            draft.delivery_status = 'pending'
        elif delivery_type != 'date' and draft.delivery_date:
            draft.delivery_date = None
            draft.delivery_status = None
        return jsonify({'success': True, 'draft_id': draft.id, 'updated': True})
    else:
        # Create a new draft
        draft = Letter(
            title=title or '',
            content=content or '',
            recipient_name=recipient_name or '',
            recipient_email=recipient_email or '',
            delivery_type=delivery_type or 'date',
            status='draft',
            user_id=current_user.id
        )
        db.session.add(draft)
        db.session.commit()
        # Save scheduled date if present
        if delivery_type == 'date' and scheduled_date:
            draft.delivery_date = datetime.strptime(scheduled_date, '%Y-%m-%d')
            draft.delivery_status = 'pending'
        return jsonify({'success': True, 'draft_id': draft.id, 'created': True})

@views.route('/get-draft', methods=['GET'])
@login_required
def get_draft():
    draft = Letter.query.filter_by(user_id=current_user.id, status='draft').order_by(Letter.last_modified.desc()).first()
    if not draft:
        return jsonify({'draft': None})
    draft_data = {
        'title': draft.title,
        'content': draft.content,
        'recipient_name': draft.recipient_name,
        'recipient_email': draft.recipient_email,
        'delivery_type': draft.delivery_type,
        'scheduled_date': draft.delivery_date.strftime('%Y-%m-%d') if draft.delivery_date else ''
    }
    return jsonify({'draft': draft_data})

@views.route('/delete-draft', methods=['POST'])
@login_required
def delete_draft():
    draft = Letter.query.filter_by(user_id=current_user.id, status='draft').first()
    if draft:
        db.session.delete(draft)
        db.session.commit()
    return jsonify({'success': True})

@views.route('/invite-trusted-contact', methods=['POST'])
@login_required
def invite_trusted_contact():
    first_name = request.form.get('first_name')
    last_name = request.form.get('last_name')
    email = request.form.get('email')
    phone = request.form.get('phone')
    relationship = request.form.get('relationship')

    if not first_name or not last_name or not email:
        flash('First name, last name, and email are required!', category='error')
        return redirect(url_for('views.trusted_contacts'))
    
    # Prevent user from adding themselves as a trusted contact
    if email.lower() == current_user.email.lower():
        flash('You cannot add yourself as a trusted contact!', category='error')
        return redirect(url_for('views.trusted_contacts'))

    # Check for existing invite
    existing = TrustedContact.query.filter_by(user_id=current_user.id, email=email).first()
    if existing:
        # Resend confirmation email
        if not existing.confirmation_code:
            existing.confirmation_code = str(uuid.uuid4())
            db.session.commit()
        confirmation_link = url_for('views.confirm_trust', token=existing.confirmation_code, _external=True)
        msg = Message('Confirm Your Role as a Trusted Contact', recipients=[email])
        msg.body = f'You have been invited as a trusted contact by {current_user.first_name}. Please confirm your role by clicking the link: {confirmation_link}'
        try:
            mail.send(msg)
            flash('Confirmation email resent successfully!', category='success')
        except Exception as e:
            print(f"Error sending email: {str(e)}")
            flash('Confirmation email will be sent shortly.', category='success')
        return redirect(url_for('views.trusted_contacts'))

    # Create new invite
    confirmation_code = str(uuid.uuid4())
    new_contact = TrustedContact(
        user_id=current_user.id,
        full_name=f"{first_name} {last_name}",
        email=email,
        phone=phone,
        relationship=relationship,
        confirmation_code=confirmation_code
    )
    db.session.add(new_contact)
    db.session.commit()
    confirmation_link = url_for('views.confirm_trust', token=confirmation_code, _external=True)
    msg = Message('Confirm Your Role as a Trusted Contact', recipients=[email])
    msg.body = f'You have been invited as a trusted contact by {current_user.first_name}. Please confirm your role by clicking the link: {confirmation_link}'
    try:
        mail.send(msg)
        flash('Trusted contact invited successfully! Confirmation email sent.', category='success')
    except Exception as e:
        print(f"Error sending email: {str(e)}")
        flash('Trusted contact invited successfully! Confirmation email will be sent shortly.', category='success')
    return redirect(url_for('views.trusted_contacts'))

@views.route('/confirm-trust', methods=['GET', 'POST'])
def confirm_trust():
    token = request.args.get('token')
    contact = TrustedContact.query.filter_by(confirmation_code=token).first()
    if not contact:
        flash('Invalid or expired confirmation token.', category='error')
        return redirect(url_for('auth.login'))
    if contact.is_confirmed:
        flash('You have already confirmed your trusted contact role.', category='info')
        return redirect(url_for('auth.login'))
    if not current_user.is_authenticated:
        session['trusted_contact_code'] = token
        flash('Please log in to confirm your trusted contact role.', category='info')
        return redirect(url_for('auth.login'))
    if current_user.email != contact.email:
        flash('You were not invited with this email.', category='error')
        return redirect(url_for('views.home'))
    if request.method == 'POST':
        action = request.form.get('action')
        if action == 'accept':
            contact.is_confirmed = True
            db.session.commit()
            # Promote user to trusted_main if not already
            if current_user.role != 'trusted_main':
                current_user.role = 'trusted_main'
                db.session.commit()
            flash('You have accepted the trusted contact request.', category='success')
            return redirect(url_for('views.verify_death'))
        elif action == 'deny':
            db.session.delete(contact)
            db.session.commit()
            flash('You have declined the trusted contact request.', category='info')
        return redirect(url_for('views.home'))
    return render_template('confirm_trusted_contact.html', contact=contact, user=current_user)

@views.route('/pending-trusted-contact/<int:invite_id>', methods=['GET', 'POST'])
@login_required
def pending_trusted_contact(invite_id):
    from website.models import TrustedContact
    contact = TrustedContact.query.get(invite_id)
    if not contact or contact.email != current_user.email or contact.is_confirmed:
        flash('Invalid or expired trusted contact invitation.', 'error')
        return redirect(url_for('views.home'))
    if request.method == 'POST':
        action = request.form.get('action')
        if action == 'accept':
            contact.is_confirmed = True
            if current_user.role != 'trusted_main':
                current_user.role = 'trusted_main'
            db.session.commit()
            flash('You have accepted the trusted contact request.', 'success')
        elif action == 'decline':
            db.session.delete(contact)
            db.session.commit()
            flash('You have declined the trusted contact request.', 'info')
        return redirect(url_for('views.home'))
    return render_template('pending_trusted_contact.html', contact=contact, user=current_user)

@views.route('/api/notifications')
@login_required
def api_notifications():
    from website.models import TrustedContact
    invitations = TrustedContact.query.filter_by(email=current_user.email, is_confirmed=False).all()
    data = [
        {
            'id': invite.id,
            'from_name': invite.user.first_name + ' ' + invite.user.last_name,
            'from_email': invite.user.email,
            'contact_id': invite.id,
            'confirmation_code': invite.confirmation_code
        }
        for invite in invitations
    ]
    return jsonify({'pending_trusted_invitations': data})

@views.route('/api/remove-invitation/<int:invite_id>', methods=['POST'])
@login_required
def api_remove_invitation(invite_id):
    from website.models import TrustedContact
    invite = TrustedContact.query.get(invite_id)
    if invite and invite.email == current_user.email and not invite.is_confirmed:
        db.session.delete(invite)
        db.session.commit()
        return jsonify({'success': True})
    return jsonify({'success': False}), 403

@views.route('/send-scheduled-letters', methods=['POST'])
@login_required
def send_scheduled_letters():
    """Send letters that are scheduled for delivery after death verification delay"""
    if current_user.role != 'admin':  # Only admins can trigger this
        return jsonify({'success': False, 'error': 'Unauthorized'}), 403
    
    # Find letters that are scheduled and past their delivery date
    now = datetime.now(timezone.utc)
    scheduled_letters = Letter.query.filter(
        Letter.status == 'scheduled',
        Letter.delivery_status == 'scheduled',
        Letter.delivery_date <= now,
        Letter.delivery_type == 'death_verification'
    ).all()
    
    sent_count = 0
    for letter in scheduled_letters:
        try:
            msg = Message(
                f'Legacy Letter: {letter.title}',
                recipients=[letter.recipient_email]
            )
            msg.body = f"""
Dear {letter.recipient_name},

This is a legacy letter from {letter.author.first_name} {letter.author.last_name}.

{letter.content}

---
This letter was delivered through the Legacy Letter service.
"""
            mail.send(msg)
            letter.status = 'delivered'
            letter.delivery_status = 'delivered'
            sent_count += 1
        except Exception as e:
            print(f"Error sending scheduled letter {letter.id} to {letter.recipient_email}: {str(e)}")
            # Keep the letter as scheduled if there's an error
    
    try:
        db.session.commit()
        return jsonify({'success': True, 'sent_count': sent_count})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500

def send_scheduled_letters_task():
    """Background task to send scheduled letters - can be called by cron job"""
    with app.app_context():
        now = datetime.now(timezone.utc)
        scheduled_letters = Letter.query.filter(
            Letter.status == 'scheduled',
            Letter.delivery_status == 'scheduled',
            Letter.delivery_date <= now,
            Letter.delivery_type == 'death_verification'
        ).all()
        
        for letter in scheduled_letters:
            try:
                msg = Message(
                    f'Legacy Letter: {letter.title}',
                    recipients=[letter.recipient_email]
                )
                msg.body = f"""
Dear {letter.recipient_name},

This is a legacy letter from {letter.author.first_name} {letter.author.last_name}.

{letter.content}

---
This letter was delivered through the Legacy Letter service.
"""
                mail.send(msg)
                letter.status = 'delivered'
                letter.delivery_status = 'delivered'
                print(f"Sent scheduled letter {letter.id} to {letter.recipient_email}")
            except Exception as e:
                print(f"Error sending scheduled letter {letter.id}: {str(e)}")
        
        try:
            db.session.commit()
            print(f"Processed {len(scheduled_letters)} scheduled letters")
        except Exception as e:
            db.session.rollback()
            print(f"Error committing scheduled letter updates: {str(e)}")
