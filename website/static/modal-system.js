// Unified Modal System for Legacy Letter Application
// This file provides a consistent modal experience across all pages

class UnifiedModalManager {
    constructor() {
        this.currentModal = null;
        this.modalCounter = 0;
        this.init();
    }
    
    init() {
        // Handle modal trigger buttons
        document.addEventListener('click', (e) => {
            const modalTrigger = e.target.closest('[data-modal]');
            if (modalTrigger) {
                e.preventDefault();
                const modalId = modalTrigger.getAttribute('data-modal');
                this.openModal(modalId);
            }
        });
        
        // Handle modal close buttons
        document.addEventListener('click', (e) => {
            if (e.target.classList.contains('modal-close') || 
                e.target.closest('.modal-close') ||
                (e.target.classList.contains('btn-secondary') && e.target.hasAttribute('data-modal'))) {
                console.log('Close button clicked, closing modal');
                console.log('Event target:', e.target);
                console.log('Current modal:', this.currentModal);
                e.preventDefault();
                this.closeModal();
            }
        });
        
        // Handle backdrop clicks
        document.addEventListener('click', (e) => {
            if (e.target.classList.contains('modal-backdrop')) {
                console.log('Backdrop clicked, closing modal');
                console.log('Event target:', e.target);
                console.log('Current modal:', this.currentModal);
                this.closeModal();
            }
        });
        
        // Handle escape key
        document.addEventListener('keydown', (e) => {
            if (e.key === 'Escape' && this.currentModal) {
                this.closeModal();
            }
        });
    }
    
    openModal(modalId) {
        console.log(`openModal called with ID: ${modalId}`);
        
        // Close any existing modal
        if (this.currentModal) {
            console.log('Closing existing modal before opening new one');
            this.closeModal();
        }
        
        const modal = document.getElementById(modalId);
        const backdrop = document.getElementById('modalBackdrop');
        
        if (!modal) {
            console.error(`Modal with ID '${modalId}' not found`);
            return;
        }
        
        console.log('Modal found, showing backdrop and modal');
        
        // Show backdrop
        if (backdrop) {
            backdrop.style.display = 'block';
            console.log('Backdrop shown');
        }
        
        // Show modal
        modal.style.display = 'flex';
        console.log('Modal shown');
        
        // Add show class for animation
        setTimeout(() => {
            modal.classList.add('show');
            console.log('Show class added to modal');
        }, 10);
        
        this.currentModal = modal;
        
        // Prevent body scroll
        document.body.style.overflow = 'hidden';
        
        console.log(`Opened modal: ${modalId}`);
    }
    
    closeModal() {
        if (!this.currentModal) return;
        
        console.log('closeModal called, current modal:', this.currentModal);
        
        const backdrop = document.getElementById('modalBackdrop');
        
        // Remove show class for animation
        this.currentModal.classList.remove('show');
        
        // Hide modal and backdrop after animation
        setTimeout(() => {
            this.currentModal.style.display = 'none';
            if (backdrop) {
                backdrop.style.display = 'none';
            }
            
            // Restore body scroll
            document.body.style.overflow = '';
            
            this.currentModal = null;
        }, 300);
        
        console.log('Closed modal');
    }
    
    // Create a dynamic modal (for JavaScript-generated modals)
    createModal(config) {
        console.log('createModal called with config:', config);
        
        // Close any existing modal first
        this.closeModal();
        
        // Generate unique modal ID
        const modalId = `dynamic-modal-${++this.modalCounter}`;
        console.log('Generated modal ID:', modalId);
        
        // Create modal element
        const modal = document.createElement('div');
        modal.id = modalId;
        modal.className = 'modal';
        modal.style.display = 'none';
        
        // Create backdrop if it doesn't exist
        let backdrop = document.getElementById('modalBackdrop');
        if (!backdrop) {
            backdrop = document.createElement('div');
            backdrop.id = 'modalBackdrop';
            backdrop.className = 'modal-backdrop';
            backdrop.style.display = 'none';
            document.body.appendChild(backdrop);
            console.log('Created new backdrop');
        } else {
            console.log('Using existing backdrop');
        }
        
        // Build modal content
        modal.innerHTML = `
            <div class="modal-content">
                <div class="modal-header ${config.headerClass || ''}">
                    <h5 class="modal-title ${config.titleClass || ''}">${config.title}</h5>
                    <button type="button" class="modal-close" data-modal="${modalId}">
                        <svg class="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"></path>
                        </svg>
                    </button>
                </div>
                <div class="modal-body">
                    ${config.body || ''}
                </div>
                <div class="modal-footer">
                    ${config.footer || ''}
                </div>
            </div>
        `;
        
        // Add to DOM
        document.body.appendChild(modal);
        console.log('Modal added to DOM');
        
        // Store modal reference
        this.currentModal = modal;
        
        // Open the modal
        console.log('About to open modal');
        this.openModal(modalId);
        
        return modal;
    }
    
    // Create a confirmation modal
    createConfirmModal(config) {
        const confirmText = config.confirmText || 'Confirm';
        const cancelText = config.cancelText || 'Cancel';
        const confirmClass = config.confirmClass || 'btn-danger';
        const iconPath = config.iconPath || '<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-2.5L13.732 4c-.77-.833-1.732-.833-2.5 0L4.268 19.5c-.77.833.192 2.5 1.732 2.5z"></path>';
        const iconColor = config.iconColor || 'text-red-600';
        const iconBg = config.iconBg || 'bg-red-100';
        
        const body = `
            <div class="text-center mb-6">
                <div class="w-16 h-16 ${iconBg} rounded-full flex items-center justify-center mx-auto mb-4">
                    <svg class="w-8 h-8 ${iconColor}" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        ${iconPath}
                    </svg>
                </div>
                <h3 class="text-xl font-bold text-gray-900 mb-2">${config.title}</h3>
                <p class="text-gray-600">${config.message}</p>
            </div>
        `;
        
        const footer = `
            <button type="button" class="btn ${confirmClass}" id="confirm-btn">
                <svg class="w-4 h-4 inline mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"></path>
                </svg>
                ${confirmText}
            </button>
            <button type="button" class="btn btn-secondary" id="cancel-btn">
                <svg class="w-4 h-4 inline mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"></path>
                </svg>
                ${cancelText}
            </button>
        `;
        
        const modal = this.createModal({
            title: config.title,
            body: body,
            footer: footer,
            headerClass: config.headerClass || 'bg-red-50',
            titleClass: config.titleClass || 'text-red-900'
        });
        
        // Add event listeners for buttons
        const confirmBtn = modal.querySelector('#confirm-btn');
        const cancelBtn = modal.querySelector('#cancel-btn');
        
        if (confirmBtn && config.onConfirm) {
            confirmBtn.addEventListener('click', (e) => {
                e.preventDefault();
                config.onConfirm();
                this.closeModal();
            });
        }
        
        if (cancelBtn && config.onCancel) {
            cancelBtn.addEventListener('click', (e) => {
                e.preventDefault();
                config.onCancel();
                this.closeModal();
            });
        }
        
        return modal;
    }
}

// Initialize modal system when DOM is loaded
document.addEventListener('DOMContentLoaded', function() {
    window.modalManager = new UnifiedModalManager();
});

// Export for use in other scripts
if (typeof module !== 'undefined' && module.exports) {
    module.exports = UnifiedModalManager;
}
