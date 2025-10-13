from flask_mail import Message
from flask import render_template, url_for
from datetime import datetime, timezone
import os

def send_payment_success_email(user, session_data):
    """Send payment success email to user"""
    try:
        from website import mail
        
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
            import stripe
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
            sender=os.getenv('MAIL_USERNAME', 'info@itbewertungen.de')
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
        
        # Send email
        mail.send(msg)
        
        print(f"✅ Payment success email sent to {user.email}")
        return True
        
    except Exception as e:
        print(f"❌ Error sending payment success email: {str(e)}")
        return False

def send_payment_failed_email(user, subscription_data):
    """Send payment failed email to user"""
    try:
        from website import mail
        
        # Create email message
        msg = Message(
            subject="⚠️ Payment Failed - LetterForLater Subscription",
            recipients=[user.email],
            sender=os.getenv('MAIL_USERNAME', 'info@itbewertungen.de')
        )
        
        # Simple text email for payment failure
        msg.body = f"""
Dear {user.first_name},

We were unable to process your payment for your LetterForLater subscription.

Please update your payment method to continue enjoying premium features:

1. Log in to your account
2. Go to Settings > Billing
3. Update your payment method

If you need assistance, please contact us at support@letterforlater.com

Best regards,
The LetterForLater Team
        """
        
        # Send email
        mail.send(msg)
        
        print(f"✅ Payment failed email sent to {user.email}")
        return True
        
    except Exception as e:
        print(f"❌ Error sending payment failed email: {str(e)}")
        return False

def send_subscription_cancelled_email(user):
    """Send subscription cancelled email to user"""
    try:
        from website import mail
        
        # Create email message
        msg = Message(
            subject="Subscription Cancelled - LetterForLater",
            recipients=[user.email],
            sender=os.getenv('MAIL_USERNAME', 'info@itbewertungen.de')
        )
        
        # Simple text email for cancellation
        msg.body = f"""
Dear {user.first_name},

Your LetterForLater subscription has been cancelled.

You can still use our free plan which includes:
- 1 legacy letter
- Bank-level encryption
- Trusted contact verification
- Email delivery tracking

If you change your mind, you can resubscribe anytime at:
https://letterforlater.com/pricing

Thank you for being part of the LetterForLater community.

Best regards,
The LetterForLater Team
        """
        
        # Send email
        mail.send(msg)
        
        print(f"✅ Subscription cancelled email sent to {user.email}")
        return True
        
    except Exception as e:
        print(f"❌ Error sending subscription cancelled email: {str(e)}")
        return False
