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
    """Create a Stripe Checkout Session for plan upgrades"""
    try:
        data = request.get_json()
        plan = data.get('plan')
        # cycle = data.get('cycle', 'month')
        cycle = data.get('cycle', 'year')
        
        print(f"DEBUG: Create Checkout Session - User: {current_user.email}, Plan: {plan}, Cycle: {cycle}")
        
        # Handle free plan - redirect to dashboard as they are already logged in
        if plan == 'free':
            print("DEBUG: Plan is free, redirecting to home")
            return jsonify({'redirect': url_for('views.home')})
        
        # Get Stripe price ID
        price_id = get_stripe_price_id(plan, cycle)
        print(f"DEBUG: Price ID: {price_id}")
        
        if not price_id:
            print(f"DEBUG: Invalid price ID for plan {plan}, cycle {cycle}")
            return jsonify({'error': 'Invalid plan or billing cycle selected.'}), 400
        
        # Determine if it's a subscription (Premium) or one-time payment (Lifetime)
        mode = 'subscription' if plan == 'premium' else 'payment'
        print(f"DEBUG: Mode: {mode}")
        
        # Build checkout session parameters
        session_params = {
            'payment_method_types': ['card'],
            'line_items': [{
                'price': price_id,
                'quantity': 1,
            }],
            'mode': mode,
            'success_url': request.url_root.rstrip('/') + url_for('stripe.payment_success') + '?session_id={CHECKOUT_SESSION_ID}',
            'cancel_url': request.url_root.rstrip('/') + url_for('stripe.payment_cancel'),
            'allow_promotion_codes': True,
            'metadata': {
                'user_id': current_user.id,
                'plan': plan,
                'cycle': cycle
            }
        }
        
        # Reuse existing customer ID if available to prevent duplicates in Stripe
        if current_user.stripe_customer_id:
            session_params['customer'] = current_user.stripe_customer_id
        else:
            session_params['customer_email'] = current_user.email
            
        # Create checkout session
        checkout_session = stripe.checkout.Session.create(**session_params)
        
        return jsonify({'checkout_url': checkout_session.url})
        
    except stripe.InvalidRequestError as e:
        if 'No such customer' in str(e):
            print(f"DEBUG: Invalid customer ID {current_user.stripe_customer_id} for this environment. Clearing it.")
            current_user.stripe_customer_id = None
            db.session.commit()
            # Optionally: Re-call the function or tell the user to try again
            return jsonify({'error': 'Your billing record was outdated for this environment. It has been reset. Please click the button again to proceed.', 'retry': True}), 400
        
        print(f"Stripe Invalid Request: {str(e)}")
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        print(f"Stripe Checkout Error: {str(e)}")
        return jsonify({'error': 'Could not initiate payment. Please try again or contact support.'}), 500

@stripe_bp.route('/create-customer-portal', methods=['POST'])
@login_required
def create_customer_portal():
    """Create a Stripe Customer Portal session for billing management"""
    try:
        # Fallback: If customer ID is missing, try to find it in Stripe by email
        if not current_user.stripe_customer_id:
            print(f"DEBUG: Customer ID missing for {current_user.email}, attempting recovery...")
            customers = stripe.Customer.list(email=current_user.email, limit=1)
            if customers.data:
                current_user.stripe_customer_id = customers.data[0].id
                db.session.commit()
                print(f"DEBUG: Recovered Customer ID: {current_user.stripe_customer_id}")
            else:
                flash("No billing record found. Please upgrade your plan first.", "info")
                return redirect(url_for('pricing.pricing_page'))

        # Create portal session
        return_url = url_for('views.settings', _external=True)
        print(f"DEBUG: Billing Portal - User: {current_user.email}")
        print(f"DEBUG: Customer ID: {current_user.stripe_customer_id}")
        print(f"DEBUG: Return URL: {return_url}")
        
        try:
            portal_session = stripe.billing_portal.Session.create(
                customer=current_user.stripe_customer_id,
                return_url=return_url,
            )
            print(f"DEBUG: Portal Session Created: {portal_session.url[:50]}...")
            return redirect(portal_session.url)
        except stripe.error.StripeError as e:
            print(f"STRIPE ERROR: {str(e)}")
            flash(f"Stripe Portal Error: {e.user_message if hasattr(e, 'user_message') else str(e)}", "error")
            return redirect(url_for('views.settings'))
        
    except Exception as e:
        print(f"GENERAL ERROR: {str(e)}")
        flash(f"System Error: {str(e)}", "error")
        return redirect(url_for('views.settings'))

@stripe_bp.route('/payment-cancel')
def payment_cancel():
    flash('Payment was cancelled. You can resume writing or try again anytime.', 'info')
    return redirect(url_for('pricing.pricing_page'))

@stripe_bp.route('/payment-success')
@login_required
def payment_success():
    """Display success page after payment (Webhook handles the actual DB update)"""
    session_id = request.args.get('session_id')
    
    # Optional: Force a quick sync from Stripe if session_id is present
    # This provides immediate feedback even if the webhook is slightly delayed
    if session_id:
        try:
            session = stripe.checkout.Session.retrieve(session_id)
            if session.payment_status == 'paid':
                # Use the core sync utility for a full update (dates, status, etc.)
                if not current_user.stripe_customer_id:
                    current_user.stripe_customer_id = session.customer
                    db.session.commit()
                
                sync_user_subscription(current_user.id)
                print(f"DEBUG: Post-payment sync completed for {current_user.email}")
        except Exception as e:
            print(f"Post-payment sync warning: {str(e)}")

    return render_template('payment_success.html',
        user_name=f"{current_user.first_name}",
        user_plan=current_user.plan
    )

# Redundant routes kept for backward compatibility but marked for removal
# The Customer Portal now handles these actions more reliably.
@stripe_bp.route('/change-billing-cycle', methods=['POST'])
@login_required
def change_billing_cycle():
    return create_customer_portal()

@stripe_bp.route('/cancel-subscription', methods=['POST'])
@login_required
def cancel_subscription():
    return create_customer_portal()

@stripe_bp.route('/reactivate-subscription', methods=['POST'])
@login_required
def reactivate_subscription():
    return create_customer_portal()
