// Mobile menu toggle
function toggleMobileMenu() {
    const mobileMenu = document.getElementById('mobile-menu');
    const btn = document.querySelector('button[onclick="toggleMobileMenu()"]');
    if (!mobileMenu) return;
    const isHidden = mobileMenu.classList.toggle('hidden');
    if (btn) {
        btn.setAttribute('aria-expanded', String(!isHidden));
        btn.setAttribute('aria-label', !isHidden ? 'Close menu' : 'Open menu');
    }
}

/**
 * Modal Management System
 * Handles opening, closing, and animating modals globally.
 */
class ModalManager {
    constructor() {
        this.currentModal = null;
        this.init();
    }

    init() {
        // Handle modal trigger buttons
        document.addEventListener('click', (e) => {
            const modalTrigger = e.target.closest('[data-modal]');
            if (modalTrigger) {
                // Don't prevent default if it's a submit button unless we handle it
                if (modalTrigger.type !== 'submit') {
                    e.preventDefault();
                }
                const modalId = modalTrigger.getAttribute('data-modal');
                this.openModal(modalId);
            }
        });

        // Handle modal close buttons
        document.addEventListener('click', (e) => {
            if (e.target.classList.contains('modal-close') ||
                e.target.closest('.modal-close') ||
                (e.target.classList.contains('btn-secondary') && e.target.hasAttribute('data-modal'))) {
                e.preventDefault();
                this.closeModal();
            }
        });

        // Handle backdrop clicks
        document.addEventListener('click', (e) => {
            if (e.target.classList.contains('modal-backdrop')) {
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
        if (this.currentModal) this.closeModal();

        const modal = document.getElementById(modalId);
        const backdrop = document.getElementById('modalBackdrop');

        if (!modal) {
            console.error(`Modal with ID '${modalId}' not found`);
            return;
        }

        if (backdrop) backdrop.style.display = 'block';
        modal.style.display = 'flex';

        setTimeout(() => {
            modal.classList.add('show');
            if (backdrop) backdrop.classList.add('show');
        }, 10);
        
        this.currentModal = modal;
        document.body.style.overflow = 'hidden';
    }

    closeModal() {
        if (!this.currentModal) return;
        const backdrop = document.getElementById('modalBackdrop');
        this.currentModal.classList.remove('show');
        if (backdrop) backdrop.classList.remove('show');

        setTimeout(() => {
            if (this.currentModal) {
                this.currentModal.style.display = 'none';
                if (backdrop) backdrop.style.display = 'none';
                document.body.style.overflow = '';
                this.currentModal = null;
            }
        }, 300);
    }
}

// Global modal manager instance
window.modalManager = new ModalManager();

// Notification dropdown toggle
function toggleNotificationDropdown() {
    const dropdown = document.getElementById('notification-dropdown-menu');
    if (dropdown) {
        dropdown.classList.toggle('hidden');
    }
}

// Close dropdown when clicking outside
document.addEventListener('click', function (e) {
    const dropdown = document.getElementById('notification-dropdown-menu');
    const button = document.getElementById('notificationDropdown');

    if (dropdown && button && !button.contains(e.target) && !dropdown.contains(e.target)) {
        dropdown.classList.add('hidden');
    }
});

function renderAllNotifications(notifications) {
    const badge = document.getElementById('notification-badge');
    const notificationList = document.getElementById('notification-list');
    const notificationCount = document.getElementById('notification-count');
    const noNotifications = document.getElementById('no-notifications');

    if (!notificationList) return;

    if (notifications.length > 0) {
        if (badge) {
            badge.textContent = notifications.length;
            badge.classList.remove('hidden');
        }
        if (notificationCount) {
            notificationCount.textContent = `${notifications.length} unread`;
        }
        if (noNotifications) {
            noNotifications.classList.add('hidden');
        }

        notificationList.innerHTML = '';
        notifications.forEach(notif => {
            const item = document.createElement('div');
            item.className = 'p-4 border-b border-gray-100 hover:bg-gray-50 transition-colors duration-150 cursor-pointer';
            item.setAttribute('data-notification-id', notif.id);

            if (notif.type === 'trusted_contact_invitation') {
                item.innerHTML = `
            <div class="flex items-start space-x-3">
                <div class="flex-shrink-0">
                    <div class="w-8 h-8 bg-blue-100 rounded-full flex items-center justify-center">
                        <svg class="w-4 h-4 text-blue-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z"></path>
                        </svg>
                    </div>
                </div>
                <div class="flex-1 min-w-0">
                    <p class="text-sm font-semibold text-gray-900">Trusted Contact Invitation</p>
                    <p class="text-sm text-gray-600">${notif.from_name} wants to add you as a trusted contact.</p>
                    <div class="mt-2 flex space-x-2">
                        <button onclick="handleInvitation(${notif.id}, 'accept')" class="text-xs bg-green-100 text-green-800 px-3 py-1.5 rounded-full hover:bg-green-200 transition-colors duration-200 font-medium disabled:opacity-50 disabled:cursor-not-allowed">
                            Accept
                        </button>
                        <button onclick="handleInvitation(${notif.id}, 'deny')" class="text-xs bg-gray-100 text-gray-800 px-3 py-1.5 rounded-full hover:bg-gray-200 transition-colors duration-200 font-medium disabled:opacity-50 disabled:cursor-not-allowed">
                            Deny
                        </button>
                    </div>
            </div>
            </div>
        `;
            } else {
                // Default notification type
                const iconColor = notif.type.includes('death') ? 'text-red-600' : (notif.type.includes('removed') ? 'text-orange-600' : 'text-green-600');
                const bgColor = notif.type.includes('death') ? 'bg-red-100' : (notif.type.includes('removed') ? 'bg-orange-100' : 'bg-green-100');
                
                item.innerHTML = `
            <div class="flex items-start space-x-3 ${notif.type === 'death_verification_confirmation' ? 'bg-red-50 border-l-4 border-red-400 p-2 rounded' : ''}">
                <div class="flex-shrink-0">
                    <div class="w-8 h-8 ${bgColor} rounded-full flex items-center justify-center">
                        <svg class="w-4 h-4 ${iconColor}" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-2.5L13.732 4c-.77-.833-1.732-.833-2.5 0L4.268 19.5c-.77.833.192 2.5 1.732 2.5z"></path>
                        </svg>
                    </div>
                </div>
                <div class="flex-1 min-w-0">
                    <p class="text-sm font-semibold text-gray-900">${notif.title}</p>
                    <p class="text-sm text-gray-600">${notif.message}</p>
                    ${notif.type === 'death_verification_confirmation' ? `
                    <div class="mt-2 flex space-x-2">
                        <button onclick="rejectDeathConfirmation(${notif.id}, ${notif.related_trusted_contact_id})" class="text-xs bg-green-600 text-white px-3 py-1.5 rounded-full hover:bg-green-700 transition-colors duration-200 font-medium">
                            I'm Alive
                        </button>
                        <button onclick="markAsRead(${notif.id})" class="text-xs bg-gray-100 text-gray-800 px-3 py-1.5 rounded-full hover:bg-gray-200 transition-colors duration-200 font-medium">
                            Dismiss
                        </button>
                    </div>
                    ` : ''}
                </div>
                ${notif.type !== 'death_verification_confirmation' ? `
                <button onclick="markAsRead(${notif.id})" class="flex-shrink-0 text-gray-400 hover:text-gray-600 transition-colors duration-200 p-1 rounded-full hover:bg-gray-100">
                    <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"></path>
                    </svg>
                </button>
                ` : ''}
            </div>
        `;
            }

            notificationList.appendChild(item);
        });
    } else {
        if (badge) badge.classList.add('hidden');
        if (notificationCount) notificationCount.textContent = '0 unread';
        if (noNotifications) noNotifications.classList.remove('hidden');
    }
}

async function markAsRead(notificationId) {
    const notificationElement = document.querySelector(`[data-notification-id="${notificationId}"]`);

    try {
        const response = await fetch(`/api/mark-notification-read/${notificationId}`, {
            method: 'POST'
        });

        if (response.ok) {
            showNotificationToast('✅ Notification marked as read', 'info');
            if (notificationElement) {
                notificationElement.style.opacity = '0.5';
                notificationElement.style.pointerEvents = 'none';
                setTimeout(() => {
                    notificationElement.remove();
                    updateNotificationCount();
                }, 500);
            }
            setTimeout(() => pollNotifications(), 1000);
        } else {
            showNotificationToast('❌ Error marking notification as read', 'error');
        }
    } catch (error) {
        console.error('Error marking notification as read:', error);
        showNotificationToast('❌ Error marking notification as read', 'error');
    }
}

async function rejectDeathConfirmation(notificationId, trustedContactId) {
    const notificationElement = document.querySelector(`[data-notification-id="${notificationId}"]`);
    const aliveBtn = notificationElement?.querySelector(`button[onclick*="rejectDeathConfirmation"]`);

    if (aliveBtn) {
        aliveBtn.disabled = true;
        aliveBtn.innerHTML = '<span class="animate-spin inline-block">⏳</span>';
    }

    try {
        const response = await fetch('/api/reject-death-confirmation', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                notification_id: notificationId,
                trusted_contact_id: trustedContactId
            })
        });

        const result = await response.json();
        if (result.success) {
            showNotificationToast('✅ Death confirmation rejected successfully.', 'success');
            if (notificationElement) {
                notificationElement.remove();
                updateNotificationCount();
            }
            setTimeout(() => pollNotifications(), 1000);
        } else {
            showNotificationToast('❌ Error: ' + (result.error || 'Unknown error'), 'error');
            if (aliveBtn) {
                aliveBtn.disabled = false;
                aliveBtn.innerHTML = "I'm Alive";
            }
        }
    } catch (error) {
        console.error('Error rejecting death confirmation:', error);
        showNotificationToast('❌ Error rejecting confirmation. Please try again.', 'error');
        if (aliveBtn) {
            aliveBtn.disabled = false;
            aliveBtn.innerHTML = "I'm Alive";
        }
    }
}

