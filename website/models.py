from . import db
from flask_login import UserMixin
from sqlalchemy.sql import func
from datetime import datetime
import json
import uuid
from sqlalchemy.dialects.postgresql import JSONB

# Association table for trusted contacts
user_trusted_contacts = db.Table('user_trusted_contacts',
    db.Column('user_id', db.Integer, db.ForeignKey('user.id', ondelete='CASCADE'), primary_key=True),
    db.Column('contact_id', db.Integer, db.ForeignKey('user.id', ondelete='CASCADE'), primary_key=True)
)

class Letter(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    content = db.Column(db.Text, nullable=False)
    created_date = db.Column(db.DateTime(timezone=True), default=func.now())
    last_modified = db.Column(db.DateTime(timezone=True), default=func.now(), onupdate=func.now())
    status = db.Column(db.String(20), default='draft')  # draft, scheduled, delivered, cancelled
    delivery_type = db.Column(db.String(20), nullable=False)  # date, death_verification
    scheduled_date = db.Column(db.DateTime(timezone=True), nullable=True)
    delivery_date = db.Column(db.DateTime(timezone=True), nullable=True)  # actual delivery date
    delivery_status = db.Column(db.String(20), default='pending')  # pending, delivered, cancelled
    recipient_email = db.Column(db.String(150), nullable=False)
    recipient_name = db.Column(db.String(150), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id', ondelete='CASCADE'))
    delay_after_verification = db.Column(db.Integer, nullable=True)  # Days to wait after death verification
    is_send_to_myself = db.Column(db.Boolean, default=False)  # True if letter is sent to the user themselves
    is_encrypted = db.Column(db.Boolean, default=False)  # True if title and content are encrypted
    
    # Media attachments
    media_attachments = db.Column(JSONB, default=[])  # Array of media file info
    
    # Reminder tracking for draft letters
    last_draft_reminder_sent_at = db.Column(db.DateTime(timezone=True), nullable=True)
    
    def encrypt_fields(self):
        """
        Encrypt title and content fields and mark as encrypted.
        
        Returns:
            bool: True if encryption succeeded, False otherwise
        
        Note: This method does NOT raise exceptions - encryption failure is non-blocking.
        If encryption fails, the letter will be saved unencrypted and the error is logged.
        """
        try:
            from .encryption import encrypt_text, is_encrypted_text
            
            # Check if fields are already encrypted - try actual decryption to verify
            title_already_encrypted = False
            content_already_encrypted = False
            
            if self.title:
                try:
                    from .encryption import decrypt_text
                    decrypt_text(self.title)  # If this succeeds, it's encrypted
                    title_already_encrypted = True
                except:
                    # Decryption failed - not encrypted (or corrupted)
                    title_already_encrypted = False
            
            if self.content:
                try:
                    from .encryption import decrypt_text
                    decrypt_text(self.content)  # If this succeeds, it's encrypted
                    content_already_encrypted = True
                except:
                    # Decryption failed - not encrypted (or corrupted)
                    content_already_encrypted = False
            
            # Store original values for rollback if needed
            original_title = self.title
            original_content = self.content
            
            # Only encrypt if not already encrypted - prepare encrypted values first
            encrypted_title = None
            encrypted_content = None
            
            if not title_already_encrypted and self.title:
                try:
                    encrypted_title = encrypt_text(self.title)
                    # Verify encryption worked
                    if not encrypted_title or not is_encrypted_text(encrypted_title):
                        print(f"WARNING: Letter {self.id} title encryption verification failed - saving unencrypted")
                        self.is_encrypted = False
                        return False
                except Exception as e:
                    print(f"ERROR: Letter {self.id} title encryption exception: {e}")
                    self.is_encrypted = False
                    return False
            
            if not content_already_encrypted and self.content:
                try:
                    encrypted_content = encrypt_text(self.content)
                    # Verify encryption worked
                    # Note: encrypt_text() returns None for empty strings, which is valid
                    if encrypted_content is None:
                        # Empty string - no encryption needed, leave as is
                        pass
                    elif not is_encrypted_text(encrypted_content):
                        print(f"WARNING: Letter {self.id} content encryption verification failed - saving unencrypted")
                        # Don't modify title if it was encrypted - rollback everything
                        self.is_encrypted = False
                        return False
                    else:
                        # Encryption succeeded - will apply it below
                        pass
                except Exception as e:
                    # If encryption raises exception (e.g., ENCRYPTION_KEY issue), fail
                    # Don't modify title if it was encrypted - rollback everything
                    print(f"ERROR: Letter {self.id} content encryption exception: {e}")
                    self.is_encrypted = False
                    return False
            
            # Apply encryption atomically - only if both succeeded
            if encrypted_title is not None:
                self.title = encrypted_title
            if encrypted_content is not None:
                self.content = encrypted_content
            
            # Mark as encrypted only if encryption succeeded
            title_ok = not self.title or title_already_encrypted or is_encrypted_text(self.title)
            content_ok = not self.content or content_already_encrypted or is_encrypted_text(self.content)
            
            if title_ok and content_ok:
                self.is_encrypted = True
                return True
            else:
                # If encryption failed, don't mark as encrypted
                print(f"WARNING: Letter {self.id} encryption verification failed - saving unencrypted")
                self.is_encrypted = False
                return False
                
        except Exception as e:
            # Log error but don't block letter creation
            print(f"ERROR: Failed to encrypt letter {self.id}: {e}")
            print(f"       Letter will be saved unencrypted. Please check ENCRYPTION_KEY configuration.")
            import traceback
            traceback.print_exc()
            # Ensure is_encrypted is False if encryption fails
            self.is_encrypted = False
            return False  # Return False instead of raising
    
    def decrypt_fields(self):
        """Decrypt title and content fields if encrypted, otherwise return as-is"""
        try:
            if self.is_encrypted:
                from .encryption import decrypt_text
                
                if self.title:
                    self.title = decrypt_text(self.title)
                if self.content:
                    self.content = decrypt_text(self.content)
            # If not encrypted, return as-is (backward compatibility)
        except Exception as e:
            print(f"Error decrypting letter {self.id}: {e}")
            raise
    
    @property
    def decrypted_title(self):
        """Get decrypted title (creates a copy, doesn't modify original)"""
        try:
            from .encryption import decrypt_text, is_encrypted_text
            
            # Check if title is actually encrypted (might be plain text despite is_encrypted flag)
            if self.is_encrypted and self.title:
                # Verify title is actually encrypted before trying to decrypt
                if is_encrypted_text(self.title):
                    return decrypt_text(self.title) or ""
                else:
                    # Title is plain text even though is_encrypted=True - return as-is
                    print(f"Warning: Letter {self.id} is marked encrypted but title appears plain text - returning as-is")
                    return self.title or ""
            return self.title or ""
        except Exception as e:
            print(f"Error getting decrypted title for letter {self.id}: {e}")
            # If decryption fails, it might be plain text - return as-is
            return self.title or ""  # Fallback to original
    
    @property
    def decrypted_content(self):
        """Get decrypted content (creates a copy, doesn't modify original)"""
        try:
            from .encryption import decrypt_text, is_encrypted_text
            
            # Check if content is actually encrypted (might be plain text despite is_encrypted flag)
            if self.is_encrypted and self.content:
                # Verify content is actually encrypted before trying to decrypt
                if is_encrypted_text(self.content):
                    return decrypt_text(self.content) or ""
                else:
                    # Content is plain text even though is_encrypted=True - return as-is
                    print(f"Warning: Letter {self.id} is marked encrypted but content appears plain text - returning as-is")
                    return self.content or ""
            return self.content or ""
        except Exception as e:
            print(f"Error getting decrypted content for letter {self.id}: {e}")
            # If decryption fails, it might be plain text - return as-is
            return self.content or ""  # Fallback to original
    
    @property
    def effective_scheduled_date(self):
        """Get the effective scheduled date - returns delivery_date for date-based delivery, or scheduled_date as fallback"""
        if self.delivery_type == 'date' and self.delivery_date:
            return self.delivery_date
        elif self.scheduled_date:
            return self.scheduled_date
        elif self.delivery_date:
            return self.delivery_date
        return None
    
    # REMOVED: delivery_schedule = db.relationship('DeliverySchedule', backref='letter', uselist=False, cascade='all, delete-orphan')

    __table_args__ = (
        db.Index('idx_letter_user_status', 'user_id', 'status'),
        db.Index('idx_letter_scheduled_date', 'scheduled_date'),
    )

# REMOVE the DeliverySchedule class entirely

class DeathVerification(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id', ondelete='CASCADE'))
    confirmations_count = db.Column(db.Integer, default=0)  # Number of trusted contacts who confirmed
    verification_date = db.Column(db.DateTime(timezone=True), default=func.now())
    status = db.Column(db.String(50), default='pending')  # pending, verified, rejected, pending_main_user_response, denied
    verification_code = db.Column(db.String(100), unique=True)

    __table_args__ = (
        db.Index('idx_death_verification_status', 'status'),
        db.Index('idx_death_verification_code', 'verification_code'),
    )

    user = db.relationship('User')
    confirmations = db.relationship('DeathVerificationConfirmation', back_populates='verification', cascade='all, delete-orphan')

class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(150), unique=True, nullable=False)
    password = db.Column(db.String(150), nullable=True)  # Made nullable for Google users
    first_name = db.Column(db.String(150), nullable=False)
    last_name = db.Column(db.String(150), nullable=False)
    created_date = db.Column(db.DateTime(timezone=True), default=func.now())
    is_active = db.Column(db.Boolean, default=True)
    role = db.Column(db.String(20), default='main')  # 'main' or 'trusted_main'
    
    # Google OAuth fields
    google_id = db.Column(db.String(100), unique=True, nullable=True)
    profile_picture = db.Column(db.String(500), nullable=True)
    is_google_user = db.Column(db.Boolean, default=False)
    
    # Using PostgreSQL's native JSONB type for better performance
    notification_preferences = db.Column(JSONB, default={'email_notifications': True})
    delivery_preferences = db.Column(JSONB, default={'delivery_method': 'email'})
    
    # Two-factor authentication fields
    two_factor_enabled = db.Column(db.Boolean, default=False)
    two_factor_secret = db.Column(db.String(32), nullable=True)
    backup_codes = db.Column(JSONB, nullable=True)
    
    # Password reset fields
    password_reset_token = db.Column(db.String(100), unique=True, nullable=True)
    password_reset_expires = db.Column(db.DateTime(timezone=True), nullable=True)
    
    # Subscription/Plan fields
    plan = db.Column(db.String(20), default='free')  # free, premium, lifetime
    subscription_cycle = db.Column(db.String(10), nullable=True)  # month, year
    stripe_customer_id = db.Column(db.String(100), nullable=True)
    subscription_id = db.Column(db.String(100), nullable=True)
    subscription_status = db.Column(db.String(20), nullable=True)  # active, cancelled, etc.
    
    # Enhanced subscription tracking
    subscription_end_date = db.Column(db.DateTime(timezone=True), nullable=True)
    subscription_cancel_at = db.Column(db.DateTime(timezone=True), nullable=True)
    subscription_cancel_at_period_end = db.Column(db.Boolean, default=False)
    last_payment_date = db.Column(db.DateTime(timezone=True), nullable=True)
    next_payment_date = db.Column(db.DateTime(timezone=True), nullable=True)
    subscription_trial_end = db.Column(db.DateTime(timezone=True), nullable=True)
    
    # Marketing consent
    marketing_consent = db.Column(db.Boolean, default=False)
    
    # Reminder tracking for users without letters
    last_no_letter_reminder_sent_at = db.Column(db.DateTime(timezone=True), nullable=True)
    
    # Reminder tracking for pricing/upsell emails
    last_pricing_reminder_sent_at = db.Column(db.DateTime(timezone=True), nullable=True)
    
    # IP address tracking
    last_login_ip = db.Column(db.String(45), nullable=True)  # Last IP address used for login
    last_login_date = db.Column(db.DateTime(timezone=True), nullable=True)  # Last login timestamp
    registration_ip = db.Column(db.String(45), nullable=True)  # IP address when account was created
    

    
    # Relationships
    letters = db.relationship('Letter', backref='author', lazy='dynamic', cascade='all, delete-orphan')
    trusted_contacts = db.relationship(
        'User',
        secondary=user_trusted_contacts,
        primaryjoin=(id == user_trusted_contacts.c.user_id),
        secondaryjoin=(id == user_trusted_contacts.c.contact_id),
        backref=db.backref('trusted_by', lazy='dynamic'),
        lazy='dynamic'
    )
    # Death verifications where this user is the subject
    death_verifications = db.relationship(
        'DeathVerification',
        foreign_keys=[DeathVerification.user_id],
        lazy='dynamic',
        cascade='all, delete-orphan',
        overlaps="user"
    )

    __table_args__ = (
        db.Index('idx_user_email', 'email'),
        db.Index('idx_user_active', 'is_active'),
    )

class TrustedContact(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id', ondelete='CASCADE'), nullable=False)
    full_name = db.Column(db.String(150), nullable=False)
    email = db.Column(db.String(150), nullable=False)
    phone = db.Column(db.String(20), nullable=True)
    relationship = db.Column(db.String(50), nullable=True)
    is_confirmed = db.Column(db.Boolean, default=False)
    created_date = db.Column(db.DateTime(timezone=True), default=func.now())
    confirmation_code = db.Column(db.String(100), unique=True)
    confirmation_expires = db.Column(db.DateTime(timezone=True), nullable=True)
    death_confirmation_cooldown_until = db.Column(db.DateTime(timezone=True), nullable=True)

    __table_args__ = (
        db.Index('idx_trusted_contact_user', 'user_id'),
        db.Index('idx_trusted_contact_email', 'email'),
    )

    user = db.relationship('User', backref=db.backref('trusted_contacts_list', lazy='dynamic', cascade='all, delete-orphan'))

    def can_verify_death(self):
        return self.is_confirmed

    def can_view_letters(self):
        return self.is_confirmed
    
    def is_in_death_confirmation_cooldown(self):
        """Check if this trusted contact is in cooldown for death confirmations"""
        if not self.death_confirmation_cooldown_until:
            return False
        from datetime import datetime, timezone
        return datetime.now(timezone.utc) < self.death_confirmation_cooldown_until
    
    def set_death_confirmation_cooldown(self, days=7):
        """Set cooldown period for death confirmations"""
        from datetime import datetime, timezone, timedelta
        self.death_confirmation_cooldown_until = datetime.now(timezone.utc) + timedelta(days=days)

class DeathVerificationConfirmation(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    verification_id = db.Column(db.Integer, db.ForeignKey('death_verification.id', ondelete='CASCADE'))
    trusted_contact_id = db.Column(db.Integer, db.ForeignKey('trusted_contact.id', ondelete='CASCADE'))
    confirmed = db.Column(db.Boolean, nullable=False)  # True=confirmed, False=rejected
    confirmed_at = db.Column(db.DateTime(timezone=True), default=func.now())

    __table_args__ = (
        db.UniqueConstraint('verification_id', 'trusted_contact_id', name='uq_verification_trusted_contact'),
    )

    verification = db.relationship('DeathVerification', back_populates='confirmations')
    trusted_contact = db.relationship('TrustedContact')

class Notification(db.Model):
    """Model for storing user notifications"""
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id', ondelete='CASCADE'), nullable=False)
    notification_type = db.Column(db.String(50), nullable=False)  # trusted_contact_confirmed, trusted_contact_removed, death_verification
    title = db.Column(db.String(200), nullable=False)
    message = db.Column(db.Text, nullable=False)
    is_read = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime(timezone=True), default=func.now())
    
    # Optional reference fields for different notification types
    related_user_id = db.Column(db.Integer, db.ForeignKey('user.id', ondelete='CASCADE'), nullable=True)
    related_letter_id = db.Column(db.Integer, db.ForeignKey('letter.id', ondelete='CASCADE'), nullable=True)
    related_trusted_contact_id = db.Column(db.Integer, db.ForeignKey('trusted_contact.id', ondelete='CASCADE'), nullable=True)
    
    __table_args__ = (
        db.Index('idx_notification_user_type', 'user_id', 'notification_type'),
        db.Index('idx_notification_read', 'is_read'),
        db.Index('idx_notification_created', 'created_at'),
    )
    
    user = db.relationship('User', foreign_keys=[user_id])
    related_user = db.relationship('User', foreign_keys=[related_user_id])
    related_letter = db.relationship('Letter', foreign_keys=[related_letter_id])
    related_trusted_contact = db.relationship('TrustedContact', foreign_keys=[related_trusted_contact_id])

class MediaAttachment(db.Model):
    """Model for storing media file information with S3 support - permanent storage only"""
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id', ondelete='CASCADE'), nullable=False)
    letter_id = db.Column(db.Integer, db.ForeignKey('letter.id', ondelete='CASCADE'), nullable=False)  # Required for permanent storage
    file_name = db.Column(db.String(255), nullable=False)
    file_path = db.Column(db.String(500), nullable=False)  # S3 key for permanent storage
    file_type = db.Column(db.String(50), nullable=False)  # image, video, audio
    mime_type = db.Column(db.String(100), nullable=False)
    file_size = db.Column(db.Integer, nullable=False)  # Size in bytes
    duration = db.Column(db.Float, nullable=True)  # For videos/audio in seconds
    thumbnail_path = db.Column(db.String(500), nullable=True)  # For videos
    is_s3_stored = db.Column(db.Boolean, default=True)  # Always True for S3 files
    s3_bucket = db.Column(db.String(100), nullable=True)  # S3 bucket name
    s3_etag = db.Column(db.String(100), nullable=True)  # S3 ETag for integrity
    created_at = db.Column(db.DateTime(timezone=True), default=func.now())
    
    __table_args__ = (
        db.Index('idx_media_user', 'user_id'),
        db.Index('idx_media_letter', 'letter_id'),
        db.Index('idx_media_type', 'file_type'),
        db.Index('idx_media_user_letter', 'user_id', 'letter_id'),
    )
    
    user = db.relationship('User', backref=db.backref('media_attachments', lazy='dynamic'))
    letter = db.relationship('Letter', backref=db.backref('media_files', lazy='dynamic', cascade='all, delete-orphan'))
    
    def get_storage_path(self):
        """Get the storage path for this media"""
        import os
        return os.path.join('uploads', str(self.user_id), str(self.letter_id), f"{self.id}.{self.file_path.split('.')[-1]}")


class NewsletterSubscriber(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(255), unique=True, nullable=False, index=True)
    status = db.Column(db.String(20), nullable=False, default='pending')  # pending, subscribed, unsubscribed, bounced, complained
    source = db.Column(db.String(100), nullable=True)
    tags = db.Column(db.String(255), nullable=True)
    double_opt_in_token = db.Column(db.String(64), nullable=True, unique=True)
    confirmed_at = db.Column(db.DateTime(timezone=True), nullable=True)
    unsubscribed_at = db.Column(db.DateTime(timezone=True), nullable=True)
    created_at = db.Column(db.DateTime(timezone=True), server_default=func.now())
    updated_at = db.Column(db.DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    ip_address = db.Column(db.String(45), nullable=True)
    user_agent = db.Column(db.Text, nullable=True)
    provider = db.Column(db.String(50), nullable=True)
    provider_contact_id = db.Column(db.String(100), nullable=True)

    __table_args__ = (
        db.Index('idx_newsletter_status', 'status'),
    )



class BlockedIP(db.Model):
    """Model to store permanently blocked IP addresses"""
    id = db.Column(db.Integer, primary_key=True)
    ip_address = db.Column(db.String(45), nullable=False, unique=True, index=True)  # IPv4 or IPv6
    reason = db.Column(db.Text, nullable=True)  # Reason for blocking
    blocked_by = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)  # Admin who blocked
    blocked_at = db.Column(db.DateTime(timezone=True), default=func.now())
    is_active = db.Column(db.Boolean, default=True)  # Can be temporarily disabled without deleting
    
    __table_args__ = (
        db.Index('idx_blocked_ip_address', 'ip_address'),
        db.Index('idx_blocked_ip_active', 'is_active'),
    )


class BlogPost(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    slug = db.Column(db.String(200), unique=True, nullable=False)
    title = db.Column(db.String(200), nullable=False)
    excerpt = db.Column(db.String(300), nullable=True)
    content_html = db.Column(db.Text, nullable=False)
    cover_image_url = db.Column(db.String(500), nullable=True)
    status = db.Column(db.String(20), default='draft')  # draft, published
    published_at = db.Column(db.DateTime(timezone=True), nullable=True)
    author_id = db.Column(db.Integer, db.ForeignKey('user.id', ondelete='SET NULL'), nullable=True)
    tags = db.Column(JSONB, nullable=True)  # Array of tag strings
    meta_title = db.Column(db.String(255), nullable=True)
    meta_description = db.Column(db.String(255), nullable=True)
    focus_keyword = db.Column(db.String(100), nullable=True)  # Main SEO focus keyword
    created_at = db.Column(db.DateTime(timezone=True), default=func.now())
    updated_at = db.Column(db.DateTime(timezone=True), default=func.now(), onupdate=func.now())

    __table_args__ = (
        db.Index('idx_blog_status_published_at', 'status', 'published_at'),
        db.Index('idx_blog_slug', 'slug'),
        db.Index('idx_blog_tags', 'tags', postgresql_using='gin'),
    )

    author = db.relationship('User')
    
    def get_tags_list(self):
        """Get tags as a list of strings"""
        if self.tags:
            return self.tags if isinstance(self.tags, list) else []
        return []
    
    def set_tags_list(self, tags_list):
        """Set tags from a list of strings"""
        if tags_list:
            # Clean and normalize tags
            clean_tags = [tag.strip().lower() for tag in tags_list if tag.strip()]
            self.tags = list(set(clean_tags))  # Remove duplicates
        else:
            self.tags = []

class RecipientInvite(db.Model):
    """Model to track recipient invites for letter delivery"""
    id = db.Column(db.Integer, primary_key=True)
    recipient_email = db.Column(db.String(150), nullable=False)
    recipient_name = db.Column(db.String(150), nullable=False)
    letter_id = db.Column(db.Integer, db.ForeignKey('letter.id', ondelete='CASCADE'), nullable=False)
    invite_token = db.Column(db.String(100), unique=True, nullable=False)
    sent_at = db.Column(db.DateTime(timezone=True), default=func.now())
    opened_at = db.Column(db.DateTime(timezone=True), nullable=True)
    clicked_at = db.Column(db.DateTime(timezone=True), nullable=True)
    registered_at = db.Column(db.DateTime(timezone=True), nullable=True)
    last_reminder_sent_at = db.Column(db.DateTime(timezone=True), nullable=True)
    recipient_user_id = db.Column(db.Integer, db.ForeignKey('user.id', ondelete='SET NULL'), nullable=True)
    
    # Relationships
    letter = db.relationship('Letter', backref=db.backref('recipient_invites', cascade='all, delete-orphan'))
    recipient_user = db.relationship('User', backref='received_invites')
    
    __table_args__ = (
        db.Index('idx_recipient_invite_email', 'recipient_email'),
        db.Index('idx_recipient_invite_token', 'invite_token'),
        db.Index('idx_recipient_invite_letter', 'letter_id'),
        db.Index('idx_recipient_invite_reminder', 'last_reminder_sent_at'),
    )
    
    def __init__(self, **kwargs):
        super(RecipientInvite, self).__init__(**kwargs)
        if not self.invite_token:
            self.invite_token = str(uuid.uuid4())
    
    def is_registered(self):
        """Check if recipient has registered"""
        return self.registered_at is not None
    
    def needs_reminder(self):
        """Check if invite needs a reminder (not registered and last reminder > 7 days ago)"""
        if self.is_registered():
            return False
        
        if not self.last_reminder_sent_at:
            return True
        
        from datetime import timedelta
        return datetime.now() - self.last_reminder_sent_at > timedelta(days=7)

class Payment(db.Model):
    """Track payment history for users"""
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id', ondelete='CASCADE'), nullable=False)
    stripe_payment_intent_id = db.Column(db.String(100), nullable=True)
    stripe_invoice_id = db.Column(db.String(100), nullable=True)
    amount = db.Column(db.Integer, nullable=False)  # Amount in cents
    currency = db.Column(db.String(3), default='usd')
    plan = db.Column(db.String(20), nullable=False)  # free, premium, lifetime
    cycle = db.Column(db.String(10), nullable=True)  # month, year, one_time
    status = db.Column(db.String(20), nullable=False)  # succeeded, failed, pending, refunded
    payment_date = db.Column(db.DateTime(timezone=True), default=func.now())
    description = db.Column(db.String(200), nullable=True)
    
    # Relationships
    user = db.relationship('User', backref='payments')
    
    __table_args__ = (
        db.Index('idx_payment_user', 'user_id'),
        db.Index('idx_payment_date', 'payment_date'),
        db.Index('idx_payment_status', 'status'),
    )
