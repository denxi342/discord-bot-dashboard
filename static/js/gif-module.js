/**
 * GIF Panel Module  
 * Handles GIF search and selection via Tenor API
 */

const GifModule = {
    isOpen: false,
    currentSearch: '',

    toggleGifPanel() {
        const panel = document.getElementById('gif-panel');
        if (GifModule.isOpen) {
            panel.style.display = 'none';
            GifModule.isOpen = false;
        } else {
            // Close emoji picker if open
            if (typeof EmojiModule !== 'undefined') EmojiModule.closeEmojiPicker();

            panel.style.display = 'block';
            GifModule.isOpen = true;

            // Focus search input
            const searchInput = document.getElementById('gif-search-input');
            if (searchInput) searchInput.focus();
        }
    },

    closeGifPanel() {
        const panel = document.getElementById('gif-panel');
        panel.style.display = 'none';
        GifModule.isOpen = false;
    },

    async searchGifs(query) {
        query = query.trim();
        if (!query) return;

        GifModule.currentSearch = query;

        const resultsEl = document.getElementById('gif-results');
        resultsEl.innerHTML = '<div class="gif-loading" style="text-align: center; padding: 40px; color: var(--text-muted);"><i class="fa-solid fa-spinner fa-spin"></i> Загрузка...</div>';

        try {
            const res = await fetch(`/api/giphy/search?q=${encodeURIComponent(query)}`);
            const data = await res.json();

            if (data.success && data.gifs && data.gifs.length > 0) {
                resultsEl.innerHTML = '';

                data.gifs.forEach(gif => {
                    const gifEl = document.createElement('div');
                    gifEl.className = 'gif-item';
                    gifEl.onclick = () => GifModule.selectGif(gif);

                    const img = document.createElement('img');
                    img.src = gif.preview || gif.url;
                    img.alt = gif.title;
                    img.loading = 'lazy';
                    img.style.width = '100%';
                    img.style.borderRadius = '8px';
                    img.style.cursor = 'pointer';

                    gifEl.appendChild(img);
                    resultsEl.appendChild(gifEl);
                });
            } else {
                resultsEl.innerHTML = '<div style="text-align: center; padding: 40px; color: var(--text-muted);">Ничего не найдено</div>';
            }
        } catch (error) {
            console.error('GIF search error:', error);
            resultsEl.innerHTML = '<div style="text-align: center; padding: 40px; color: var(--text-danger);">Ошибка поиска GIF</div>';
        }
    },

    selectGif(gif) {
        // Send GIF as a message
        const input = document.getElementById('global-input');
        if (input) {
            // Set GIF URL as message 
            input.value = gif.url;

            // Trigger send
            if (typeof DiscordModule !== 'undefined' && DiscordModule.handleInput) {
                DiscordModule.handleInput();
            }

            // Clear input
            input.value = '';
        }

        // Close panel
        GifModule.closeGifPanel();

        // Clear search
        const searchInput = document.getElementById('gif-search-input');
        if (searchInput) searchInput.value = '';
    }
};

// Close on outside click
document.addEventListener('click', (e) => {
    const panel = document.getElementById('gif-panel');
    const btn = document.getElementById('gif-panel-btn');
    if (panel && GifModule.isOpen && !panel.contains(e.target) && e.target !== btn) {
        GifModule.closeGifPanel();
    }
});
