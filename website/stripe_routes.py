from flask import Blueprint, render_template, request, jsonify, redirect, url_for, flash
from flask_login import login_required, current_user
import stripe
from . import db
from .models import User
from .stripe_config import get_stripe_price_id, STRIPE_PRODUCTS
from .email_service import send_payment_success_email

stripe_bp = Blueprint('stripe', __name__)

@stripe_bp.route('/create-checkout-session', methods=['POST'])
@login_required
def create_checkout_session():
    try:
        plan = request.json.get('plan')
        cycle = request.json.get('cycle', 'month')
        
        # Handle free plan - just redirect to signup
        if plan == 'free':
            return jsonify({'redirect': url_for('auth.sign_up', plan='free')})
        
        # Get Stripe price ID
        price_id = get_stripe_price_id(plan, cycle)
        
        if not price_id:
            return jsonify({'error': 'Invalid plan'}), 400
        
        # Determine if it's a subscription or one-time payment
        mode = 'subscription' if plan == 'premium' else 'payment'
        
        # Create checkout session
        checkout_session = stripe.checkout.Session.create(
            payment_method_types=['card'],
            line_items=[{
                'price': price_id,
                'quantity': 1,
            }],
            mode=mode,
            success_url=request.url_root + 'payment-success?session_id={CHECKOUT_SESSION_ID}',
            cancel_url=request.url_root + 'payment-cancel',
            customer_email=current_user.email,
            allow_promotion_codes=True,
            metadata={
                'user_id': current_user.id,
                'plan': plan,
                'cycle': cycle
            }
        )
        
        return jsonify({'checkout_url': checkout_session.url})
        
    except Exception as e:
        print(f"Stripe error: {str(e)}")
        return jsonify({'error': 'Payment processing failed. Please try again.'}), 500

@stripe_bp.route('/payment-cancel')
def payment_cancel():
    flash('Payment was cancelled. You can try again anytime.', 'info')
    return render_template('payment_cancel.html')

@stripe_bp.route('/payment-success')
@login_required
def payment_success():
    session_id = request.args.get('session_id')
    
    if session_id:
        try:
            # Retrieve the session from Stripe
            session = stripe.checkout.Session.retrieve(session_id)
            
            # Get plan info from metadata
            plan = session.metadata.get('plan')
            cycle = session.metadata.get('cycle', 'month')
            
            # Update user's plan in database
            current_user.plan = plan
            if plan == 'premium':
                current_user.subscription_cycle = cycle
            
            # Store Stripe customer ID if this is their first payment
            if not current_user.stripe_customer_id:
                current_user.stripe_customer_id = session.customer
            
            db.session.commit()
            
            # Send payment success email
            email_sent = send_payment_success_email(current_user, session)
            if email_sent:
                print(f"✅ Payment success email sent to {current_user.email}")
            else:
                print(f"❌ Failed to send payment success email to {current_user.email}")
            
            flash(f'Welcome to {plan.title()} plan! Your payment was successful.', 'success')
            
        except Exception as e:
            print(f"Error processing payment success: {str(e)}")
            flash('Payment was successful, but there was an error updating your account. Please contact support.', 'warning')
    
    return render_template('payment_success.html',
        user_name=f"{current_user.first_name} {current_user.last_name}",
        user_plan=current_user.plan,
        user_cycle=current_user.subscription_cycle,
        user_next_payment=current_user.next_payment_date
    )

@stripe_bp.route('/change-billing-cycle', methods=['POST'])
@login_required
def change_billing_cycle():
    """Change user's billing cycle"""
    try:
        new_cycle = request.form.get('new_cycle')
        
        if not new_cycle or new_cycle not in ['month', 'year']:
            flash('Invalid billing cycle selected.', 'error')
            return redirect(url_for('views.settings'))
        
        if not current_user.subscription_id:
            flash('No active subscription found.', 'error')
            return redirect(url_for('views.settings'))
        
        # Get the new price ID
        new_price_id = None
        if new_cycle == 'month':
            new_price_id = STRIPE_PRODUCTS['premium_monthly']
        elif new_cycle == 'year':
            new_price_id = STRIPE_PRODUCTS['premium_yearly']
        
        if not new_price_id:
            flash('Unable to process billing cycle change.', 'error')
            return redirect(url_for('views.settings'))
        
        # Update the subscription in Stripe
        subscription = stripe.Subscription.retrieve(current_user.subscription_id)
        
        # Update the subscription with new price
        stripe.Subscription.modify(
            current_user.subscription_id,
            items=[{
                'id': subscription['items']['data'][0]['id'],
                'price': new_price_id,
            }],
            proration_behavior='create_prorations'
        )
        
        # Update user's billing cycle in database
        current_user.subscription_cycle = new_cycle
        db.session.commit()
        
        flash(f'Billing cycle changed to {new_cycle.title()} successfully!', 'success')
        
    except Exception as e:
        print(f"Error changing billing cycle: {str(e)}")
        flash('Failed to change billing cycle. Please try again.', 'error')
        db.session.rollback()
    
    return redirect(url_for('views.settings'))

@stripe_bp.route('/cancel-subscription', methods=['POST'])
@login_required
def cancel_subscription():
    """Cancel user's subscription"""
    try:
        cancel_reason = request.form.get('cancel_reason', '')
        cancel_feedback = request.form.get('cancel_feedback', '')
        
        if not current_user.subscription_id:
            flash('No active subscription found.', 'error')
            return redirect(url_for('views.settings'))
        
        # Cancel the subscription in Stripe (at period end)
        stripe.Subscription.modify(
            current_user.subscription_id,
            cancel_at_period_end=True
        )
        
        # Update user's subscription status
        current_user.subscription_cancel_at_period_end = True
        db.session.commit()
        
        # Log cancellation reason for analytics
        print(f"Subscription cancelled for user {current_user.email}")
        print(f"Reason: {cancel_reason}")
        print(f"Feedback: {cancel_feedback}")
        
        flash('Your subscription has been cancelled. You\'ll keep access until your next billing date.', 'success')
        
    except Exception as e:
        print(f"Error cancelling subscription: {str(e)}")
        flash('Failed to cancel subscription. Please contact support.', 'error')
        db.session.rollback()
    
    return redirect(url_for('views.settings'))

@stripe_bp.route('/reactivate-subscription', methods=['POST'])
@login_required
def reactivate_subscription():
    """Reactivate a cancelled subscription"""
    try:
        if not current_user.subscription_id:
            flash('No subscription found.', 'error')
            return redirect(url_for('views.settings'))
        
        # Reactivate the subscription in Stripe
        stripe.Subscription.modify(
            current_user.subscription_id,
            cancel_at_period_end=False
        )
        
        # Update user's subscription status
        current_user.subscription_cancel_at_period_end = False
        db.session.commit()
        
        flash('Your subscription has been reactivated!', 'success')
        
    except Exception as e:
        print(f"Error reactivating subscription: {str(e)}")
        flash('Failed to reactivate subscription. Please contact support.', 'error')
        db.session.rollback()
    
    return redirect(url_for('views.settings'))
