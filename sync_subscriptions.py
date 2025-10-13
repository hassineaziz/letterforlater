from website import create_app, db
from website.models import User
from website.subscription_utils import sync_all_subscriptions
import logging

def sync_all_user_subscriptions():
    """Sync all premium users' subscription data from Stripe"""
    app = create_app()
    with app.app_context():
        print('🔄 Syncing all user subscriptions...')
        print('=' * 50)
        
        results = sync_all_subscriptions()
        
        print(f'Synced {len(results)} users:')
        for result in results:
            status = '✅ Success' if result['success'] else '❌ Failed'
            print(f'  {result["email"]}: {status}')
        
        print()
        print('📊 Current Subscription Status:')
        print('=' * 30)
        
        premium_users = User.query.filter(User.plan.in_(['premium', 'lifetime'])).all()
        for user in premium_users:
            print(f'📧 {user.email}')
            print(f'   Plan: {user.plan}')
            print(f'   Status: {user.subscription_status}')
            print(f'   Next Payment: {user.next_payment_date}')
            print(f'   Last Payment: {user.last_payment_date}')
            print()

if __name__ == '__main__':
    sync_all_user_subscriptions()
