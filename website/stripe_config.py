import stripe
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Initialize Stripe with your secret key
stripe.api_key = os.getenv('STRIPE_SECRET_KEY')
STRIPE_PUBLISHABLE_KEY = os.getenv('STRIPE_PUBLISHABLE_KEY')
STRIPE_WEBHOOK_SECRET = os.getenv('STRIPE_WEBHOOK_SECRET')

# Your Stripe product/price IDs (configured in Stripe Dashboard)
# Using environment variables is preferred for production
STRIPE_PRODUCTS = {
    'free': None,
    'premium_monthly': os.getenv('STRIPE_PRICE_PREMIUM_MONTHLY', 'price_1TXjIVDzxRSZ7ssLS76WxLu7'),
    'premium_yearly': os.getenv('STRIPE_PRICE_PREMIUM_YEARLY', 'price_1TXjHpDzxRSZ7ssLL1X3eWoH'),
    'lifetime': os.getenv('STRIPE_PRICE_LIFETIME', 'price_1TXiH7DzxRSZ7ssLAKLk25Mq')
}

def get_stripe_price_id(plan, cycle='month'):
    """Get the Stripe price ID for a given plan and cycle"""
    if plan == 'free':
        return None
    elif plan == 'premium':
        key = f'premium_{cycle}ly'
        return STRIPE_PRODUCTS.get(key)
    elif plan == 'lifetime':
        return STRIPE_PRODUCTS.get('lifetime')
    return None

def is_premium(user):
    """Check if a user has an active premium or lifetime plan"""
    if not user or not user.is_authenticated:
        return False
    return user.plan in ['premium', 'lifetime']
