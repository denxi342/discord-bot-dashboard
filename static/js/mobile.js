/* mobile.js - Premium Mobile interactions and navigation */

const MobileModule = {
    currentTab: 'chats',

    init: function() {
        console.log("[MobileModule] Initializing Premium Mobile UI...");
        this.bindEvents();
        // Set initial state
        if (window.innerWidth <= 768) {
            this.switchTab('chats');
        }
    },

    bindEvents: function() {
        // Handle window resize to reset views if needed
        window.addEventListener('resize', this.handleResize.bind(this));

        // Swipe gestures for navigation
        this.initSwipes();

        // Intercept channel/chat clicks to show the chat view
        document.addEventListener('click', (e) => {
            const chatItem = e.target.closest('.chat-list-item') || e.target.closest('.channel-item') || e.target.closest('.dm-item') || e.target.closest('.friend-item');
            if (chatItem && window.innerWidth <= 768) {
                // Ensure we are not clicking a button inside
                if (!e.target.closest('button') && !e.target.closest('.user-controls')) {
                    this.enterChat();
                }
            }
            
            // Handle Settings Navigation in Mobile
            const settingsNavItem = e.target.closest('.settings-sidebar-nav .nav-item') || e.target.closest('.settings-sidebar-nav .nav-link-item');
            if (settingsNavItem && window.innerWidth <= 768) {
                this.showSettingsContent();
            }
            
            // Back button in settings
            if (e.target.closest('.settings-mobile-back')) {
                this.showSettingsSidebar();
            }
        });
    },

    switchTab: function(tab) {
        console.log("[MobileModule] Switching to tab:", tab);
        this.currentTab = tab;

        // Update Nav UI
        document.querySelectorAll('.mobile-nav-item').forEach(el => el.classList.remove('active'));
        const activeNav = document.getElementById(`nav-item-${tab}`);
        if (activeNav) activeNav.classList.add('active');

        // Reset Chat View
        this.exitChat();

        // Close any open modals that might interfere
        if (window.DiscordModule) {
            DiscordModule.closeSettings();
            DiscordModule.closeServerSettings();
            DiscordModule.closeModal();
        }

        // Handle specific views
        switch(tab) {
            case 'chats':
                // Main chat list is handled by channel-sidebar
                this.showSidebar();
                break;
            case 'friends':
                // Enter Chat view but with Friends content
                if (window.DiscordModule) {
                    this.enterChat(); // Treat it as a "Detail" view for now
                    DiscordModule.selectChannel('friends', 'channel');
                }
                break;
            case 'settings':
                if (window.DiscordModule) DiscordModule.openSettings();
                break;
            case 'admin':
                if (window.AdminModule) AdminModule.openAdminPanel();
                break;
        }
    },

    enterChat: function() {
        console.log("[MobileModule] Entering Chat View");
        const chatArea = document.querySelector('.chat-area');
        const sidebar = document.querySelector('.channel-sidebar');
        const bottomNav = document.querySelector('.mobile-bottom-nav');

        if (chatArea) chatArea.classList.add('active-mobile');
        if (sidebar) sidebar.classList.add('sidebar-hidden-mobile');
        if (bottomNav) bottomNav.classList.add('nav-hidden-mobile');
        
        document.body.classList.add('in-chat-mobile');
    },

    exitChat: function() {
        console.log("[MobileModule] Exiting Chat View");
        const chatArea = document.querySelector('.chat-area');
        const sidebar = document.querySelector('.channel-sidebar');
        const bottomNav = document.querySelector('.mobile-bottom-nav');

        if (chatArea) chatArea.classList.remove('active-mobile');
        if (sidebar) sidebar.classList.remove('sidebar-hidden-mobile');
        if (bottomNav) bottomNav.classList.remove('nav-hidden-mobile');
        
        document.body.classList.remove('in-chat-mobile');
    },

    showSidebar: function() {
        this.exitChat();
    },

    // Settings Specifics
    showSettingsContent: function() {
        const sidebar = document.querySelector('.settings-sidebar-col');
        const content = document.querySelector('.settings-content-col');
        if (sidebar && content) {
            sidebar.classList.add('hidden-mobile-settings');
            content.classList.add('active-mobile-settings');
        }
    },

    showSettingsSidebar: function() {
        const sidebar = document.querySelector('.settings-sidebar-col');
        const content = document.querySelector('.settings-content-col');
        if (sidebar && content) {
            sidebar.classList.remove('hidden-mobile-settings');
            content.classList.remove('active-mobile-settings');
        }
    },

    handleResize: function() {
        if (window.innerWidth > 768) {
            this.exitChat();
            // Reset settings
            this.showSettingsSidebar();
        }
    },

    initSwipes: function() {
        let touchStartX = 0;
        let touchEndX = 0;
        
        document.addEventListener('touchstart', e => {
            touchStartX = e.changedTouches[0].screenX;
        }, {passive: true});

        document.addEventListener('touchend', e => {
            touchEndX = e.changedTouches[0].screenX;
            this.handleSwipe(touchStartX, touchEndX);
        }, {passive: true});
    },

    handleSwipe: function(startX, endX) {
        if (window.innerWidth > 768) return;
        
        // Right swipe (opening sidebar or going back)
        if (endX - startX > 100) {
            if (document.body.classList.contains('in-chat-mobile')) {
                this.exitChat();
            }
        }
    }
};

document.addEventListener('DOMContentLoaded', () => MobileModule.init());
