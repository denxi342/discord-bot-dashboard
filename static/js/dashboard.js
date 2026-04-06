/**
 * Dashboard Pro - Messenger Edition
 * Pure Discord Logic + Dynamic Server Management
 */

// Main initialization is at the bottom of the file

const Utils = {
    showToast: (msg) => console.log('Toast:', msg),
    escapeHtml: (text) => text ? text.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;") : '',
    copyToClipboard: (text) => navigator.clipboard.writeText(text),

    formatMessageTime: (timestamp) => {
        if (!timestamp) return '';

        const date = new Date(timestamp * 1000);
        const now = new Date();
        const today = new Date(now.getFullYear(), now.getMonth(), now.getDate());
        const yesterday = new Date(today);
        yesterday.setDate(yesterday.getDate() - 1);
        const messageDate = new Date(date.getFullYear(), date.getMonth(), date.getDate());

        if (messageDate.getTime() === today.getTime()) {
            // Today - show time HH:MM
            const hours = String(date.getHours()).padStart(2, '0');
            const minutes = String(date.getMinutes()).padStart(2, '0');
            return `${hours}:${minutes}`;
        } else if (messageDate.getTime() === yesterday.getTime()) {
            // Yesterday
            return 'Вчера';
        } else {
            // Older - show DD.MM
            const day = String(date.getDate()).padStart(2, '0');
            const month = String(date.getMonth() + 1).padStart(2, '0');
            return `${day}.${month}`;
        }
    }
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
    typingTimeout: null,
    isTyping: false,
    recentOwnMessages: new Set(), // Set of "content" to prevent duplicates

    // Disappearing messages timer (seconds until message expires)
    disappearingTimer: null, // null = off, or number of seconds (30, 60, 300, 3600, 86400)

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
        // For messenger mode, load DMs instead of servers
        await DiscordModule.refreshDMs();
        await DiscordModule.loadUserStatuses();

        // Fetch Me for context
        try {
            const res = await fetch('/api/user/me');
            const d = await res.json();
            if (d.success) DiscordModule.me = d.user;
        } catch (e) { }

        // Load servers in background for backward compatibility
        await DiscordModule.loadServers();
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
        if (!list) {
            console.warn('[App] .server-list not found, skipping sidebar render.');
            return;
        }

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
        // Очистить контейнер
        container.innerHTML = '';

        // 1. Поиск (Messenger Style)
        container.innerHTML += `
        <div style="padding: 10px 10px 0 10px;">
            <button class="search-bar-styled">
                Найти или начать беседу
            </button>
        </div>
        <div style="height: 1px; background: rgba(255,255,255,0.06); margin: 8px 10px;"></div>
        `;

        // 2. Навигация (Messenger Style)
        const navItems = [
            { id: 'friends', icon: 'user-group', label: 'Друзья', badge: null },
            { id: 'cloud', icon: 'cloud', label: 'Моё Облако', badge: null }
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

        // 3. Личные сообщения Header
        container.innerHTML += `
        <div class="dm-header">
            <span>Личные сообщения</span>
            <i class="fa-solid fa-plus" style="cursor:pointer;" onclick="DiscordModule.openAddFriend()" title="Создать DM"></i>
        </div>`;

        // 4. Список чатов
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
                    const timeStr = Utils.formatMessageTime(dm.last_message_timestamp);
                    const preview = dm.last_message_text || 'Начните беседу';
                    const unreadBadge = dm.unread_count > 0 ? `<div class="unread-badge">${dm.unread_count}</div>` : '';

                    // Check if user is online
                    const isOnline = DiscordModule.userStatuses && DiscordModule.userStatuses[u.id] === 'online';
                    const onlineClass = isOnline ? 'is-online' : '';

                    container.innerHTML += `
                    <div class="chat-list-item" id="btn-ch-dm-${dm.id}" onclick="DiscordModule.selectChannel('dm-${dm.id}', 'dm')">
                        <div class="member-avatar ${onlineClass}">
                            <img src="${u.avatar}" class="chat-avatar" onerror="this.src=DEFAULT_AVATAR">
                            <div class="status-indicator"></div>
                        </div>
                        <div class="chat-info">
                            <div class="chat-info-header">
                                <span class="chat-name">${Utils.escapeHtml(u.display_name || u.username)}</span>
                                <span class="chat-time">${timeStr}</span>
                            </div>
                            <div class="chat-preview">${Utils.escapeHtml(preview)}</div>
                        </div>
                        ${unreadBadge}
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

            document.querySelectorAll('.channel-view').forEach(el => el.classList.remove('active'));
            const targetView = document.getElementById('channel-view-general');
            if (targetView) targetView.classList.add('active');

            // DiscordModule.loadDM(realId); // This will be handled after the common view logic below
        }

        DiscordModule.currentChannel = chanId;
        DiscordModule.activeDM = null; // Clear DM context when switching to normal channel

        // Hide welcome screen
        const welcomeView = document.getElementById('personal-welcome-view');
        if (welcomeView) welcomeView.classList.remove('active');

        // Define views that should NOT have a chat input field (read-only or pure UI)
        const noInputViews = ['friends', 'admin', 'admin_v2', 'settings', 'leaderboard', 'my-profile', 'discovery', 'nitro', 'shop'];
        
        const chatInput = document.querySelector('.chat-input-area');
        if (chatInput) {
            // Hide input for special UI-only views
            if (noInputViews.includes(chanId)) {
                chatInput.style.display = 'none';
                console.log(`[UI] Hiding chat input for view: ${chanId}`);
            } else {
                chatInput.style.display = 'flex';
                console.log(`[UI] Showing chat input for view: ${chanId}`);
            }
        }

        document.querySelectorAll('.channel-item').forEach(el => el.classList.remove('active'));
        document.querySelectorAll('.nav-item').forEach(el => el.classList.remove('active')); // For friend btn

        const btn = document.getElementById(`btn-ch-${chanId}`);
        if (btn) {
            btn.classList.add('active');
            document.getElementById('current-channel-name').innerText = btn.innerText.trim();
        }

        if (chanId.startsWith('dm-')) {
            const realId = chanId.split('-')[1];
            DiscordModule.loadDM(realId);
            // Ensure sidebar item gets active class correctly
            const dmBtn = document.getElementById(`btn-ch-${chanId}`);
            if (dmBtn) {
                document.querySelectorAll('.chat-list-item').forEach(el => el.classList.remove('active'));
                dmBtn.classList.add('active');
                
                // Get name safely from .chat-name child
                const nameEl = dmBtn.querySelector('.chat-name');
                const header = document.getElementById('current-channel-name');
                if (header && nameEl) header.innerText = nameEl.innerText.trim();
            }
            return; // 🚀 CRITICAL FIX: Stop execution for DMs to avoid fall-through UI reset
        }
        
        if (chanId === 'friends') {
            document.querySelectorAll('.channel-view').forEach(el => el.classList.remove('active'));
            const targetView = document.getElementById('channel-view-general');
            if (targetView) targetView.classList.add('active');
            
            DiscordModule.loadFriends();
            // Highlight sidebar item
            const fBtn = document.getElementById('btn-ch-friends');
            if (fBtn) fBtn.classList.add('active');
            
            // Hide cloud sidebar
            document.getElementById('cloud-folders-sidebar').style.display = 'none';
            document.getElementById('channels-list').style.display = 'block';
            return;
        }

        if (chanId === 'cloud') {
            CloudModule.openCloud();
            return;
        }

        const mappedViews = {
            'news': 'news', 'leaderboard': 'community', 'video-feed': 'general',
            'chat-gpt': 'helper', 'search-rules': 'search', 'ad-editor': 'smi', 'users': 'admin', 'my-profile': 'profile',
            'admin': 'admin'
        };

        let viewKey = 'general';
        const chNameData = DiscordModule.serverData[DiscordModule.currentServer].channels.find(c => c.id === chanId);
        // Hide all views
        document.querySelectorAll('.channel-view, .main-view-section, .personal-welcome-view').forEach(v => v.style.display = 'none');
        
        // Persistent UI elements to hide in Admin Dashboard
        const toolbar = document.querySelector('.header-toolbar');
        const memberSidebar = document.getElementById('member-sidebar');
        
        if (chanId === 'admin_v2') {
            const adminView = document.getElementById('admin-v2-view');
            const app = document.querySelector('.discord-app');
            if (app) app.classList.add('admin-mode-layout');
            
            if (adminView) {
                adminView.style.display = 'block';
                StaffDashboard.init();
            }
            if (toolbar) toolbar.style.display = 'none';
            if (chatInput) chatInput.style.display = 'none';
            if (memberSidebar) memberSidebar.style.display = 'none';

            // Update active state in sidebar
            document.querySelectorAll('.nav-item').forEach(n => n.classList.remove('active'));
            document.getElementById('node-admin-v2')?.classList.add('active');
            return;
        } else {
            // Restore for normal channels
            const app = document.querySelector('.discord-app');
            if (app) app.classList.remove('admin-mode-layout');
            
            if (toolbar) toolbar.style.display = 'flex';
            if (chatInput) chatInput.style.display = 'flex';
            if (memberSidebar) memberSidebar.style.display = 'flex';
        }
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

                Utils.showToast('РќР°СЃС‚СЂРѕР№Рєи СЃРѕС…СЂР°РЅРµРЅС‹!');
            } else {
                alert(data.error || 'Ошибка сохранения');
            }
        } catch (e) {
            console.error(e);
            alert('Ошибка сохранения настроек');
        }
    },

    uploadServerIcon: () => {
        alert('Р¤СѓРЅРєС†иСЏ Р·Р°РіСЂСѓР·Рєи иРєРѕРЅРєи РЅР°С…РѕРґиС‚СЃСЏ РІ СЂР°Р·СЂР°Р±РѕС‚РєРµ.');
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
                container.innerHTML = '<div style="padding:20px; color:#72767d; text-align:center;">РЈС‡Р°СЃС‚РЅиРєи РЅРµ РЅР°Р№РґРµРЅС‹</div>';
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
                container.innerHTML = '<div style="padding:20px; color:#72767d; text-align:center;">Р РѕР»и РЅРµ РЅР°СЃС‚СЂРѕРµРЅС‹</div>';
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
        alert('Р—Р°РіСЂСѓР·РєР° иРєРѕРЅРєи СЃРµСЂРІРµСЂР° Р±СѓРґРµС‚ СЂРµР°Р»иР·РѕРІР°РЅР° РІ СЃР»РµРґСѓСЋС‰РµРј РѕР±РЅРѕРІР»РµРЅии');
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

        // Determine if message is sent by current user
        const isSent = msgData.author === 'You' || msgData.author === window.currentUsername;
        let messageClass = isSent ? 'sent' : 'received';
        if (msgData.sending) messageClass += ' sending';

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

        // Handle voice message attachments
        let voiceHtml = '';
        if (msgData.attachments && msgData.attachments.length > 0) {
            msgData.attachments.forEach(attachment => {
                if (attachment.type === 'voice' && typeof VoiceRecorder !== 'undefined') {
                    voiceHtml += VoiceRecorder.renderVoiceMessage({
                        audio_url: attachment.url,
                        duration: attachment.duration || 0,
                        timestamp: msgData.timestamp || Date.now(),
                        author: msgData.author,
                        isOwn: isSent
                    });
                }
            });
        }

        const html = `
        <div class="message-group ${messageClass}" 
             ${msgData.tempId ? `id="${msgData.tempId}"` : ''} 
             ${msgData.id ? `data-message-id="${msgData.id}"` : ''}
             oncontextmenu="${msgData.id ? `DiscordModule.showMessageMenu(event, ${msgData.id}, ${isSent});` : ''} return false;">
            ${!isSent ? `<img src="${msgData.avatar || DEFAULT_AVATAR}" class="message-avatar">` : ''}
            <div class="message-content">
                ${!isSent ? `<span class="msg-author">${msgData.author}</span>` : ''}
                <div class="message-bubble">
                    ${msgData.text ? `<div class="message-text">${Utils.escapeHtml(msgData.text)}</div>` : ''}
                    ${embedHtml}
                    ${voiceHtml}
                    ${msgData.sending ? '<div class="msg-status"><i class="fa-solid fa-circle-notch fa-spin"></i></div>' : ''}
                </div>
                <span class="msg-timestamp">${time}</span>
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

        // Upload files first if any
        const attachments = await DiscordModule.uploadFiles();

        // Require either text or attachments  
        if (!text && attachments.length === 0) return;
        input.value = '';
        input.style.height = '36px'; // Reset height (Beautiful UX)

        // Check if virtual channel
        const virtuals = ['helper', 'news', 'community', 'admin', 'profile', 'biography', 'search-rules', 'ad-editor'];
        if (virtuals.includes(DiscordModule.currentChannel)) {
            DiscordModule.addMessage(DiscordModule.currentChannel, {
                author: 'You', avatar: DEFAULT_AVATAR, text: text, attachments: attachments
            });
            if (DiscordModule.currentChannel === 'helper') await DiscordModule.askAI(text);
        } else if (DiscordModule.activeDM) {
            // Direct Message
            console.log('[handleInput] Sending DM to:', DiscordModule.activeDM);
            DiscordModule.sendDMMessage(DiscordModule.activeDM, text, attachments);
        } else {
            // Real Persistent Channel
            console.log('[handleInput] Sending message to channel:', DiscordModule.currentChannel);
            DiscordModule.sendMessage(DiscordModule.currentChannel, text, attachments);
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
            DiscordModule.addMessage('helper', { author: 'Octave', bot: true, text: data.response });
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

    // Storage for user statuses
    userStatuses: {},

    // Preload all user statuses
    loadUserStatuses: async () => {
        try {
            const res = await fetch('/api/admin/users');
            const data = await res.json();
            if (data.success && data.users) {
                data.users.forEach(u => {
                    DiscordModule.userStatuses[u.id] = u.status;
                });
                console.log('[Status] Loaded statuses for', data.users.length, 'users');
            }
        } catch (e) {
            console.error('[Status] Failed to load:', e);
        }
    },

    renderMembers: async () => {
        const container = document.getElementById('member-list-content');
        if (!container) return;

        container.innerHTML = '<div style="padding:20px;color:gray;text-align:center">Loading...</div>';

        try {
            // Using existing admin API which returns all users with real status
            const res = await fetch('/api/admin/users');
            const data = await res.json();

            if (data.success && data.users) {
                container.innerHTML = '';

                // Group by online/offline status
                const onlineUsers = data.users.filter(u => u.status === 'online');
                const offlineUsers = data.users.filter(u => u.status !== 'online');

                // Store statuses in memory for real-time updates
                data.users.forEach(u => {
                    DiscordModule.userStatuses[u.id] = u.status;
                });

                // Render online users first
                if (onlineUsers.length > 0) {
                    container.innerHTML += `
                        <div class="member-group">
                            <div class="group-name">Р’ РЎР•РўР˜ вЂ” ${onlineUsers.length}</div>
                        </div>`;

                    onlineUsers.forEach(u => {
                        container.innerHTML += `
                         <div class="member-item" data-user-id="${u.id}">
                            <div class="member-avatar">
                               <img src="${u.avatar}" style="width:100%;height:100%;border-radius:50%;">
                               <div class="member-status" style="background:#23A559"></div>
                            </div>
                            <div class="member-name">${u.username}</div>
                         </div>`;
                    });
                }

                // Render offline users
                if (offlineUsers.length > 0) {
                    container.innerHTML += `
                        <div class="member-group">
                            <div class="group-name">РќР• Р’ РЎР•РўР˜ вЂ” ${offlineUsers.length}</div>
                        </div>`;

                    offlineUsers.forEach(u => {
                        container.innerHTML += `
                         <div class="member-item" data-user-id="${u.id}">
                            <div class="member-avatar">
                               <img src="${u.avatar}" style="width:100%;height:100%;border-radius:50%;">
                               <div class="member-status" style="background:#80848E"></div>
                            </div>
                            <div class="member-name" style="opacity:0.5">${u.username}</div>
                         </div>`;
                    });
                }
            }
        } catch (e) {
            container.innerHTML = '<div style="padding:20px;color:red;">Failed to load members</div>';
        }
    },

    // Real-time status update for member list
    updateMemberStatus: (userId, status) => {
        const memberItem = document.querySelector(`.member-item[data-user-id="${userId}"]`);
        if (memberItem) {
            const statusDot = memberItem.querySelector('.member-status');
            const nameEl = memberItem.querySelector('.member-name');
            if (statusDot) {
                statusDot.style.background = status === 'online' ? '#23A559' : '#80848E';
            }
            if (nameEl) {
                nameEl.style.opacity = status === 'online' ? '1' : '0.5';
            }
        }
        // Also refresh the entire list if visible to update counts
        const container = document.getElementById('member-list-content');
        if (container && container.innerHTML !== '') {
            // Debounce to prevent too many calls
            if (DiscordModule.memberRefreshTimeout) clearTimeout(DiscordModule.memberRefreshTimeout);
            DiscordModule.memberRefreshTimeout = setTimeout(() => {
                DiscordModule.renderMembers();
            }, 1000);
        }
    },

    // Real-time status update for friend list
    updateFriendStatus: (userId, status) => {
        const friendItem = document.querySelector(`.friend-item[data-user-id="${userId}"]`);
        if (friendItem) {
            const statusText = friendItem.querySelector('.friend-status');
            if (statusText) {
                statusText.textContent = status === 'online' ? 'В сети' : 'РќРµ РІ СЃРµС‚и';
            }
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
                document.getElementById('field-custom-status').innerText = u.custom_status || "Not set";
            }
        } catch (e) { console.error(e); }
    },

    editField: (fieldName) => {
        const fieldLabels = {
            'display_name': 'DISPLAY NAME',
            'username': 'USERNAME',
            'email': 'EMAIL',
            'phone': 'PHONE NUMBER',
            'custom_status': 'CUSTOM STATUS'
        };

        const currentValue = document.getElementById(`field-${fieldName.replace('_', '-')}`).innerText;
        const actualValue = currentValue === 'Not set' ? '' : currentValue;

        const placeholder = fieldName === 'custom_status' ? '🎮 Playing games' : '';
        const newValue = prompt(`Введите ${fieldLabels[fieldName]}:`, actualValue);

        if (newValue !== null) {
            DiscordModule.updateUserField(fieldName, newValue.trim());
        }
    },

    updateUserField: async (fieldName, value) => {
        try {
            const res = await fetch('/api/user/update', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ [fieldName]: value })
            });

            const data = await res.json();
            if (data.success) {
                Utils.showToast('✅ Обновлено!');
                // Refresh settings
                DiscordModule.openSettings();
            } else {
                Utils.showToast('❌ Ошибка: ' + (data.error || 'Unknown'));
            }
        } catch (e) {
            console.error('Update field error:', e);
            Utils.showToast('❌ Ошибка обновления');
        }
    },


    uiEditProfile: () => {
        const modal = document.createElement('div');
        modal.className = 'modal-backdrop';
        modal.style.display = 'flex';
        modal.innerHTML = `
            <div class="discord-modal" style="max-width: 500px;">
                <button class="close-modal" onclick="this.closest('.modal-backdrop').remove()">
                    <i class="fa-solid fa-xmark"></i>
                </button>
                <h2 style="margin-bottom: 20px;">Редактировать профиль</h2>
                
                <div class="input-group" style="margin-bottom: 16px;">
                    <label>CUSTOM STATUS</label>
                    <input id="edit-custom-status" type="text" placeholder="🎮 Playing games" maxlength="128">
                    <div style="font-size: 12px; color: var(--text-muted); margin-top: 4px;">
                        Р”РѕР±Р°РІСЊС‚Рµ СЌРјРѕРґР·и в начале для красоты!
                    </div>
                </div>
                
                <div style="display: flex; justify-content: flex-end; gap: 10px; margin-top: 20px;">
                    <button class="footer-btn secondary" onclick="this.closest('.modal-backdrop').remove()">
                        Отмена
                    </button>
                    <button class="footer-btn primary" onclick="DiscordModule.saveProfileChanges()">
                        Сохранить
                    </button>
                </div>
            </div>
        `;
        document.body.appendChild(modal);

        // Load current status
        fetch('/api/user/me')
            .then(res => res.json())
            .then(data => {
                if (data.success && data.user.custom_status) {
                    document.getElementById('edit-custom-status').value = data.user.custom_status;
                }
            });
    },

    saveProfileChanges: async () => {
        const customStatus = document.getElementById('edit-custom-status').value.trim();

        try {
            const res = await fetch('/api/user/update', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ custom_status: customStatus })
            });

            const data = await res.json();
            if (data.success) {
                Utils.showToast('✅ Профиль обновлён!');
                document.querySelector('.modal-backdrop')?.remove();
                // Refresh settings if open
                if (document.getElementById('settings-modal').style.display === 'flex') {
                    DiscordModule.openSettings();
                }
            } else {
                Utils.showToast('❌ Ошибка: ' + (data.error || 'Unknown'));
            }
        } catch (e) {
            console.error('Save profile error:', e);
            Utils.showToast('❌ Ошибка сохранения');
        }
    },


    closeSettings: () => {
        const m = document.getElementById('settings-modal');
        m.style.opacity = '0';
        setTimeout(() => m.style.display = 'none', 200);
    },

    switchSettingsTab: (tab) => {
        const tabEl = document.getElementById(`settings-tab-${tab}`);
        if (!tabEl) return;
        
        document.querySelectorAll('.settings-tab-view').forEach(el => el.style.display = 'none');
        tabEl.style.display = 'block';

        if (tab === 'admin-reports') {
            DiscordModule.loadAdminReports();
        }
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
        // Open the avatar capture/upload modal
        const modal = document.createElement('div');
        modal.className = 'modal-overlay active';
        modal.id = 'avatar-modal';
        modal.innerHTML = `
            <div class="modal-content profile-edit-modal">
                <div class="modal-header">
                    <h2>Изменить профиль</h2>
                    <button class="close-btn" onclick="DiscordModule.closeAvatarModal()"><i class="fa-solid fa-xmark"></i></button>
                </div>
                <div class="profile-edit-body">
                    <div class="avatar-edit-section">
                        <div class="avatar-preview-big">
                            <img src="${sessionStorage.getItem('user_avatar') || DEFAULT_AVATAR}" id="avatar-preview-img">
                        </div>
                        <input type="file" id="avatar-upload-input" hidden accept="image/*" onchange="DiscordModule.handleAvatarFile(this)">
                        <button class="welcome-btn primary" onclick="document.getElementById('avatar-upload-input').click()">
                            <i class="fa-solid fa-upload"></i> Выбрать файл
                        </button>
                    </div>
                </div>
                <div class="modal-footer">
                    <button class="welcome-btn secondary" onclick="DiscordModule.closeAvatarModal()">Отмена</button>
                    <button class="welcome-btn primary" id="avatar-save-btn" disabled onclick="DiscordModule.saveNewAvatar()">Сохранить</button>
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
            Utils.showToast('РћС€иР±РєР° Р·Р°РіСЂСѓР·Рєи');
            console.error(e);
        }
    },

    updateAvatar: () => {
        // 🛠️ Staff Only Visibility
        if (['admin', 'moderator', 'support', 'developer'].includes(window.currentUserRole)) {
            document.querySelectorAll('.staff-only').forEach(el => el.style.display = 'flex');
        }
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
            <!-- Simplified Compact Header (Tabs Only) -->
            <div class="friends-header-bar">
                <div class="fh-tabs">
                    <div class="fh-tab ${activeTab === 'online' ? 'active' : ''}" onclick="DiscordModule.filterFriends('online')">В сети</div>
                    <div class="fh-tab ${activeTab === 'all' ? 'active' : ''}" onclick="DiscordModule.filterFriends('all')">Все</div>
                    <div class="fh-tab ${activeTab === 'pending' ? 'active' : ''}" onclick="DiscordModule.filterFriends('pending')">Ожидание</div>
                    <div class="fh-tab add-friend ${activeTab === 'add' ? 'active' : ''}" onclick="DiscordModule.filterFriends('add')">Добавить</div>
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
        if (!container) return;
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
                <div id="user-search-results" class="search-results-popout" style="display:none; margin-top:10px; background: rgba(0,0,0,0.2); border-radius:8px;"></div>
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
        if (tab === 'online' || tab === 'all') {
            list = data.friends || [];
            if (tab === 'online') list = list.filter(u => DiscordModule.userStatuses[u.id] === 'online');
        }
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
                <div class="friend-action danger" onclick="DiscordModule.removeFriend(${u.id})" title="Удалить"><i class="fa-solid fa-trash"></i></div>
                `;
            }

            const isOnline = DiscordModule.userStatuses[u.id] === 'online';
            const statusColor = isOnline ? '#23A559' : '#80848E';

            container.innerHTML += `
            <div class="friend-item" data-username="${u.username}" data-user-id="${u.id}">
                <div class="friend-avatar-wrapper">
                    <img src="${u.avatar || DEFAULT_AVATAR}" class="friend-avatar">
                    <div class="friend-status-dot" style="background:${statusColor}"></div>
                </div>
                <div class="friend-info">
                    <div class="friend-name">${u.username}</div>
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

    // --- DM Logic moves to consolidated startDM below ---

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
                        id: msg.id,
                        author: msg.author,
                        avatar: msg.avatar,
                        text: msg.content,
                        timestamp: msg.timestamp,
                        is_pinned: msg.is_pinned
                    });
                });
            } else {
                stream.innerHTML = '<div class="empty-state">No messages here yet. Be the first!</div>';
            }
            stream.scrollTop = stream.scrollHeight;
        } catch (e) { console.error(e); }
    },

    sendMessage: async (cid, text) => {
        const tempId = 'msg-sending-' + Date.now();

        // Optimistic UI
        DiscordModule.addMessage(cid, {
            author: window.currentUsername || 'You',
            avatar: DiscordModule.me ? DiscordModule.me.avatar : DEFAULT_AVATAR,
            text: text,
            tempId: tempId,
            sending: true
        });

        const stream = document.querySelector('#stream-general');
        if (stream) stream.scrollTop = stream.scrollHeight;

        try {
            const res = await fetch(`/api/channels/${cid}/messages`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ content: text })
            });
            const d = await res.json();

            // Add to recent cache to prevent socket double-add
            if (d.success) {
                const cacheKey = `${text.trim()}`;
                DiscordModule.recentOwnMessages.add(cacheKey);
                setTimeout(() => DiscordModule.recentOwnMessages.delete(cacheKey), 5000);
            }

            // Remove sent indicator once confirmed (relying on Socket.IO for the final message usually, 
            // but we can remove the 'sending' class here)
            const sendingEl = document.getElementById(tempId);
            if (sendingEl) {
                sendingEl.classList.remove('sending');
                const timeEl = sendingEl.querySelector('.msg-timestamp');
                if (timeEl) timeEl.innerHTML = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
            }

            if (!d.success) {
                console.error('Failed to send message:', d.error);
                if (sendingEl) sendingEl.style.opacity = '0.5';
            }
        } catch (e) {
            console.error(e);
            const sendingEl = document.getElementById(tempId);
            if (sendingEl) sendingEl.style.opacity = '0.5';
        }
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
                // Load and SWITCH to the DM view
                DiscordModule.selectChannel('dm-' + data.dm_id, 'dm');
            } else {
                Utils.showToast('Failed to start DM');
            }
        } catch (e) {
            console.error("StartDM Error:", e);
            Utils.showToast('Error starting DM');
        }
    },

    loadDM: async (dmId) => {
        DiscordModule.activeDM = dmId; // Set immediately to prevent race conditions
        // Create view logic for DM... 
        const container = document.getElementById('channel-view-general');
        const activeDM = DiscordModule.dmList ? DiscordModule.dmList.find(d => d.id == dmId) : null;
        const otherUser = activeDM ? activeDM.other_user : null;
        let name = otherUser ? (otherUser.display_name || otherUser.username) : 'Chat';
        const avatar = otherUser ? (otherUser.avatar || DEFAULT_AVATAR) : DEFAULT_AVATAR;

        // Show chat input for DM (except system team with ID 0)
        const chatInput = document.querySelector('.chat-input-area');
        if (chatInput) {
            // dmId 0 is "Команда Octave", which is read-only announcement channel
            if (String(dmId) === '0') {
                chatInput.style.display = 'none';
                console.log('[UI] Read-only channel (ID 0). Hiding input.');
            } else {
                chatInput.style.display = 'flex';
                console.log(`[UI] DM channel (ID ${dmId}). Showing input.`);
            }
        }

        // Update main header for DM view
        const channelName = document.getElementById('current-channel-name');
        if (channelName) channelName.textContent = name;

        // Hide welcome screen
        const welcomeView = document.getElementById('personal-welcome-view');
        if (welcomeView) welcomeView.classList.remove('active');

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

            // Check real online status from userStatuses dict
            const isOnline = DiscordModule.userStatuses[otherUser.id] === 'online';
            const statusClass = isOnline ? 'online' : 'offline';

            dmProfileContainer.innerHTML = `
                <div class="dm-profile-card">
                    <div class="dm-profile-banner"></div>
                    <div class="dm-profile-avatar-wrapper">
                        <img src="${avatar}" class="dm-profile-avatar" alt="${name}">
                        <div class="dm-profile-status ${statusClass}"></div>
                    </div>
                    <div class="dm-profile-info">
                        <div class="dm-profile-name">${name}</div>
                        <div class="dm-profile-tag">${otherUser.display_name || name}</div>
                    </div>

                    <!-- Tabs -->
                    <div class="dm-profile-tabs">
                        <div class="dm-profile-tab active" id="tab-profile-btn" onclick="DiscordModule.switchProfileTab('profile', ${dmId})">
                            <i class="fa-solid fa-user"></i> Профиль
                        </div>
                        <div class="dm-profile-tab" id="tab-media-btn" onclick="DiscordModule.switchProfileTab('media', ${dmId})">
                            <i class="fa-solid fa-image"></i> Медиа
                        </div>
                        <div class="dm-profile-tab" id="tab-files-btn" onclick="DiscordModule.switchProfileTab('files', ${dmId})">
                            <i class="fa-solid fa-file"></i> Файлы
                        </div>
                    </div>

                    <!-- Tab: Profile -->
                    <div class="dm-tab-content active" id="dm-tab-profile">
                        <div class="dm-profile-section">
                            <div class="dm-profile-section-title">В числе участников с</div>
                            <div class="dm-profile-section-value">${otherUser.created_at ? new Date(otherUser.created_at * 1000).toLocaleDateString('ru-RU', { day: 'numeric', month: 'short', year: 'numeric' }) : 'Неизвестно'}</div>
                        </div>
                        <div class="dm-profile-note">
                            <textarea placeholder="Нажмите, чтобы добавить заметку"></textarea>
                        </div>
                    </div>

                    <!-- Tab: Media -->
                    <div class="dm-tab-content" id="dm-tab-media">
                        <div class="shared-media-header">
                            <span class="shared-media-count" id="shared-media-count">Загрузка...</span>
                        </div>
                        <div class="shared-media-grid" id="shared-media-grid">
                            <div class="shared-media-loading">
                                <i class="fa-solid fa-spinner fa-spin"></i>
                            </div>
                        </div>
                    </div>

                    <!-- Tab: Files -->
                    <div class="dm-tab-content" id="dm-tab-files">
                        <div class="shared-files-list" id="shared-files-list">
                            <div class="shared-media-loading">
                                <i class="fa-solid fa-spinner fa-spin"></i>
                            </div>
                        </div>
                    </div>
                </div>
            `;

            // Load shared media in background
            DiscordModule.loadSharedMedia(dmId);
        }

        // --- CLOUD DRIVE MODE DETECTION ---
        const isCloudBySelf = otherUser && String(otherUser.id) === String(window.currentUserId);
        const isCloudByTitle = channelName && (channelName.textContent.includes("Облако") || channelName.textContent.includes("Saved Messages"));
        const isCloudByDMList = DiscordModule.dmList?.some(d => d.id == dmId && (d.other_user?.id == window.currentUserId || d.other_user?.display_name === "Saved Messages"));
        const isCloudByDisplayName = otherUser && (otherUser.display_name === "Saved Messages" || otherUser.username === "Saved Messages");
        const isCloud = isCloudBySelf || isCloudByDMList || isCloudByTitle || isCloudByDisplayName;
        
        const cloudFoldersSidebar = document.getElementById('cloud-folders-sidebar');
        const channelsList = document.getElementById('channels-list');

        if (isCloud) {
            name = "Моё Облако";
            const globalInput = document.getElementById('global-input');
            if (channelName) channelName.innerHTML = `<i class="fa-solid fa-cloud" style="margin-right:8px; color:var(--blurple);"></i> Моё Облако`;
            if (globalInput) globalInput.placeholder = "Сохранить в облако...";
            
            // Show folders sidebar above channels list
            if (cloudFoldersSidebar) {
                cloudFoldersSidebar.classList.add('active-context');
                cloudFoldersSidebar.style.display = 'block';
            }
            // Ensure DM list stays visible
            if (channelsList) channelsList.style.display = 'block';
            
            // Load folders
            CloudModule.loadFolders();
        } else {
            if (cloudFoldersSidebar) {
                cloudFoldersSidebar.classList.remove('active-context');
                cloudFoldersSidebar.style.display = 'none';
            }
            if (channelsList) channelsList.style.display = 'block';
        }

        // Update Global Input Placeholder if not cloud
        const globalInputUpdate = document.getElementById('global-input');
        if (globalInputUpdate && !isCloud) globalInputUpdate.placeholder = `Message @${name}`;
        DiscordModule.activeDM = dmId;
        DiscordModule.fetchDMMessages(dmId);
    },

    fetchDMMessages: async (dmId) => {
        console.log('[DEBUG fetchDMMessages] dmId:', dmId);
        const lockKey = `fetching_${dmId}`;
        if (DiscordModule[lockKey]) return;
        DiscordModule[lockKey] = true;

        try {
            const res = await fetch(`/api/dms/by_id/${dmId}/messages`);
            const data = await res.json();

            const box = document.getElementById(`dm-messages-${dmId}`);
            if (!box) {
                DiscordModule[lockKey] = false;
                return;
            }

            // Only clear if container is empty (first load)
            const isFirstLoad = box.children.length === 0;
            if (isFirstLoad) {
                box.innerHTML = '';
            }
            box.classList.add('dm-bubbles-container');

            const myUsername = window.currentUsername || '';

            if (!data.messages || data.messages.length === 0) {
                if (isFirstLoad) box.innerHTML = '<div class="dm-empty">Начните беседу!</div>';
                DiscordModule[lockKey] = false;
                return;
            }

            // Get existing message IDs to prevent duplicates
            const existingIds = new Set(Array.from(box.querySelectorAll('.dm-bubble[data-id]')).map(el => el.getAttribute('data-id')));

            data.messages.forEach((m) => {
                if (existingIds.has(String(m.id))) return;

                const isOwn = m.username === myUsername;

                // Build reply preview HTML
                let replyHtml = '';
                if (m.reply_to) {
                    replyHtml = `
                        <div class="dm-bubble-reply" onclick="DiscordModule.scrollToMessage(${m.reply_to.id})">
                            <i class="fa-solid fa-reply"></i>
                            <span class="reply-author">@${Utils.escapeHtml(m.reply_to.username)}</span>
                            <span class="reply-text">${Utils.escapeHtml(m.reply_to.content)}</span>
                        </div>`;
                }

                // Build attachments HTML
                let attachmentHTML = '';
                if (m.attachments) {
                    const attachments = typeof m.attachments === 'string' ? JSON.parse(m.attachments) : m.attachments;
                    attachmentHTML = DiscordModule.renderAttachments(attachments);
                }

                // Build reactions HTML
                let reactionsHtml = '';
                if (m.reactions && Object.keys(m.reactions).length > 0) {
                    const reactItems = Object.entries(m.reactions)
                        .map(([emoji, count]) => `<div class="reaction-item" onclick="DiscordModule.toggleReaction(${m.id}, '${emoji}')">${emoji} ${count}</div>`)
                        .join('');
                    reactionsHtml = `<div class="message-reactions">${reactItems}</div>`;
                }

                const bubbleClass = isOwn ? 'own' : 'other';
                const avatarImg = `<img src="${m.avatar || DEFAULT_AVATAR}" onerror="this.onerror=null;this.src=window.DEFAULT_AVATAR" class="dm-bubble-avatar">`;

                // If own, avatar is usually hidden in modern messenger style, but let's follow the app style
                // The current style seems to use avatar for 'other' and none or different for 'own'

                const timeStr = new Date(m.timestamp * 1000).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });

                // Tags HTML
                let tagsHtml = '';
                if (m.tags && typeof m.tags === 'string') {
                    const tagList = m.tags.split(',').map(t => t.trim()).filter(t => t);
                    tagsHtml = `<div class="message-tags">${tagList.map(t => `<span class="tag-badge">#${Utils.escapeHtml(t)}</span>`).join('')}</div>`;
                }

                box.innerHTML += `
                    <div class="dm-bubble ${bubbleClass}" data-id="${m.id}" data-message-id="${m.id}" data-tags="${Utils.escapeHtml(m.tags || '')}" data-folder-id="${m.cloud_folder_id || ''}" oncontextmenu="DiscordModule.showMessageMenu(event, ${m.id}, ${isOwn}); return false;">
                        ${!isOwn ? avatarImg : ''}
                        <div class="dm-bubble-content">
                            ${replyHtml}
                            ${m.is_encrypted ?
                        `<span class="encrypted-msg" data-enc="${Utils.escapeHtml(m.content)}" data-author-id="${m.author_id}"><i class="fa-solid fa-lock"></i> Encrypted Message</span>`
                        : (m.content ? `<div class="dm-bubble-text">${Utils.escapeHtml(m.content)}</div>` : '')
                    }
                            ${attachmentHTML}
                            ${tagsHtml}
                            ${reactionsHtml}
                            <div class="dm-bubble-time">${timeStr}</div>
                        </div>
                    </div>`;
            });

            // Trigger decryption if UI present
            if (typeof EncryptionUI !== 'undefined') {
                setTimeout(() => EncryptionUI.tryDecryptElements(), 500);
            }

            box.scrollTop = box.scrollHeight;
        } catch (e) {
            console.error(`[DM] Fetch error: `, e);
        } finally {
            // Release lock
            DiscordModule[lockKey] = false;
        }
    },

    forceRefresh: false,

    handleTypingInput: () => {
        // Only for DMs
        if (!DiscordModule.activeDM) return;

        // Emit typing_start if not already typing
        if (!DiscordModule.isTyping && typeof WebSocketModule !== 'undefined' && WebSocketModule.socket) {
            DiscordModule.isTyping = true;

            // Get recipient ID from current DM
            const dm = DiscordModule.dmList?.find(d => d.id == DiscordModule.activeDM);
            if (dm && dm.other_user) {
                WebSocketModule.socket.emit('typing_start', {
                    dm_id: DiscordModule.activeDM,
                    recipient_id: dm.other_user.id
                });
            }
        }

        // Reset timeout
        clearTimeout(DiscordModule.typingTimeout);
        DiscordModule.typingTimeout = setTimeout(() => {
            // Stop typing after 3 seconds
            DiscordModule.isTyping = false;
            if (typeof WebSocketModule !== 'undefined' && WebSocketModule.socket) {
                const dm = DiscordModule.dmList?.find(d => d.id == DiscordModule.activeDM);
                if (dm && dm.other_user) {
                    WebSocketModule.socket.emit('typing_stop', {
                        dm_id: DiscordModule.activeDM,
                        recipient_id: dm.other_user.id
                    });
                }
            }
        }, 3000);
    },

    detectAndRenderLinkPreview: async (messageText) => {
        const urlRegex = /(https?:\/\/[^\s]+)/g;
        const urls = messageText.match(urlRegex);

        if (!urls || urls.length === 0) return '';

        try {
            const url = urls[0]; // Preview first link only
            const res = await fetch('/api/messages/preview-link', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ url })
            });

            const data = await res.json();

            if (data.success && data.preview) {
                return DiscordModule.renderLinkPreview(data.preview);
            }
        } catch (error) {
            console.error('Link preview error:', error);
        }

        return '';
    },

    renderLinkPreview: (preview) => {
        if (preview.type === 'youtube') {
            return `
    < div class="youtube-embed" >
        <iframe
            src="https://www.youtube.com/embed/${preview.video_id}"
            frameborder="0"
            allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture"
            allowfullscreen>
        </iframe>
                </div> `;
        }

        if (preview.type === 'image') {
            return `
    < div class="link-preview-card" >
        <img src="${preview.url}" alt="Image preview">
        </div>`;
        }

        if (preview.type === 'website') {
            return `
            < div class="link-preview-card" >
                ${preview.image ? `<img src="${preview.image}" alt="${preview.title}">` : ''}
