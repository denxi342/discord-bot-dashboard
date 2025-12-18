// ============================================
// ANIMATIONS.JS - Animation Helper Module
// ============================================

const AnimationsModule = {
    /**
     * Add animation class to newly created message
     * @param {HTMLElement} messageElement - The message bubble element
     * @param {boolean} isOwn - Whether this is user's own message
     */
    animateNewMessage(messageElement, isOwn = false) {
        if (!messageElement) return;

        // Add animation class
        messageElement.classList.add('animate-in');

        // Add direction-specific class if not already present
        if (isOwn && !messageElement.classList.contains('own')) {
            messageElement.classList.add('own');
        } else if (!isOwn && !messageElement.classList.contains('other')) {
            messageElement.classList.add('other');
        }

        // Add bounce effect for received messages
        if (!isOwn) {
            setTimeout(() => {
                messageElement.classList.add('received-notification');
            }, 300);
        }

        // Remove animation classes after animation completes
        setTimeout(() => {
            messageElement.classList.remove('animate-in', 'received-notification');
        }, 1000);
    },

    /**
     * Animate chat switch transition
     * @param {string} fromChatId - Previous chat ID
     * @param {string} toChatId - New chat ID
     */
    animateChatSwitch(fromChatId, toChatId) {
        const fromChat = document.getElementById(`dm-messages-${fromChatId}`);
        const toChat = document.getElementById(`dm-messages-${toChatId}`);

        if (fromChat) {
            fromChat.parentElement.classList.add('switching');
            setTimeout(() => {
                fromChat.parentElement.classList.remove('active', 'switching');
            }, 200);
        }

        if (toChat) {
            setTimeout(() => {
                toChat.parentElement.classList.add('active');
            }, 200);
        }
    },

    /**
     * Animate message bubble on hover
     * @param {HTMLElement} messageElement - The message bubble
     */
    addMessageHoverEffects(messageElement) {
        if (!messageElement) return;

        messageElement.addEventListener('mouseenter', () => {
            messageElement.style.transform = 'translateY(-2px)';
        });

        messageElement.addEventListener('mouseleave', () => {
            messageElement.style.transform = '';
        });
    },

    /**
     * Add typing indicator animation
     * @param {string} dmId - DM conversation ID
     * @param {boolean} show - Whether to show or hide
     */
    showTypingIndicator(dmId, show = true) {
        const container = document.getElementById(`dm-messages-${dmId}`);
        if (!container) return;

        const existingIndicator = container.querySelector('.typing-indicator-wrapper');

        if (show && !existingIndicator) {
            const indicator = document.createElement('div');
            indicator.className = 'dm-bubble other typing-indicator-wrapper';
            indicator.innerHTML = `
                <div class="typing-indicator">
                    <span></span>
                    <span></span>
                    <span></span>
                </div>
            `;
            container.appendChild(indicator);

            // Scroll to bottom
            container.scrollTop = container.scrollHeight;
        } else if (!show && existingIndicator) {
            existingIndicator.remove();
        }
    },

    /**
     * Animate scroll to bottom
     * @param {HTMLElement} container - Container to scroll
     * @param {boolean} smooth - Use smooth scrolling
     */
    scrollToBottom(container, smooth = true) {
        if (!container) return;

        container.scrollTo({
            top: container.scrollHeight,
            behavior: smooth ? 'smooth' : 'auto'
        });
    },

    /**
     * Add pulse animation to notification badge
     * @param {HTMLElement} badgeElement - Badge element
     */
    pulseBadge(badgeElement) {
        if (!badgeElement) return;

        badgeElement.classList.add('unread-badge');
    },

    /**
     * Initialize IntersectionObserver for scroll animations
     */
    initScrollAnimations() {
        const observer = new IntersectionObserver(
            (entries) => {
                entries.forEach(entry => {
                    if (entry.isIntersecting) {
                        entry.target.classList.add('in-view');
                        observer.unobserve(entry.target);
                    }
                });
            },
            { threshold: 0.1 }
        );

        // Observe all message bubbles
        document.querySelectorAll('.dm-bubble').forEach(bubble => {
            observer.observe(bubble);
        });

        return observer;
    },

    /**
     * Add shimmer loading effect
     * @param {HTMLElement} element - Element to add shimmer
     */
    addLoadingShimmer(element) {
        if (!element) return;
        element.classList.add('loading-shimmer');
    },

    /**
     * Remove shimmer loading effect
     * @param {HTMLElement} element - Element to remove shimmer from
     */
    removeLoadingShimmer(element) {
        if (!element) return;
        element.classList.remove('loading-shimmer');
    },

    /**
     * Animate DM list item selection
     * @param {string} dmId - DM ID to highlight
     */
    highlightDMItem(dmId) {
        // Remove previous highlights
        document.querySelectorAll('.dm-item').forEach(item => {
            item.classList.remove('active');
        });

        // Add highlight to selected
        const selectedItem = document.querySelector(`[data-dm-id="${dmId}"]`);
        if (selectedItem) {
            selectedItem.classList.add('active');
        }
    }
};

// Make available globally
window.AnimationsModule = AnimationsModule;

console.log('[AnimationsModule] Animation helper module loaded');