async function handleInvitation(notificationId, action) {
    const notificationElement = document.querySelector(`[data-notification-id="${notificationId}"]`);
    const btn = notificationElement?.querySelector(`button[onclick*="${action}"]`);

    if (btn) {
        btn.disabled = true;
        btn.innerHTML = '<span class="animate-spin inline-block">⏳</span>';
    }

    try {
        const response = await fetch('/api/handle-invitation', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                notification_id: notificationId,
                action: action
            })
        });

        const result = await response.json();
        if (result.success) {
            showNotificationToast(action === 'accept' ? '✅ Invitation accepted!' : '❌ Invitation declined.', 'success');
            if (notificationElement) {
                notificationElement.remove();
                updateNotificationCount();
            }
            setTimeout(() => pollNotifications(), 1000);
        } else {
            showNotificationToast('❌ Error: ' + (result.error || 'Unknown error'), 'error');
            if (btn) {
                btn.disabled = false;
                btn.innerHTML = action.charAt(0).toUpperCase() + action.slice(1);
            }
        }
    } catch (error) {
        console.error('Error handling invitation:', error);
        showNotificationToast('❌ Error handling invitation.', 'error');
        if (btn) {
            btn.disabled = false;
            btn.innerHTML = action.charAt(0).toUpperCase() + action.slice(1);
        }
    }
}

