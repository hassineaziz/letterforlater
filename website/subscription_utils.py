import stripe
from datetime import datetime, timezone
from .models import User, db
from .stripe_config import stripe

def sync_user_subscription(user_id):
    """Sync user's subscription data from Stripe"""
    user = User.query.get(user_id)
    if not user or not user.stripe_customer_id:
        return False
    
    try:
        # Get customer from Stripe
        customer = stripe.Customer.retrieve(user.stripe_customer_id)
        
        # Get active subscriptions
        subscriptions = stripe.Subscription.list(
            customer=user.stripe_customer_id,
            status='all',
            limit=1
        )
        
        if subscriptions.data:
            subscription = subscriptions.data[0]
            
            # Update user with subscription data
            user.subscription_id = subscription.id
            user.subscription_status = subscription.status
            
            # Get subscription data as dict to access nested fields
            sub_dict = subscription.to_dict()
            
            # Get current period end from subscription items (new Stripe API structure)
            current_period_end = None
            if 'items' in sub_dict and sub_dict['items'] and sub_dict['items'].get('data'):
                current_period_end = sub_dict['items']['data'][0].get('current_period_end')
            
            # Convert timestamps to datetime objects
            if current_period_end:
                user.subscription_end_date = datetime.fromtimestamp(
                    current_period_end, tz=timezone.utc
                )
            
            if hasattr(subscription, 'canceled_at') and subscription.canceled_at:
                user.subscription_cancel_at = datetime.fromtimestamp(
                    subscription.canceled_at, tz=timezone.utc
                )
            
            user.subscription_cancel_at_period_end = getattr(subscription, 'cancel_at_period_end', False)
            
            if hasattr(subscription, 'trial_end') and subscription.trial_end:
                user.subscription_trial_end = datetime.fromtimestamp(
                    subscription.trial_end, tz=timezone.utc
                )
            
            # Get latest invoice for payment info
            if subscription.latest_invoice:
                invoice = stripe.Invoice.retrieve(subscription.latest_invoice)
                if invoice.status == 'paid' and invoice.status_transitions.paid_at:
                    user.last_payment_date = datetime.fromtimestamp(
                        invoice.status_transitions.paid_at, tz=timezone.utc
                    )
            
            # Calculate next payment date
            if subscription.status == 'active' and current_period_end:
                user.next_payment_date = datetime.fromtimestamp(
                    current_period_end, tz=timezone.utc
                )
            
            db.session.commit()
            return True
            
        else:
            # No active subscription - user should be on free plan
            user.plan = 'free'
            user.subscription_status = 'cancelled'
            user.subscription_id = None
            db.session.commit()
            return True
            
    except Exception as e:
        print(f"Error syncing subscription for user {user_id}: {str(e)}")
        return False

def is_subscription_active(user):
    """Check if user has an active subscription"""
    if not user or user.plan == 'free':
        return False
    
    if user.plan == 'lifetime':
        return True
    
    if user.subscription_status == 'active':
        # Check if subscription hasn't expired
        if user.subscription_end_date and user.subscription_end_date > datetime.now(timezone.utc):
            return True
    
    return False

def get_subscription_status(user):
    """Get detailed subscription status for user"""
    if not user:
        return {'status': 'no_user', 'message': 'No user provided'}
    
    if user.plan == 'free':
        return {'status': 'free', 'message': 'Free plan user'}
    
    if user.plan == 'lifetime':
        return {'status': 'lifetime', 'message': 'Lifetime plan - permanent access'}
    
    if not user.stripe_customer_id:
        return {'status': 'error', 'message': 'No Stripe customer ID'}
    
    # Sync latest data from Stripe
    sync_user_subscription(user.id)
    
    if user.subscription_status == 'active':
        if user.subscription_end_date and user.subscription_end_date > datetime.now(timezone.utc):
            return {
                'status': 'active',
                'message': 'Subscription active',
                'next_payment': user.next_payment_date,
                'end_date': user.subscription_end_date
            }
        else:
            return {'status': 'expired', 'message': 'Subscription expired'}
    
    elif user.subscription_status == 'cancelled':
        if user.subscription_cancel_at_period_end and user.subscription_end_date:
            if user.subscription_end_date > datetime.now(timezone.utc):
                return {
                    'status': 'cancelled_at_period_end',
                    'message': 'Cancelled but active until period end',
                    'end_date': user.subscription_end_date
                }
            else:
                return {'status': 'cancelled', 'message': 'Subscription cancelled and expired'}
        else:
            return {'status': 'cancelled', 'message': 'Subscription cancelled immediately'}
    
    elif user.subscription_status == 'past_due':
        return {'status': 'past_due', 'message': 'Payment failed - subscription past due'}
    
    else:
        return {'status': 'unknown', 'message': f'Unknown status: {user.subscription_status}'}

def sync_all_subscriptions():
    """Sync all premium users' subscription data"""
    premium_users = User.query.filter(User.plan.in_(['premium', 'lifetime'])).all()
    results = []
    
    for user in premium_users:
        if user.stripe_customer_id:
            success = sync_user_subscription(user.id)
            results.append({
                'user_id': user.id,
                'email': user.email,
                'success': success
            })
    
    return results
