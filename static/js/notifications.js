/**
 * Notification System - Sound & Visual Effects
 * Handles notification sounds and glow animations for new messages
 */

const NotificationSystem = {
    soundEnabled: true,

    // Create notification sound using Web Audio API
    playNotificationSound: function () {
        if (!this.soundEnabled) return;

        try {
            const audioContext = new (window.AudioContext || window.webkitAudioContext)();
            const oscillator = audioContext.createOscillator();
            const gainNode = audioContext.createGain();

            oscillator.connect(gainNode);
            gainNode.connect(audioContext.destination);

            // Pleasant notification sound (two-tone)
            oscillator.frequency.setValueAtTime(800, audioContext.currentTime);
            oscillator.frequency.setValueAtTime(600, audioContext.currentTime + 0.1);

            gainNode.gain.setValueAtTime(0.3, audioContext.currentTime);
            gainNode.gain.exponentialRampToValueAtTime(0.01, audioContext.currentTime + 0.3);

            oscillator.start(audioContext.currentTime);
            oscillator.stop(audioContext.currentTime + 0.3);
        } catch (e) {
            console.warn('Could not play notification sound:', e);
        }
    },

    // Apply glow animation to new message
    applyMessageAnimation: function (messageElement) {
        if (!messageElement) return;

        messageElement.classList.add('new-message');

        // Remove animation class after it completes
        setTimeout(() => {
            messageElement.classList.remove('new-message');
        }, 2000);
    },

    // Apply glow to chat area
    applyChatAreaGlow: function () {
        const chatArea = document.querySelector('.chat-area');
        if (!chatArea) return;

        chatArea.classList.add('has-notification');

        setTimeout(() => {
            chatArea.classList.remove('has-notification');
        }, 1500);
    },

    // Main notification handler for new messages
    onMessageReceived: function (messageElement, isOwnMessage = false) {
        // Don't notify for own messages
        if (isOwnMessage) return;

        // Play sound
        this.playNotificationSound();

        // Apply animations
        this.applyMessageAnimation(messageElement);
        this.applyChatAreaGlow();
    },

    // Toggle sound on/off
    toggleSound: function () {
        this.soundEnabled = !this.soundEnabled;
        localStorage.setItem('notificationSoundEnabled', this.soundEnabled);
        return this.soundEnabled;
    },

    // Initialize from localStorage
    init: function () {
        const saved = localStorage.getItem('notificationSoundEnabled');
        if (saved !== null) {
            this.soundEnabled = saved === 'true';
        }
    }
};

// Initialize on load
NotificationSystem.init();

// Make globally available
window.NotificationSystem = NotificationSystem;