<div class="link-preview-title">${Utils.escapeHtml(preview.title)}</div>
                    ${preview.description ? `<div class="link-preview-description">${Utils.escapeHtml(preview.description)}</div>` : ''}
<div class="link-preview-url">${preview.url}</div>
                </div> `;
        }

        return '';
    },

    renderUserProfile: (user) => {
        let profileHTML = '';

        if (user.custom_status || user.status_emoji) {
            profileHTML += `
    < div class="user-status-badge" >
        ${user.status_emoji ? `<span class="user-status-emoji">${user.status_emoji}</span>` : ''}
                    ${user.custom_status || ''}
                </div> `;
        }

        if (user.bio) {
            profileHTML += `
                <div class="user-bio-section">
                    <div class="user-bio-label">О себе</div>
                    <div class="user-bio-text">${Utils.escapeHtml(user.bio)}</div>
                </div>`;
        }

        return profileHTML;
    },

    /**
     * Render message attachments (images, files, voice messages, etc.)
     */
    renderAttachments: (attachments) => {
        if (!attachments || attachments.length === 0) return '';

        let html = '';

        for (const attachment of attachments) {
            // Voice message
            if (attachment.type === 'voice') {
                html += typeof VoiceRecorder !== 'undefined' ?
                    VoiceRecorder.renderVoiceMessage({
                        audio_url: attachment.url || attachment.path,
                        duration: attachment.duration || 0
                    }) : '';
            }
            // Image
            else if (attachment.type === 'image' || /\.(jpg|jpeg|png|gif|webp)$/i.test(attachment.name || attachment.filename || attachment.url || attachment.path)) {
                html += `<div class="message-attachment-image"><img src="${attachment.url || attachment.path}" alt="${attachment.name || attachment.filename || 'Image'}" /></div>`;
            }
            // Video
            else if (attachment.type === 'video' || /\.(mp4|webm|ogg)$/i.test(attachment.name || attachment.filename || attachment.url || attachment.path)) {
                html += `<div class="message-attachment-video"><video controls src="${attachment.url || attachment.path}"></video></div>`;
            }
            // Generic file
            else {
                const fileName = attachment.name || attachment.filename || 'File';
                html += `<div class="message-attachment-file">
                    <i class="fa-solid fa-file"></i>
                    <a href="${attachment.url || attachment.path}" download="${fileName}" target="_blank">${fileName}</a>
                </div>`;
            }
        }

        return html;
    },

    sendDMMessage: async (dmId, text, attachments = []) => {
        console.log('[DEBUG sendDMMessage] dmId:', dmId, 'text:', text);
        if (!text && (!attachments || attachments.length === 0)) return;

        const box = document.getElementById(`dm-messages-${dmId}`);
        const tempId = 'sending-' + Date.now();

        if (box) {
            // Render attachments for optimistic UI
            let attachmentHTML = '';
            if (attachments && attachments.length > 0) {
                attachmentHTML = DiscordModule.renderAttachments(attachments);
            }

            // Render reply preview if replying
            let replyHtml = '';
            if (DiscordModule.replyingTo) {
                replyHtml = `
    <div class="dm-bubble-reply">
                        <i class="fa-solid fa-reply"></i>
                        <span class="reply-author">@${Utils.escapeHtml(DiscordModule.replyingTo.username)}</span>
                        <span class="reply-text">${Utils.escapeHtml(DiscordModule.replyingTo.content)}</span>
                    </div> `;
            }

            // Show timer icon if disappearing message
            const timerIcon = DiscordModule.disappearingTimer ?
                `<i class="fa-solid fa-clock disappearing-icon" title="Исчезнет через ${DiscordModule.formatDisappearingTime(DiscordModule.disappearingTimer)}"></i>` : '';

            box.innerHTML += `
    <div class="dm-bubble own sending ${DiscordModule.disappearingTimer ? 'disappearing' : ''}" id="${tempId}" data-folder-id="${CloudModule.activeFolderId || ''}" oncontextmenu="return false;">
        <div class="dm-bubble-content">
            ${replyHtml}
            ${text ? `<div class="dm-bubble-text">${Utils.escapeHtml(text)}</div>` : ''}
            ${attachmentHTML}
            <div class="dm-bubble-time">${timerIcon}<i class="fa-solid fa-circle-notch fa-spin"></i></div>
        </div>
            </div>`;
            box.scrollTop = box.scrollHeight;
        }

        const nonce = 'n-' + Date.now() + '-' + Math.random().toString(36).substr(2, 9);
        if (typeof DiscordModule.recentOwnMessages === 'undefined') {
            DiscordModule.recentOwnMessages = new Set();
        }
        DiscordModule.recentOwnMessages.add(nonce);
        
        const contentKey = (text || '').trim();
        if (contentKey) DiscordModule.recentOwnMessages.add(contentKey);

        // Auto-cleanup
        setTimeout(() => {
            DiscordModule.recentOwnMessages.delete(nonce);
            if (contentKey) DiscordModule.recentOwnMessages.delete(contentKey);
        }, 10000);

        try {
            let contentToSend = text;
            let isEncrypted = false;
            let encryptionMetadata = null;

            // ENCRYPTION LOGIC
            // Check if E2EE is enabled and we have keys
            if (typeof EncryptionModule !== 'undefined' && EncryptionModule.privateKey && typeof EncryptionUI !== 'undefined') {
                try {
                    const dm = DiscordModule.dmList ? DiscordModule.dmList.find(d => d.id == dmId) : null;
                    if (dm && dm.other_user) {
                        const recipientKey = await EncryptionUI.getRecipientKey(dm.other_user.id);
                        if (recipientKey) {
                            const secret = await EncryptionModule.getSharedSecret(dm.other_user.id, recipientKey);
                            if (text) {
                                const enc = await EncryptionModule.encryptMessage(text, secret);
                                contentToSend = JSON.stringify(enc);
                                isEncrypted = true;
                            }
                        } else {
                            console.warn("[E2EE] Recipient has no public key, sending unencrypted");
                        }
                    }
                } catch (err) {
                    console.error("[E2EE] Encryption failed:", err);
                }
            }

            const payload = { content: contentToSend, is_encrypted: isEncrypted, encryption_metadata: encryptionMetadata, nonce: nonce };
            if (attachments && attachments.length > 0) {
                payload.attachments = JSON.stringify(attachments);
            }
            if (DiscordModule.replyingTo) {
                payload.reply_to_id = DiscordModule.replyingTo.id;
                DiscordModule.cancelReply(); // Clear reply state
            }
            // Add expires_in for disappearing messages
            if (DiscordModule.disappearingTimer) {
                payload.expires_in = DiscordModule.disappearingTimer;
            }
            
            // AUTOMATIC CLOUD FOLDER ASSIGNMENT
            if (CloudModule.activeFolderId) {
                payload.folder_id = CloudModule.activeFolderId;
            }

            const res = await fetch(`/api/dms/by_id/${dmId}/send`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload)
            });

            const d = await res.json();

            if (!res.ok || !d.success) {
                throw new Error(d.error || `Server error ${res.status}`);
            }

            // Add to recent cache to prevent socket double-add
            const cacheKey = `${text.trim()}`;
            DiscordModule.recentOwnMessages.add(cacheKey);
            setTimeout(() => DiscordModule.recentOwnMessages.delete(cacheKey), 5000);

            // Immediately clear "sending" status and add message ID for expiration tracking
            const sendingEl = document.getElementById(tempId);
            if (sendingEl) {
                sendingEl.classList.remove('sending');
                // Add data-message-id for expiration tracking
                if (d.message && d.message.id) {
                    sendingEl.setAttribute('data-message-id', d.message.id);
                }
                const timeEl = sendingEl.querySelector('.dm-bubble-time');
                // Keep timer icon if disappearing message
                const timerIcon = d.message && d.message.expires_at ?
                    `<i class="fa-solid fa-clock disappearing-icon"></i>` : '';
                if (timeEl) timeEl.innerHTML = timerIcon + new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
            }
        } catch (e) {
            console.error("[DM] Send error:", e);
            const failEl = document.getElementById(tempId);
            if (failEl) failEl.remove();
            Utils.showToast("Ошибка отправки: " + e.message);
        }
    },

    // === SHARED MEDIA (GALLERY) ===

    switchProfileTab: (tab, dmId) => {
        // Toggle tab buttons
        document.querySelectorAll('.dm-profile-tab').forEach(el => el.classList.remove('active'));
        const activeBtn = document.getElementById(`tab-${tab}-btn`);
        if (activeBtn) activeBtn.classList.add('active');

        // Toggle content panels
        document.querySelectorAll('.dm-tab-content').forEach(el => el.classList.remove('active'));
        const activePanel = document.getElementById(`dm-tab-${tab}`);
        if (activePanel) activePanel.classList.add('active');

        // Load media/files on first switch
        if (tab === 'media' || tab === 'files') {
            const grid = document.getElementById('shared-media-grid');
            const filesList = document.getElementById('shared-files-list');
            const isLoaded = grid && !grid.querySelector('.shared-media-loading')
                          && filesList && !filesList.querySelector('.shared-media-loading');
            if (!isLoaded) {
                DiscordModule.loadSharedMedia(dmId);
            }
        }
    },

    loadSharedMedia: async (dmId) => {
        try {
            const res = await fetch(`/api/dms/by_id/${dmId}/messages?limit=200`);
            const data = await res.json();

            const grid = document.getElementById('shared-media-grid');
            const filesList = document.getElementById('shared-files-list');
            const countEl = document.getElementById('shared-media-count');

            if (!grid || !filesList) return;

            const messages = data.messages || [];
            const mediaItems = [];
            const fileItems = [];

            // Scan all messages for attachments
            messages.forEach(m => {
                if (!m.attachments) return;
                const attachments = typeof m.attachments === 'string'
                    ? JSON.parse(m.attachments) : m.attachments;

                attachments.forEach(att => {
                    const attUrl = att.url || att.path || '';
                    const attName = att.name || att.filename || '';
                    const isImage = att.type === 'image'
                        || /\.(jpg|jpeg|png|gif|webp|svg)$/i.test(attName || attUrl);
                    const isVideo = att.type === 'video'
                        || /\.(mp4|webm|ogg|mov)$/i.test(attName || attUrl);

                    if (isImage || isVideo) {
                        mediaItems.push({ ...att, isVideo, msgTime: m.timestamp });
                    } else if (att.type !== 'voice') {
                        fileItems.push({ ...att, msgTime: m.timestamp, author: m.username });
                    }
                });
            });

            // Render Media Grid
            if (mediaItems.length === 0) {
                grid.innerHTML = `
                    <div class="shared-media-empty">
                        <i class="fa-solid fa-photo-film"></i>
                        <p>Нет медиафайлов</p>
                    </div>`;
                if (countEl) countEl.textContent = '0 медиафайлов';
            } else {
                if (countEl) {
                    let count = mediaItems.length;
                    let text = count + ' медиафайлов';
                    if (count % 10 === 1 && count % 100 !== 11) {
                        text = count + ' медиафайл';
                    } else if ([2, 3, 4].includes(count % 10) && ![12, 13, 14].includes(count % 100)) {
                        text = count + ' медиафайла';
                    }
                    countEl.textContent = text;
                }
                grid.innerHTML = mediaItems.map(item => {
                    const mediaUrl = item.url || item.path;
                    if (item.isVideo) {
                        return `
                        <div class="shared-media-item" onclick="DiscordModule.openMediaViewer('${mediaUrl}', 'video')">
                            <video src="${mediaUrl}" class="shared-media-thumb"></video>
                            <div class="shared-media-play-icon"><i class="fa-solid fa-play"></i></div>
                        </div>`;
                    }
                    return `
                    <div class="shared-media-item" onclick="DiscordModule.openMediaViewer('${mediaUrl}', 'image')">
                        <img src="${mediaUrl}" class="shared-media-thumb" alt="Недоступно" loading="lazy" onerror="DiscordModule.handleBrokenSharedMedia(this)">
                    </div>`;
                }).join('');
            }

            // Render Files List
            if (fileItems.length === 0) {
                filesList.innerHTML = `
                    <div class="shared-media-empty">
                        <i class="fa-solid fa-folder-open"></i>
                        <p>Нет файлов</p>
                    </div>`;
            } else {
                const fileIcons = {
                    pdf: 'fa-file-pdf', doc: 'fa-file-word', docx: 'fa-file-word',
                    xls: 'fa-file-excel', xlsx: 'fa-file-excel',
                    zip: 'fa-file-zipper', rar: 'fa-file-zipper',
                    txt: 'fa-file-lines', js: 'fa-file-code', py: 'fa-file-code',
                    mp3: 'fa-file-audio', wav: 'fa-file-audio',
                };
                filesList.innerHTML = fileItems.map(item => {
                    const name = item.name || item.url?.split('/').pop() || 'Файл';
                    const ext = name.split('.').pop().toLowerCase();
                    const iconClass = fileIcons[ext] || 'fa-file';
                    const date = item.msgTime
                        ? new Date(item.msgTime * 1000).toLocaleDateString('ru-RU', { day: 'numeric', month: 'short' })
                        : '';
                    const sizeStr = item.size ? DiscordModule.formatFileSize(item.size) : '';

                    return `
                    <a class="shared-file-item" href="${item.url}" target="_blank" download="${name}">
                        <div class="shared-file-icon">
                            <i class="fa-solid ${iconClass}"></i>
                        </div>
                        <div class="shared-file-info">
                            <div class="shared-file-name">${Utils.escapeHtml(name)}</div>
                            <div class="shared-file-meta">${[sizeStr, date].filter(Boolean).join(' · ')}</div>
                        </div>
                        <div class="shared-file-download">
                            <i class="fa-solid fa-download"></i>
                        </div>
                    </a>`;
                }).join('');
            }
        } catch (e) {
            console.error('[SharedMedia] Load error:', e);
        }
    },

    formatFileSize: (bytes) => {
        if (!bytes) return '';
        if (bytes < 1024) return bytes + ' B';
        if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB';
        return (bytes / (1024 * 1024)).toFixed(1) + ' MB';
    },

    openMediaViewer: (url, type) => {
        const existing = document.getElementById('media-viewer-overlay');
        if (existing) existing.remove();

        const overlay = document.createElement('div');
        overlay.id = 'media-viewer-overlay';
        overlay.className = 'media-viewer-overlay';
        overlay.onclick = (e) => { if (e.target === overlay) overlay.remove(); };

        const mediaEl = type === 'video'
            ? `<video src="${url}" controls autoplay class="media-viewer-content"></video>`
            : `<img src="${url}" class="media-viewer-content" alt="media">`;

        overlay.innerHTML = `
            <button class="media-viewer-close" onclick="document.getElementById('media-viewer-overlay').remove()">
                <i class="fa-solid fa-xmark"></i>
            </button>
            ${mediaEl}
            <a href="${url}" download target="_blank" class="media-viewer-download">
                <i class="fa-solid fa-download"></i> Скачать
            </a>
        `;
        document.body.appendChild(overlay);
    },

    handleBrokenSharedMedia: (imgElement) => {
        const div = document.createElement('div');
        div.className = 'shared-media-thumb';
        div.style.display = 'flex';
        div.style.alignItems = 'center';
        div.style.justifyContent = 'center';
        div.style.background = '#2b2d31';
        div.style.color = '#80848e';
        div.style.fontSize = '2.5rem';
        div.title = 'Файл недоступен или удалён';
        div.innerHTML = '<i class="fa-solid fa-file-circle-xmark"></i>';
        imgElement.replaceWith(div);
    },

    // === РАСШИРЕННЫЕ ФУНКЦИИ СООБЩЕНИЙ ===

    replyingTo: null, // { id, username, content }

    showMessageMenu: (event, messageId, isOwn) => {
        event.preventDefault();
        event.stopPropagation(); // Stop bubbling

        // Remove existing menu
        const existingMenu = document.getElementById('message-context-menu');
        if (existingMenu) existingMenu.remove();

        const menu = document.createElement('div');
        menu.id = 'message-context-menu'; // Use ID for singleton
        menu.className = 'message-context-menu'; // Keep class for styling if needed
        menu.innerHTML = `
            <div class="menu-item" onclick="DiscordModule.startReply(${messageId})">
                <i class="fa-solid fa-reply"></i> Ответить
            </div>
            <div class="menu-item" onclick="DiscordModule.showEmojiPicker(${messageId})">
                <i class="fa-solid fa-face-smile"></i> Реакция
            </div>
            <div class="menu-item" onclick="DiscordModule.togglePin(${messageId})">
                <i class="fa-solid fa-thumbtack"></i> Закрепить
            </div>
            ${!isOwn ? `
            <div class="menu-item danger" onclick="DiscordModule.reportMessage(${messageId})">
                <i class="fa-solid fa-flag"></i> Пожаловаться
            </div>
            ` : ''}
            ${isOwn ? `
            <div class="menu-divider"></div>
            <div class="menu-item" onclick="DiscordModule.editMessage(${messageId})">
                <i class="fa-solid fa-pen"></i> Редактировать
            </div>
            <div class="menu-item danger" onclick="DiscordModule.deleteMessage(${messageId})">
                <i class="fa-solid fa-trash"></i> Удалить
            </div>
            ` : ''}
        `;

        menu.style.left = event.pageX + 'px';
        menu.style.top = event.pageY + 'px';
        document.body.appendChild(menu);

        // Close on click outside
        setTimeout(() => {
            document.addEventListener('click', function closeMenu() {
                menu.remove();
                document.removeEventListener('click', closeMenu);
            }, { once: true });
        }, 10);
    },

    startReply: (messageId) => {
        const msgEl = document.querySelector(`[data-message-id="${messageId}"]`);
        if (!msgEl) return;

        const content = msgEl.querySelector('.dm-bubble-text')?.textContent || '';
        const username = msgEl.classList.contains('own') ? window.currentUsername :
            (DiscordModule.dmList?.find(d => d.id == DiscordModule.activeDM)?.other_user?.username || 'User');

        DiscordModule.replyingTo = { id: messageId, username, content: content.slice(0, 50) };

        // Show reply preview above input
        let replyBar = document.getElementById('reply-preview-bar');
        if (!replyBar) {
            replyBar = document.createElement('div');
            replyBar.id = 'reply-preview-bar';
            replyBar.className = 'reply-preview-bar';
            const inputArea = document.querySelector('.chat-input-area');
            if (inputArea) inputArea.insertBefore(replyBar, inputArea.firstChild);
        }

        replyBar.innerHTML = `
            <i class="fa-solid fa-reply"></i>
            <span>Ответ на <strong>@${Utils.escapeHtml(username)}</strong>: ${Utils.escapeHtml(content.slice(0, 40))}...</span>
            <button onclick="DiscordModule.cancelReply()"><i class="fa-solid fa-xmark"></i></button>
        `;
        replyBar.style.display = 'flex';

        document.getElementById('global-input')?.focus();
    },

    cancelReply: () => {
        DiscordModule.replyingTo = null;
        const replyBar = document.getElementById('reply-preview-bar');
        if (replyBar) replyBar.style.display = 'none';
    },

    scrollToMessage: (messageId) => {
        const msgEl = document.querySelector(`[data-message-id="${messageId}"]`);
        if (!msgEl) {
            Utils.showToast('⚠️ Не удалось найти сообщение');
            return;
        }

        // Scroll to message
        msgEl.scrollIntoView({ behavior: 'smooth', block: 'center' });

        // Add highlight animation
        msgEl.classList.add('message-highlighted');
        setTimeout(() => {
            msgEl.classList.remove('message-highlighted');
        }, 1800);
    },

    showEmojiPicker: (messageId) => {
        const existingPicker = document.querySelector('.emoji-picker-popup');
        if (existingPicker) existingPicker.remove();

        const emojis = ['рџ‘Ќ', 'вќ¤пёЏ', 'рџ‚', 'рџ®', 'рџў', 'рџЎ', 'рџ”Ґ', 'рџ‘Џ', 'рџЋ‰', 'рџ’Ї'];
        const picker = document.createElement('div');
        picker.className = 'emoji-picker-popup';
        picker.innerHTML = emojis.map(e =>
            `<div class="emoji-option" onclick="DiscordModule.addReaction(${messageId}, '${e}')">${e}</div>`
        ).join('');

        document.body.appendChild(picker);

        // Position near the message
        const msgEl = document.querySelector(`[data-message-id="${messageId}"]`);
        if (msgEl) {
            const rect = msgEl.getBoundingClientRect();
            picker.style.left = rect.left + 'px';
            picker.style.top = (rect.bottom + 5) + 'px';
        }

        setTimeout(() => {
            document.addEventListener('click', function closePicker() {
                picker.remove();
                document.removeEventListener('click', closePicker);
            }, { once: true });
        }, 10);
    },

    addReaction: async (messageId, emoji) => {
        try {
            const res = await fetch(`/api/messages/${messageId}/react`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ emoji })
            });
            const data = await res.json();
            if (data.success) {
                DiscordModule.forceRefresh = true;
                DiscordModule.fetchDMMessages(DiscordModule.activeDM);
            }
        } catch (e) {
            console.error('Reaction error:', e);
        }
    },

    toggleReaction: async (messageId, emoji) => {
        await DiscordModule.addReaction(messageId, emoji);
    },

    togglePin: async (messageId) => {
        try {
            const res = await fetch(`/api/messages/${messageId}/pin`, { method: 'POST' });
            const data = await res.json();
            if (data.success) {
                Utils.showToast(data.is_pinned ? 'Сообщение закреплено' : 'Сообщение откреплено');
                DiscordModule.forceRefresh = true;
                DiscordModule.fetchDMMessages(DiscordModule.activeDM);
            }
        } catch (e) {
            console.error('Pin error:', e);
        }
    },

    editMessage: (messageId) => {
        const msgEl = document.querySelector(`[data-message-id="${messageId}"]`);
        if (!msgEl) return;

        const textEl = msgEl.querySelector('.dm-bubble-text');
        const currentText = textEl?.textContent || '';

        const newText = prompt('Редактировать сообщение:', currentText);
        if (newText && newText !== currentText) {
            DiscordModule.saveEditedMessage(messageId, newText);
        }
    },

    saveEditedMessage: async (messageId, newContent) => {
        try {
            const res = await fetch(`/api/messages/${messageId}/edit`, {
                method: 'PUT',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ content: newContent })
            });
            const data = await res.json();
            if (data.success) {
                Utils.showToast('Сообщение изменено');
                DiscordModule.forceRefresh = true;
                DiscordModule.fetchDMMessages(DiscordModule.activeDM);
            } else {
                Utils.showToast('Ошибка: ' + (data.error || 'Unknown'));
            }
        } catch (e) {
            console.error('Edit error:', e);
        }
    },

    deleteMessage: async (messageId) => {
        if (!confirm('Удалить это сообщение?')) return;

        try {
            const res = await fetch(`/api/messages/${messageId}/delete`, { method: 'DELETE' });
            const data = await res.json();
            if (data.success) {
                Utils.showToast('Сообщение удалено');
                const msgEl = document.querySelector(`[data-message-id="${messageId}"]`);
                if (msgEl) msgEl.remove();
            } else {
                Utils.showToast('Ошибка: ' + (data.error || 'Unknown'));
            }
        } catch (e) {
            console.error('Delete error:', e);
        }
    },

    showPinnedMessages: async () => {
        const dmId = DiscordModule.activeDM;
        if (!dmId) return;

        try {
            const res = await fetch(`/api/dms/${dmId}/pinned`);
            const data = await res.json();

            if (!data.success) return;

            const modal = document.createElement('div');
            modal.className = 'pinned-modal';
            modal.innerHTML = `
                <div class="pinned-modal-backdrop" onclick="this.parentElement.remove()"></div>
                <div class="pinned-modal-content">
                    <h3><i class="fa-solid fa-thumbtack"></i> Закреплённые сообщения</h3>
                    ${data.pinned.length === 0 ? '<p class="empty">Нет закреплённых сообщений</p>' :
                    data.pinned.map(m => `
                            <div class="pinned-item">
                                <div class="pinned-author">${Utils.escapeHtml(m.username)}</div>
                                <div class="pinned-text">${Utils.escapeHtml(m.content)}</div>
                                <div class="pinned-time">${new Date(m.timestamp * 1000).toLocaleString()}</div>
                            </div>
                        `).join('')
                }
                    <button onclick="this.closest('.pinned-modal').remove()">Закрыть</button>
                </div>
            `;
            document.body.appendChild(modal);
        } catch (e) {
            console.error('Pinned error:', e);
        }
    },

    // --- DISAPPEARING MESSAGES UI ---
    formatDisappearingTime: (seconds) => {
        if (seconds < 60) return `${seconds} сек`;
        if (seconds < 3600) return `${Math.floor(seconds / 60)} мин`;
        if (seconds < 86400) return `${Math.floor(seconds / 3600)} ч`;
        return `${Math.floor(seconds / 86400)} д`;
    },

    toggleDisappearingTimer: () => {
        let dropdown = document.getElementById('disappearing-timer-dropdown');
        if (dropdown) {
            dropdown.remove();
            return;
        }

        const btn = document.getElementById('disappearing-timer-btn');
        if (!btn) return;

        dropdown = document.createElement('div');
        dropdown.id = 'disappearing-timer-dropdown';
        dropdown.className = 'disappearing-dropdown';
        dropdown.innerHTML = `
            <div class="dropdown-header">⏱️ Исчезающие сообщения</div>
            <div class="dropdown-item ${!DiscordModule.disappearingTimer ? 'active' : ''}" onclick="DiscordModule.setDisappearingTimer(null)">
                <i class="fa-solid fa-xmark"></i> Выкл
            </div>
            <div class="dropdown-item ${DiscordModule.disappearingTimer === 30 ? 'active' : ''}" onclick="DiscordModule.setDisappearingTimer(30)">
                <i class="fa-solid fa-clock"></i> 30 секунд
            </div>
            <div class="dropdown-item ${DiscordModule.disappearingTimer === 60 ? 'active' : ''}" onclick="DiscordModule.setDisappearingTimer(60)">
                <i class="fa-solid fa-clock"></i> 1 минута
            </div>
            <div class="dropdown-item ${DiscordModule.disappearingTimer === 300 ? 'active' : ''}" onclick="DiscordModule.setDisappearingTimer(300)">
                <i class="fa-solid fa-clock"></i> 5 минут
            </div>
            <div class="dropdown-item ${DiscordModule.disappearingTimer === 3600 ? 'active' : ''}" onclick="DiscordModule.setDisappearingTimer(3600)">
                <i class="fa-solid fa-clock"></i> 1 час
            </div>
            <div class="dropdown-item ${DiscordModule.disappearingTimer === 86400 ? 'active' : ''}" onclick="DiscordModule.setDisappearingTimer(86400)">
                <i class="fa-solid fa-clock"></i> 24 часа
            </div>
        `;
        btn.parentElement.appendChild(dropdown);

        // Close on outside click
        setTimeout(() => {
            document.addEventListener('click', function closeDropdown(e) {
                if (!dropdown.contains(e.target) && e.target !== btn) {
                    dropdown.remove();
                    document.removeEventListener('click', closeDropdown);
                }
            });
        }, 10);
    },

    setDisappearingTimer: (seconds) => {
        DiscordModule.disappearingTimer = seconds;
        const btn = document.getElementById('disappearing-timer-btn');
        if (btn) {
            if (seconds) {
                btn.classList.add('active');
                btn.title = `Таймер: ${DiscordModule.formatDisappearingTime(seconds)}`;
            } else {
                btn.classList.remove('active');
                btn.title = 'Исчезающие сообщения';
            }
        }
        document.getElementById('disappearing-timer-dropdown')?.remove();
        Utils.showToast(seconds ? `⏱️ Таймер: ${DiscordModule.formatDisappearingTime(seconds)}` : '⏱️ Таймер выключен');
    },

    // --- CONTEXT MENU FOR MESSAGES ---
    // --- CONTEXT MENU REMOVED (Duplicate) ---


    copyMessageText: (messageId) => {
        const msgEl = document.querySelector(`[data-message-id="${messageId}"]`);
        const textEl = msgEl?.querySelector('.dm-bubble-text');
        if (textEl) {
            Utils.copyToClipboard(textEl.textContent);
            Utils.showToast('Текст скопирован');
        }
    },

    // --- REPORT SYSTEM FRONTEND ---
    reportMessage: (messageId) => {
        AdminModule.reportMessagePrompt(messageId);
    },

    closeReportModal: () => {
        const modal = document.getElementById('report-modal');
        if (modal) modal.style.display = 'none';
    },

    submitReport: async (messageId) => {
        const reason = document.querySelector('input[name="report-reason"]:checked')?.value || 'Other';
        try {
            const res = await fetch(`/api/messages/${messageId}/report`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ reason })
            });
            const data = await res.json();
            if (data.success) {
                Utils.showToast('✅ Жалоба отправлена. Спасибо!');
                DiscordModule.closeReportModal();
            } else {
                Utils.showToast('❌ Ошибка: ' + data.error);
            }
        } catch (e) {
            console.error('Report error:', e);
            Utils.showToast('❌ Произошла ошибка');
        }
    },

    // --- ADMIN REPORTS SYSTEM ---
    loadAdminReports: async () => {
        const list = document.getElementById('admin-reports-list');
        if (!list) return;
        
        try {
            const res = await fetch('/api/admin/reports');
            const data = await res.json();
            if (!data.success) {
                list.innerHTML = `<tr><td colspan="6" style="text-align:center; color:var(--danger);">${data.error || 'Access Denied'}</td></tr>`;
                return;
            }
            
            if (data.reports.length === 0) {
                list.innerHTML = `<tr><td colspan="6" style="text-align:center; padding:20px; color:var(--text-muted);">Активных жалоб нет</td></tr>`;
                return;
            }
            
            list.innerHTML = data.reports.map(r => `
                <tr>
                    <td style="color:var(--text-muted); font-size:11px;">${new Date(r.timestamp * 1000).toLocaleString()}</td>
                    <td><strong>@${Utils.escapeHtml(r.reporter_username)}</strong></td>
                    <td><span style="color:var(--danger);">@${Utils.escapeHtml(r.reported_username)}</span></td>
                    <td><span class="tag-badge" style="background:rgba(237, 66, 69, 0.1); color:var(--danger);">${r.reason}</span></td>
                    <td style="max-width:200px; overflow:hidden; text-overflow:ellipsis; white-space:nowrap;" title="${Utils.escapeHtml(r.message_text)}">
                        ${Utils.escapeHtml(r.message_text)}
                    </td>
                    <td>
                        <div class="admin-reports-actions">
                            <button class="btn-mini-danger" onclick="DiscordModule.resolveReport(${r.id}, 'delete')">Удалить сообщение</button>
                            <button class="btn-mini-secondary" onclick="DiscordModule.resolveReport(${r.id}, 'dismiss')">Отклонить</button>
                        </div>
                    </td>
                </tr>
            `).join('');
        } catch (e) {
            list.innerHTML = `<tr><td colspan="6" style="text-align:center; color:var(--danger);">Error loading reports</td></tr>`;
        }
    },

    resolveReport: async (reportId, action) => {
        const confirmMsg = action === 'delete' ? 'Удалить это сообщение и закрыть жалобу?' : 'Отклонить жалобу?';
        if (!confirm(confirmMsg)) return;
        
        try {
            const res = await fetch(`/api/admin/reports/${reportId}/resolve`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ action })
            });
            const data = await res.json();
            if (data.success) {
                Utils.showToast(action === 'delete' ? 'Сообщение успешно удалено' : 'Жалоба отклонена');
                DiscordModule.loadAdminReports();
            } else {
                Utils.showToast('Ошибка: ' + data.error);
            }
        } catch (e) {
            Utils.showToast('Произошла ошибка при разрешении жалобы');
        }
    }

};

const WebSocketModule = {
    socket: null,
    init: () => {
        if (typeof io === 'undefined') return;
        WebSocketModule.socket = io({
            transports: ['websocket', 'polling']
        });

        const socket = WebSocketModule.socket;

        socket.on('connect', () => {
            console.log("Connected to Socket.IO");
            const userBarAvatar = document.getElementById('user-bar-avatar');
            if (userBarAvatar) userBarAvatar.classList.add('is-online');
        });

        socket.on('disconnect', () => {
            console.log("Disconnected from Socket.IO");
            const userBarAvatar = document.getElementById('user-bar-avatar');
            if (userBarAvatar) userBarAvatar.classList.remove('is-online');
        });

        // Channel Messages
        socket.on('new_channel_message', (data) => {
            console.log('[DEBUG WS] Received new_channel_message:', data);
            if (DiscordModule.currentServer === data.sid && DiscordModule.currentChannel === data.cid) {
                const myUsername = window.currentUsername || '';
                const isOwn = data.message.author === myUsername;

                if (isOwn) {
                    const cacheKey = `${data.message.text || data.message.content}`.trim();
                    if (DiscordModule.recentOwnMessages.has(cacheKey)) {
                        console.log('[DEBUG] Skipping own message from socket (already added)');
                        const placeholders = document.querySelectorAll('.message-group.sending');
                        placeholders.forEach(p => {
                            p.classList.remove('sending');
                            const status = p.querySelector('.msg-status');
                            if (status) status.remove();
                        });
                        return;
                    }
                }

                DiscordModule.addMessage(data.cid, data.message);
                const stream = document.getElementById('stream-general');
                if (stream) stream.scrollTop = stream.scrollHeight;
            }
        });

        // DM Messages
        socket.on('new_dm_message', (data) => {
            console.log('[DEBUG WS] Received new_dm_message:', data);
            if (DiscordModule.currentServer === 'home') {
                DiscordModule.loadDMList();
            }

            if (DiscordModule.activeDM && String(DiscordModule.activeDM) === String(data.dm_id)) {
                const myUsername = window.currentUsername || '';
                const isOwn = data.author === myUsername;

                if (isOwn) {
                    const contentKey = `${data.content}`.trim();
                    const hasNonce = data.nonce && DiscordModule.recentOwnMessages.has(data.nonce);
                    const hasContent = contentKey && DiscordModule.recentOwnMessages.has(contentKey);

                    if (hasNonce || hasContent) {
                        console.log('[DEBUG] Skipping own DM from socket (already added)');
                        const placeholders = document.querySelectorAll('.dm-bubble.sending');
                        placeholders.forEach(p => {
                            p.classList.remove('sending');
                            const status = p.querySelector('.dm-bubble-time i.fa-spin');
                            if (status) status.parentElement.innerHTML = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
                        });
                        return;
                    }
                }

                // If message already in DOM (from fetchDMMessages polling or something), skip
                const box = document.getElementById(`dm-messages-${data.dm_id}`);
                if (box) {
                    if (box.querySelector(`[data-id="${data.id}"]`)) return;

                    let attachmentHTML = '';
                    if (data.attachments) {
                        const attachments = typeof data.attachments === 'string' ? JSON.parse(data.attachments) : data.attachments;
                        attachmentHTML = DiscordModule.renderAttachments(attachments);
                    }

                    const bubbleClass = isOwn ? 'own' : 'other';
                    const avatarImg = `<img src="${data.avatar || DEFAULT_AVATAR}" onerror="this.onerror=null;this.src=window.DEFAULT_AVATAR" class="dm-bubble-avatar">`;

                    // Render reply preview
                    let replyHtml = '';
                    if (data.reply_to) {
                        replyHtml = `
                            <div class="dm-bubble-reply" onclick="DiscordModule.scrollToMessage(${data.reply_to.id})">
                                <i class="fa-solid fa-reply"></i>
                                <span class="reply-author">@${Utils.escapeHtml(data.reply_to.username)}</span>
                                <span class="reply-text">${Utils.escapeHtml(data.reply_to.content)}</span>
                            </div>`;
                    }

                    box.innerHTML += `
                        <div class="dm-bubble ${bubbleClass}" data-id="${data.id}" data-message-id="${data.id}" oncontextmenu="DiscordModule.showMessageMenu(event, ${data.id}, ${isOwn}); return false;">
                            ${!isOwn ? avatarImg : ''}
                            <div class="dm-bubble-content">
                                ${replyHtml}
                                ${data.is_encrypted ?
                            `<span class="encrypted-msg" data-enc="${Utils.escapeHtml(data.content)}" data-author-id="${data.author_id || data.user_id}"><i class="fa-solid fa-lock"></i> Encrypted Message</span>`
                            : (data.content ? `<div class="dm-bubble-text">${Utils.escapeHtml(data.content)}</div>` : '')
                        }
                                ${attachmentHTML}
                                <div class="dm-bubble-time">${new Date(data.timestamp * 1000).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}</div>
                            </div>
                        </div>`;
                    box.scrollTop = box.scrollHeight;

                    if (typeof EncryptionUI !== 'undefined') {
                        setTimeout(() => EncryptionUI.tryDecryptElements(), 100);
                    }
                }
            }
        });

        socket.on('user_status', (data) => {
            if (!DiscordModule.userStatuses) DiscordModule.userStatuses = {};
            DiscordModule.userStatuses[data.user_id] = data.status;
            DiscordModule.updateMemberStatus(data.user_id, data.status);
            DiscordModule.updateFriendStatus(data.user_id, data.status);
        });

        socket.on('typing_start', (data) => {
            const indicator = document.getElementById('typing-indicator');
            const usersEl = document.getElementById('typing-users');
            if (indicator && usersEl && data.dm_id == DiscordModule.activeDM) {
                usersEl.textContent = `${data.username} печатает`;
                indicator.style.display = 'flex';
            }
        });

        socket.on('typing_stop', (data) => {
            const indicator = document.getElementById('typing-indicator');
            if (indicator && data.dm_id == DiscordModule.activeDM) {
                indicator.style.display = 'none';
            }
        });

        // Handle expired (disappearing) messages
        socket.on('message_expired', (data) => {
            console.log('[WS] Message expired:', data);
            const msgEl = document.querySelector(`[data-message-id="${data.message_id}"]`);
            if (msgEl) {
                msgEl.classList.add('fade-out');
                setTimeout(() => msgEl.remove(), 500);
            }
        });
    }
};


document.addEventListener('DOMContentLoaded', () => {
    console.log('[App] Initializing modules...');
    if (typeof DiscordModule !== 'undefined') DiscordModule.init();
    if (typeof WebSocketModule !== 'undefined') WebSocketModule.init();

    // Set current user as online immediately (fallback)
    const userBarAvatar = document.getElementById('user-bar-avatar');
    if (userBarAvatar) userBarAvatar.classList.add('is-online');

    const globalInput = document.getElementById('global-input');
    if (globalInput) {
        globalInput.addEventListener('input', function() {
            // 1. Auto-resize height (Beautiful UX)
            this.style.height = '36px';
            const newHeight = Math.min(this.scrollHeight, 200);
            this.style.height = (newHeight) + 'px';
            
            // 2. Typing indicator
            if (DiscordModule && typeof DiscordModule.handleTypingInput === 'function') {
                DiscordModule.handleTypingInput();
            }
        });
    }

    // Add context menu handler for messages (event delegation)
    document.addEventListener('contextmenu', (e) => {
        const bubble = e.target.closest('.dm-bubble[data-message-id]');
        if (bubble) {
            const messageId = bubble.getAttribute('data-message-id');
            const isOwn = bubble.classList.contains('own');
            if (messageId) {
                DiscordModule.showMessageMenu(e, messageId, isOwn);
            }
        }
    });
});

// === GIF MODULE ===
const GifModule = {
    isOpen: false,

    toggleGifPanel: () => {
        const panel = document.getElementById('gif-panel');
        if (!panel) return;

        GifModule.isOpen = !GifModule.isOpen;
        panel.style.display = GifModule.isOpen ? 'flex' : 'none';

        // Close emoji picker if open
        const emojiPicker = document.getElementById('emoji-picker-panel');
        if (emojiPicker) emojiPicker.style.display = 'none';

        // Auto-search trending if opening
        if (GifModule.isOpen) {
            GifModule.searchGifs('trending');
        }
    },

    closeGifPanel: () => {
        const panel = document.getElementById('gif-panel');
        if (panel) panel.style.display = 'none';
        GifModule.isOpen = false;
    },

    searchGifs: async (query) => {
        const resultsContainer = document.getElementById('gif-results');
        if (!resultsContainer) return;

        if (!query || query.trim() === '') {
            resultsContainer.innerHTML = `
                <div class="gif-loading" style="text-align: center; padding: 40px; color: var(--text-muted);">
                    Введите запрос для поиска GIF
                </div>`;
            return;
        }

        // Show loading
        resultsContainer.innerHTML = `
            <div class="gif-loading" style="text-align: center; padding: 40px; color: var(--text-muted);">
                <i class="fa-solid fa-circle-notch fa-spin" style="font-size: 24px;"></i>
                <p>Поиск GIF...</p>
            </div>`;

        try {
            const res = await fetch(`/api/giphy/search?q=${encodeURIComponent(query)}`);
            const data = await res.json();

            if (!data.success || !data.gifs || data.gifs.length === 0) {
                resultsContainer.innerHTML = `
                    <div class="gif-loading" style="text-align: center; padding: 40px; color: var(--text-muted);">
                        Нет результатов
                    </div>`;
                return;
            }

            // Render GIF grid
            resultsContainer.innerHTML = data.gifs.map(gif => `
                <div class="gif-item" onclick="GifModule.selectGif('${gif.url}')">
                    <img src="${gif.preview || gif.url}" alt="${gif.title || 'GIF'}">
                </div>
            `).join('');

        } catch (error) {
            console.error('GIF search error:', error);
            resultsContainer.innerHTML = `
                <div class="gif-loading" style="text-align: center; padding: 40px; color: var(--text-muted);">
                    Ошибка поиска
                </div>`;
        }
    },

    selectGif: (gifUrl) => {
        // Close panel
        GifModule.closeGifPanel();

        // Insert GIF into message
        const input = document.getElementById('global-input');
        if (input) {
            // Add GIF URL to message
            input.value = (input.value + ' ' + gifUrl).trim();
            input.focus();
        }
    }
};

// Explicitly export for HTML inline handlers
window.DiscordModule = DiscordModule;
window.Utils = Utils;
window.DEFAULT_AVATAR = DEFAULT_AVATAR;
window.GifModule = GifModule;



// =========================================================================
// ENCRYPTION UI & INTEGRATION
// =========================================================================

const EncryptionUI = {
    password: null, // Temporary storage for session

    init: async () => {
        if (typeof EncryptionModule === 'undefined') return;

        try {
            await EncryptionModule.init();

            // Check if we have keys
            const hasKey = await EncryptionModule.hasStoredKey();

            // Check session storage for password (cached)
            const cachedPwd = sessionStorage.getItem('e2ee_pwd');
            if (cachedPwd) {
                await EncryptionUI.unlockKeys(cachedPwd);
            }

            // Update UI status
            const status = await EncryptionUI.getStatus();
            EncryptionUI.updateStatus(status);

        } catch (e) { console.error("EncryptionUI Init Error:", e); }
    },

    getStatus: async () => {
        if (!EncryptionModule.isInitialized) {
            await EncryptionModule.init();
        }
        if (EncryptionModule.privateKey) return 'ready';
        const hasKey = await EncryptionModule.hasStoredKey();
        return hasKey ? 'locked' : 'setup';
    },

    updateStatus: (status) => {
        const indicators = document.querySelectorAll('.encryption-status-indicator');
        const text = document.getElementById('encryption-status-text');

        if (status === 'ready') {
            indicators.forEach(el => {
                el.classList.remove('disabled');
                el.classList.add('enabled');
                el.textContent = 'Active';
            });
            if (text) text.textContent = 'Keys loaded. Valid for this session.';

            // Generate fingerprint
            if (EncryptionModule.publicKey) {
                EncryptionModule.getFingerprint().then(fp => {
                    const fpEl = document.getElementById('my-fingerprint');
                    if (fpEl) fpEl.textContent = fp;
                });
            }

            const toggle = document.getElementById('e2ee-toggle');
            if (toggle) toggle.style.display = 'flex';

        } else if (status === 'locked') {
            indicators.forEach(el => {
                el.classList.add('disabled');
                el.classList.remove('enabled');
                el.textContent = 'Locked';
            });
            if (text) text.textContent = 'Keys locked. Enter password to decrypt history.';
        } else {
            indicators.forEach(el => {
                el.classList.add('disabled');
                el.classList.remove('enabled');
                el.textContent = 'Not Setup';
            });
            if (text) text.textContent = 'Encryption not configured. Create a password in settings.';
        }
    },

    unlockKeys: async (password) => {
        try {
            await EncryptionModule.loadPrivateKey(password);
            EncryptionUI.password = password; // Cache in memory
            sessionStorage.setItem('e2ee_pwd', password); // Persist for session
            EncryptionUI.updateStatus('ready');
            EncryptionUI.tryDecryptElements();
            return true;
        } catch (e) {
            console.error("Unlock error:", e);
            return false;
        }
    },

    tryDecryptElements: async () => {
        if (!EncryptionModule.privateKey) return;

        // Decrypt text messages
        const elements = document.querySelectorAll('.encrypted-msg');
        for (const el of elements) {
            try {
                const metadataStr = el.getAttribute('data-enc');
                if (!metadataStr) continue;

                const metadata = JSON.parse(metadataStr);
                const authorId = el.getAttribute('data-author-id');

                // Need author's public key if not me
                let sharedSecret;
                if (authorId == DiscordModule.me?.id) {
                    // It's my own message, need recipient's key? 
                    // Actually, E2EE protocol stores a version for each participant usually.
                    // Here it depends on implementation. If implemented as one secret for the DM:
                    // we just need the other person's key.
                }

                // Assume DM context - get other user's key
                const dmId = DiscordModule.activeDM;
                const dm = DiscordModule.dmList?.find(d => d.id == dmId);
                const otherUser = dm ? dm.other_user : null;

                if (!otherUser) continue;

                const theirKey = await EncryptionUI.getRecipientKey(otherUser.id);
                if (!theirKey) continue;

                sharedSecret = await EncryptionModule.getSharedSecret(otherUser.id, theirKey);
                const decrypted = await EncryptionModule.decryptMessage(metadata, sharedSecret);

                el.innerHTML = `<i class="fa-solid fa-lock-open" style="color:var(--status-online); margin-right:5px;"></i> ${Utils.escapeHtml(decrypted)}`;
                el.classList.remove('encrypted-msg');
                el.classList.add('decrypted-msg');
            } catch (e) {
                console.error("Decryption element error:", e);
            }
        }
    },

    toggleEncryptionInfo: () => {
        DiscordModule.openSettings();
        DiscordModule.switchSettingsTab('privacy');
    },

    getRecipientKey: async (userId) => {
        try {
            const res = await fetch(`/api/keys/${userId}`);
            const data = await res.json();
            if (data.success && data.public_key) {
                return data.public_key;
            }
        } catch (e) { console.error(e); }
        return null;
    }
};

// Expose
window.EncryptionUI = EncryptionUI;

// === CLOUD MODULE ===
const CloudModule = {
    folders: [],
    activeFolderId: null,
    activeMessageId: null,

    openCloud: async () => {
        // Get or Create DM with self
        try {
            const res = await fetch(`/api/dms/get_or_create/${window.currentUserId}`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' }
            });
            const data = await res.json();
            if (data.success && data.dm_id) {
                // Refresh DM list so loadDM can find the otherUser
                await DiscordModule.loadDMList();
                // Open the DM
                DiscordModule.selectChannel('dm-' + data.dm_id, 'dm');
                // Fresh load of folders
                CloudModule.loadFolders();
            } else {
                Utils.showToast("Не удалось открыть облако");
            }
        } catch (e) { console.error(e); }
    },

    loadFolders: async () => {
        try {
            const res = await fetch('/api/cloud/folders');
            const data = await res.json();
            if (data.success) {
                CloudModule.folders = data.folders;
                CloudModule.renderFolders();
            }
        } catch (e) { console.error(e); }
    },

    renderFolders: () => {
        const container = document.getElementById('cloud-folders-list');
        if (!container) return;
        
        container.innerHTML = '';
        CloudModule.folders.forEach(f => {
            const isActive = CloudModule.activeFolderId == f.id;
            container.innerHTML += `
                <div class="folder-item ${isActive ? 'active' : ''}" onclick="CloudModule.filterByFolder(${f.id})" style="border-left: 3px solid ${f.color || '#5865F2'}; ${isActive ? 'background: rgba(255,255,255,0.05); border-right: 2px solid ' + f.color : ''}">
                    <i class="fa-solid fa-${f.icon || 'folder'}"></i>
                    <span>${Utils.escapeHtml(f.name)}</span>
                </div>
            `;
        });
        
        // Populate organizational dropdown if modal exists
        const select = document.getElementById('organize-folder-select');
        if (select) {
            select.innerHTML = '<option value="">Без папки</option>';
            CloudModule.folders.forEach(f => {
                select.innerHTML += `<option value="${f.id}">${f.name}</option>`;
            });
        }
    },

    openAddFolderModal: () => {
        document.getElementById('create-folder-modal').style.display = 'flex';
        document.getElementById('new-folder-name').focus();
    },

    closeModals: () => {
        document.getElementById('create-folder-modal').style.display = 'none';
        document.getElementById('organize-message-modal').style.display = 'none';
    },

    createFolder: async () => {
        const name = document.getElementById('new-folder-name').value.trim();
        const color = document.getElementById('new-folder-color').value;
        if (!name) return;

        try {
            const res = await fetch('/api/cloud/folders', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ name: name, color: color, icon: 'folder' })
            });
            const data = await res.json();
            if (data.success) {
                CloudModule.loadFolders();
                CloudModule.closeModals();
            }
        } catch (e) { console.error(e); }
    },

    openOrganizeModal: (messageId) => {
        CloudModule.activeMessageId = messageId;
        const msgEl = document.querySelector(`.dm-bubble[data-message-id="${messageId}"]`);
        if (!msgEl) return;
        
        const folderId = msgEl.dataset.folderId;
        const tags = msgEl.dataset.tags || '';
        
        document.getElementById('organize-folder-select').value = folderId || '';
        document.getElementById('organize-tags-input').value = tags;
        document.getElementById('organize-message-modal').style.display = 'flex';
        
        const existingMenu = document.getElementById('message-context-menu');
        if (existingMenu) existingMenu.remove();
    },

    saveMessageOrganization: async () => {
        const folderId = document.getElementById('organize-folder-select').value || null;
        const tags = document.getElementById('organize-tags-input').value.trim();
        
        try {
            const res = await fetch(`/api/messages/${CloudModule.activeMessageId}/organize`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ folder_id: folderId, tags: tags })
            });
            const data = await res.json();
            if (data.success) {
                CloudModule.closeModals();
                // Update local element immediately
                const msgEl = document.querySelector(`.dm-bubble[data-message-id="${CloudModule.activeMessageId}"]`);
                if (msgEl) {
                    msgEl.dataset.folderId = folderId || '';
                    msgEl.dataset.tags = tags;
                    // Trigger tag redraw
                    const contentEl = msgEl.querySelector('.dm-bubble-content');
                    // Find or create tags container
                    let tagsContainer = contentEl.querySelector('.message-tags');
                    if (!tags) {
                        if (tagsContainer) tagsContainer.remove();
                    } else {
                        if (!tagsContainer) {
                            tagsContainer = document.createElement('div');
                            tagsContainer.className = 'message-tags';
                            // insert before time
                            const timeEl = contentEl.querySelector('.dm-bubble-time');
                            contentEl.insertBefore(tagsContainer, timeEl);
                        }
                        const tagList = tags.split(',').map(t => t.trim()).filter(t => t);
                        tagsContainer.innerHTML = tagList.map(t => `<span class="tag-badge">#${Utils.escapeHtml(t)}</span>`).join('');
                    }
                }
            }
        } catch (e) { console.error(e); }
    },

    filterByFolder: (folderId) => {
        // Toggle logic: if clicking the same folder, clear filter
        if (CloudModule.activeFolderId == folderId) {
            CloudModule.activeFolderId = null;
            Utils.showToast("Фильтр сброшен");
        } else {
            CloudModule.activeFolderId = folderId;
            Utils.showToast("Фильтр по папке активирован");
        }
        
        // Refresh UI highlight
        CloudModule.renderFolders();
        
        // Client-side filtering
        const bubbles = document.querySelectorAll('.dm-bubble');
        bubbles.forEach(b => {
            if (CloudModule.activeFolderId === null || b.dataset.folderId == CloudModule.activeFolderId) {
                b.style.display = 'flex';
            } else {
                b.style.display = 'none';
            }
        });
    }
};

