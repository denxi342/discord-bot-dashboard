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

const DEFAULT_AVATAR = "data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHZpZXdCb3g9IjAgMCAxMDAgMTAwIj48cmVjdCB3aWR0aD0iMTAwIiBoZWlnaHQ9IjEwMCIgZmlsbD0iIzU4NjVmMiIvPjwvc3ZnPg==";
window.DEFAULT_AVATAR = DEFAULT_AVATAR;

// Global avatar error handler - catches all broken avatar images
document.addEventListener('error', function (e) {
    if (e.target.tagName === 'IMG' && e.target.src.includes('/static/avatars/')) {
        e.target.onerror = null; // Prevent infinite loop
        e.target.src = DEFAULT_AVATAR;
    }
}, true);

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

    // openServerSettings is defined later in the file (line ~580) - removed duplicate

    closeServerSettings: () => {
        document.getElementById('server-settings-modal').style.display = 'none';
    },

    switchServerTab: (tab) => {
        console.log('=== switchServerTab called ===', tab);
        DiscordModule.currentServerSettingsTab = tab;

        // Tabs Styles
        document.querySelectorAll('.settings-sidebar .settings-item').forEach(el => el.classList.remove('active'));
        const activeTab = document.getElementById(`ss-tab-${tab}`);
        if (activeTab) activeTab.classList.add('active');

        // Views
        document.querySelectorAll('.server-tab-view').forEach(el => el.style.display = 'none');
        const view = document.getElementById(`ss-view-${tab}`);
        if (view) view.style.display = 'block';

        // Load data for the tab
        if (tab === 'roles') DiscordModule.loadRolesUI();
        if (tab === 'members') DiscordModule.loadServerMembers();
        if (tab === 'overview') DiscordModule.loadServerOverview();
        if (tab === 'invites') DiscordModule.loadServerInvites();
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
        // Fetch Me for context
        try {
            const res = await fetch('/api/user/me');
            const d = await res.json();
            if (d.success) DiscordModule.me = d.user;
        } catch (e) { }

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

                // Ensure 'home' exists for the Discord icon
                if (!DiscordModule.serverData['home']) {
                    DiscordModule.serverData['home'] = {
                        name: 'Home',
                        icon: 'discord',
                        is_image: false,
                        channels: []
                    };
                }

                DiscordModule.renderServerList();
                if (!DiscordModule.currentServer) {
                    const serverIds = Object.keys(data.servers);
                    if (serverIds.length > 0) {
                        // Select first non-home server
                        const firstServer = serverIds.find(id => id !== 'home');
                        if (firstServer) {
                            DiscordModule.selectServer(firstServer);
                        }
                    }
                }
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
            DiscordModule.loadSiteNews(); // Show site news in main area
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

        // Reset main content area (clear news/DM content)
        const mainView = document.getElementById('channel-view-general');
        if (mainView) {
            mainView.innerHTML = `
                <div class="message-stream" id="stream-general">
                    <div class="empty-state" style="padding:20px; color:var(--text-muted);">
                        Загрузка сообщений...
                    </div>
                </div>
            `;
        }

        const first = data.channels.find(c => c.type !== 'voice' && c.type !== 'category');
        if (first) {
            DiscordModule.selectChannel(first.id, first.type || 'channel');
        }
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

        // 4. User List (Real DMs)
        container.innerHTML += `<div id="home-dm-list" style="margin-top:20px;"></div>`;
        DiscordModule.loadDMList();
    },

    loadSiteNews: async () => {
        const container = document.getElementById('channel-view-general');
        if (!container) return;

        // Update header
        const channelName = document.getElementById('current-channel-name');
        if (channelName) channelName.textContent = 'Новости сайта';

        // Change icon to newspaper
        const headerIcon = document.querySelector('.chat-header > i');
        if (headerIcon) {
            headerIcon.className = 'fa-solid fa-newspaper';
        }

        // Hide toolbar for news
        const toolbar = document.querySelector('.header-toolbar');
        if (toolbar) toolbar.style.display = 'none';

        container.innerHTML = `
            <div class="site-news-container">
                <div class="news-loading">
                    <i class="fa-solid fa-spinner fa-spin"></i> Загрузка новостей...
                </div>
            </div>
        `;

        try {
            const res = await fetch('/api/site-news');
            const data = await res.json();

            if (data.news && data.news.length > 0) {
                let newsHtml = '<div class="site-news-list">';
                data.news.forEach(item => {
                    newsHtml += `
                        <div class="news-card">
                            <div class="news-card-header">
                                <i class="fa-solid fa-newspaper"></i>
                                <span class="news-date">${item.date || 'Недавно'}</span>
                            </div>
                            <h3 class="news-title">${Utils.escapeHtml(item.title)}</h3>
                            <p class="news-content">${Utils.escapeHtml(item.content)}</p>
                        </div>
                    `;
                });
                newsHtml += '</div>';
                container.innerHTML = newsHtml;
            } else {
                container.innerHTML = `
                    <div class="site-news-empty">
                        <i class="fa-solid fa-newspaper"></i>
                        <h2>Нет новостей</h2>
                        <p>Новости сайта появятся здесь</p>
                    </div>
                `;
            }
        } catch (e) {
            container.innerHTML = `
                <div class="site-news-empty">
                    <i class="fa-solid fa-exclamation-triangle"></i>
                    <h2>Ошибка загрузки</h2>
                    <p>Не удалось загрузить новости</p>
                </div>
            `;
        }
    },

    loadDMList: async () => {
        const container = document.getElementById('home-dm-list');
        if (!container) return;

        try {
            const res = await fetch('/api/dms');
            const data = await res.json();

            if (data.success && data.dms.length > 0) {
                DiscordModule.dmList = data.dms; // Store for later access
                container.innerHTML = '';
                data.dms.forEach(dm => {
                    const u = dm.other_user;
                    container.innerHTML += `
                    <div class="channel-item" id="btn-ch-dm-${dm.id}" onclick="DiscordModule.selectChannel('dm-${dm.id}', 'dm')">
                        <div class="member-avatar" style="width:32px; height:32px; margin-right:8px;">
                            <img src="${u.avatar}" style="width:100%; height:100%; border-radius:50%;">
                        </div>
                        <span style="color:#949BA4; font-weight:500;">${u.username}</span>
                    </div>`;
                });
            } else {
                container.innerHTML = `
                <div style="padding: 20px; text-align: center; color: #949BA4; font-size: 13px;">
                    Пока нет личных сообщений
                </div>`;
            }
        } catch (e) { console.error(e); }
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
        DiscordModule.activeDM = null; // Clear DM context when switching to normal channel

        // Show chat input when selecting a channel (hide only on friends)
        const chatInput = document.querySelector('.chat-input-area');
        if (chatInput && chanId !== 'friends') {
            chatInput.style.display = 'flex';
        }

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

            // --- Sidebar Visibility Logic ---
            const memberSidebar = document.getElementById('member-sidebar');
            const serverListContainer = document.getElementById('server-member-list-container');
            const dmProfileContainer = document.getElementById('dm-profile-container');

            // Always clear DM profile when switching to server channel
            if (dmProfileContainer) {
                dmProfileContainer.style.display = 'none';
                dmProfileContainer.innerHTML = '';
            }

            if (viewKey === 'general') {
                // Show Server Member List for chat channels
                if (memberSidebar) memberSidebar.style.display = 'flex';
                if (serverListContainer) serverListContainer.style.display = 'block';
                DiscordModule.loadChannelMessages(chanId);
            } else {
                // Hide Sidebar for non-chat views (AI, News, etc.)
                if (memberSidebar) memberSidebar.style.display = 'none';
            }

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

    createChannelPrompt: (sid, categoryId) => {
        DiscordModule.currentServerForChannel = sid;
        DiscordModule.currentCategoryForChannel = categoryId;

        // Reset form
        document.getElementById('new-channel-name').value = '';
        document.querySelector('input[name="channel-type"][value="channel"]').checked = true;

        // Show modal
        document.getElementById('create-channel-modal').style.display = 'flex';
    },

    closeChannelModal: () => {
        document.getElementById('create-channel-modal').style.display = 'none';
    },

    finishCreateChannel: () => {
        const name = document.getElementById('new-channel-name').value.trim();
        if (!name) {
            alert('Введите название канала');
            return;
        }

        const type = document.querySelector('input[name="channel-type"]:checked').value;
        const sid = DiscordModule.currentServerForChannel;
        const categoryId = DiscordModule.currentCategoryForChannel;

        DiscordModule.apiCreateChannel(sid, name, type, categoryId);
        DiscordModule.closeChannelModal();
    },

    uiCreateChannel: (sid) => {
        DiscordModule.createChannelPrompt(sid, null);
    },

    openServerSettings: (tab = 'overview') => {
        console.log('=== openServerSettings called ===', { tab, currentServer: DiscordModule.currentServer });

        // Close the dropdown menu first
        const dropdown = document.getElementById('server-dropdown-menu');
        if (dropdown) dropdown.classList.remove('active');

        // Reset dropdown icons
        const iconOpen = document.getElementById('server-header-icon-open');
        const iconClose = document.getElementById('server-header-icon-close');
        if (iconOpen) iconOpen.style.display = 'block';
        if (iconClose) iconClose.style.display = 'none';

        // Check if a server is selected
        if (!DiscordModule.currentServer) {
            alert('Сначала выберите сервер');
            console.warn('No server selected - currentServer is undefined');
            return;
        }

        // Use the correct modal ID
        const settingsModal = document.getElementById('server-settings-modal');

        if (!settingsModal) {
            alert('Модальное окно настроек не найдено!');
            console.warn('server-settings-modal element not found in DOM');
            return;
        }

        // Update server name in modal header
        const serverData = DiscordModule.serverData[DiscordModule.currentServer];
        if (serverData) {
            const headerEl = document.querySelector('.settings-header');
            if (headerEl) headerEl.textContent = serverData.name;
        }

        // Show the modal
        settingsModal.style.display = 'flex';

        // Switch to the selected tab
        DiscordModule.switchServerTab(tab);
    },

    // switchServerTab is defined earlier in the file (line ~60) - removed duplicate

    closeServerSettings: () => {
        const settingsModal = document.getElementById('server-settings-modal');
        if (settingsModal) settingsModal.style.display = 'none';
    },

    loadServerOverview: async () => {
        if (!DiscordModule.currentServer) return;
        const sid = DiscordModule.currentServer;
        const serverData = DiscordModule.serverData[sid];

        if (serverData) {
            document.getElementById('server-name-input').value = serverData.name || '';
            document.getElementById('server-desc-input').value = serverData.description || '';
            const iconPreview = document.getElementById('server-icon-preview');
            if (iconPreview) {
                if (serverData.icon && (serverData.icon.startsWith('http') || serverData.icon.startsWith('/') || serverData.icon.startsWith('data:'))) {
                    iconPreview.src = serverData.icon;
                } else {
                    // Use a Data URI placeholder to avoid external CDN blocking
                    iconPreview.src = 'data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHZpZXdCb3g9IjAgMCAxMDAgMTAwIj48cmVjdCB3aWR0aD0iMTAwIiBoZWlnaHQ9IjEwMCIgZmlsbD0iIzM2MzkzZiIvPjx0ZXh0IHg9IjUwIiB5PSI1MCIgZm9udC1mYW1pbHk9IkFyaWFsIiBmb250LXNpemU9IjUwIiBmaWxsPSIjZGNkZGNkIiB0ZXh0LWFuY2hvcj0ibWlkZGxlIiBkb21pbmFudC1iYXNlbGluZT0ibWlkZGxlIj4/PC90ZXh0Pjwvc3ZnPg==';
                }
            }
        }
    },

    saveServerOverview: async () => {
        if (!DiscordModule.currentServer) return;
        const sid = DiscordModule.currentServer;

        const name = document.getElementById('server-name-input').value.trim();
        const description = document.getElementById('server-desc-input').value.trim();

        if (!name) {
            alert('Введите название сервера');
            return;
        }

        try {
            const res = await fetch(`/api/servers/${sid}/update`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ name, description })
            });
            const data = await res.json();

            if (data.success) {
                DiscordModule.serverData[sid].name = name;
                DiscordModule.serverData[sid].description = description;
                DiscordModule.renderServerList();

                // Update server name in main header
                document.getElementById('current-server-name').textContent = name;

                // Update server name in modal header
                const modalHeader = document.querySelector('.settings-header');
                if (modalHeader) modalHeader.textContent = name;

                Utils.showToast('Настройки сохранены!');
            } else {
                alert(data.error || 'Ошибка сохранения');
            }
        } catch (e) {
            console.error(e);
            alert('Ошибка сохранения настроек');
        }
    },

    uploadServerIcon: () => {
        alert('Функция загрузки иконки находится в разработке.');
    },

    loadServerMembers: async () => {
        if (!DiscordModule.currentServer) return;
        const sid = DiscordModule.currentServer;

        try {
            const res = await fetch(`/api/servers/${sid}/members`);
            const data = await res.json();

            const container = document.getElementById('ss-members-list');
            if (!container) return;

            if (data.success && data.members) {
                container.innerHTML = data.members.map(member => `
                    <div class="member-item" style="display:flex; align-items:center; padding:10px; gap:12px; border-bottom:1px solid #2f3136;">
                        <img src="${member.avatar || DEFAULT_AVATAR}" style="width:40px; height:40px; border-radius:50%;">
                        <div style="flex:1;">
                            <div style="color:white; font-weight:500;">${member.username}</div>
                            <div style="color:#72767d; font-size:12px;">ID: ${member.id}</div>
                        </div>
                    </div>
                `).join('');
            } else {
                container.innerHTML = '<div style="padding:20px; color:#72767d; text-align:center;">Участники не найдены</div>';
            }
        } catch (e) {
            console.error(e);
        }
    },

    loadServerRoles: async () => {
        if (!DiscordModule.currentServer) return;
        const sid = DiscordModule.currentServer;

        try {
            const res = await fetch(`/api/servers/${sid}/roles`);
            const data = await res.json();

            const container = document.getElementById('roles-list-ui');
            if (!container) return;

            if (data.success && data.roles) {
                container.innerHTML = data.roles.map(role => `
                    <div class="role-item" onclick="DiscordModule.selectRole('${role.id}')" style="padding:8px 12px; cursor:pointer; color:${role.color || '#fff'};">
                        <i class="fa-solid fa-circle" style="font-size:10px; margin-right:8px;"></i>
                        ${role.name}
                    </div>
                `).join('');
            } else {
                container.innerHTML = '<div style="padding:20px; color:#72767d; text-align:center;">Роли не настроены</div>';
            }
        } catch (e) {
            console.error(e);
        }
    },

    loadServerInvites: async () => {
        if (!DiscordModule.currentServer) return;
        // TODO: Implement invites loading from backend
        console.log('Loading invites for server:', DiscordModule.currentServer);
    },

    uploadServerIcon: () => {
        alert('Загрузка иконки сервера будет реализована в следующем обновлении');
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

    apiCreateChannel: async (sid, name, type, categoryId) => {
        try {
            const payload = { name, type };
            if (categoryId) payload.category_id = categoryId;

            const res = await fetch(`/api/servers/${sid}/channels/create`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload)
            });
            const d = await res.json();
            if (d.success) {
                DiscordModule.serverData[sid].channels.push(d.channel);
                DiscordModule.renderChannels(sid);
            } else {
                alert(d.error || 'Failed to create channel');
            }
        } catch (e) {
            console.error(e);
            alert('Error creating channel');
        }
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
            <img src="${msgData.avatar || DEFAULT_AVATAR}" class="message-avatar">
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
        if (!input) {
            console.error('global-input element not found!');
            return;
        }

        const text = input.value.trim();
        console.log('[handleInput] text:', text, 'currentChannel:', DiscordModule.currentChannel, 'activeDM:', DiscordModule.activeDM);

        if (!text) return;
        input.value = '';

        // Check if virtual channel
        const virtuals = ['helper', 'news', 'community', 'admin', 'profile', 'biography', 'search-rules', 'ad-editor'];
        if (virtuals.includes(DiscordModule.currentChannel)) {
            DiscordModule.addMessage(DiscordModule.currentChannel, {
                author: 'You', avatar: DEFAULT_AVATAR, text: text
            });
            if (DiscordModule.currentChannel === 'helper') await DiscordModule.askAI(text);
        } else if (DiscordModule.activeDM) {
            // Direct Message
            console.log('[handleInput] Sending DM to:', DiscordModule.activeDM);
            DiscordModule.sendDMMessage(DiscordModule.activeDM, text);
        } else {
            // Real Persistent Channel
            console.log('[handleInput] Sending message to channel:', DiscordModule.currentChannel);
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
        // Create beautiful avatar edit modal with file upload
        const existingModal = document.getElementById('avatar-edit-modal');
        if (existingModal) existingModal.remove();

        const modal = document.createElement('div');
        modal.id = 'avatar-edit-modal';
        modal.className = 'avatar-edit-modal';
        modal.innerHTML = `
            <div class="avatar-modal-backdrop" onclick="DiscordModule.closeAvatarModal()"></div>
            <div class="avatar-modal-content">
                <div class="avatar-modal-bg-animation"></div>
                <div class="avatar-modal-inner">
                    <button class="avatar-modal-close" onclick="DiscordModule.closeAvatarModal()">
                        <i class="fa-solid fa-xmark"></i>
                    </button>
                    <h2>Изменить аватар</h2>
                    <p>Выберите изображение с вашего устройства</p>
                    
                    <div class="avatar-preview-container" onclick="document.getElementById('avatar-file-input').click()">
                        <img id="avatar-preview-img" src="${document.getElementById('settings-avatar-img')?.src || ''}" alt="Preview">
                        <div class="avatar-overlay">
                            <i class="fa-solid fa-camera"></i>
                            <span>Выбрать фото</span>
                        </div>
                    </div>
                    
                    <input type="file" id="avatar-file-input" accept="image/*" style="display:none" 
                           onchange="DiscordModule.handleAvatarFile(this)">
                    
                    <div class="avatar-input-group">
                        <button class="avatar-choose-btn" onclick="document.getElementById('avatar-file-input').click()">
                            <i class="fa-solid fa-folder-open"></i> Выбрать файл
                        </button>
                        <button class="avatar-save-btn" id="avatar-save-btn" onclick="DiscordModule.saveNewAvatar()" disabled>
                            <i class="fa-solid fa-check"></i> Сохранить
                        </button>
                    </div>
                </div>
            </div>
        `;
        document.body.appendChild(modal);
    },

    closeAvatarModal: () => {
        const modal = document.getElementById('avatar-edit-modal');
        if (modal) {
            modal.classList.add('closing');
            setTimeout(() => modal.remove(), 300);
        }
    },

    handleAvatarFile: (input) => {
        const file = input.files[0];
        if (file) {
            const reader = new FileReader();
            reader.onload = (e) => {
                const preview = document.getElementById('avatar-preview-img');
                if (preview) preview.src = e.target.result;
                // Store file for upload
                DiscordModule.pendingAvatarFile = file;
                // Enable save button
                document.getElementById('avatar-save-btn').disabled = false;
            };
            reader.readAsDataURL(file);
        }
    },

    pendingAvatarFile: null,

    saveNewAvatar: async () => {
        if (!DiscordModule.pendingAvatarFile) return;

        const formData = new FormData();
        formData.append('avatar', DiscordModule.pendingAvatarFile);

        try {
            const res = await fetch('/api/user/upload-avatar', {
                method: 'POST',
                body: formData
            });
            const data = await res.json();
            if (data.success) {
                Utils.showToast('Аватар обновлён!');
                // Update all avatar images on page
                document.querySelectorAll('[id*="avatar"]').forEach(img => {
                    if (img.tagName === 'IMG' && data.avatar_url) {
                        img.src = data.avatar_url;
                    }
                });
                DiscordModule.closeAvatarModal();
                DiscordModule.pendingAvatarFile = null;
            } else {
                Utils.showToast('Ошибка: ' + (data.error || 'Unknown'));
            }
        } catch (e) {
            Utils.showToast('Ошибка загрузки');
            console.error(e);
        }
    },

    updateAvatar: () => {
        // Redirect to new modal
        DiscordModule.uiEditProfile();
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
        const container = document.getElementById('channel-view-general');

        // Hide chat input on friends page
        const chatInput = document.querySelector('.chat-input-area');
        if (chatInput) chatInput.style.display = 'none';

        // Hide member sidebar on friends page
        const memberSidebar = document.getElementById('member-sidebar');
        if (memberSidebar) memberSidebar.style.display = 'none';

        container.innerHTML = `
        <div class="friends-page">
            <!-- Header Bar with Tabs -->
            <div class="friends-header-bar">
                <div class="fh-left">
                    <i class="fa-solid fa-user-group"></i>
                    <span class="fh-label">Друзья</span>
                    <div class="fh-divider"></div>
                    <div class="fh-tabs">
                        <div class="fh-tab ${activeTab === 'online' ? 'active' : ''}" onclick="DiscordModule.filterFriends('online')">В сети</div>
                        <div class="fh-tab ${activeTab === 'all' ? 'active' : ''}" onclick="DiscordModule.filterFriends('all')">Все</div>
                        <div class="fh-tab ${activeTab === 'pending' ? 'active' : ''}" onclick="DiscordModule.filterFriends('pending')">Ожидание</div>
                        <div class="fh-tab add-friend ${activeTab === 'add' ? 'active' : ''}" onclick="DiscordModule.filterFriends('add')">Добавить в друзья</div>
                    </div>
                </div>
            </div>
            
            <!-- Search Bar -->
            <div class="friends-search-bar">
                <i class="fa-solid fa-magnifying-glass"></i>
                <input type="text" id="friends-search-input" placeholder="Поиск" oninput="DiscordModule.searchFriendsList(this.value)">
            </div>
            
            <!-- Section Label -->
            <div class="friends-section-label" id="friends-section-label">В сети</div>
            
            <!-- Friends List -->
            <div class="friends-list" id="friends-list-content">
                <div style="padding:20px; color:var(--text-muted);">Загрузка...</div>
            </div>
        </div>
        `;

        try {
            const res = await fetch('/api/friends');
            const data = await res.json();
            DiscordModule.friendsData = data;
            DiscordModule.filterFriends(activeTab);
        } catch (e) {
            console.error(e);
        }
    },

    searchFriendsList: (query) => {
        // Filter displayed friends by search query
        const items = document.querySelectorAll('.friend-item');
        const lowerQuery = query.toLowerCase();
        items.forEach(item => {
            const name = item.dataset.username?.toLowerCase() || '';
            item.style.display = name.includes(lowerQuery) ? 'flex' : 'none';
        });
    },

    filterFriends: (tab) => {
        const container = document.getElementById('friends-list-content');
        const label = document.getElementById('friends-section-label');
        container.innerHTML = '';

        // Update tabs visual
        document.querySelectorAll('.fh-tab').forEach(e => e.classList.remove('active'));
        const tabs = document.querySelectorAll('.fh-tab');
        if (tab === 'online') tabs[0]?.classList.add('active');
        if (tab === 'all') tabs[1]?.classList.add('active');
        if (tab === 'pending') tabs[2]?.classList.add('active');
        if (tab === 'add') tabs[3]?.classList.add('active');

        if (tab === 'add') {
            if (label) label.style.display = 'none';
            container.innerHTML = `
             <div class="add-friend-section">
                <h3 class="add-friend-title">ДОБАВИТЬ В ДРУЗЬЯ</h3>
                <p class="add-friend-subtitle">Вы можете добавить друзей по имени пользователя.</p>
                
                <div class="add-friend-input-row">
                    <input type="text" id="add-friend-input" class="add-friend-input" placeholder="Введите имя пользователя" autocomplete="off" onkeyup="if(event.key === 'Enter') DiscordModule.sendFriendRequest()">
                    <button class="add-friend-btn" onclick="DiscordModule.sendFriendRequest()">Отправить запрос</button>
                </div>
             </div>`;
            return;
        }

        if (label) {
            label.style.display = 'block';
            if (tab === 'online') label.textContent = 'В сети';
            if (tab === 'all') label.textContent = 'Все друзья';
            if (tab === 'pending') label.textContent = 'Ожидающие';
        }

        const data = DiscordModule.friendsData;
        if (!data) return;

        let list = [];
        if (tab === 'online' || tab === 'all') list = data.friends || [];
        if (tab === 'pending') list = [...(data.incoming || []), ...(data.outgoing || [])];

        if (list.length === 0) {
            container.innerHTML = `<div class="friends-empty">Здесь пока никого нет</div>`;
            return;
        }

        list.forEach(u => {
            const isPending = (data.incoming || []).some(f => f.id === u.id) || (data.outgoing || []).some(f => f.id === u.id);
            const isIncoming = (data.incoming || []).some(f => f.id === u.id);

            let actions = '';
            if (isPending) {
                if (isIncoming) {
                    actions = `<div class="friend-action accept" onclick="DiscordModule.acceptFriend(${u.id})" title="Принять"><i class="fa-solid fa-check"></i></div>`;
                } else {
                    actions = `<span class="friend-status-text">Исходящий запрос</span>`;
                }
            } else {
                actions = `
                <div class="friend-action" onclick="DiscordModule.startDM(${u.id})" title="Сообщение"><i class="fa-solid fa-message"></i></div>
                <div class="friend-action danger" title="Удалить"><i class="fa-solid fa-trash"></i></div>
                `;
            }

            container.innerHTML += `
            <div class="friend-item" data-username="${u.username}">
                <img src="${u.avatar || DEFAULT_AVATAR}" class="friend-avatar">
                <div class="friend-info">
                    <div class="friend-name">${u.username}</div>
                    <div class="friend-status">${isPending ? 'Запрос в друзья' : 'В сети'}</div>
                </div>
                <div class="friend-actions">${actions}</div>
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

        // Show chat input for channel
        const chatInput = document.querySelector('.chat-input-area');
        if (chatInput) chatInput.style.display = 'flex';

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

    startDM: async (userId) => {
        try {
            // Get or Create DM via API
            const res = await fetch(`/api/dms/${userId}/messages`);
            const data = await res.json();
            if (data.success && data.dm_id) {
                // Refresh DM List to ensure it appears in sidebar
                await DiscordModule.loadDMList();
                // Load the DM view
                DiscordModule.loadDM(data.dm_id);
            } else {
                Utils.showToast('Failed to start DM');
            }
        } catch (e) {
            console.error("StartDM Error:", e);
            Utils.showToast('Error starting DM');
        }
    },

    loadDM: async (dmId) => {
        // Create view logic for DM... 
        const container = document.getElementById('channel-view-general');
        const activeDM = DiscordModule.dmList ? DiscordModule.dmList.find(d => d.id == dmId) : null;
        const otherUser = activeDM ? activeDM.other_user : null;
        const name = otherUser ? otherUser.username : 'Chat';
        const avatar = otherUser ? (otherUser.avatar || DEFAULT_AVATAR) : DEFAULT_AVATAR;

        // Show chat input for DM
        const chatInput = document.querySelector('.chat-input-area');
        if (chatInput) chatInput.style.display = 'flex';

        // Update main header for DM view
        const channelName = document.getElementById('current-channel-name');
        if (channelName) channelName.textContent = name;

        // Change # icon to @ for DM
        const headerIcon = document.querySelector('.chat-header > i.fa-hashtag');
        if (headerIcon) {
            headerIcon.classList.remove('fa-hashtag');
            headerIcon.classList.add('fa-at');
        }

        // Hide toolbar (call/search/members) for DM
        const toolbar = document.querySelector('.header-toolbar');
        if (toolbar) toolbar.style.display = 'none';

        container.innerHTML = `
            <div class="chat-messages dm-bubbles-container" id="dm-messages-${dmId}">
                Fetching history...
            </div>
         `;

        // Show user profile sidebar (Toggle containers)
        const memberSidebar = document.getElementById('member-sidebar');
        const serverListContainer = document.getElementById('server-member-list-container');
        const dmProfileContainer = document.getElementById('dm-profile-container');

        if (memberSidebar && otherUser && dmProfileContainer) {
            memberSidebar.style.display = 'flex'; // Ensure sidebar is visible

            // Hide server list, show DM profile
            if (serverListContainer) serverListContainer.style.display = 'none';
            dmProfileContainer.style.display = 'flex';
            dmProfileContainer.style.flexDirection = 'column';

            dmProfileContainer.innerHTML = `
                <div class="dm-profile-card">
                    <div class="dm-profile-banner"></div>
                    <div class="dm-profile-avatar-wrapper">
                        <img src="${avatar}" class="dm-profile-avatar" alt="${name}">
                        <div class="dm-profile-status online"></div>
                    </div>
                    <div class="dm-profile-info">
                        <div class="dm-profile-name">${name}</div>
                        <div class="dm-profile-tag">${otherUser.display_name || name}</div>
                    </div>
                    <div class="dm-profile-section">
                        <div class="dm-profile-section-title">В число участников с</div>
                        <div class="dm-profile-section-value">${otherUser.created_at ? new Date(otherUser.created_at * 1000).toLocaleDateString('ru-RU', { day: 'numeric', month: 'short', year: 'numeric' }) : 'Неизвестно'}</div>
                    </div>
                    <div class="dm-profile-note">
                        <textarea placeholder="Нажмите, чтобы добавить заметку"></textarea>
                    </div>
                </div>
            `;
        }

        // Update Global Input Placeholder
        const globalInput = document.getElementById('global-input');
        if (globalInput) globalInput.placeholder = `Message @${name}`;
        DiscordModule.activeDM = dmId;

        DiscordModule.fetchDMMessages(dmId);

        // Start polling fallback for real-time updates (every 3 seconds)
        if (DiscordModule.dmPollingInterval) {
            clearInterval(DiscordModule.dmPollingInterval);
        }
        DiscordModule.dmPollingInterval = setInterval(() => {
            if (DiscordModule.activeDM === dmId) {
                DiscordModule.fetchDMMessages(dmId);
            } else {
                clearInterval(DiscordModule.dmPollingInterval);
            }
        }, 3000);
    },

    fetchDMMessages: async (dmId) => {
        console.log(`[DM FETCH] Fetching messages for DM ${dmId}`);

        try {
            const res = await fetch(`/api/dms/by_id/${dmId}/messages`);
            const data = await res.json();

            console.log(`[DM FETCH] Response:`, data);
            console.log(`[DM FETCH] Messages count from server: ${data.messages ? data.messages.length : 'undefined'}`);

            const box = document.getElementById(`dm-messages-${dmId}`);
            if (!box) {
                console.log(`[DM FETCH] ERROR: Container dm-messages-${dmId} not found`);
                return;
            }

            // Check if we should skip update
            const newCount = data.messages ? data.messages.length : 0;
            const currentCount = box.querySelectorAll('.dm-bubble:not(.sending)').length;

            console.log(`[DM FETCH] newCount: ${newCount}, currentCount: ${currentCount}, forceRefresh: ${DiscordModule.forceRefresh}`);

            // Skip update if count is same (prevents jitter during polling)
            if (currentCount > 0 && newCount === currentCount && !DiscordModule.forceRefresh) {
                console.log(`[DM FETCH] Skipping update - counts match`);
                return;
            }
            DiscordModule.forceRefresh = false;

            console.log(`[DM FETCH] Rebuilding message list...`);
            box.innerHTML = '';
            box.classList.add('dm-bubbles-container');

            // Use global currentUsername set by Jinja template
            const myUsername = window.currentUsername || '';
            console.log(`[DM FETCH] My username: "${myUsername}"`);

            if (!data.messages || data.messages.length === 0) {
                console.log(`[DM FETCH] No messages to display`);
                box.innerHTML = '<div class="dm-empty">Начните беседу!</div>';
                return;
            }

            data.messages.forEach((m, index) => {
                const isOwn = m.username === myUsername;
                const isNew = index === data.messages.length - 1;
                box.innerHTML += `
                <div class="dm-bubble ${isOwn ? 'own' : 'other'} ${isNew ? 'new-message' : ''}">
                    ${!isOwn ? `<img src="${m.avatar}" onerror="this.onerror=null;this.src=window.DEFAULT_AVATAR" class="dm-bubble-avatar">` : ''}
                    <div class="dm-bubble-content">
                        <div class="dm-bubble-text">${Utils.escapeHtml(m.content)}</div>
                        <div class="dm-bubble-time">${new Date(m.timestamp * 1000).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}</div>
                    </div>
                    ${isOwn ? `<img src="${m.avatar}" onerror="this.onerror=null;this.src=window.DEFAULT_AVATAR" class="dm-bubble-avatar">` : ''}
                </div>`;
            });

            console.log(`[DM FETCH] Displayed ${data.messages.length} messages`);
            box.scrollTop = box.scrollHeight;
        } catch (e) {
            console.error(`[DM FETCH] Error:`, e);
        }
    },

    forceRefresh: false,

    sendDMMessage: async (dmId, text) => {
        if (!text) return;

        console.log(`[DM] Sending message to DM ${dmId}: "${text.substring(0, 50)}..."`);

        // Optimistic UI: add message immediately with sending state
        const box = document.getElementById(`dm-messages-${dmId}`);
        const tempId = 'sending-' + Date.now();
        if (box) {
            box.innerHTML += `
            <div class="dm-bubble own sending" id="${tempId}">
                <div class="dm-bubble-content">
                    <div class="dm-bubble-text">${Utils.escapeHtml(text)}</div>
                    <div class="dm-bubble-time"><i class="fa-solid fa-circle-notch fa-spin"></i></div>
                </div>
            </div>`;
            box.scrollTop = box.scrollHeight;
        }

        try {
            console.log(`[DM] Fetching /api/dms/by_id/${dmId}/send`);
            const res = await fetch(`/api/dms/by_id/${dmId}/send`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ content: text })
            });

            console.log(`[DM] Response status: ${res.status}`);

            const d = await res.json();
            console.log('[DM] Response data:', d);

            if (!res.ok) {
                console.error('[DM] Server error response:', res.status, d);
                throw new Error(d.error || `Server error ${res.status}`);
            }

            if (!d.success) {
                console.error('[DM] Failed response:', d);
                throw new Error(d.error || "Failed to send");
            }

            console.log('[DM] Message sent successfully');

            // Update the optimistic message to show success
            const tempEl = document.getElementById(tempId);
            if (tempEl) {
                tempEl.classList.remove('sending');
                const timeEl = tempEl.querySelector('.dm-bubble-time');
                if (timeEl) {
                    const now = new Date();
                    timeEl.innerHTML = now.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
                }
            }

            // Force refresh after send (to ensure sync)
            DiscordModule.forceRefresh = true;
            setTimeout(() => DiscordModule.fetchDMMessages(dmId), 500);

        } catch (e) {
            console.error("[DM] Send Error:", e);
            // Remove optimistic message on error
            const failEl = document.getElementById(tempId);
            if (failEl) failEl.remove();
            Utils.showToast("Failed to send message: " + e.message);
        }
    }

};

const WebSocketModule = {
    socket: null,
    init: () => {
        if (typeof io === 'undefined') return;
        // Force WebSocket transport to avoid 400 errors with Polling on Render/Cloud platforms
        WebSocketModule.socket = io({
            transports: ['websocket', 'polling']
        });

        const socket = WebSocketModule.socket;

        socket.on('connect', () => {
            console.log("Connected to Socket.IO");
        });

        // Channel Messages
        socket.on('new_channel_message', (data) => {
            if (DiscordModule.currentServer === data.sid && DiscordModule.currentChannel === data.cid) {
                DiscordModule.addMessage(data.cid, data.message);
                const stream = document.getElementById('stream-general'); // simplifiction for generic channel
                if (stream) stream.scrollTop = stream.scrollHeight;
            }
        });

        // DM Messages
        socket.on('new_dm_message', (data) => {
            // 1. Refresh DM Sidebar (to show new convos or reorder)
            if (DiscordModule.currentServer === 'home') {
                DiscordModule.loadDMList();
            }

            // 2. If we are currently viewing this DM, append message with bubble style
            if (DiscordModule.activeDM && String(DiscordModule.activeDM) === String(data.dm_id)) {
                const myUsername = window.currentUsername || '';
                const isOwn = data.author === myUsername;

                // Skip own messages (already added optimistically)
                if (isOwn) return;

                const box = document.getElementById(`dm-messages-${data.dm_id}`);
                if (box) {
                    box.innerHTML += `
                        <div class="dm-bubble other">
                            <img src="${data.avatar}" onerror="this.onerror=null;this.src=window.DEFAULT_AVATAR" class="dm-bubble-avatar">
                            <div class="dm-bubble-content">
                                <div class="dm-bubble-text">${Utils.escapeHtml(data.content)}</div>
                                <div class="dm-bubble-time">${new Date(data.timestamp * 1000).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}</div>
                            </div>
                        </div>`;
                    box.scrollTop = box.scrollHeight;
                }
            }
        });
    }
};


document.addEventListener('DOMContentLoaded', () => { DiscordModule.init(); WebSocketModule.init(); });

// Explicitly export for HTML inline handlers
window.DiscordModule = DiscordModule;
window.Utils = Utils;
window.DEFAULT_AVATAR = DEFAULT_AVATAR;

