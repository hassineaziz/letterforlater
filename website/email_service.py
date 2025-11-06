from flask_mail import Message
from flask import render_template, url_for
from datetime import datetime, timezone
import os
from .email_rate_limit import safe_send_email

def send_welcome_email(user):
    """Send welcome email to new user"""
    try:
        # Create email message
        msg = Message(
            subject="🎉 Welcome to LetterForLater - Your Legacy Awaits!",
            recipients=[user.email],
            sender=os.getenv('MAIL_USERNAME', 'support@letterforlater.com')
        )
        
        # Render HTML template
        msg.html = render_template('emails/welcome.html',
            user_name=f"{user.first_name} {user.last_name}",
            user_email=user.email,
            dashboard_url="https://letterforlater.com"
        )
        
        # Render text template
        msg.body = render_template('emails/welcome.txt',
            user_name=f"{user.first_name} {user.last_name}",
            user_email=user.email,
            dashboard_url="https://letterforlater.com"
        )
        
        # Send email using safe_send_email for rate limiting and error handling
        success = safe_send_email(msg, email_type='welcome')
        
        if success:
            print(f"✅ Welcome email sent to {user.email}")
            return True
        else:
            print(f"❌ Failed to send welcome email to {user.email} (rate limited or error)")
            return False
        
    except Exception as e:
        print(f"❌ Error sending welcome email: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

def send_payment_success_email(user, session_data):
    """Send payment success email to user"""
    try:
        # Extract data from Stripe session
        plan = session_data.get('metadata', {}).get('plan', 'premium')
        cycle = session_data.get('metadata', {}).get('cycle', 'month')
        
        # Format plan name
        plan_name = plan.title()
        if plan == 'premium':
            plan_name = f"Premium ({cycle.title()})"
        
        # Format billing cycle
        billing_cycle = cycle.title() if cycle else "Monthly"
        
        # Get amount from session
        amount = "0.00"
        if session_data.get('amount_total'):
            amount = f"{session_data['amount_total'] / 100:.2f}"
        
        # Calculate next payment date
        next_payment_date = "N/A"
        if session_data.get('subscription'):
            # Get subscription details
            from website.stripe_config import stripe
            try:
                subscription = stripe.Subscription.retrieve(session_data['subscription'])
                if subscription.current_period_end:
                    next_payment = datetime.fromtimestamp(subscription.current_period_end, tz=timezone.utc)
                    next_payment_date = next_payment.strftime('%B %d, %Y')
            except:
                pass
        
        # Create email message
        msg = Message(
            subject="🎉 Payment Successful - Welcome to LetterForLater!",
            recipients=[user.email],
            sender=os.getenv('MAIL_USERNAME', 'support@letterforlater.com')
        )
        
        # Render HTML template
        msg.html = render_template('emails/payment_success.html',
            user_name=f"{user.first_name} {user.last_name}",
            user_email=user.email,
            plan_name=plan_name,
            billing_cycle=billing_cycle,
            amount=amount,
            next_payment_date=next_payment_date,
            dashboard_url="https://letterforlater.com"  # Use absolute URL instead of url_for
        )
        
        # Render text template
        msg.body = render_template('emails/payment_success.txt',
            user_name=f"{user.first_name} {user.last_name}",
            user_email=user.email,
            plan_name=plan_name,
            billing_cycle=billing_cycle,
            amount=amount,
            next_payment_date=next_payment_date,
            dashboard_url="https://letterforlater.com"  # Use absolute URL instead of url_for
        )
        
        # Send email using safe_send_email for rate limiting and error handling
        success = safe_send_email(msg, email_type='payment_success')
        
        if success:
            print(f"✅ Payment success email sent to {user.email}")
            return True
        else:
            print(f"❌ Failed to send payment success email to {user.email} (rate limited or error)")
            return False
        
    except Exception as e:
        print(f"❌ Error sending payment success email: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

def send_payment_failed_email(user, subscription_data):
    """Send payment failed email to user"""
    try:
        # Create email message
        msg = Message(
            subject="⚠️ Payment Failed - LetterForLater Subscription",
            recipients=[user.email],
            sender=os.getenv('MAIL_USERNAME', 'support@letterforlater.com')
        )
        
        # Render HTML template
        msg.html = render_template('emails/payment_failed.html',
            user_name=f"{user.first_name} {user.last_name}",
            user_email=user.email,
            dashboard_url="https://letterforlater.com"
        )
        
        # Render text template
        msg.body = render_template('emails/payment_failed.txt',
            user_name=f"{user.first_name} {user.last_name}",
            user_email=user.email,
            dashboard_url="https://letterforlater.com"
        )
        
        # Send email using safe_send_email for rate limiting and error handling
        success = safe_send_email(msg, email_type='payment_failed')
        
        if success:
            print(f"✅ Payment failed email sent to {user.email}")
            return True
        else:
            print(f"❌ Failed to send payment failed email to {user.email} (rate limited or error)")
            return False
        
    except Exception as e:
        print(f"❌ Error sending payment failed email: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

def send_subscription_cancelled_email(user):
    """Send subscription cancelled email to user"""
    try:
        # Create email message
        msg = Message(
            subject="Subscription Cancelled - LetterForLater",
            recipients=[user.email],
            sender=os.getenv('MAIL_USERNAME', 'support@letterforlater.com')
        )
        
        # Render HTML template
        msg.html = render_template('emails/subscription_cancelled.html',
            user_name=f"{user.first_name} {user.last_name}",
            user_email=user.email,
            dashboard_url="https://letterforlater.com"
        )
        
        # Render text template
        msg.body = render_template('emails/subscription_cancelled.txt',
            user_name=f"{user.first_name} {user.last_name}",
            user_email=user.email,
            dashboard_url="https://letterforlater.com"
        )
        
        # Send email using safe_send_email for rate limiting and error handling
        success = safe_send_email(msg, email_type='subscription_cancelled')
        
        if success:
            print(f"✅ Subscription cancelled email sent to {user.email}")
            return True
        else:
            print(f"❌ Failed to send subscription cancelled email to {user.email} (rate limited or error)")
            return False
        
    except Exception as e:
        print(f"❌ Error sending subscription cancelled email: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

def send_newsletter_welcome_email(email):
    """Send welcome email with link to download page to newsletter subscribers"""
    try:
        # Create email message
        msg = Message(
            subject="🎉 Welcome to Our Newsletter + Free Legacy Template!",
            recipients=[email],
            sender=os.getenv('MAIL_USERNAME', 'support@letterforlater.com')
        )
        
        # Render HTML template
        msg.html = render_template('emails/newsletter_welcome.html',
            unsubscribe_url=url_for('views.newsletter_unsubscribe', email=email, _external=True)
        )
        
        # Render text template
        msg.body = render_template('emails/newsletter_welcome.txt',
            unsubscribe_url=url_for('views.newsletter_unsubscribe', email=email, _external=True)
        )
        
        # Send email using safe_send_email for rate limiting and error handling
        success = safe_send_email(msg, email_type='newsletter_welcome')
        
        if success:
            print(f"✅ Newsletter welcome email sent to {email}")
            return True
        else:
            print(f"❌ Failed to send newsletter welcome email to {email} (rate limited or error)")
            return False
        
    except Exception as e:
        print(f"❌ Error sending newsletter welcome email: {str(e)}")
        import traceback
        traceback.print_exc()
        return False
