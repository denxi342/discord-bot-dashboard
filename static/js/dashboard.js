/**
 * Dashboard Pro - Messenger Edition
 * Pure Discord Logic + Dynamic Server Management
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
    currentChannel: null,
    serverData: {}, // Now loaded from API

    init: async () => {
        await DiscordModule.loadServers();

        // Initial Bot Message if empty
        if (!DiscordModule.currentChannel) {
            DiscordModule.selectServer('home');
        }
    },

    loadServers: async () => {
        try {
            const res = await fetch('/api/servers');
            const data = await res.json();
            if (data.success && data.servers) {
                DiscordModule.serverData = data.servers;
                DiscordModule.renderServerList();
            }
        } catch (e) { console.error("Failed to load servers", e); }
    },

    renderServerList: () => {
        const list = document.querySelector('.server-list');
        const profile = list.querySelector('#server-profile');
        const addBtn = list.querySelector('.add-server');

        list.innerHTML = '';

        const keys = Object.keys(DiscordModule.serverData).sort((a, b) => {
            if (a === 'home') return -1;
            if (b === 'home') return 1;
            return 0;
        });

        keys.forEach(sid => {
            const s = DiscordModule.serverData[sid];
            const active = (sid === DiscordModule.currentServer) ? 'active' : '';
            let iconHtml = `<i class="fa-solid fa-${s.icon || 'server'}"></i>`;
            if (s.is_image) {
                iconHtml = `<img src="${s.icon}" style="width:100%; height:100%; border-radius:50%; object-fit:cover;">`;
            } else if (s.icon === 'discord') {
                iconHtml = `<i class="fa-brands fa-discord"></i>`;
            }

            const html = `
            <div class="server-icon ${active}" id="server-${sid}" onclick="DiscordModule.selectServer('${sid}')" data-tooltip="${s.name}">
                ${iconHtml}
            </div>`;

            list.innerHTML += html;
            if (sid === 'home') list.innerHTML += `<div class="server-sep"></div>`;
        });

        list.innerHTML += `<div class="server-sep"></div>`;
        if (addBtn) list.appendChild(addBtn);
        if (profile) list.appendChild(profile);
    },

    selectServer: (serverId) => {
        if (!DiscordModule.serverData[serverId]) return;
        DiscordModule.currentServer = serverId;

        document.querySelectorAll('.server-icon').forEach(el => el.classList.remove('active'));
        const btn = document.getElementById(`server-${serverId}`);
        if (btn) btn.classList.add('active');

        const s = DiscordModule.serverData[serverId];
        document.getElementById('current-server-name').textContent = s.name;

        DiscordModule.renderChannels(serverId);
    },

    renderChannels: (serverId) => {
        const container = document.getElementById('channel-list-container');
        container.innerHTML = '';

        if (serverId === 'home') {
            DiscordModule.renderHomeSidebar(container);
            return;
        }

        const data = DiscordModule.serverData[serverId];
        if (!data) return;

        data.channels.forEach(ch => {
            if (ch.type === 'category') {
                container.innerHTML += `
                 <div class="channel-category">
                    <i class="fa-solid fa-angle-down"></i> ${ch.name} 
                    <i class="fa-solid fa-plus" style="margin-left:auto; cursor:pointer;" onclick="DiscordModule.uiCreateChannel('${serverId}')" title="Add Channel"></i>
                 </div>`;
            } else {
                const icon = ch.type === 'voice' ? 'volume-high' : (ch.icon || 'hashtag');
                container.innerHTML += `
                <div class="channel-item" id="btn-ch-${ch.id}" onclick="DiscordModule.selectChannel('${ch.id}', '${ch.type}')">
                    <i class="fa-solid fa-${icon}"></i> ${ch.name}
                </div>`;
            }
        });

        const first = data.channels.find(c => c.type === 'channel');
        if (first) DiscordModule.selectChannel(first.id, 'channel');
    },

    renderHomeSidebar: (container) => {
        // Search Button
        container.innerHTML += `
        <div style="padding:0 8px; margin-bottom:8px;">
            <button style="width:100%; background:#1E1F22; color:#949BA4; border:none; border-radius:4px; padding:6px; text-align:left; font-size:13px; cursor:pointer;">
                Найти или начать беседу
            </button>
        </div>`;

        // Static Items (Friends, Nitro)
        container.innerHTML += `
        <div class="channel-item active" onclick="DiscordModule.selectChannel('friends', 'channel')"><i class="fa-solid fa-user-group"></i> Друзья</div>
        <div class="channel-item" onclick="Utils.showToast('Nitro Store is closed')"><i class="fa-solid fa-bolt"></i> Nitro</div>
        <div class="channel-item" onclick="Utils.showToast('Shop is closed')"><i class="fa-solid fa-shop"></i> Магазин</div>
        `;

        // Direct Messages Header (Removed per user request)
        // container.innerHTML += `
        // <div class="channel-category" style="margin-top:16px;">
        //    ЛИЧНЫЕ СООБЩЕНИЯ <i class="fa-solid fa-plus" style="margin-left:auto;"></i>
        // </div>`;

        // DM Items (Tools mapped as Users)
        const dms = [
            { id: 'helper', name: 'Arizona AI', icon: 'https://cdn-icons-png.flaticon.com/512/4712/4712027.png', status: 'online' },
            { id: 'news', name: 'News Feed', icon: 'https://cdn-icons-png.flaticon.com/512/2540/2540832.png', status: 'dnd' },
            { id: 'users', name: 'Admin Console', icon: 'https://cdn-icons-png.flaticon.com/512/3135/3135715.png', status: 'idle' },
            { id: 'smi', name: 'SMI Editor', icon: 'https://cdn-icons-png.flaticon.com/512/2919/2919601.png', status: 'online' },
            { id: 'community', name: 'Leaderboard', icon: 'https://cdn-icons-png.flaticon.com/512/3112/3112946.png', status: 'online' }
        ];

        dms.forEach(dm => {
            const statusColor = dm.status === 'online' ? '#23A559' : (dm.status === 'dnd' ? '#F23F42' : '#F0B232');
            container.innerHTML += `
            <div class="dm-item" id="btn-ch-${dm.id}" onclick="DiscordModule.selectChannel('${dm.id}')">
                <div class="dm-avatar-wrapper">
                    <img src="${dm.icon}" class="dm-avatar">
                    <div class="dm-status" style="background-color:${statusColor};"></div>
                </div>
                <div class="dm-name">${dm.name}</div>
            </div>`;
        });
    },

    selectChannel: (chanId, type = 'channel') => {
        if (type === 'voice') {
            DiscordModule.connectVoice(chanId);
            return;
        }

        DiscordModule.currentChannel = chanId;

        document.querySelectorAll('.channel-item').forEach(el => el.classList.remove('active'));
        const btn = document.getElementById(`btn-ch-${chanId}`);
        if (btn) {
            btn.classList.add('active');
            document.getElementById('current-channel-name').innerText = btn.innerText.trim();
        }

        const mappedViews = {
            'news': 'news', 'leaderboard': 'community', 'video-feed': 'general',
            'chat-gpt': 'helper', 'search-rules': 'search', 'ad-editor': 'smi', 'users': 'admin', 'my-profile': 'profile'
        };

        let viewKey = 'general';
        const chNameData = DiscordModule.serverData[DiscordModule.currentServer].channels.find(c => c.id === chanId);
        if (chNameData && mappedViews[chNameData.name]) viewKey = mappedViews[chNameData.name];
        else if (mappedViews[chanId]) viewKey = mappedViews[chanId];
        else if (chanId === 'general') viewKey = 'general';

        document.querySelectorAll('.channel-view').forEach(el => el.classList.remove('active'));
        let targetView = document.getElementById(`channel-view-${viewKey}`);

        if (!targetView) {
            targetView = document.getElementById('channel-view-general');
            const welcome = targetView.querySelector('h1');
            if (welcome) welcome.textContent = `Welcome to #${chNameData ? chNameData.name : 'channel'}`;
        }

        if (targetView) {
            targetView.classList.add('active');
            if (viewKey === 'news') DiscordModule.loadNews();
            if (viewKey === 'community') DiscordModule.loadLeaderboard();
            if (viewKey === 'admin') DiscordModule.loadUsers();
            if (viewKey === 'profile') DiscordModule.loadProfile();
        }
    },

    connectVoice: (chanId) => {
        document.querySelector('.user-controls i.fa-microphone').style.color = '#23a559';
        // toast?
    },

    // --- CREATION UTILS (NEW MODAL LOGIC) ---
    currentUploadData: null,

    uiCreateServer: () => {
        // Reset state
        DiscordModule.currentUploadData = null;
        const preview = document.getElementById('new-server-icon-preview');
        const text = document.getElementById('new-server-icon-text');

        if (preview) preview.style.backgroundImage = 'none';
        if (text) text.style.display = 'flex';

        const modal = document.getElementById('create-server-modal');
        if (modal) {
            modal.style.display = 'flex';
            modal.style.opacity = '1';
            DiscordModule.uiServerStep1();
        }
    },

    closeModal: () => {
        const modal = document.getElementById('create-server-modal');
        if (modal) {
            modal.style.opacity = '0';
            setTimeout(() => modal.style.display = 'none', 200);
        }
    },

    uiServerStep1: () => {
        document.getElementById('modal-step-1').style.display = 'block';
        document.getElementById('modal-step-2').style.display = 'none';
    },

    uiServerStep2: (templateName) => {
        document.getElementById('modal-step-1').style.display = 'none';
        document.getElementById('modal-step-2').style.display = 'block';

        // Auto-fill name logic
        const input = document.getElementById('new-server-name');
        if (templateName === 'Свой шаблон') {
            input.value = "Сервер пользователя";
        } else {
            input.value = templateName;
        }
        input.focus();
    },

    triggerIconUpload: () => {
        document.getElementById('server-icon-input').click();
    },

    handleIconSelect: (input) => {
        if (input.files && input.files[0]) {
            const reader = new FileReader();
            reader.onload = function (e) {
                DiscordModule.currentUploadData = e.target.result;
                const preview = document.getElementById('new-server-icon-preview');
                const text = document.getElementById('new-server-icon-text');

                preview.style.backgroundImage = `url(${e.target.result})`;
                text.style.display = 'none';
            }
            reader.readAsDataURL(input.files[0]);
        }
    },

    finishCreateServer: async () => {
        const name = document.getElementById('new-server-name').value;
        if (name) {
            const payload = { name: name, icon_data: DiscordModule.currentUploadData };
            await DiscordModule.apiCreateServer(payload);
            DiscordModule.closeModal();
        }
    },

    uiCreateChannel: (sid) => {
        const name = prompt("Название канала:");
        const isVoice = confirm("Это голосовой канал?");
        if (name) DiscordModule.apiCreateChannel(sid, name, isVoice ? 'voice' : 'channel');
    },

    apiCreateServer: async (payload) => {
        try {
            const body = typeof payload === 'string' ? { name: payload } : payload;
            const res = await fetch('/api/servers/create', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) });
            const d = await res.json();
            if (d.success) {
                DiscordModule.serverData[d.id] = d.server;
                DiscordModule.renderServerList();
                DiscordModule.selectServer(d.id);
            }
        } catch (e) { console.error(e); }
    },

    apiCreateChannel: async (sid, name, type) => {
        try {
            const res = await fetch(`/api/servers/${sid}/channels/create`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ name, type }) });
            const d = await res.json();
            if (d.success) {
                DiscordModule.serverData[sid].channels.push(d.channel);
                DiscordModule.renderChannels(sid);
            }
        } catch (e) { console.error(e); }
    },

    addMessage: (channelId, msgData) => {
        const main = document.getElementById('channel-view-general').querySelector('#stream-general');
        let container = null;
        if (channelId === 'news') container = document.getElementById('stream-news');
        else if (channelId === 'community') container = document.getElementById('stream-leaderboard');
        else if (channelId === 'helper') container = document.getElementById('stream-helper');
        else if (channelId === 'smi') container = document.getElementById('stream-smi');
        else if (channelId === 'admin') container = document.getElementById('stream-admin');
        else if (channelId === 'profile') container = document.getElementById('stream-profile');
        else if (channelId === 'biography') container = document.getElementById('stream-search');
        else container = main;

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
            <img src="${msgData.avatar || 'https://cdn.discordapp.com/embed/avatars/0.png'}" class="message-avatar">
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
    },

    handleInput: async () => {
        const input = document.getElementById('global-input');
        const text = input.value.trim();
        if (!text) return;
        input.value = '';

        DiscordModule.addMessage(DiscordModule.currentChannel, {
            author: 'You', avatar: 'https://cdn.discordapp.com/embed/avatars/1.png', text: text
        });

        if (DiscordModule.currentChannel === 'helper' || DiscordModule.serverData.ai?.channels.find(c => c.id === DiscordModule.currentChannel)?.name === 'chat-gpt') {
            await DiscordModule.askAI(text);
        }
    },

    // Stub Helpers (Re-implement if needed fully, but keeping brief for now as they trigger server side mostly)
    loadNews: async () => {
        const container = document.getElementById('stream-news');
        if (container.innerHTML.trim()) return;
        try {
            const res = await fetch('/api/arizona/news');
            const d = await res.json();
            if (d.news) {
                d.news.forEach(n => {
                    DiscordModule.addMessage('news', {
                        author: 'News Bot', bot: true, avatar: 'https://cdn-icons-png.flaticon.com/512/2540/2540832.png',
                        text: '',
                        embed: { title: n.title, desc: n.summary, image: n.image, color: '#F47B67' }
                    });
                });
            }
        } catch (e) { }
    },
    loadLeaderboard: async () => {
        const container = document.getElementById('stream-leaderboard');
        if (container.innerHTML.trim()) return;
        try {
            const res = await fetch('/api/reputation/top');
            const d = await res.json();
            if (d.top) {
                let fields = d.top.map((u, i) => ({ name: `#${i + 1} ${u.username}`, value: `Reputation: ${u.reputation}` }));
                DiscordModule.addMessage('community', {
                    author: 'Leaderboard Bot', bot: true, avatar: 'https://cdn-icons-png.flaticon.com/512/3112/3112946.png',
                    text: 'Top users by reputation:',
                    embed: { title: 'Hall of Fame', color: '#FFD700', fields: fields }
                });
            }
        } catch (e) { }
    },
    loadUsers: async () => {
        // Simple stub
        const container = document.getElementById('stream-admin');
        if (container.innerHTML.trim()) return;
        DiscordModule.addMessage('admin', { author: 'Admin Bot', bot: true, text: 'Ready for commands. Type /users to see list.' });
    },
    loadProfile: async () => {
        // Simple stub
        const container = document.getElementById('stream-profile');
        if (container.innerHTML.trim()) return;
        DiscordModule.addMessage('profile', { author: 'Profile System', bot: true, text: 'Your profile stats will appear here.' });
    },

    askAI: async (q) => {
        try {
            const res = await fetch('/api/arizona/helper', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ question: q }) });
            const data = await res.json();
            DiscordModule.addMessage('helper', { author: 'Arizona AI', bot: true, text: data.response });
        } catch (e) { }
    },

    // --- UI ENHANCEMENTS (REAL) ---
    fakeCall: () => Utils.showToast('Voice/Video call unavailable (WebRTC not implemented)'),
    showPinned: () => Utils.showToast('No pinned messages.'),

    // Member List (Real Data)
    toggleMemberList: () => {
        const sb = document.getElementById('member-sidebar');
        if (sb) {
            sb.classList.toggle('hidden');
            if (!sb.classList.contains('hidden')) DiscordModule.renderMembers();
        }
    },

    renderMembers: async () => {
        const container = document.getElementById('member-list-content');
        if (!container) return;

        container.innerHTML = '<div style="padding:20px;color:gray;text-align:center">Loading...</div>';

        try {
            // Using existing admin API which returns all users
            const res = await fetch('/api/admin/users');
            const data = await res.json();

            if (data.success && data.users) {
                container.innerHTML = '';

                // Group by online/offline (mock status for now as backend doesn't track properly realtime yet)
                const online = data.users; // Assume all "registered" are visible

                container.innerHTML += `
                    <div class="member-group">
                        <div class="group-name">MEMBERS — ${online.length}</div>
                    </div>`;

                online.forEach(u => {
                    // Randomize status for visual flair since we don't have real presence
                    // In a real app, this would come from the websocket heartbeat
                    const statuses = ['online', 'idle', 'dnd'];
                    const status = u.status || statuses[Math.floor(Math.random() * statuses.length)];
                    const color = status === 'online' ? '#23A559' : (status === 'dnd' ? '#F23F42' : '#F0B232');

                    container.innerHTML += `
                     <div class="member-item">
                        <div class="member-avatar">
                           <img src="${u.avatar}" style="width:100%;height:100%;border-radius:50%;">
                           <div class="member-status" style="background:${color}"></div>
                        </div>
                        <div class="member-name">${u.username}</div>
                     </div>`;
                });
            }
        } catch (e) {
            container.innerHTML = '<div style="padding:20px;color:red;">Failed to load members</div>';
        }
    },

    // Settings (Real)
    openSettings: () => {
        document.getElementById('settings-modal').style.display = 'flex';
        document.getElementById('settings-modal').style.opacity = '1';
    },

    closeSettings: () => {
        const m = document.getElementById('settings-modal');
        m.style.opacity = '0';
        setTimeout(() => m.style.display = 'none', 200);
    },

    switchSettingsTab: (tab) => {
        document.querySelectorAll('.settings-item').forEach(el => el.classList.remove('active'));
        document.querySelectorAll('.settings-tab-view').forEach(el => el.style.display = 'none');
        document.getElementById(`settings-tab-${tab}`).style.display = 'block';

        const items = document.querySelectorAll('.settings-item');
        if (tab === 'account') items[0].classList.add('active');
        if (tab === 'profile') items[1].classList.add('active');
    },

    updateAvatar: async () => {
        const url = prompt("Enter new Avatar URL:");
        if (url) {
            try {
                const res = await fetch('/api/user/update', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ avatar: url })
                });
                const d = await res.json();
                if (d.success) {
                    document.getElementById('settings-avatar-img').src = url;
                    Utils.showToast('Avatar updated!');
                    location.reload(); // To update everywherre
                } else Utils.showToast('Failed to update');
            } catch (e) { console.error(e); }
        }
    },

    logout: () => window.location.href = '/logout'
};

const WebSocketModule = { init: () => { } };
