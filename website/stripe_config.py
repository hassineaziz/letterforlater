import stripe
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Initialize Stripe with your secret key
stripe.api_key = os.getenv('STRIPE_SECRET_KEY')
STRIPE_PUBLISHABLE_KEY = os.getenv('STRIPE_PUBLISHABLE_KEY')

# Your Stripe product/price IDs (replace with your actual LIVE IDs from Stripe dashboard)
STRIPE_PRODUCTS = {
    'free': None,  # No payment needed for free plan
    'premium_monthly': 'price_1SHmDfDzxRSZ7ssLQGMMLS4Q',  # Replace with your live monthly price ID
    'premium_yearly': 'price_1SHmDfDzxRSZ7ssLBgZBW3Dk',   # Replace with your live yearly price ID  
    'lifetime': 'price_1SHmG0DzxRSZ7ssL1UDSX9Wg'          # Replace with your live lifetime price ID
}

def get_stripe_price_id(plan, cycle='month'):
    """Get the Stripe price ID for a given plan and cycle"""
    if plan == 'free':
        return None
    elif plan == 'premium':
        return STRIPE_PRODUCTS[f'premium_{cycle}ly']
    elif plan == 'lifetime':
        return STRIPE_PRODUCTS['lifetime']
    return None
