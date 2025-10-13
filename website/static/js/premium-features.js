/**
 * Premium Feature Management & Upgrade Prompts
 */

class PremiumFeatures {
    constructor() {
        this.init();
    }

    init() {
        this.bindEvents();
        this.showFixedUpgradeBar();
        this.initTooltips();
    }

    bindEvents() {
        // Handle premium feature clicks
        document.addEventListener('click', (e) => {
            const premiumElement = e.target.closest('[data-premium-feature]');
            if (premiumElement) {
                e.preventDefault();
                this.handlePremiumFeatureClick(premiumElement);
            }

            // Handle upgrade modal close
            if (e.target.classList.contains('upgrade-modal') || e.target.classList.contains('upgrade-modal-close')) {
                this.closeUpgradeModal();
            }

            // Handle upgrade buttons
            if (e.target.classList.contains('upgrade-button')) {
                this.handleUpgradeClick(e.target);
            }
        });

        // Handle keyboard events
        document.addEventListener('keydown', (e) => {
            if (e.key === 'Escape') {
                this.closeUpgradeModal();
            }
        });
    }

    handlePremiumFeatureClick(element) {
        const feature = element.dataset.premiumFeature;
        const featureData = this.getFeatureData(feature);
        
        this.showUpgradeModal(featureData);
    }

    getFeatureData(feature) {
        const featureMap = {
            'unlimited_letters': {
                icon: 'M15.232 5.232l3.536 3.536m-2.036-5.036a2.5 2.5 0 113.536 3.536L6.5 21.036H3v-3.572L16.732 3.732z',
                title: 'Unlock Unlimited Letters',
                message: 'Create as many legacy letters as you want for your loved ones.',
                benefit: 'Write letters for birthdays, graduations, weddings, and special moments.',
                cta: 'Upgrade to Premium'
            },
            'media_attachments': {
                icon: 'M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z',
                title: 'Add Photos & Videos',
                message: 'Attach precious photos, videos, and audio recordings to your letters.',
                benefit: 'Make your memories come alive with multimedia attachments.',
                cta: 'Unlock Media Features'
            },
            'unlimited_contacts': {
                icon: 'M12 4.354a4 4 0 110 5.292M15 21H3v-1a6 6 0 0112 0v1zm0 0h6v-1a6 6 0 00-9-5.197m13.5-9a2.5 2.5 0 11-5 0 2.5 2.5 0 015 0z',
                title: 'Add More Trusted Contacts',
                message: 'Share your letters with unlimited trusted family and friends.',
                benefit: 'Ensure everyone important receives your messages.',
                cta: 'Unlock Unlimited Contacts'
            },
            'scheduled_delivery': {
                icon: 'M8 7V3m8 4V3m-9 8h10M5 21h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z',
                title: 'Schedule for Special Moments',
                message: 'Schedule letters to be delivered on birthdays, graduations, and milestones.',
                benefit: 'Create magical moments with perfectly timed deliveries.',
                cta: 'Unlock Scheduling'
            },
            'priority_support': {
                icon: 'M18.364 5.636l-3.536 3.536m0 5.656l3.536 3.536M9.172 9.172L5.636 5.636m3.536 9.192L5.636 18.364M12 2.25a9.75 9.75 0 100 19.5 9.75 9.75 0 000-19.5z',
                title: 'Get Priority Support',
                message: 'Get faster, dedicated support when you need help.',
                benefit: 'We\'re here to help you preserve your legacy.',
                cta: 'Upgrade for Priority Support'
            }
        };

        return featureMap[feature] || {
            icon: 'M12 8c-1.657 0-3 .895-3 2s1.343 2 3 2 3 .895 3 2-1.343 2-3 2m0-8c1.11 0 2.08.402 2.599 1M12 8V7m0 1v8m0 0v1m0-1c-1.11 0-2.08-.402-2.599-1',
            title: 'Premium Feature',
            message: 'This feature is available with Premium.',
            benefit: 'Upgrade to unlock unlimited access.',
            cta: 'Upgrade Now'
        };
    }

