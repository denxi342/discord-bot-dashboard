/**
 * Dashboard Pro - Messenger Edition
 * Pure Discord Logic
 */

document.addEventListener('DOMContentLoaded', () => {
    if (typeof DiscordModule !== 'undefined') DiscordModule.init();
    if (typeof WebSocketModule !== 'undefined') WebSocketModule.init();
});

const Utils = {
    showToast: (msg) => console.log('Toast:', msg),
    escapeHtml: (text) => text ? text.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;") : '',
    copyToClipboard: (text) => navigator.clipboard.writeText(text)
};

const DiscordModule = {
    currentServer: 'home',
    currentChannel: 'general',

    serverData: {
        'home': {
            name: 'Главная',
            channels: [
                { id: 'cat-info', type: 'category', name: 'ИНФОРМАЦИЯ' },
                { id: 'general', type: 'channel', name: 'general', icon: 'hashtag' },
                { id: 'news', type: 'channel', name: 'news-feed', icon: 'newspaper' },
                { id: 'community', type: 'channel', name: 'leaderboard', icon: 'trophy' }
            ]
        },
        'ai': {
            name: 'Arizona AI',
            channels: [
                { id: 'cat-ai', type: 'category', name: 'ASSISTANT' },
                { id: 'helper', type: 'channel', name: 'chat-gpt', icon: 'robot' },
                { id: 'biography', type: 'channel', name: 'search-rules', icon: 'magnifying-glass' }
            ]
        },
        'smi': {
            name: 'СМИ WORK',
            channels: [
                { id: 'cat-work', type: 'category', name: 'TOOLS' },
                { id: 'smi', type: 'channel', name: 'ad-editor', icon: 'pen-to-square' }
            ]
        },
        'admin': {
            name: 'Admin Control',
            channels: [
                { id: 'cat-admin', type: 'category', name: 'ADMINISTRATION' },
                { id: 'admin', type: 'channel', name: 'users', icon: 'users-gear' }
            ]
        },
        'profile': {
            name: 'User Settings',
            channels: [
                { id: 'profile', type: 'channel', name: 'my-profile', icon: 'user' }
            ]
        }
    },

    init: () => {
        DiscordModule.selectServer('home');
        // Initial Bot Message in General
        DiscordModule.addMessage('general', {
            author: 'System Bot',
            avatar: 'https://cdn.discordapp.com/embed/avatars/0.png',
            text: 'System online. Waiting for commands.',
            type: 'system',
            embed: {
                title: 'Connected',
                desc: 'Dashboard connected to backend successfully.',
                color: '#23a559'
            }
        });
        DiscordModule.loadServersStatus();
    },

    selectServer: (serverId) => {
        // UI Update
        document.querySelectorAll('.server-icon').forEach(el => el.classList.remove('active'));
        const btn = document.getElementById(`server-${serverId}`);
        if (btn) btn.classList.add('active');

        DiscordModule.currentServer = serverId;
        const data = DiscordModule.serverData[serverId];
        if (data) document.getElementById('current-server-name').textContent = data.name;

        // Render Channels
        const container = document.getElementById('channel-list-container');
        container.innerHTML = '';
        if (data) {
            data.channels.forEach(ch => {
                if (ch.type === 'category') {
                    container.innerHTML += `<div class="channel-category"><i class="fa-solid fa-angle-down"></i> ${ch.name}</div>`;
                } else {
                    container.innerHTML += `<div class="channel-item" id="btn-ch-${ch.id}" onclick="DiscordModule.selectChannel('${ch.id}')"><i class="fa-solid fa-${ch.icon}"></i> ${ch.name}</div>`;
                }
            });
            // Auto Select First
            const first = data.channels.find(c => c.type === 'channel');
            if (first) DiscordModule.selectChannel(first.id);
        }
    },

    selectChannel: (chanId) => {
        DiscordModule.currentChannel = chanId;

        // UI
        document.querySelectorAll('.channel-item').forEach(el => el.classList.remove('active'));
        const btn = document.getElementById(`btn-ch-${chanId}`);
        if (btn) {
            btn.classList.add('active');
            document.getElementById('current-channel-name').textContent = btn.textContent.trim();
        }

        // View Switch
        document.querySelectorAll('.channel-view').forEach(el => el.classList.remove('active'));

        // Map generic IDs to views
        let viewId = 'general'; // Default
        if (chanId === 'general') viewId = 'general';
        if (chanId === 'news') viewId = 'news';
        if (chanId === 'community') viewId = 'community';
        if (chanId === 'helper') viewId = 'helper';
        if (chanId === 'biography') viewId = 'search'; // Mapped search here for simplicity
        if (chanId === 'smi') viewId = 'smi';
        if (chanId === 'admin') viewId = 'admin';
        if (chanId === 'profile') viewId = 'profile';

        const view = document.getElementById(`channel-view-${viewId}`);
        if (view) {
            view.classList.add('active');
            // Auto-scroll to bottom of that view
            const scrollArea = document.getElementById('main-scroll-area');
            scrollArea.scrollTop = scrollArea.scrollHeight;
        }

        // Trigger Data Load
        if (chanId === 'news') DiscordModule.loadNews();
        if (chanId === 'community') DiscordModule.loadLeaderboard();
        if (chanId === 'admin') DiscordModule.loadUsers();
        if (chanId === 'profile') DiscordModule.loadProfile();
    },

    // --- MESSAGING SYSTEM ---
    addMessage: (channelId, msgData) => {
        // Find target stream
        let streamId = `stream-${channelId}`;
        // Mapping fix
        if (channelId === 'news') streamId = 'stream-news';
        if (channelId === 'community') streamId = 'stream-leaderboard';
        if (channelId === 'helper') streamId = 'stream-helper';
        if (channelId === 'smi') streamId = 'stream-smi';
        if (channelId === 'admin') streamId = 'stream-admin';
        if (channelId === 'profile') streamId = 'stream-profile';

        const container = document.getElementById(streamId);
        // Fallback to general if not found or if it is general
        if (!container && channelId === 'general') container = document.getElementById('stream-general');

        if (!container) return;

        const time = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });

        let embedHtml = '';
        if (msgData.embed) {
            embedHtml = `
            <div class="discord-embed" style="border-left-color: ${msgData.embed.color || '#5865F2'};">
                ${msgData.embed.title ? `<div class="embed-title">${msgData.embed.title}</div>` : ''}
                ${msgData.embed.desc ? `<div class="embed-desc">${msgData.embed.desc.replace(/\n/g, '<br>')}</div>` : ''}
                ${msgData.embed.image ? `<img src="${msgData.embed.image}" class="embed-image">` : ''}
                ${msgData.embed.fields ? msgData.embed.fields.map(f => `
                    <div class="embed-field">
                        <div class="embed-field-name">${f.name}</div>
                        <div class="embed-field-value">${f.value}</div>
                    </div>
                `).join('') : ''}
            </div>`;
        }

        const html = `
        <div class="message-group">
            <img src="${msgData.avatar}" class="message-avatar">
            <div class="message-content">
                <div class="message-header">
                    <span class="msg-author" style="color:${msgData.color || 'white'}">${msgData.author}</span>
                    ${msgData.bot ? '<span class="msg-tag">BOT</span>' : ''}
                    <span class="msg-timestamp">${time}</span>
                </div>
                <div class="message-text">${Utils.escapeHtml(msgData.text)}</div>
                ${embedHtml}
            </div>
        </div>
        `;

        container.insertAdjacentHTML('beforeend', html);

        // Scroll parent
        const mainArea = document.getElementById('main-scroll-area');
        if (mainArea) mainArea.scrollTop = mainArea.scrollHeight;
    },

    handleInput: async () => {
        const input = document.getElementById('global-input');
        const text = input.value.trim();
        if (!text) return;

        const chan = DiscordModule.currentChannel;
        input.value = '';

        // User Message
        DiscordModule.addMessage(chan, {
            author: 'You',
            avatar: 'https://cdn.discordapp.com/embed/avatars/1.png', // Placeholder
            text: text
        });

        // Handler
        if (chan === 'helper') await DiscordModule.askAI(text);
        if (chan === 'smi') await DiscordModule.editAd(text);
        if (chan === 'biography') await DiscordModule.searchRules(text);
    },

    // --- LOGIC ---
    loadNews: async () => {
        const container = document.getElementById('stream-news');
        if (container.childElementCount > 0) return; // Don't reload

        DiscordModule.addMessage('news', { author: 'News Bot', bot: true, avatar: 'https://cdn.discordapp.com/embed/avatars/2.png', text: 'Загружаю новости...', color: '#3498db' });

        try {
            const res = await fetch('/api/arizona/news');
            const data = await res.json();
            if (data.success) {
                data.news.forEach(item => {
                    DiscordModule.addMessage('news', {
                        author: 'Arizona News',
                        bot: true,
                        avatar: 'https://cdn.discordapp.com/embed/avatars/2.png',
                        text: '',
                        embed: {
                            title: item.title,
                            desc: item.summary + `\n\n[Читать далее](${item.url})`,
                            image: item.image,
                            color: item.tag === 'Обновление' ? '#e74c3c' : '#3498db'
                        }
                    });
                });
            }
        } catch (e) { console.error(e); }
    },

    loadUsers: async () => {
        const container = document.getElementById('stream-admin');
        container.innerHTML = '';

        // Command Mock
        DiscordModule.addMessage('admin', { author: 'You', avatar: 'https://cdn.discordapp.com/embed/avatars/1.png', text: '/list_users' });

        try {
            const res = await fetch('/api/admin/users');
            const data = await res.json();
            if (data.success && data.users) {
                // Generate a "Code Block" list or Embeds
                const userList = data.users.map(u => `${u.id.padEnd(20)} | ${u.username.padEnd(20)} | ${u.role}`).join('\n');

                DiscordModule.addMessage('admin', {
                    author: 'Admin Bot',
                    bot: true,
                    avatar: 'https://cdn.discordapp.com/embed/avatars/3.png',
                    text: 'Список пользователей:',
                    embed: {
                        desc: '```\nID                   | Username             | Role\n----------------------------------------------------\n' + userList + '\n```',
                        color: '#faa61a'
                    }
                });
            }
        } catch (e) { }
    },

    loadLeaderboard: async () => {
        const container = document.getElementById('stream-leaderboard');
        if (container.childElementCount > 0) return;

        try {
            const res = await fetch('/api/reputation/top');
            const data = await res.json();
            if (data.success) {
                const fields = data.top.map((u, i) => ({
                    name: `#${i + 1} ${u.username}`,
                    value: `Reputation: ${u.reputation} | Role: ${u.role}`
                }));

                DiscordModule.addMessage('community', {
                    author: 'Leaderboard Bot',
                    bot: true,
                    text: 'Топ 10 пользователей по репутации:',
                    avatar: 'https://cdn.discordapp.com/embed/avatars/4.png',
                    embed: {
                        title: '🏆 Hall of Fame',
                        fields: fields,
                        color: '#f1c40f'
                    }
                });
            }
        } catch (e) { }
    },

    loadProfile: async () => {
        // Profile is just a self-message with embed
        const container = document.getElementById('stream-profile');
        container.innerHTML = '';

        // Mock fetching me
        // In real app we use values from template or API
        // Here we'll just mock it slightly or assume we can get it
        DiscordModule.addMessage('profile', {
            author: 'Profile System',
            bot: true,
            avatar: 'https://cdn.discordapp.com/embed/avatars/0.png',
            text: 'Ваш профиль:',
            embed: {
                title: 'User Profile',
                desc: 'Статистика аккаунта',
                color: '#5865F2',
                fields: [
                    { name: 'ID', value: 'Loading...' },
                    { name: 'Role', value: 'User' },
                    { name: 'Reputation', value: '0' }
                ]
            }
        });
    },

    askAI: async (q) => {
        // AI Thinking...
        DiscordModule.addMessage('helper', { author: 'Arizona AI', bot: true, avatar: 'https://cdn.discordapp.com/embed/avatars/5.png', text: 'Thinking...', color: '#9b59b6' });
        try {
            const res = await fetch('/api/arizona/helper', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ question: q }) });
            const data = await res.json();
            // Remove "Thinking" (Simplest way here is just add new message, ignoring removal for MVU)
            DiscordModule.addMessage('helper', {
                author: 'Arizona AI',
                bot: true,
                avatar: 'https://cdn.discordapp.com/embed/avatars/5.png',
                text: data.response
            });
        } catch (e) { }
    },

    editAd: async (text) => {
        try {
            const res = await fetch('/api/arizona/smi/edit', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ text: text }) });
            const data = await res.json();
            DiscordModule.addMessage('smi', {
                author: 'SMI Helper',
                bot: true,
                avatar: 'https://cdn.discordapp.com/embed/avatars/6.png',
                text: 'Отредактированное объявление:',
                embed: {
                    desc: `**${data.response}**`,
                    color: '#2ecc71',
                    footer: { text: `Source: ${data.source}` }
                }
            });
        } catch (e) { }
    },

    searchRules: async (text) => {
        try {
            const res = await fetch('/api/arizona/rules', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ question: text }) });
            const data = await res.json();
            DiscordModule.addMessage('biography', { // mapped to search
                author: 'Rules Bot',
                bot: true,
                avatar: 'https://cdn.discordapp.com/embed/avatars/7.png',
                text: '',
                embed: {
                    title: 'Результат поиска',
                    desc: data.response,
                    color: '#e67e22'
                }
            });
        } catch (e) { }
    },

    loadServersStatus: async () => {
        // Background update
        // ...
    }
};

const WebSocketModule = {
    init: () => {
        // ... (Keep existing WS logic if needed for stats, but supress UI if targets missing)
    }
};
