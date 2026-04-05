
import os

file_path = r'C:\Users\kompd\.gemini\antigravity\scratch\discord_bot\static\js\dashboard.js'

with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
    lines = f.readlines()

start_idx = -1
end_idx = -1

for i, line in enumerate(lines):
    if 'const AdminModule = {' in line:
        start_idx = i
    if 'window.AdminModule = AdminModule;' in line:
        end_idx = i - 1
        break

if start_idx != -1 and end_idx != -1:
    new_admin_module = """const AdminModule = {
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
        try {
            const res = await fetch('/api/admin/users');
            const data = await res.json();
            if (data.success && Array.isArray(data.users)) {
                AdminModule.users = data.users;
                AdminModule.renderUsers(data.users);
            } else {
                AdminModule.renderUsers([]);
            }
        } catch (e) {
            console.error(e);
            AdminModule.renderUsers([]);
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
    }
};
"""
    
    final_lines = lines[:start_idx] + [new_admin_module + '\n'] + lines[end_idx+1:]
    
    with open(file_path, 'w', encoding='utf-8') as f:
        f.writelines(final_lines)
    print("Successfully patched AdminModule in dashboard.js")
else:
    print(f"Markers not found: start={start_idx}, end={end_idx}")
