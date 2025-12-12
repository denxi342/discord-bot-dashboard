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
    // --- SERVER & DROPDOWN HEADER ---
    toggleServerDropdown: () => {
        const dd = document.getElementById('server-dropdown-menu');
        const iconOpen = document.getElementById('server-header-icon-open');
        const iconClose = document.getElementById('server-header-icon-close');

        if (dd.classList.contains('active')) {
            dd.classList.remove('active');
            iconOpen.style.display = 'block';
            iconClose.style.display = 'none';
        } else {
            dd.classList.add('active');
            iconOpen.style.display = 'none';
            iconClose.style.display = 'block';
        }
    },

    // Close dropdown on click outside
    initGlobalListeners: () => {
        document.addEventListener('click', (e) => {
            const dd = document.getElementById('server-dropdown-menu');
            const header = document.getElementById('server-header-click');
            if (dd && dd.classList.contains('active') && !dd.contains(e.target) && !header.contains(e.target)) {
                DiscordModule.toggleServerDropdown();
            }
        });
    },

    // --- SERVER SETTINGS UI ---
    currentServerSettingsTab: 'overview',

    openServerSettings: (tab = 'overview') => {
        // Hide dropdown
        document.getElementById('server-dropdown-menu').classList.remove('active');

        const modal = document.getElementById('server-settings-modal');
        modal.style.display = 'flex';
        DiscordModule.switchServerTab(tab);

        // Load roles if roles tab
        if (tab === 'roles') DiscordModule.loadRolesUI();
    },

    closeServerSettings: () => {
        document.getElementById('server-settings-modal').style.display = 'none';
    },

    switchServerTab: (tab) => {
        DiscordModule.currentServerSettingsTab = tab;

        // Tabs Styles
        document.querySelectorAll('.settings-sidebar .settings-item').forEach(el => el.classList.remove('active'));
        const activeTab = document.getElementById(`ss-tab-${tab}`);
        if (activeTab) activeTab.classList.add('active');

        // Views
        document.querySelectorAll('.server-tab-view').forEach(el => el.style.display = 'none');
        const view = document.getElementById(`ss-view-${tab}`);
        if (view) view.style.display = 'block';

        if (tab === 'roles') DiscordModule.loadRolesUI();
    },

    // --- ROLE MANAGER ---
    rolesCache: [],
    activeRole: null,

    loadRolesUI: () => {
        // Fetch roles from current server data (which is in DiscordModule.serverData)
        const s = DiscordModule.serverData[DiscordModule.currentServer];
        if (!s || !s.roles) return;

        DiscordModule.rolesCache = s.roles; // Sync
        const list = document.getElementById('roles-list-ui');
        list.innerHTML = '';

        s.roles.forEach((r, idx) => {
            const div = document.createElement('div');
            div.className = 'role-item';
            if (DiscordModule.activeRole && r.id === DiscordModule.activeRole.id) div.classList.add('active');
            div.innerHTML = `<div class="role-circle" style="background:${r.color}"></div> ${r.name}`;
            div.onclick = () => DiscordModule.selectRole(r);
            list.appendChild(div);
        });
    },

    selectRole: (role) => {
        DiscordModule.activeRole = role;
        DiscordModule.loadRolesUI(); // Refresh highlight

        document.getElementById('role-editor-ui').style.display = 'block';
        document.getElementById('edit-role-name').value = role.name;
        document.getElementById('edit-role-color').value = role.color;

        // Permissions checkboxes
        document.getElementById('perm-admin').checked = (role.permissions & 8) === 8;
        // ... other perms logic
    },

    previewRoleEdit: () => {
        // Live preview if we had a preview box
    },

    createRolePrompt: async () => {
        const sid = DiscordModule.currentServer;
        try {
            const res = await fetch(`/api/servers/${sid}/roles/create`, { method: 'POST' });
            const d = await res.json();
            if (d.success) {
                // Update local data
                DiscordModule.serverData[sid].roles.push(d.role);
                DiscordModule.loadRolesUI();
                DiscordModule.selectRole(d.role); // Auto-select new role
                Utils.showToast("Role created");
            } else {
                Utils.showToast(d.error || "Failed to create role");
            }
        } catch (e) { console.error(e); }
    },

    saveRoleChanges: async () => {
        if (!DiscordModule.activeRole) return;

        const sid = DiscordModule.currentServer;
        const rid = DiscordModule.activeRole.id;

        const name = document.getElementById('edit-role-name').value;
        const color = document.getElementById('edit-role-color').value;

        // Calc permissions bitmask
        let perms = 0;
        if (document.getElementById('perm-admin').checked) perms |= 8;
        // if(document.getElementById('perm-channels').checked) perms |= 16; # example bit

        try {
            const res = await fetch(`/api/servers/${sid}/roles/${rid}/update`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ name: name, color: color, permissions: perms })
            });
            const d = await res.json();
            if (d.success) {
                // Update local cache
                DiscordModule.activeRole.name = name;
                DiscordModule.activeRole.color = color;
                DiscordModule.activeRole.permissions = perms;

                DiscordModule.loadRolesUI(); // Refresh sidebar list
                Utils.showToast("Changes saved");
            } else {
                Utils.showToast(d.error || "Failed to save");
            }
        } catch (e) { console.error(e); }
    },

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
        const container = document.getElementById('channels-list');
        if (!container) return; // safety
        container.innerHTML = '';

        if (serverId === 'home') {
            DiscordModule.renderHomeSidebar(container);
            return;
        }

        const data = DiscordModule.serverData[serverId];
        if (!data) return;

        data.channels.forEach(ch => {
            if (ch.type === 'category') {
                const catId = ch.id;
                container.innerHTML += `
                 <div class="channel-category" onclick="this.nextElementSibling.classList.toggle('collapsed')">
                    <i class="fa-solid fa-angle-down"></i> <span>${ch.name}</span>
                    <i class="fa-solid fa-plus add-channel-btn" onclick="event.stopPropagation(); DiscordModule.createChannelPrompt('${serverId}', '${catId}')" title="Create Channel"></i>
                 </div>
                 <div class="category-content">`; // Added for collapsing categories
            } else {
                const icon = ch.type === 'voice' ? 'volume-high' : (ch.icon || 'hashtag');
                container.innerHTML += `
                <div class="channel-item" id="btn-ch-${ch.id}" onclick="DiscordModule.selectChannel('${ch.id}', '${ch.type}')">
                    <i class="fa-solid fa-${icon}"></i> ${ch.name}
                </div>`;
            }
        });

        // Always show Create Channel button at bottom
        container.innerHTML += `
        <div class="channel-item" onclick="DiscordModule.createChannelPrompt('${serverId}', null)" style="margin-top:10px; color:rgba(255,255,255,0.4); cursor:pointer; justify-content:center; border:1px dashed rgba(255,255,255,0.1);">
            <i class="fa-solid fa-plus"></i>
        </div>`;

        const first = data.channels.find(c => c.type === 'channel');
        if (first) DiscordModule.selectChannel(first.id, 'channel');
    },

    renderHomeSidebar: (container) => {
        // 1. Search Bar
        container.innerHTML += `
        <div style="padding: 10px 10px 0 10px;">
            <button class="search-bar-styled">
                Найти или начать беседу
            </button>
        </div>
        <div style="height: 1px; background: rgba(255,255,255,0.06); margin: 8px 10px;"></div>
        `;

        // 2. Navigation Items
        const navItems = [
            { id: 'friends', icon: 'user-group', label: 'Друзья', badge: null }
        ];

        navItems.forEach(item => {
            let badgeHtml = '';
            if (item.badge) {
                badgeHtml = `<div class="dm-badge ${item.badgeClass || ''}">${item.badge}</div>`;
            }
            container.innerHTML += `
            <div class="nav-item ${item.id === 'friends' ? 'active' : ''}" id="btn-ch-${item.id}" onclick="DiscordModule.selectChannel('${item.id}', 'channel')">
                <i class="fa-solid fa-${item.icon}"></i>
                <span>${item.label}</span>
                ${badgeHtml}
            </div>`;
        });

        // 3. Direct Messages Header
        container.innerHTML += `
        <div class="dm-header">
            <span>Личные сообщения</span>
            <i class="fa-solid fa-plus" style="cursor:pointer;" onclick="DiscordModule.openAddFriend()" title="Создать DM"></i>
        </div>`;

        // 4. User List (Empty for now, waiting for real logic)
        // Future: Fetch real DMs
        container.innerHTML += `
        <div style="padding: 20px; text-align: center; color: #949BA4; font-size: 13px;">
            Пока нет личных сообщений
        </div>`;
    },

    selectChannel: (chanId, type = 'channel') => {
        if (type === 'voice') {
            DiscordModule.connectVoice(chanId);
            return;
        }

        if (String(chanId).startsWith('dm-')) {
            const realId = chanId.split('-')[1];
            DiscordModule.loadDM(realId);
            return;
        }

        DiscordModule.currentChannel = chanId;

        document.querySelectorAll('.channel-item').forEach(el => el.classList.remove('active'));
        document.querySelectorAll('.nav-item').forEach(el => el.classList.remove('active')); // For friend btn

        const btn = document.getElementById(`btn-ch-${chanId}`);
        if (btn) {
            btn.classList.add('active');
            document.getElementById('current-channel-name').innerText = btn.innerText.trim();
        }

        if (chanId === 'friends') {
            DiscordModule.loadFriends();
            // Highlight sidebar item
            const fBtn = document.querySelector('.nav-item'); // Assuming first one is friends
            if (fBtn) fBtn.classList.add('active');
            return;
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
            if (viewKey === 'general') DiscordModule.loadChannelMessages(chanId);
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

    // --- CHANNEL & ROLE CREATION ---
    createChannelPrompt: async (sid, catId) => {
        const name = prompt("Enter Channel Name:");
        if (!name) return;

        let type = 'channel';
        if (confirm("Is this a Voice Channel? (OK=Voice, Cancel=Text)")) type = 'voice';

        try {
            const res = await fetch(`/api/servers/${sid}/channels/create`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ name: name, type: type, category_id: catId })
            });
            const d = await res.json();
            if (d.success) {
                DiscordModule.renderChannels(sid);
                Utils.showToast('Channel Created');
            } else {
                Utils.showToast(d.error || 'Failed');
            }
        } catch (e) { console.error(e); }
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

        // Check if virtual channel
        const virtuals = ['helper', 'news', 'community', 'admin', 'profile', 'biography', 'search-rules', 'ad-editor'];
        if (virtuals.includes(DiscordModule.currentChannel)) {
            DiscordModule.addMessage(DiscordModule.currentChannel, {
                author: 'You', avatar: 'https://cdn.discordapp.com/embed/avatars/1.png', text: text
            });
            if (DiscordModule.currentChannel === 'helper') await DiscordModule.askAI(text);
        } else {
            // Real Persistent Channel
            DiscordModule.sendMessage(DiscordModule.currentChannel, text);
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
    // Settings (Real)
    openSettings: async () => {
        const m = document.getElementById('settings-modal');
        m.style.display = 'flex';
        // Anim
        setTimeout(() => m.style.opacity = '1', 10);

        // Fetch fresh data
        try {
            const res = await fetch('/api/user/me');
            const data = await res.json();
            if (data.success) {
                const u = data.user;
                document.getElementById('setting-display-name').innerText = u.display_name || u.username;
                document.getElementById('setting-username').innerText = u.username;
                document.getElementById('settings-avatar-img').src = u.avatar;

                if (u.banner && u.banner.startsWith('http')) {
                    document.getElementById('settings-banner').style.backgroundImage = `url(${u.banner})`;
                    document.getElementById('settings-banner').style.backgroundSize = 'cover';
                } else if (u.banner) {
                    document.getElementById('settings-banner').style.backgroundColor = u.banner;
                }

                document.getElementById('field-display-name').innerText = u.display_name || "Not set";
                document.getElementById('field-username').innerText = u.username;
                document.getElementById('field-email').innerText = u.email || "********@gmail.com"; // privacy
                document.getElementById('field-phone').innerText = u.phone || "Not set";
            }
        } catch (e) { console.error(e); }
    },

    closeSettings: () => {
        const m = document.getElementById('settings-modal');
        m.style.opacity = '0';
        setTimeout(() => m.style.display = 'none', 200);
    },

    switchSettingsTab: (tab) => {
        // Simple tab switching for now
        document.querySelectorAll('.settings-tab-view').forEach(el => el.style.display = 'none');
        document.getElementById(`settings-tab-${tab}`).style.display = 'block';

        document.querySelectorAll('.settings-sidebar-nav .nav-item').forEach(el => el.classList.remove('active'));
        // Re-active logic is tricky without IDs on nav items, skipping visual highlight update for speed or adding IDs later.
        // But for "My Account" we can assume default is active.
    },

    // Unified Edit Function
    editField: async (field) => {
        // Debug
        // alert('Editing ' + field);
        let currentVal = document.getElementById(`field-${field}`) ? document.getElementById(`field-${field}`).innerText : '';
        if (currentVal === 'Not set') currentVal = '';

        const val = prompt(`Enter new ${field.replace('_', ' ')}:`, currentVal);
        if (val !== null) {
            DiscordModule.updateUser({ [field]: val });
        }
    },

    uiEditProfile: () => {
        // Shortcut to edit banner or avatar
        const choice = prompt("Type 'avatar' or 'banner' to edit:");
        if (choice === 'avatar') DiscordModule.updateAvatar();
        if (choice === 'banner') {
            const url = prompt("Enter Banner Image URL or Color Hex:");
            if (url) DiscordModule.updateUser({ banner: url });
        }
    },

    updateAvatar: async () => {
        const url = prompt("Enter new Avatar URL:");
        if (url) DiscordModule.updateUser({ avatar: url });
    },

    updateUser: async (payload) => {
        try {
            const res = await fetch('/api/user/update', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload)
            });
            const d = await res.json();
            if (d.success) {
                Utils.showToast('Saved changes!');
                // Refresh settings UI
                DiscordModule.openSettings();
            } else {
                Utils.showToast('Failed: ' + d.error);
            }
        } catch (e) { console.error(e); }
    },

    logout: () => window.location.href = '/logout',

    // --- FRIEND SYSTEM ---
    openAddFriend: () => {
        DiscordModule.selectChannel('friends', 'channel');
        DiscordModule.loadFriends('add'); // Direct load with 'add' tab
    },

    loadFriends: async (activeTab = 'all') => {
        const container = document.getElementById('channel-view-general'); // Reuse general/friends view
        container.innerHTML = `
        <div class="friends-header">
            <div class="fh-title"><i class="fa-solid fa-user-group"></i> Friends</div>
            <div class="fh-tabs">
                <div class="fh-tab active" onclick="DiscordModule.filterFriends('all')">All</div>
                <div class="fh-tab" onclick="DiscordModule.filterFriends('pending')">Pending</div>
                <div class="fh-tab add-friend" onclick="DiscordModule.filterFriends('add')">Add Friend</div>
            </div>
        </div>
        <div class="friends-list-container" id="friends-list-content">
            <div style="padding:20px; color:gray;">Loading friends...</div>
        </div>
        `;

        try {
            const res = await fetch('/api/friends');
            const data = await res.json();
            DiscordModule.friendsData = data; // Cache
            DiscordModule.filterFriends(activeTab);
        } catch (e) {
            console.error(e);
        }
    },

    filterFriends: (tab) => {
        const container = document.getElementById('friends-list-content');
        container.innerHTML = '';

        // Update tabs visual
        document.querySelectorAll('.fh-tab').forEach(e => e.classList.remove('active'));
        // Simple hack to find the clicked tab based on text, or just re-render logic. 
        // For speed, just rendering content:

        if (tab === 'add') {
            container.innerHTML = `
             <div class="add-friend-hero">
                <h3 class="hero-title">ADD FRIEND</h3>
                <div class="hero-subtitle">You can add friends with their Discord username. It's case sensitive!</div>
                
                <div class="add-friend-input-wrapper" style="position:relative;">
                    <div style="flex:1;">
                        <input type="text" id="add-friend-input" class="modern-input" placeholder="Enter a Username" autocomplete="off" onkeyup="if(event.key === 'Enter') DiscordModule.sendFriendRequest()">
                        <!-- Autocomplete result box could go here -->
                    </div>
                    <button class="btn-primary" onclick="DiscordModule.sendFriendRequest()">Send Friend Request</button>
                </div>

                <div class="hero-empty-state">
                    <img src="https://assets-global.website-files.com/6257adef93867e56f84d3092/636e0a6a49cf127bf92de1e2_icon_clyde_blurple_RGB.png" width="120" style="opacity:0.2; filter:grayscale(1);">
                    <p>Wumpus is waiting on friends. You don't have to though!</p>
                </div>
             </div>`;
            return;
        }

        const data = DiscordModule.friendsData;
        if (!data) return;

        let list = [];
        if (tab === 'all') list = data.friends;
        if (tab === 'pending') list = [...data.incoming, ...data.outgoing]; // Show both

        if (list.length === 0) {
            container.innerHTML = `<div class="empty-state">No friends to show here!</div>`;
            return;
        }

        list.forEach(u => {
            const isPending = data.incoming.includes(u) || data.outgoing.includes(u);
            const isIncoming = data.incoming.includes(u);

            let actions = '';
            if (isPending) {
                if (isIncoming) {
                    actions = `<i class="fa-solid fa-check" title="Accept" style="color:#23A559; cursor:pointer;" onclick="DiscordModule.acceptFriend(${u.id})"></i>`;
                } else {
                    actions = `<span style="font-size:12px; color:gray;">Outgoing Request</span>`;
                }
            } else {
                actions = `
                <div class="action-icon" onclick="DiscordModule.startDM(${u.id})"><i class="fa-solid fa-message"></i></div>
                <div class="action-icon" style="color:#F23F42"><i class="fa-solid fa-trash"></i></div>
                `;
            }

            container.innerHTML += `
            <div class="friend-row" style="display:flex; align-items:center; padding:10px 20px; border-top:1px solid rgba(255,255,255,0.06); hover:background:rgba(255,255,255,0.05);">
                <img src="${u.avatar}" style="width:32px; height:32px; border-radius:50%; margin-right:12px;">
                <div style="flex:1;">
                    <div style="color:white; font-weight:600;">${u.username}</div>
                    <div style="color:gray; font-size:12px;">${isPending ? 'Friend Request' : 'Online'}</div>
                </div>
                <div style="display:flex; gap:10px;">${actions}</div>
            </div>`;
        });
    },

    searchUsers: async (query) => {
        const box = document.getElementById('user-search-results');
        if (query.length < 2) {
            box.style.display = 'none';
            return;
        }

        try {
            const res = await fetch(`/api/users/search?q=${encodeURIComponent(query)}`);
            const data = await res.json();

            if (data.users && data.users.length > 0) {
                box.innerHTML = '';
                data.users.forEach(u => {
                    box.innerHTML += `
                    <div onclick="DiscordModule.selectSearchUser('${u.username}')" 
                         style="padding:10px; display:flex; align-items:center; cursor:pointer; border-bottom:1px solid rgba(255,255,255,0.05); hover:background:#3F4147;">
                        <img src="${u.avatar}" style="width:24px; height:24px; border-radius:50%; margin-right:10px;">
                        <span style="color:white; font-weight:500;">${u.username}</span>
                        <span style="color:#B9BBBE; font-size:12px; margin-left:auto;">#${u.id}</span>
                    </div>`;
                });
                box.style.display = 'block';
            } else {
                box.style.display = 'none';
            }
        } catch (e) { console.error(e); }
    },

    selectSearchUser: (username) => {
        document.getElementById('add-friend-input').value = username;
        document.getElementById('user-search-results').style.display = 'none';
    },

    sendFriendRequest: async () => {
        const username = document.getElementById('add-friend-input').value;
        if (!username) return;
        try {
            const res = await fetch('/api/friends/request', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ username: username })
            });
            const d = await res.json();
            if (d.success) {
                Utils.showToast("Request sent!");
                document.getElementById('add-friend-input').value = '';
                DiscordModule.loadFriends(); // Refresh
            } else {
                Utils.showToast(d.error || "Failed");
            }
        } catch (e) { console.error(e); }
    },

    acceptFriend: async (uid) => {
        try {
            await fetch('/api/friends/accept', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ user_id: uid })
            });
            DiscordModule.loadFriends();
            DiscordModule.refreshDMs(); // Refresh sidebar to maybe show new friend?
        } catch (e) { console.error(e); }
    },

    refreshDMs: async () => {
        // Fetch real DMs and update sidebar
        try {
            const res = await fetch('/api/dms');
            const data = await res.json();
            if (data.success) {
                const container = document.getElementById('channels-list');
                // We need to only update the DM section part, but currently renderHomeSidebar redraws everything.
                // Simpler: re-render sidebar but with fetched DM data inject.
                // NOTE: simpler hack -> Just find the .dm-user-item elements and replace them.
                // Or better: Store DM data in DiscordModule and re-call renderHomeSidebar.
                DiscordModule.dmList = data.dms;
                DiscordModule.renderHomeSidebar(container);
            }
        } catch (e) { console.error(e); }
    },

    startDM: async (uid) => {
        try {
            const res = await fetch('/api/dms/create', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ target_id: uid })
            });
            const d = await res.json();
            if (d.success) {
                // Open DM view
                DiscordModule.activeDM = d.dm_id;
                DiscordModule.selectChannel('dm-' + d.dm_id, 'dm');
                DiscordModule.refreshDMs();
            }
        } catch (e) { console.error(e); }
    },

    // Override generic selectChannel to handle 'dm' type
    // We'll modify selectChannel logic or handle it via ID 'dm-X'

    // --- REAL CHANNEL MESSAGING ---
    loadChannelMessages: async (cid) => {
        const main = document.getElementById('channel-view-general');
        const stream = main.querySelector('#stream-general');
        if (!stream) return;
        stream.innerHTML = '<div class="loading-state">Loading messages...</div>';

        try {
            const res = await fetch(`/api/channels/${cid}/messages`);
            const data = await res.json();
            stream.innerHTML = '';

            if (data.success && data.messages.length > 0) {
                data.messages.forEach(msg => {
                    // Reuse addMessage logic but adapt it
                    DiscordModule.addMessage(DiscordModule.currentChannel, {
                        author: msg.author,
                        avatar: msg.avatar,
                        text: msg.content,
                        timestamp: msg.timestamp
                    });
                });
            } else {
                stream.innerHTML = '<div class="empty-state">No messages here yet. Be the first!</div>';
            }
            stream.scrollTop = stream.scrollHeight;
        } catch (e) { console.error(e); }
    },

    sendMessage: async (cid, text) => {
        try {
            const res = await fetch(`/api/channels/${cid}/messages`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ content: text })
            });
            const d = await res.json();
            if (d.success) {
                // Optimistic update done by socket?? Or manual add?
                // Add message locally
                DiscordModule.addMessage(cid, {
                    author: d.message.author,
                    avatar: d.message.avatar,
                    text: d.message.content
                });
                const stream = document.querySelector('#stream-general');
                if (stream) stream.scrollTop = stream.scrollHeight;
            }
        } catch (e) { console.error(e); }
    },

    // --- FRIEND LOGIC ---
    sendFriendRequest: async () => {
        // Debugging
        console.log("Sending Friend Request...");

        const input = document.getElementById('add-friend-input');
        if (!input) {
            alert("Error: Input not found!");
            return;
        }
        const username = input.value.trim();
        if (!username) return;

        try {
            const res = await fetch('/api/friends/request', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ username: username })
            });
            const d = await res.json();
            if (d.success) {
                Utils.showToast(`Friend request sent to ${username}`);
                input.value = '';
                DiscordModule.filterFriends('pending'); // Switch view
            } else {
                Utils.showToast(d.error || 'Failed to send request');
            }
        } catch (e) { console.error(e); }
    },

    startDM: async (uid) => {
        // For now, simulate opening a DM by just loading the view
        console.log("Starting DM with", uid);
        // Deselect friend view
        DiscordModule.selectChannel(null, 'dm');

        // Find friend info to make a dummy DM object
        let user = null;
        if (DiscordModule.friendsData) {
            user = DiscordModule.friendsData.friends.find(u => u.id === uid);
        }

        // Render DM view
        const container = document.getElementById('channel-view-general');
        container.innerHTML = `
            <div class="chat-header">
                <i class="fa-solid fa-at"></i> 
                <span style="font-weight:700; margin-left:8px; color:white;">${user ? user.username : 'User'}</span>
            </div>
            <div class="chat-messages" id="dm-messages-${uid}">
                <div style="padding:20px; color:gray;">Start of your history with ${user ? user.username : 'this user'}.</div>
            </div>
            <div class="chat-input-area">
                <input type="text" placeholder="Message @${user ? user.username : 'User'}" 
                    style="width:100%; background:transparent; border:none; color:white; outline:none;"
                    onkeydown="if(event.key==='Enter') DiscordModule.sendDMMessage(${uid}, this)">
            </div>
        `;

        // Load messages
        DiscordModule.fetchDMMessages(uid);
    },

    acceptFriend: async (id) => {
        try {
            const res = await fetch('/api/friends/accept', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ id: id })
            });
            const d = await res.json();
            if (d.success) {
                Utils.showToast("Friend Request Accepted");
                DiscordModule.loadFriends(); // Refresh all
            }
        } catch (e) { console.error(e); }
    },

    loadDM: async (dmId) => {
        // Create view logic for DM... 
        // For now, let's reuse Chat Logic but point it to DM endpoint?
        // This requires refactoring loadChannel to support DMs or creating loadDMChat.
        // Let's create a stub for now that shows "Chat with X".
        const container = document.getElementById('channel-view-general');
        const activeDM = DiscordModule.dmList.find(d => d.id == dmId);
        const name = activeDM ? activeDM.user.username : 'Unknown';

        container.innerHTML = `
            <div class="chat-header">
                <i class="fa-solid fa-at"></i> <span style="font-weight:700; margin-left:8px;">${name}</span>
            </div>
            <div class="chat-messages" id="dm-messages-${dmId}">
                Fetching history...
            </div>
            <div class="chat-input-area">
                <input type="text" placeholder="Message @${name}" onkeydown="if(event.key==='Enter') DiscordModule.sendDMMessage(${dmId}, this)">
            </div>
         `;

        DiscordModule.fetchDMMessages(dmId);
    },

    fetchDMMessages: async (dmId) => {
        const res = await fetch(`/api/dms/${dmId}/messages`);
        const data = await res.json();
        const box = document.getElementById(`dm-messages-${dmId}`);
        box.innerHTML = '';
        data.messages.forEach(m => {
            box.innerHTML += `
            <div class="message">
                <img src="${m.avatar}" class="message-avatar">
                <div class="message-content">
                    <div class="message-header">
                        <span class="message-username">${m.username}</span>
                        <span class="message-time">${new Date(m.timestamp * 1000).toLocaleTimeString()}</span>
                    </div>
                    <div class="message-text">${Utils.escapeHtml(m.content)}</div>
                </div>
            </div>`;
        });
        box.scrollTop = box.scrollHeight;
    },

    sendDMMessage: async (dmId, input) => {
        const text = input.value.trim();
        if (!text) return;

        await fetch(`/api/dms/${dmId}/send`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ content: text })
        });
        input.value = '';
        DiscordModule.fetchDMMessages(dmId); // Simple refresh
    }

};

const WebSocketModule = { init: () => { } };


document.addEventListener('DOMContentLoaded', () => { DiscordModule.init(); WebSocketModule.init(); });

// Explicitly export for HTML inline handlers
window.DiscordModule = DiscordModule;
window.Utils = Utils;

