/**
 * Octave Trust & Safety (T&S) Dashboard
 * Comprehensive moderation and remediation suite.
 */

const StaffDashboard = {
    activeTab: 'dashboard',
    userData: [],
    selectedUserId: null,
    isAdminPanelOpen: false,

    init: async () => {
        console.log("[StaffDashboard] Initializing T&S Panel...");
        await StaffDashboard.loadDashboard();
    },

    switchTab: async (tab) => {
        StaffDashboard.activeTab = tab;
        document.querySelectorAll('.admin-nav-btn').forEach(b => b.classList.toggle('active', b.dataset.tab === tab));
        
        const container = document.getElementById('admin-v2-main-content');
        if (!container) return;
        container.innerHTML = '<div class="admin-loading">Загрузка...</div>';

        if (tab === 'dashboard') await StaffDashboard.loadDashboard();
        if (tab === 'users') await StaffDashboard.loadUsers();
        if (tab === 'inspector') StaffDashboard.renderInspector();
        if (tab === 'audit') await StaffDashboard.loadAuditLogs();
        if (tab === 'reports') await StaffDashboard.loadReports();
    },

    // --- DASHBOARD VIEW ---
    loadDashboard: async () => {
        try {
            const res = await fetch('/api/admin/dashboard-v2');
            const data = await res.json();
            if (!data.success) {
                StaffDashboard.renderError(data.error);
                return;
            }

            const s = data.stats;
            const container = document.getElementById('admin-v2-main-content');
            container.innerHTML = `
                <div class="admin-stats-grid">
                    <div class="stat-card">
                        <div class="label">Онлайн</div>
                        <div class="value">${s.online}</div>
                    </div>
                    <div class="stat-card">
                        <div class="label">Новые (24ч)</div>
                        <div class="value">${s.new_regs}</div>
                    </div>
                    <div class="stat-card">
                        <div class="label">Жалобы</div>
                        <div class="value" style="color:${s.pending_reports > 0 ? 'var(--risk-high)' : 'inherit'}">${s.pending_reports}</div>
                    </div>
                    <div class="stat-card">
                        <div class="label">Риск-алерты</div>
                        <div class="value">${s.risk_alerts}</div>
                    </div>
                </div>

                <div style="display:grid; grid-template-columns: 2fr 1fr; gap:24px;">
                    <div class="admin-table-container">
                        <div class="admin-table-header"><h3>Недавние регистрации</h3></div>
                        <div id="recent-users-mini">Загрузка...</div>
                    </div>
                    <div class="admin-table-container">
                        <div class="admin-table-header"><h3>Распределение ролей</h3></div>
                        <div style="padding:20px;">
                            ${Object.entries(s.roles).map(([role, count]) => `
                                <div style="display:flex; justify-content:space-between; margin-bottom:8px; font-size:14px;">
                                    <span style="color:rgba(255,255,255,0.6)">${role}</span>
                                    <span style="font-weight:600;">${count}</span>
                                </div>
                            `).join('')}
                        </div>
                    </div>
                </div>
            `;
            await StaffDashboard.loadRecentUsers();
        } catch (e) { StaffDashboard.renderError(e); }
    },

    loadRecentUsers: async () => {
        const res = await fetch('/api/admin/users/search-v2');
        const data = await res.json();
        const container = document.getElementById('recent-users-mini');
        if (data.success && container) {
            container.innerHTML = `
                <table class="ts-table">
                    <thead><tr><th>Пользователь</th><th>Дата</th><th>Риск</th></tr></thead>
                    <tbody>
                        ${data.users.slice(0, 5).map(u => `
                            <tr onclick="StaffDashboard.openProfile(${u.id})" style="cursor:pointer;">
                                <td>
                                    <div class="ts-user-item">
                                        <img src="${u.avatar}" class="ts-avatar">
                                        <span>${u.username}</span>
                                    </div>
                                </td>
                                <td>${new Date(u.created_at * 1000).toLocaleDateString()}</td>
                                <td><span class="risk-badge ${StaffDashboard.getRiskClass(u.risk)}">${u.risk}</span></td>
                            </tr>
                        `).join('')}
                    </tbody>
                </table>
            `;
        }
    },

    // --- USER MANAGEMENT ---
    loadUsers: async (query = '') => {
        const container = document.getElementById('admin-v2-main-content');
        container.innerHTML = `
            <div class="admin-table-container">
                <div class="admin-table-header">
                    <h3>Управление пользователями</h3>
                    <input type="text" class="admin-search-input" placeholder="Поиск по ID / имени / IP..." 
                           onkeyup="if(event.key === 'Enter') StaffDashboard.loadUsers(this.value)" value="${query}">
                </div>
                <table class="ts-table" id="users-full-table">
                    <thead><tr><th>Пользователь</th><th>Роль</th><th>IP</th><th>Риск</th><th>Статус</th><th>Действия</th></tr></thead>
                    <tbody><tr><td colspan="6" style="text-align:center;">Загрузка...</td></tr></tbody>
                </table>
            </div>
        `;

        try {
            const res = await fetch(`/api/admin/users/search-v2?query=${encodeURIComponent(query)}`);
            const data = await res.json();
            const tbody = document.querySelector('#users-full-table tbody');
            if (data.success && tbody) {
                tbody.innerHTML = data.users.map(u => `
                    <tr>
                        <td onclick="StaffDashboard.openProfile(${u.id})" style="cursor:pointer;">
                            <div class="ts-user-item">
                                <img src="${u.avatar}" class="ts-avatar">
                                <div>
                                    <div style="font-weight:600;">${u.username}</div>
                                    <div style="font-size:11px; color:rgba(255,255,255,0.3);">ID: ${u.id}</div>
                                </div>
                            </div>
                        </td>
                        <td><span class="tag-badge ${u.role}">${u.role}</span></td>
                        <td style="font-family:monospace; color:rgba(255,255,255,0.5);">${u.ip || 'Unknown'}</td>
                        <td><span class="risk-badge ${StaffDashboard.getRiskClass(u.risk)}">${u.risk}</span></td>
                        <td>
                            ${u.is_banned ? '<span style="color:var(--risk-high);">Banned</span>' : 
                              (u.is_muted ? '<span style="color:var(--risk-med);">Muted</span>' : '<span style="color:var(--risk-low);">Active</span>')}
                        </td>
                        <td>
                            <button class="btn-mini-secondary" onclick="StaffDashboard.openProfile(${u.id})">Управление</button>
                        </td>
                    </tr>
                `).join('');
            }
        } catch (e) { console.error(e); }
    },

    // --- PROFILE DRAWER ---
    openProfile: async (uid) => {
        StaffDashboard.selectedUserId = uid;
        const drawer = document.getElementById('ts-profile-drawer');
        if (!drawer) return;
        
        drawer.classList.add('active');
        drawer.innerHTML = '<div style="padding:20px;">Загрузка профиля...</div>';

        try {
            const res = await fetch(`/api/admin/users/${uid}/profile`);
            const data = await res.json();
            if (!data.success) return;

            const p = data.profile;
            drawer.innerHTML = `
                <div class="drawer-header">
                    <h3>Профиль пользователя</h3>
                    <button class="btn-circular" onclick="StaffDashboard.closeDrawer()"><i class="fa-solid fa-xmark"></i></button>
                </div>
                
                <div style="display:flex; align-items:center; gap:20px; margin-bottom:24px;">
                    <img src="${p.avatar || DEFAULT_AVATAR}" style="width:80px; height:80px; border-radius:12px;">
                    <div>
                        <div style="font-size:20px; font-weight:700;">${p.username}</div>
                        <div style="color:rgba(255,255,255,0.5);">@${p.id}</div>
                    </div>
                </div>

                <div class="admin-stats-grid" style="grid-template-columns: 1fr 1fr; gap:12px;">
                    <div class="stat-card" style="padding:12px;">
                        <div class="label">Риск</div>
                        <div class="value ${StaffDashboard.getRiskClass(p.risk)}" style="font-size:20px;">${p.risk}</div>
                    </div>
                    <div class="stat-card" style="padding:12px;">
                        <div class="label">Роль</div>
                        <div class="value" style="font-size:20px;">${p.role}</div>
                    </div>
                </div>

                <div style="margin-top:24px;">
                    <div class="label" style="font-size:12px; color:rgba(255,255,255,0.3); margin-bottom:12px;">ИНФОРМАЦИЯ</div>
                    <div style="font-size:14px; display:grid; gap:8px;">
                        <div>IP: <code>${p.ip}</code></div>
                        <div>Email: <code>${p.email || 'None'}</code></div>
                        <div>Регистрация: <span>${new Date(p.created_at * 1000).toLocaleString()}</span></div>
                    </div>
                </div>

                <div style="margin-top:32px;">
                    <div class="label" style="font-size:12px; color:rgba(255,255,255,0.3); margin-bottom:12px;">ДЕЙСТВИЯ</div>
                    <div class="action-btn danger" onclick="StaffDashboard.remediate('ban')">
                        <i class="fa-solid fa-gavel"></i> Забанить навсегда
                    </div>
                    <div class="action-btn med" onclick="StaffDashboard.remediate('mute')">
                        <i class="fa-solid fa-microphone-slash"></i> Заглушить (Mute)
                    </div>
                    <div class="action-btn" onclick="StaffDashboard.inspectMessages(${p.id})">
                        <i class="fa-solid fa-eye"></i> Проверить сообщения (Inspector)
                    </div>
                    ${p.ban.active ? `
                        <div class="action-btn success" style="color:var(--risk-low);" onclick="StaffDashboard.remediate('unban')">
                            <i class="fa-solid fa-rotate-left"></i> Разбанить
                        </div>
                    ` : ''}
                </div>
            `;
        } catch (e) { console.error(e); }
    },

    closeDrawer: () => {
        const drawer = document.getElementById('ts-profile-drawer');
        if (drawer) {
            drawer.classList.remove('active');
            StaffDashboard.selectedUserId = null;
        }
    },

    remediate: async (action) => {
        const uid = StaffDashboard.selectedUserId;
        const reason = prompt(`Причина для ${action}:`, "Нарушение правил");
        if (reason === null) return;

        const duration = (action === 'ban' || action === 'mute') ? 
                         prompt("Длительность в часах (пусто для перманентного):", "") : null;

        try {
            const res = await fetch('/api/admin/users/remediate', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ user_id: uid, action, reason, duration })
            });
            const data = await res.json();
            if (data.success) {
                Utils.showToast("✅ Действие выполнено");
                StaffDashboard.openProfile(uid); // Refresh
                if (StaffDashboard.activeTab === 'users') StaffDashboard.loadUsers();
            } else {
                Utils.showToast("❌ Ошибка: " + data.error);
            }
        } catch (e) { console.error(e); }
    },

    // --- MESSAGE INSPECTOR ---
    renderInspector: () => {
        const container = document.getElementById('admin-v2-main-content');
        container.innerHTML = `
            <div class="admin-table-container">
                <div class="admin-table-header">
                    <h3>Chat Inspector</h3>
                    <div style="display:flex; gap:12px;">
                        <input type="text" id="inspector-user-id" class="admin-search-input" style="width:150px;" placeholder="User ID">
                        <input type="text" id="inspector-keyword" class="admin-search-input" placeholder="Ключевое слово...">
                        <button class="btn-primary" onclick="StaffDashboard.runInspector()">Искать</button>
                    </div>
                </div>
                <div id="inspector-results" style="padding:20px;">
                    <div style="text-align:center; color:rgba(255,255,255,0.3); padding:40px;">Введите критерии для поиска сообщений</div>
                </div>
            </div>
        `;
    },

    runInspector: async () => {
        const uid = document.getElementById('inspector-user-id').value;
        const key = document.getElementById('inspector-keyword').value;
        const results = document.getElementById('inspector-results');
        
        results.innerHTML = 'Загрузка...';

        try {
            const res = await fetch(`/api/admin/inspector/messages?user_id=${uid}&keyword=${encodeURIComponent(key)}`);
            const data = await res.json();
            if (data.success) {
                results.innerHTML = `
                    <div class="inspector-messages">
                        ${data.messages.length === 0 ? '<div style="text-align:center; padding:20px;">Ничего не найдено</div>' : 
                          data.messages.map(m => `
                            <div class="inspector-item">
                                <div class="inspector-meta">
                                    <strong>@${m.author}</strong> (ID:${m.author_id || '?'}) at ${new Date(m.time * 1000).toLocaleString()} in DM:${m.dm_id}
                                </div>
                                <div class="inspector-text">${Utils.escapeHtml(m.content)}</div>
                            </div>
                          `).join('')}
                    </div>
                `;
            } else {
                results.innerHTML = `<div style="color:var(--risk-high);">${data.error}</div>`;
            }
        } catch (e) { results.innerHTML = 'Error'; }
    },

    // --- REVIEWS & LOGS ---
    loadAuditLogs: async () => {
        const container = document.getElementById('admin-v2-main-content');
        container.innerHTML = `
            <div class="admin-table-container">
                <div class="admin-table-header"><h3>Audit Logs (Последние 100 действий)</h3></div>
                <table class="ts-table" id="audit-table">
                    <thead><tr><th>Сотрудник</th><th>Действие</th><th>IP</th><th>Время</th></tr></thead>
                    <tbody></tbody>
                </table>
            </div>
        `;

        try {
            const res = await fetch('/api/admin/logs');
            const data = await res.json();
            if (data.success) {
                document.querySelector('#audit-table tbody').innerHTML = data.logs.map(l => `
                    <tr>
                        <td style="font-weight:600; color:var(--ts-accent);">@${l.admin}</td>
                        <td>${l.action} ${l.details ? `<br><small style="color:rgba(255,255,255,0.4)">${l.details}</small>` : ''}</td>
                        <td style="font-family:monospace; font-size:12px;">${l.ip}</td>
                        <td style="color:rgba(255,255,255,0.4);">${new Date(l.timestamp * 1000).toLocaleString()}</td>
                    </tr>
                `).join('');
            }
        } catch (e) {
            document.querySelector('#audit-table tbody').innerHTML = '<tr><td colspan="4">Error</td></tr>';
        }
    },

    // --- HELPERS ---
    getRiskClass: (risk) => {
        if (risk > 70) return 'high';
        if (risk > 30) return 'med';
        return 'low';
    },

    renderError: (err) => {
        const container = document.getElementById('admin-v2-main-content');
        if (container) container.innerHTML = `<div style="padding:40px; text-align:center; color:var(--risk-high); font-weight:600;">Ошибка: ${err}</div>`;
    }
};
