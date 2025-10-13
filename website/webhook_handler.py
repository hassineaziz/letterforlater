from flask import Blueprint, request, jsonify
import stripe
import os
from datetime import datetime, timezone
from . import db
from .models import User, Payment
from .subscription_utils import sync_user_subscription
from .email_service import send_payment_failed_email, send_subscription_cancelled_email
import logging

webhook_bp = Blueprint('webhook', __name__)

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@webhook_bp.route('/stripe-webhook', methods=['POST'])
def stripe_webhook():
    """Handle Stripe webhook events"""
    payload = request.get_data()
    sig_header = request.headers.get('Stripe-Signature')
    webhook_secret = os.getenv('STRIPE_WEBHOOK_SECRET')
    
    # Check if this is a test request (bypass signature verification)
    if sig_header == 'test_signature':
        logger.info("Processing test webhook event (signature verification bypassed)")
        try:
            event = request.get_json()
        except Exception as e:
            logger.error(f"Invalid JSON payload: {e}")
            return jsonify({'error': 'Invalid JSON payload'}), 400
    else:
        # Normal webhook processing with signature verification
        if not webhook_secret:
            logger.error("STRIPE_WEBHOOK_SECRET not configured")
            return jsonify({'error': 'Webhook secret not configured'}), 500
        
        try:
            # Verify webhook signature
            event = stripe.Webhook.construct_event(
                payload, sig_header, webhook_secret
            )
        except ValueError as e:
            logger.error(f"Invalid payload: {e}")
            return jsonify({'error': 'Invalid payload'}), 400
        except stripe._error.SignatureVerificationError as e:
            logger.error(f"Invalid signature: {e}")
            return jsonify({'error': 'Invalid signature'}), 400
    
    # Handle the event
    try:
        if event['type'] == 'customer.subscription.created':
            handle_subscription_created(event['data']['object'])
        elif event['type'] == 'customer.subscription.updated':
            handle_subscription_updated(event['data']['object'])
        elif event['type'] == 'customer.subscription.deleted':
            handle_subscription_deleted(event['data']['object'])
        elif event['type'] == 'invoice.payment_succeeded':
            handle_payment_succeeded(event['data']['object'])
        elif event['type'] == 'invoice.payment_failed':
            handle_payment_failed(event['data']['object'])
        elif event['type'] == 'customer.subscription.trial_will_end':
            handle_trial_will_end(event['data']['object'])
        else:
            logger.info(f"Unhandled event type: {event['type']}")
    
    except Exception as e:
        logger.error(f"Error handling webhook event {event['type']}: {str(e)}")
        return jsonify({'error': 'Webhook handler error'}), 500
    
    return jsonify({'status': 'success'})

def handle_subscription_created(subscription):
    """Handle new subscription creation"""
    logger.info(f"Subscription created: {subscription['id']}")
    
    customer_id = subscription['customer']
    user = User.query.filter_by(stripe_customer_id=customer_id).first()
    
    if user:
        # Update user plan
        user.plan = 'premium'
        user.subscription_id = subscription['id']
        user.subscription_status = subscription['status']
        
        # Set subscription cycle based on price
        if subscription.get('items', {}).get('data'):
            price_id = subscription['items']['data'][0]['price']['id']
            if 'yearly' in price_id or 'year' in price_id:
                user.subscription_cycle = 'year'
            else:
                user.subscription_cycle = 'month'
        
        db.session.commit()
        logger.info(f"Updated user {user.email} to premium plan")
    else:
        logger.warning(f"No user found for customer {customer_id}")

def handle_subscription_updated(subscription):
    """Handle subscription updates (status changes, cancellations, etc.)"""
    logger.info(f"Subscription updated: {subscription['id']}")
    
    subscription_id = subscription['id']
    user = User.query.filter_by(subscription_id=subscription_id).first()
    
    if user:
        # Sync all subscription data
        sync_user_subscription(user.id)
        logger.info(f"Synced subscription data for user {user.email}")
    else:
        logger.warning(f"No user found for subscription {subscription_id}")

def handle_subscription_deleted(subscription):
    """Handle subscription cancellation"""
    logger.info(f"Subscription deleted: {subscription['id']}")
    
    subscription_id = subscription['id']
    user = User.query.filter_by(subscription_id=subscription_id).first()
    
    if user:
        # Downgrade to free plan
        user.plan = 'free'
        user.subscription_status = 'cancelled'
        user.subscription_id = None
        user.subscription_cycle = None
        user.subscription_end_date = None
        user.subscription_cancel_at = datetime.now(timezone.utc)
        user.subscription_cancel_at_period_end = False
        user.next_payment_date = None
        
        db.session.commit()
        logger.info(f"Downgraded user {user.email} to free plan")
        
        # Send cancellation email
        email_sent = send_subscription_cancelled_email(user)
        if email_sent:
            logger.info(f"Cancellation email sent to {user.email}")
        else:
            logger.warning(f"Failed to send cancellation email to {user.email}")
    else:
        logger.warning(f"No user found for subscription {subscription_id}")

def handle_payment_succeeded(invoice):
    """Handle successful payment"""
    logger.info(f"Payment succeeded for invoice: {invoice['id']}")
    
    subscription_id = invoice.get('subscription')
    if subscription_id:
        user = User.query.filter_by(subscription_id=subscription_id).first()
        if user:
            # Update last payment date
            if invoice.get('status_transitions', {}).get('paid_at'):
                user.last_payment_date = datetime.fromtimestamp(
                    invoice['status_transitions']['paid_at'], tz=timezone.utc
                )
            
            # Update subscription status
            user.subscription_status = 'active'
            
            # Create payment record
            payment = Payment(
                user_id=user.id,
                stripe_invoice_id=invoice['id'],
                amount=invoice['amount_paid'],
                currency=invoice['currency'],
                plan=user.plan,
                cycle=user.subscription_cycle,
                status='succeeded',
                payment_date=datetime.fromtimestamp(
                    invoice['status_transitions']['paid_at'], tz=timezone.utc
                ) if invoice.get('status_transitions', {}).get('paid_at') else datetime.now(timezone.utc),
                description=f"{user.plan.title()} subscription payment"
            )
            db.session.add(payment)
            db.session.commit()
            logger.info(f"Updated payment info for user {user.email}")

def handle_payment_failed(invoice):
    """Handle failed payment"""
    logger.info(f"Payment failed for invoice: {invoice['id']}")
    
    subscription_id = invoice.get('subscription')
    if subscription_id:
        user = User.query.filter_by(subscription_id=subscription_id).first()
        if user:
            # Update subscription status
            user.subscription_status = 'past_due'
            db.session.commit()
            logger.info(f"Marked subscription as past due for user {user.email}")
            
            # Send payment failed email
            email_sent = send_payment_failed_email(user, invoice)
            if email_sent:
                logger.info(f"Payment failed email sent to {user.email}")
            else:
                logger.warning(f"Failed to send payment failed email to {user.email}")

def handle_trial_will_end(subscription):
    """Handle trial ending soon"""
    logger.info(f"Trial will end for subscription: {subscription['id']}")
    
    subscription_id = subscription['id']
    user = User.query.filter_by(subscription_id=subscription_id).first()
    
    if user:
        # You could send an email notification here
        logger.info(f"Trial ending soon for user {user.email}")
        # TODO: Add email notification logic

@webhook_bp.route('/test-webhook', methods=['GET'])
def test_webhook():
    """Test endpoint to verify webhook is working"""
    return jsonify({
        'status': 'success',
        'message': 'Webhook endpoint is working',
        'timestamp': datetime.now(timezone.utc).isoformat()
    })
