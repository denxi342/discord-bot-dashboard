/**
 * Emoji Picker Module
 * Handles emoji selection and insertion
 */

const EmojiModule = {
    isOpen: false,
    currentCategory: 'Smileys & Emotion',

    init() {
        // Populate categories
        const categoriesEl = document.getElementById('emoji-categories');
        if (categoriesEl && typeof EMOJI_DATA !== 'undefined') {
            const categories = Object.keys(EMOJI_DATA);
            categoriesEl.innerHTML = '';

            categories.forEach((cat, idx) => {
                const btn = document.createElement('button');
                btn.className = 'emoji-category-btn' + (idx === 0 ? ' active' : '');
                btn.textContent = cat.split(' ')[0]; // Short name
                btn.onclick = () => EmojiModule.selectCategory(cat);
                categoriesEl.appendChild(btn);
            });

            // Show first category
            EmojiModule.showCategory(EmojiModule.currentCategory);
        }

        // Close on outside click
        document.addEventListener('click', (e) => {
            const picker = document.getElementById('emoji-picker-panel');
            const btn = document.getElementById('emoji-picker-btn');
            if (picker && EmojiModule.isOpen && !picker.contains(e.target) && e.target !== btn) {
                EmojiModule.closeEmojiPicker();
            }
        });
    },

    toggleEmojiPicker() {
        const panel = document.getElementById('emoji-picker-panel');
        if (EmojiModule.isOpen) {
            panel.style.display = 'none';
            EmojiModule.isOpen = false;
        } else {
            // Close GIF panel if open
            if (typeof GifModule !== 'undefined') GifModule.closeGifPanel();

            panel.style.display = 'block';
            EmojiModule.isOpen = true;

            // Initialize if first time
            if (!panel.dataset.initialized) {
                panel.dataset.initialized = 'true';
                EmojiModule.init();
            }
        }
    },

    closeEmojiPicker() {
        const panel = document.getElementById('emoji-picker-panel');
        panel.style.display = 'none';
        EmojiModule.isOpen = false;
    },

    selectCategory(category) {
        EmojiModule.currentCategory = category;

        // Update active button
        document.querySelectorAll('.emoji-category-btn').forEach(btn => {
            btn.classList.remove('active');
            if (btn.textContent === category.split(' ')[0]) {
                btn.classList.add('active');
            }
        });

        EmojiModule.showCategory(category);
    },

    showCategory(category) {
        const grid = document.getElementById('emoji-grid');
        if (!grid || typeof EMOJI_DATA === 'undefined') return;

        const emojis = EMOJI_DATA[category] || [];
        grid.innerHTML = '';

        emojis.forEach(emoji => {
            const div = document.createElement('div');
            div.className = 'emoji-item';
            div.textContent = emoji;
            div.onclick = () => EmojiModule.insertEmoji(emoji);
            div.title = emoji;
            grid.appendChild(div);
        });
    },

    searchEmoji(query) {
        query = query.trim().toLowerCase();
        const grid = document.getElementById('emoji-grid');

        if (!query) {
            // Show current category
            EmojiModule.showCategory(EmojiModule.currentCategory);
            return;
        }

        // Simple search - show all emoji (can be enhanced later)
        grid.innerHTML = '';
        let count = 0;

        for (const [category, emojis] of Object.entries(EMOJI_DATA)) {
            emojis.forEach(emoji => {
                if (count < 100) { // Limit results
                    const div = document.createElement('div');
                    div.className = 'emoji-item';
                    div.textContent = emoji;
                    div.onclick = () => EmojiModule.insertEmoji(emoji);
                    grid.appendChild(div);
                    count++;
                }
            });
        }

        if (count === 0) {
            grid.innerHTML = '<div style="padding: 20px; text-align: center; color: var(--text-muted);">Ничего не найдено</div>';
        }
    },

    insertEmoji(emoji) {
        const input = document.getElementById('global-input');
        if (input) {
            const cursorPos = input.selectionStart || input.value.length;
            const before = input.value.substring(0, cursorPos);
            const after = input.value.substring(cursorPos);
            input.value = before + emoji + after;

            // Set cursor after emoji
            const newPos = cursorPos + emoji.length;
            input.setSelectionRange(newPos, newPos);
            input.focus();
        }

        // Don't close picker - allow multiple emoji selections
    }
};

// Initialize when DOM is ready
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', () => {
        // Module will init on first open
    });
} else {
    // DOM already loaded
}