async function pollNotifications() {
    try {
        const res = await fetch('/api/notifications', {
            headers: { 'Accept': 'application/json' },
            credentials: 'same-origin',
            cache: 'no-store'
        });
        if (!res.ok) return;
        const data = await res.json();
        if (data && data.notifications) {
            renderAllNotifications(data.notifications);
            checkForDeathConfirmations(data.notifications);
        }
    } catch (error) {
        console.debug('Notifications polling skipped:', error);
    }
}

function checkForDeathConfirmations(notifications) {
    const hasShownPopup = sessionStorage.getItem('deathConfirmationPopupShown');
    if (hasShownPopup) return;

    const deathConfirmations = notifications.filter(notif => notif.type === 'death_verification_confirmation');
    if (deathConfirmations.length > 0) {
        showDeathConfirmationPopup(deathConfirmations);
        sessionStorage.setItem('deathConfirmationPopupShown', 'true');
    }
}

function showDeathConfirmationPopup(confirmations) {
    if (window.modalManager && typeof window.modalManager.createConfirmModal === 'function') {
        window.modalManager.createConfirmModal({
            title: 'Death Confirmation Alert',
            message: `Trusted contacts confirmed your death. Review immediately:\n\n${confirmations.map(c => `• ${c.trusted_contact_name || 'Contact'}`).join('\n')}`,
            confirmText: 'Confirm I\'m Alive',
            cancelText: 'Dismiss',
            confirmClass: 'btn-success',
            onConfirm: () => { window.location.href = '/verify-death'; }
        });
    } else {
        const names = confirmations.map(c => c.trusted_contact_name || 'Contact').join(', ');
        showNotificationToast(`🚨 URGENT: ${names} confirmed your death. Review immediately!`, 'error');
    }
}