    showUpgradeModal(featureData) {
        const modal = this.createUpgradeModal(featureData);
        document.body.appendChild(modal);
        
        // Trigger animation
        setTimeout(() => {
            modal.classList.add('active');
        }, 10);
    }

    createUpgradeModal(featureData) {
        const modal = document.createElement('div');
        modal.className = 'upgrade-modal';
        modal.innerHTML = `
            <div class="upgrade-modal-content">
                <button class="upgrade-modal-close absolute top-4 right-4 text-gray-400 hover:text-gray-600 transition-colors">
                    <svg class="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"></path>
                    </svg>
                </button>
                
                <div class="upgrade-feature-icon">
                    <svg fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="${featureData.icon}"></path>
                    </svg>
                </div>
                
                <div class="text-center mb-6">
                    <h3 class="text-2xl font-bold text-gray-900 mb-3">${featureData.title}</h3>
                    <p class="text-gray-600 mb-4">${featureData.message}</p>
                    <p class="text-sm text-gray-500 bg-gray-50 rounded-lg p-3">${featureData.benefit}</p>
                </div>
                
                <div class="flex flex-col sm:flex-row gap-3">
                    <button class="upgrade-button flex-1 bg-gradient-to-r from-blue-600 to-purple-600 hover:from-blue-700 hover:to-purple-700 text-white font-semibold py-3 px-6 rounded-xl transition-all duration-300 shadow-lg hover:shadow-xl hover:-translate-y-1" data-plan="premium">
                        <svg class="w-5 h-5 mr-2 inline" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M3 10h18M7 15h1m4 0h1m-7 4h12a3 3 0 003-3V8a3 3 0 00-3-3H6a3 3 0 00-3 3v8a3 3 0 003 3z"></path>
                        </svg>
                        ${featureData.cta} - $5.99/month
                    </button>
                    <button class="upgrade-button flex-1 bg-gradient-to-r from-green-600 to-emerald-600 hover:from-green-700 hover:to-emerald-700 text-white font-semibold py-3 px-6 rounded-xl transition-all duration-300 shadow-lg hover:shadow-xl hover:-translate-y-1" data-plan="lifetime">
                        <svg class="w-5 h-5 mr-2 inline" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z"></path>
                        </svg>
                        Get Lifetime - $99.99
                    </button>
                </div>
                
                <div class="text-center mt-4">
                    <p class="text-xs text-gray-500">Save 20% with annual billing</p>
                </div>
            </div>
        `;
        
        return modal;
    }

    closeUpgradeModal() {
        const modal = document.querySelector('.upgrade-modal');
        if (modal) {
            modal.classList.remove('active');
            setTimeout(() => {
                modal.remove();
            }, 300);
        }
    }

    handleUpgradeClick(button) {
        const plan = button.dataset.plan;
        this.closeUpgradeModal();
        
        // Redirect to checkout
        this.initiateCheckout(plan);
    }

