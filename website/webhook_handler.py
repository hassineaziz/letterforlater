from flask import Blueprint, request, jsonify
import stripe
import os
from datetime import datetime, timezone
from . import db
from .models import User, Payment
from .subscription_utils import sync_user_subscription
import logging

webhook_bp = Blueprint('webhook', __name__)
logger = logging.getLogger(__name__)

@webhook_bp.route('/stripe-webhook', methods=['POST'])
def stripe_webhook():
    """Handle incoming Stripe webhook events"""
    payload = request.get_data()
    sig_header = request.headers.get('Stripe-Signature')
    webhook_secret = os.getenv('STRIPE_WEBHOOK_SECRET')
    
    # Signature verification
    try:
        event = stripe.Webhook.construct_event(payload, sig_header, webhook_secret)
    except Exception as e:
        logger.error(f"Webhook error: {str(e)}")
        return jsonify({'error': 'Invalid payload or signature'}), 400
    
    # Event Router
    event_type = event['type']
    data_object = event['data']['object']
    
    try:
        if event_type == 'checkout.session.completed':
            handle_checkout_completed(data_object)
        elif event_type in ['customer.subscription.created', 'customer.subscription.updated', 'customer.subscription.deleted']:
            handle_subscription_event(data_object)
        elif event_type == 'invoice.payment_succeeded':
            handle_payment_succeeded(data_object)
        elif event_type == 'invoice.payment_failed':
            handle_payment_failed(data_object)
    except Exception as e:
        logger.error(f"Error processing {event_type}: {str(e)}")
        return jsonify({'error': 'Processing failed'}), 500
    
    return jsonify({'status': 'success'})

def handle_checkout_completed(session):
    """Handle completed checkout for one-time payments (Lifetime)"""
    user_id = session.get('metadata', {}).get('user_id')
    plan = session.get('metadata', {}).get('plan')
    
    if not user_id: return
    
    user = User.query.get(int(user_id))
    if not user: return
    
    # Always update customer ID
    user.stripe_customer_id = session.get('customer')
    
    if session.get('mode') == 'payment' and plan == 'lifetime':
        user.plan = 'lifetime'
        user.subscription_status = 'active'
        
        # Log payment
        payment = Payment(
            user_id=user.id,
            stripe_payment_intent_id=session.get('payment_intent'),
            amount=session.get('amount_total', 0),
            currency=session.get('currency', 'usd'),
            plan='lifetime',
            status='succeeded',
            description="Lifetime Heritage Plan purchase"
        )
        db.session.add(payment)
    
    db.session.commit()
    logger.info(f"Checkout completed for user {user.email} (Plan: {plan})")

def handle_subscription_event(subscription):
    """Source of truth for all subscription changes"""
    customer_id = subscription.get('customer')
    user = User.query.filter_by(stripe_customer_id=customer_id).first()
    
    if user:
        sync_user_subscription(user.id)
        logger.info(f"Synced subscription for {user.email} due to {subscription.get('status')}")

def handle_payment_succeeded(invoice):
    """Log successful recurring payments"""
    customer_id = invoice.get('customer')
    user = User.query.filter_by(stripe_customer_id=customer_id).first()
    
    if user:
        payment = Payment(
            user_id=user.id,
            stripe_invoice_id=invoice.get('id'),
            amount=invoice.get('amount_paid', 0),
            currency=invoice.get('currency', 'usd'),
            plan=user.plan,
            status='succeeded',
            description=f"Recurring payment for {user.plan} plan"
        )
        db.session.add(payment)
        db.session.commit()

def handle_payment_failed(invoice):
    """Log failed payments"""
    customer_id = invoice.get('customer')
    user = User.query.filter_by(stripe_customer_id=customer_id).first()
    if user:
        logger.warning(f"Payment failed for user {user.email} (Invoice: {invoice.get('id')})")
        # Logic for emails or access restriction can go here

@webhook_bp.route('/test-webhook', methods=['GET'])
def test_webhook():
    """Test endpoint to verify webhook is working"""
    return jsonify({
        'status': 'success',
        'message': 'Webhook endpoint is working',
        'timestamp': datetime.now(timezone.utc).isoformat()
    })