window.CloudModule = CloudModule;

const AdminModule = {
    users: [],
    reports: [],
    currentTab: 'overview',
    isVerified: false,
    
    openAdminPanel: () => {
        if (!AdminModule.isVerified) {
            const modal = document.getElementById('admin-2fa-modal');
            if (modal) {
                modal.style.display = 'flex';
                document.getElementById('admin-2fa-pin').focus();
            }
            return;
        }
        DiscordModule.selectChannel('admin', 'channel');
        AdminModule.switchTab('overview');
    },

    verify2FA: async () => {
        const pinInput = document.getElementById('admin-2fa-pin');
        const pin = pinInput ? pinInput.value : '';
        if (!pin) return;
        
        try {
            const res = await fetch('/api/admin/verify-2fa', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ pin: pin })
            });
            const data = await res.json();
            if (data.success) {
                AdminModule.isVerified = true;
                const modal = document.getElementById('admin-2fa-modal');
                if (modal) modal.style.display = 'none';
                Utils.showToast("Доступ разрешен");
                AdminModule.openAdminPanel();
            } else {
                Utils.showToast(data.error || "Неверный PIN");
                if (pinInput) pinInput.value = '';
            }
        } catch (e) {
            console.error(e);
            Utils.showToast("Ошибка проверки");
        }
    },

    close2FA: () => {
        const modal = document.getElementById('admin-2fa-modal');
        if (modal) modal.style.display = 'none';
        const pinInput = document.getElementById('admin-2fa-pin');
        if (pinInput) pinInput.value = '';
    },

    switchTab: (tab) => {
        AdminModule.currentTab = tab;
        document.querySelectorAll('.admin-tab-btns .tab-btn').forEach(btn => btn.classList.remove('active'));
        const activeBtn = document.getElementById(`admin-tab-btn-${tab}`);
        if (activeBtn) activeBtn.classList.add('active');

        document.querySelectorAll('.admin-tab-view').forEach(view => view.style.display = 'none');
        const activeView = document.getElementById(`admin-view-${tab}`);
        if (activeView) activeView.style.display = 'block';

        if (tab === 'overview') AdminModule.fetchStats();
        if (tab === 'users') AdminModule.fetchUsers();
        if (tab === 'reports') AdminModule.fetchReports();
        if (tab === 'logs') AdminModule.fetchLogs();
    },

    refreshCurrentTab: () => {
        AdminModule.switchTab(AdminModule.currentTab);
        Utils.showToast("Данные обновлены");
    },
    
    fetchStats: async () => {
        try {
            const res = await fetch('/api/admin/dashboard-stats');
            const data = await res.json();
            if (data.success) {
                const s = data.stats;
                document.getElementById('admin-stat-users').textContent = s.total_users;
                document.getElementById('admin-stat-online').textContent = s.online_users;
                document.getElementById('admin-stat-messages').textContent = s.total_messages;
                const h = Math.floor(s.uptime / 3600);
                const m = Math.floor((s.uptime % 3600) / 60);
                const sec = s.uptime % 60;
                document.getElementById('admin-stat-uptime').textContent = 
                    `${String(h).padStart(2, '0')}:${String(m).padStart(2, '0')}:${String(sec).padStart(2, '0')}`;
            }
        } catch (e) { console.error(e); }
    },
    
    fetchUsers: async () => {
        const tbody = document.getElementById('admin-users-table-body');
        try {
            const res = await fetch('/api/admin/users');
            if (!res.ok) {
                const errData = await res.json().catch(() => ({}));
                const msg = errData.error || `HTTP ${res.status}`;
                if (tbody) tbody.innerHTML = `<tr><td colspan="5" style="text-align: center; padding: 40px; color: #ed4245;">Ошибка сервера: ${msg}</td></tr>`;
                return;
            }
            const data = await res.json();
            if (data.success && Array.isArray(data.users)) {
                AdminModule.users = data.users;
                AdminModule.renderUsers(data.users);
            } else {
                if (tbody) tbody.innerHTML = '<tr><td colspan="5" style="text-align: center; padding: 40px; color: #ed4245;">Некорректный ответ от сервера</td></tr>';
            }
        } catch (e) {
            console.error("Error in fetchUsers:", e);
            if (tbody) tbody.innerHTML = '<tr><td colspan="5" style="text-align: center; padding: 40px; color: #ed4245;">Ошибка соединения или парсинга</td></tr>';
        }
    },

    fetchReports: async () => {
        try {
            const res = await fetch('/api/admin/reports');
            const data = await res.json();
            if (data.success) {
                AdminModule.reports = data.reports;
                const badge = document.getElementById('admin-report-count');
                if (badge) badge.textContent = `${data.reports.length} активных`;
                AdminModule.renderReports(data.reports);
            }
        } catch (e) { console.error(e); }
    },

    renderReports: (reports) => {
        const container = document.getElementById('admin-reports-list');
        if (!container) return;
        if (!Array.isArray(reports) || reports.length === 0) {
            container.innerHTML = '<div style="text-align: center; color: #949ba4; padding: 40px;">Жалоб нет</div>';
            return;
        }
        container.innerHTML = reports.map(r => `
            <div class="report-item-card">
                <div class="report-header">
                    <span>@${Utils.escapeHtml(r.reporter)} -> @${Utils.escapeHtml(r.author)}</span>
                    <span>${Utils.formatMessageTime(r.timestamp)}</span>
                </div>
                <div class="reported-content"><p>${Utils.escapeHtml(r.content)}</p></div>
                <div class="report-reason"><strong>Причина:</strong> ${Utils.escapeHtml(r.reason)}</div>
                <div class="report-actions">
                    <button class="admin-btn danger sm" onclick="AdminModule.resolveReport(${r.report_id}, 'delete')">Удалить</button>
                    <button class="admin-btn secondary sm" onclick="AdminModule.resolveReport(${r.report_id}, 'ignore')">Отклонить</button>
                </div>
            </div>`).join('');
    },

    resolveReport: async (reportId, action) => {
        if (action === 'delete' && !confirm("Удалить?")) return;
        try {
            const res = await fetch('/api/admin/reports/resolve', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ report_id: reportId, action: action })
            });
            const data = await res.json();
            if (data.success) {
                Utils.showToast("Обработано");
                AdminModule.fetchReports();
            }
        } catch (e) { console.error(e); }
    },

    renderUsers: (users) => {
        const tbody = document.getElementById('admin-users-table-body');
        if (!tbody) return;
        if (!Array.isArray(users) || users.length === 0) {
            tbody.innerHTML = '<tr><td colspan="5" style="text-align: center; padding: 20px;">Нет данных</td></tr>';
            return;
        }
        tbody.innerHTML = users.map(u => `
            <tr>
                <td><div style="display: flex; align-items: center; gap: 10px;">
                    <img src="${u.avatar}" style="width: 28px; height: 28px; border-radius: 50%;">
                    <span>${Utils.escapeHtml(u.username)}</span>
                </div></td>
                <td style="font-size: 12px; color: #949ba4;">#${u.id}</td>
                <td><span class="role-badge ${u.role}">${u.role.toUpperCase()}</span></td>
                <td style="font-size: 13px;">${AdminModule.formatLastSeen(u.last_seen)}</td>
                <td><div style="display: flex; gap: 6px;">
                    <button class="admin-btn sm" onclick="DiscordModule.startDM(${u.id})"><i class="fa-solid fa-message"></i></button>
                    ${u.role === 'user' ? `<button class="admin-btn sm" onclick="AdminModule.grantAdminByRow(${u.id})"><i class="fa-solid fa-shield"></i></button>` : ''}
                </div></td>
            </tr>`).join('');
    },

    formatLastSeen: (ts) => {
        if (!ts) return '<span style="color: #ed4245;">Ни разу не был</span>';
        const diff = Math.floor(Date.now() / 1000) - ts;
        if (diff < 60) return '<span style="color: #23a559;">В сети</span>';
        if (diff < 3600) return `${Math.floor(diff / 60)} мин. назад`;
        if (diff < 86400) return `${Math.floor(diff / 3600)} ч. назад`;
        return new Date(ts * 1000).toLocaleDateString();
    },

    sendBroadcast: async () => {
        const input = document.getElementById('admin-broadcast-text');
        const text = input ? input.value : '';
        if (!text || !text.trim()) { Utils.showToast("Введите текст"); return; }
        const btn = document.getElementById('admin-broadcast-btn');
        btn.disabled = true;
        try {
            const res = await fetch('/api/admin/broadcast', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ content: text.trim() })
            });
            const data = await res.json();
            if (data.success) { Utils.showToast("Готово!"); if (input) input.value = ''; }
        } catch (e) { console.error(e); } finally { btn.disabled = false; }
    },

    fetchLogs: async () => {
        try {
            const res = await fetch('/api/admin/logs');
            const data = await res.json();
            if (data.success) AdminModule.renderLogs(data.logs);
        } catch (e) { console.error(e); }
    },

    renderLogs: (logs) => {
        const tbody = document.getElementById('admin-logs-table-body');
        if (!tbody) return;
        if (!Array.isArray(logs) || logs.length === 0) {
            tbody.innerHTML = '<tr><td colspan="4" style="text-align: center; padding: 20px;">Логов нет</td></tr>';
            return;
        }
        tbody.innerHTML = logs.map(l => `
            <tr>
                <td style="color: #fff;">@${Utils.escapeHtml(l.admin)}</td>
                <td><code style="background: rgba(0,0,0,0.3); padding: 2px 6px; border-radius: 4px;">${l.ip}</code></td>
                <td>${Utils.escapeHtml(l.action)}</td>
                <td style="color: #949ba4; font-size: 11px;">${Utils.formatMessageTime(l.timestamp)}</td>
            </tr>`).join('');
    },

    grantAdminByRow: async (id) => {
        if (!confirm(`Выдать админку #${id}?`)) return;
        try {
            const res = await fetch('/api/admin/grant-admin', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ identifier: id.toString() })
            });
            const data = await res.json();
            if (data.success) { Utils.showToast("Права выданы"); AdminModule.fetchUsers(); }
        } catch (e) { console.error(e); }
    },

    grantAdmin: async () => {
        const identifier = document.getElementById('admin-grant-id').value.trim();
        if (!identifier) return;
        try {
            const res = await fetch('/api/admin/grant-admin', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ identifier })
            });
            const data = await res.json();
            if (data.success) { Utils.showToast(data.message); AdminModule.fetchUsers(); }
        } catch (e) { console.error(e); }
    },

    runMigration: async () => {
        if (!confirm("Запустить обновление базы данных? Это может занять несколько секунд.")) return;
        try {
            const res = await fetch('/api/admin/migrate-now', { method: 'POST' });
            const data = await res.json();
            if (data.success) {
                alert(data.message);
                location.reload();
            } else {
                alert("Ошибка: " + data.error);
            }
        } catch (e) { console.error(e); alert("Ошибка соединения"); }
    }
};

window.AdminModule = AdminModule;