    async initiateCheckout(plan) {
        try {
            const response = await fetch('/create-checkout-session', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({ 
                    plan: plan,
                    cycle: plan === 'premium' ? 'month' : null
                })
            });
            
            const data = await response.json();
            
            if (data.checkout_url) {
                window.location.href = data.checkout_url;
            } else if (data.redirect) {
                window.location.href = data.redirect;
            } else {
                this.showError('Unable to start checkout. Please try again.');
            }
        } catch (error) {
            console.error('Checkout error:', error);
            this.showError('Something went wrong. Please try again.');
        }
    }

    showError(message) {
        // Create error notification
        const notification = document.createElement('div');
        notification.className = 'fixed top-4 right-4 bg-red-500 text-white px-6 py-3 rounded-lg shadow-lg z-50 fade-in';
        notification.textContent = message;
        document.body.appendChild(notification);
        
        setTimeout(() => {
            notification.remove();
        }, 5000);
    }

    showFixedUpgradeBar() {
        // Only show for free users (this would be determined server-side)
        const isFreeUser = document.body.dataset.userPlan === 'free';
        
        // Check if user has dismissed the banner recently
        const dismissedUntil = localStorage.getItem('upgrade-banner-dismissed');
        const now = Date.now();
        
        if (dismissedUntil && now < parseInt(dismissedUntil)) {
            return; // Don't show if dismissed recently
        }
        
        if (isFreeUser) {
            const upgradeBar = this.createFixedUpgradeBar();
            document.body.appendChild(upgradeBar);
            
            // Show after a delay
            setTimeout(() => {
                upgradeBar.classList.add('show');
            }, 2000);
        }
    }

    createFixedUpgradeBar() {
        const bar = document.createElement('div');
        bar.className = 'fixed-upgrade-bar';
        bar.innerHTML = `
            <div class="fixed-upgrade-content">
                <div class="fixed-upgrade-text">
                    <div class="fixed-upgrade-title">Unlock Your Full Legacy Potential</div>
                    <div class="fixed-upgrade-subtitle">Get unlimited letters, media attachments, and scheduling</div>
                </div>
                <div class="fixed-upgrade-buttons">
                    <a href="/pricing" class="fixed-upgrade-button primary">
                        <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M3 10h18M7 15h1m4 0h1m-7 4h12a3 3 0 003-3V8a3 3 0 00-3-3H6a3 3 0 00-3 3v8a3 3 0 003 3z"></path>
                        </svg>
                        Upgrade to Premium
                    </a>
                    <a href="/pricing" class="fixed-upgrade-button">
                        <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z"></path>
                        </svg>
                        Get Lifetime
                    </a>
                    <span class="fixed-upgrade-savings">Save 20%</span>
                </div>
                <button class="fixed-upgrade-close" onclick="this.parentElement.parentElement.remove(); localStorage.setItem('upgrade-banner-dismissed', Date.now() + (5 * 60 * 1000));" title="Close banner">
                    <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"></path>
                    </svg>
                </button>
            </div>
        `;
        
        return bar;
    }

    initTooltips() {
        // Initialize tooltips for premium features
        const premiumElements = document.querySelectorAll('[data-premium-feature]');
        premiumElements.forEach(element => {
            this.addTooltip(element);
        });
    }

    addTooltip(element) {
        const tooltip = document.createElement('div');
        tooltip.className = 'premium-tooltip';
        tooltip.textContent = 'Upgrade to unlock';
        element.appendChild(tooltip);
    }

    // Utility method to check if user has premium access
    hasPremiumAccess() {
        const userPlan = document.body.dataset.userPlan;
        return userPlan === 'premium' || userPlan === 'lifetime';
    }

    // Method to show inline upgrade banner
    showUpgradeBanner(container, featureData) {
        const banner = document.createElement('div');
        banner.className = 'upgrade-banner slide-up';
        banner.innerHTML = `
            <div class="upgrade-banner-content">
                <div class="upgrade-banner-icon">
                    <svg fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="${featureData.icon}"></path>
                    </svg>
                </div>
                <div class="upgrade-banner-text">
                    <div class="upgrade-banner-title">${featureData.title}</div>
                    <div class="upgrade-banner-subtitle">${featureData.message}</div>
                </div>
            </div>
            <button class="upgrade-banner-button upgrade-button" data-plan="premium">
                Upgrade Now
            </button>
        `;
        
        container.appendChild(banner);
        
        // Auto-remove after 10 seconds
        setTimeout(() => {
            banner.remove();
        }, 10000);
    }
}

// Initialize when DOM is loaded
document.addEventListener('DOMContentLoaded', () => {
    new PremiumFeatures();
});

// Export for use in other scripts
window.PremiumFeatures = PremiumFeatures;
