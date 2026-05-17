import stripe
from datetime import datetime, timezone
from .models import User, db
from .stripe_config import stripe

def sync_user_subscription(user_id):
    """
    Sync user's subscription data from Stripe.
    This is the core synchronization logic that ensures our DB matches Stripe.
    """
    user = User.query.get(user_id)
    if not user or not user.stripe_customer_id:
        return False
    
    try:
        # Get active subscriptions for this customer
        subscriptions = stripe.Subscription.list(
            customer=user.stripe_customer_id,
            status='all',
            limit=1
        )
        
        if subscriptions.data:
            subscription = subscriptions.data[0]
            
            # Basic info
            user.subscription_id = subscription.id
            user.subscription_status = subscription.status
            user.plan = 'premium' # If they have an active sub, they are premium
            
            # Handle cancellation status
            user.subscription_cancel_at_period_end = subscription.cancel_at_period_end
            
            if subscription.cancel_at:
                user.subscription_cancel_at = datetime.fromtimestamp(subscription.cancel_at, tz=timezone.utc)
            else:
                user.subscription_cancel_at = None

            # Period dates
            user.subscription_end_date = datetime.fromtimestamp(subscription.current_period_end, tz=timezone.utc)
            
            if subscription.trial_end:
                user.subscription_trial_end = datetime.fromtimestamp(subscription.trial_end, tz=timezone.utc)
            else:
                user.subscription_trial_end = None

            # Cycle detection
            price = subscription['items']['data'][0]['price']
            user.subscription_cycle = price['recurring']['interval'] # 'month' or 'year'
            
            # Next payment date
            if subscription.status == 'active' and not subscription.cancel_at_period_end:
                user.next_payment_date = datetime.fromtimestamp(subscription.current_period_end, tz=timezone.utc)
            else:
                user.next_payment_date = None

            db.session.commit()
            return True
            
        else:
            # No subscription found in Stripe. 
            # If they are 'lifetime', we don't touch them.
            if user.plan != 'lifetime':
                user.plan = 'free'
                user.subscription_status = None
                user.subscription_id = None
                user.subscription_cycle = None
                user.next_payment_date = None
                db.session.commit()
            return True
            
    except Exception as e:
        print(f"Error syncing subscription for user {user_id}: {str(e)}")
        return False

def is_subscription_active(user):
    """Check if user has an active premium or lifetime plan"""
    if not user or not user.is_authenticated:
        return False
    
    if user.plan == 'lifetime':
        return True
    
    if user.plan == 'premium' and user.subscription_status in ['active', 'trialing']:
        return True
    
    # Grace period check for cancelled subscriptions that haven't reached period end
    if user.subscription_status == 'cancelled' and user.subscription_end_date:
        if user.subscription_end_date > datetime.now(timezone.utc):
            return True
            
    return False

def get_subscription_status(user):
    """Get human-readable subscription status for the UI"""
    if not user:
        return {'status': 'none', 'label': 'No account'}
    
    if user.plan == 'lifetime':
        return {'status': 'lifetime', 'label': 'Lifetime Heritage'}
    
    if user.plan == 'free':
        return {'status': 'free', 'label': 'Free Plan'}
    
    status_map = {
        'active': 'Premium (Active)',
        'trialing': 'Premium (Trial)',
        'past_due': 'Premium (Payment Overdue)',
        'unpaid': 'Premium (Unpaid)',
        'cancelled': 'Premium (Cancelled)',
        'incomplete': 'Premium (Pending Setup)'
    }
    
    label = status_map.get(user.subscription_status, f"Premium ({user.subscription_status})")
    
    if user.subscription_cancel_at_period_end:
        label += " - Ending soon"
        
    return {
        'status': user.subscription_status,
        'label': label,
        'end_date': user.subscription_end_date,
        'next_payment': user.next_payment_date
    }
