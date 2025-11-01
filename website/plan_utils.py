"""
Plan utilities for managing feature restrictions and upgrade prompts
"""
from flask import current_app
from functools import wraps
from flask_login import current_user

def get_user_plan():
    """Get the current user's plan"""
    if not current_user.is_authenticated:
        return 'free'
    return current_user.plan or 'free'

def is_premium_user():
    """Check if user has premium or lifetime plan"""
    plan = get_user_plan()
    return plan in ['premium', 'lifetime']

def is_lifetime_user():
    """Check if user has lifetime plan"""
    return get_user_plan() == 'lifetime'

def can_create_unlimited_letters():
    """Check if user can create unlimited letters"""
    return is_premium_user()

def can_upload_media():
    """Check if user can upload photos, videos, audio"""
    return is_premium_user()

def can_schedule_letters():
    """Check if user can schedule letters for birthdays/milestones"""
    return is_premium_user()

def can_use_scheduled_delivery():
    """Check if user can use date-based scheduled delivery (premium only)"""
    return is_premium_user()

def can_use_death_verification():
    """Check if user can use death verification delivery (available to all users)"""
    return True  # Available to all users

def can_add_unlimited_contacts():
    """Check if user can add unlimited trusted contacts - ALL USERS CAN"""
    return True  # No restrictions on trusted contacts

def get_max_letters():
    """Get maximum letters allowed for user's plan"""
    if is_premium_user():
        return float('inf')  # Unlimited
    return 1

def get_max_contacts():
    """Get maximum trusted contacts allowed for user's plan - UNLIMITED FOR ALL"""
    return float('inf')  # Unlimited for all users

def get_storage_limit():
    """Get storage limit for user's plan"""
    if is_lifetime_user():
        return float('inf')  # No limit for lifetime
    elif is_premium_user():
        return 5 * 1024 * 1024 * 1024  # 5GB for premium
    else:
        return 0  # No media storage for free

def get_plan_features():
    """Get available features for user's current plan"""
    plan = get_user_plan()
    
    features = {
        'letters': {
            'unlimited': can_create_unlimited_letters(),
            'max_count': get_max_letters(),
            'text_only': not can_upload_media()
        },
        'media': {
            'enabled': can_upload_media(),
            'storage_limit': get_storage_limit(),
            'types': ['photos', 'videos', 'audio'] if can_upload_media() else []
        },
        'contacts': {
            'unlimited': can_add_unlimited_contacts(),
            'max_count': get_max_contacts()
        },
        'scheduling': {
            'enabled': can_schedule_letters(),
            'milestones': can_schedule_letters()
        },
        'support': {
            'priority': is_premium_user(),
            'email_only': not is_premium_user()
        }
    }
    
    return features

def get_upgrade_message(feature_name, current_plan=None):
    """Get upgrade message for specific feature"""
    plan = current_plan or get_user_plan()
    
    messages = {
        'unlimited_letters': {
            'title': 'Unlock Unlimited Letters',
            'message': 'Create as many legacy letters as you want for your loved ones.',
            'benefit': 'Write letters for birthdays, graduations, weddings, and special moments.'
        },
        'media_attachments': {
            'title': 'Add Photos & Videos',
            'message': 'Attach precious photos, videos, and audio recordings to your letters.',
            'benefit': 'Make your memories come alive with multimedia attachments.'
        },
        'unlimited_contacts': {
            'title': 'Add More Trusted Contacts',
            'message': 'Share your letters with unlimited trusted family and friends.',
            'benefit': 'Ensure everyone important receives your messages.'
        },
        'scheduled_delivery': {
            'title': 'Schedule for Special Moments',
            'message': 'Schedule letters to be delivered on birthdays, graduations, and milestones.',
            'benefit': 'Create magical moments with perfectly timed deliveries.'
        },
        'priority_support': {
            'title': 'Get Priority Support',
            'message': 'Get faster, dedicated support when you need help.',
            'benefit': 'We\'re here to help you preserve your legacy.'
        }
    }
    
    return messages.get(feature_name, {
        'title': 'Upgrade to Premium',
        'message': 'Unlock this feature and more with Premium.',
        'benefit': 'Get unlimited access to all features.'
    })

def get_plan_comparison():
    """Get plan comparison data"""
    return {
        'free': {
            'name': 'Free',
            'price': '$0',
            'period': 'forever',
            'features': [
                'Unlimited letters',
                'Text only (no media)',
                'Unlimited trusted contacts',
                'Death verification delivery',
                'Email support',
                'Bank-level encryption',
                'Email delivery tracking'
            ],
            'limitations': [
                'No media attachments',
                'No scheduled delivery',
                'Standard support'
            ]
        },
        'premium': {
            'name': 'Premium',
            'price': '$2.99',
            'period': 'per month',
            'features': [
                'Unlimited letters',
                'Photos, videos, and audio attachments',
                'Unlimited trusted contacts',
                'Schedule letters for birthdays & milestones',
                'Priority support',
                'All free features included'
            ],
            'benefits': [
                'Write unlimited letters',
                'Attach precious memories',
                'Share with everyone important',
                'Create magical moments'
            ]
        },
        'lifetime': {
            'name': 'Lifetime',
            'price': '$99.99',
            'period': 'one-time payment',
            'features': [
                'Everything in Premium',
                'Pay once, use forever',
                'Unlimited storage',
                'Lifetime updates',
                'VIP support'
            ],
            'benefits': [
                'No recurring payments',
                'Permanent access',
                'Maximum value',
                'Future-proof'
            ]
        }
    }

def requires_premium(feature_name=None):
    """Decorator to require premium access for a function"""
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not is_premium_user():
                from flask import jsonify, request
                if request.is_json:
                    return jsonify({
                        'error': 'Premium feature',
                        'message': get_upgrade_message(feature_name or 'premium_feature'),
                        'upgrade_url': '/pricing'
                    }), 403
                else:
                    from flask import redirect, url_for, flash
                    flash('This feature requires Premium. Upgrade to unlock unlimited access!', 'info')
                    return redirect(url_for('pricing.pricing_page'))
            return f(*args, **kwargs)
        return decorated_function
    return decorator

def check_feature_access(feature_name):
    """Check if user has access to a specific feature"""
    access_map = {
        'unlimited_letters': can_create_unlimited_letters(),
        'media_attachments': can_upload_media(),
        'unlimited_contacts': can_add_unlimited_contacts(),
        'scheduled_delivery': can_schedule_letters(),
        'priority_support': is_premium_user()
    }
    
    return access_map.get(feature_name, False)

def get_upgrade_cta_text(plan=None):
    """Get call-to-action text for upgrades"""
    current_plan = plan or get_user_plan()
    
    if current_plan == 'free':
        return {
            'primary': 'Upgrade to Premium',
            'secondary': 'Get Lifetime Access',
            'price_primary': '$2.99/month',
            'price_secondary': '$99.99 one-time',
            'benefit': 'Save 20% on annual subscription!'
        }
    elif current_plan == 'premium':
        return {
            'primary': 'Upgrade to Lifetime',
            'secondary': 'Get Lifetime Access',
            'price_primary': '$99.99 one-time',
            'price_secondary': 'Pay once, use forever',
            'benefit': 'No more monthly payments!'
        }
    
    return {
        'primary': 'View Plans',
        'secondary': 'Learn More',
        'price_primary': '',
        'price_secondary': '',
        'benefit': ''
    }
