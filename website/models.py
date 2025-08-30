from . import db
from flask_login import UserMixin
from sqlalchemy.sql import func
from datetime import datetime
import json
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
    status = db.Column(db.String(20), default='pending')  # pending, verified, rejected
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
    password = db.Column(db.String(150), nullable=False)
    first_name = db.Column(db.String(150), nullable=False)
    last_name = db.Column(db.String(150), nullable=False)
    created_date = db.Column(db.DateTime(timezone=True), default=func.now())
    is_active = db.Column(db.Boolean, default=True)
    role = db.Column(db.String(20), default='main')  # 'main' or 'trusted_main'
    
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

    __table_args__ = (
        db.Index('idx_trusted_contact_user', 'user_id'),
        db.Index('idx_trusted_contact_email', 'email'),
    )

    user = db.relationship('User', backref=db.backref('trusted_contacts_list', lazy='dynamic', cascade='all, delete-orphan'))

    def can_verify_death(self):
        return self.is_confirmed

    def can_view_letters(self):
        return self.is_confirmed

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