function showNotificationToast(message, type = 'info') {
    const existingToasts = document.querySelectorAll('.notification-toast');
    existingToasts.forEach(toast => toast.remove());

    const toast = document.createElement('div');
    toast.className = `notification-toast fixed top-4 right-4 z-[200] max-w-sm w-full bg-white rounded-2xl shadow-2xl border-l-4 p-4 transform transition-all duration-300 translate-x-full`;

    if (type === 'success') toast.classList.add('border-green-500');
    else if (type === 'error') toast.classList.add('border-red-500');
    else toast.classList.add('border-primary');

    toast.innerHTML = `
        <div class="flex items-start">
            <div class="flex-1 text-sm font-medium text-gray-900">${message}</div>
            <button onclick="this.parentElement.parentElement.remove()" class="ml-4 text-gray-400 hover:text-gray-600">
                <span class="material-symbols-outlined text-sm">close</span>
            </button>
        </div>
    `;

    document.body.appendChild(toast);
    setTimeout(() => { toast.style.transform = 'translateX(0)'; }, 100);
    setTimeout(() => {
        toast.style.transform = 'translateX(110%)';
        setTimeout(() => toast.remove(), 300);
    }, 5000);
}

function showConfirmationModal(title, message, confirmText = 'Confirm', cancelText = 'Cancel') {
    return new Promise((resolve) => {
        const modal = document.createElement('div');
        modal.className = 'confirmation-modal fixed inset-0 z-[200] flex items-center justify-center p-4 bg-on-surface/40 backdrop-blur-sm';
        modal.innerHTML = `
            <div class="bg-white rounded-[2rem] shadow-2xl max-w-md w-full overflow-hidden p-8">
                <h3 class="text-xl font-bold mb-4">${title}</h3>
                <p class="text-sm text-on-surface-variant mb-8">${message}</p>
                <div class="flex gap-4">
                    <button id="modal-cancel" class="flex-1 py-3 rounded-xl text-xs font-bold uppercase tracking-widest border border-surface-container-highest text-on-surface-variant hover:bg-surface-container transition-all">${cancelText}</button>
                    <button id="modal-confirm" class="flex-1 py-3 rounded-xl text-xs font-bold uppercase tracking-widest bg-red-600 text-white hover:bg-red-700 transition-all shadow-lg shadow-red-200">${confirmText}</button>
                </div>
            </div>
        `;
        document.body.appendChild(modal);
        modal.querySelector('#modal-confirm').onclick = () => { modal.remove(); resolve(true); };
        modal.querySelector('#modal-cancel').onclick = () => { modal.remove(); resolve(false); };
    });
}

function updateNotificationCount() {
    const list = document.getElementById('notification-list');
    const badge = document.getElementById('notification-badge');
    const countEl = document.getElementById('notification-count');
    const noNotif = document.getElementById('no-notifications');

    if (!list) return;
    const count = list.querySelectorAll('[data-notification-id]').length;

    if (badge) {
        if (count === 0) badge.classList.add('hidden');
        else {
            badge.textContent = count;
            badge.classList.remove('hidden');
        }
    }
    if (countEl) countEl.textContent = `${count} unread`;
    if (noNotif) {
        if (count === 0) noNotif.classList.remove('hidden');
        else noNotif.classList.add('hidden');
    }
}

document.addEventListener('DOMContentLoaded', function () {
    const notificationButton = document.getElementById('notificationDropdown');
    if (notificationButton) {
        notificationButton.addEventListener('click', (e) => {
            e.preventDefault();
            e.stopPropagation();
            toggleNotificationDropdown();
        });
    }
    pollNotifications();
    setInterval(pollNotifications, 30000);
});

// Dropdown Menus
function toggleContactsDropdown(e) { e.preventDefault(); e.stopPropagation(); document.getElementById('contacts-dropdown-menu').classList.toggle('hidden'); }
function toggleAccountDropdown(e) { e.preventDefault(); e.stopPropagation(); document.getElementById('account-dropdown-menu').classList.toggle('hidden'); }

document.addEventListener('click', () => {
    const menus = ['contacts-dropdown-menu', 'account-dropdown-menu', 'notification-dropdown-menu'];
    menus.forEach(id => {
        const el = document.getElementById(id);
        if (el) el.classList.add('hidden');
    });
});

// Scroll management
window.addEventListener('beforeunload', () => { 
    sessionStorage.setItem('scrollPos', window.scrollY); 
    sessionStorage.setItem('scrollPath', window.location.pathname);
});
window.addEventListener('load', () => {
    const pos = sessionStorage.getItem('scrollPos');
    const path = sessionStorage.getItem('scrollPath');
    if (pos && path === window.location.pathname) {
        window.scrollTo(0, parseInt(pos));
    } else {
        window.scrollTo(0, 0);
    }
});
