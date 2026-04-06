/* mobile.js - Mobile interactions and sidebar toggling logic */

const MobileModule = {
    init: function() {
        console.log("[MobileModule] Initialized for mobile optimizations.");
        this.bindEvents();
    },

    bindEvents: function() {
        // Intercept clicks on the chat list to hide sidebar on mobile
        document.addEventListener('click', (e) => {
            const chatItem = e.target.closest('.chat-list-item') || e.target.closest('.channel-item') || e.target.closest('.folder-item');
            if (chatItem) {
                this.hideSidebar();
            }
        });

        // Prevent body scrolling when the sidebar is open on mobile
        window.addEventListener('resize', this.handleResize.bind(this));
        
        // Add swipe gesture listener on chat area to go back
        this.initSwipes();
    },

    hideSidebar: function() {
        if (window.innerWidth <= 768) {
            const sidebar = document.querySelector('.channel-sidebar');
            if (sidebar && !sidebar.classList.contains('hidden-mobile')) {
                sidebar.classList.add('hidden-mobile');
            }
        }
    },

    showSidebar: function() {
        const sidebar = document.querySelector('.channel-sidebar');
        if (sidebar) {
            sidebar.classList.remove('hidden-mobile');
        }
    },

    handleResize: function() {
        // Restore sidebar visibility if resized back to desktop constraints
        if (window.innerWidth > 768) {
            const sidebar = document.querySelector('.channel-sidebar');
            if (sidebar) {
                sidebar.classList.remove('hidden-mobile');
            }
        }
    },
    
    initSwipes: function() {
        let touchStartX = 0;
        let touchEndX = 0;
        
        const chatArea = document.querySelector('.chat-area');
        if(!chatArea) return;

        chatArea.addEventListener('touchstart', e => {
            touchStartX = e.changedTouches[0].screenX;
        }, {passive: true});

        chatArea.addEventListener('touchend', e => {
            touchEndX = e.changedTouches[0].screenX;
            this.handleSwipe(touchStartX, touchEndX);
        }, {passive: true});
    },
    
    handleSwipe: function(startX, endX) {
        if (window.innerWidth > 768) return;
        
        // Right swipe (opening sidebar)
        if (endX - startX > 80 && startX < 50) { 
            // Only trigger if swipe starts from the left edge (startX < 50px)
            this.showSidebar();
        }
    }
};

// Auto-init on load
document.addEventListener('DOMContentLoaded', () => {
    MobileModule.init();
});
