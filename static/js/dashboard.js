/**
 * Dashboard Pro - Main JavaScript Logic
 * Rewritten for stability and performance
 */

document.addEventListener('DOMContentLoaded', () => {
    console.log('Dashboard Initializing...');

    // Initialize Modules
    TabsModule.init();
    WebSocketModule.init();
    ArizonaModule.init();
    TempMailModule.init();
    FavoritesModule.init();
    UIModule.init();
});

// --- CORE UTILS ---
const Utils = {
    showToast: (msg, type = 'info') => {
        const t = document.createElement('div');
        t.className = `toast ${type}`;
        t.textContent = msg;
        document.body.appendChild(t);
        setTimeout(() => t.remove(), 3000);
    },

    escapeHtml: (text) => {
        if (!text) return '';
        return text.replace(/&/g, "&amp;")
            .replace(/</g, "&lt;")
            .replace(/>/g, "&gt;");
    },

    copyToClipboard: (text, successMsg = 'Скопировано!') => {
        navigator.clipboard.writeText(text).then(() => {
            Utils.showToast(successMsg, 'success');
        }).catch(err => {
            console.error('Copy failed:', err);
            Utils.showToast('Ошибка копирования', 'error');
        });
    }
};

// --- UI MODULE ---
const UIModule = {
    init: () => {
        // Theme Toggle
        const themeBtn = document.querySelector('.theme-toggle');
        if (themeBtn) {
            themeBtn.addEventListener('click', UIModule.toggleTheme);
            // Restore theme
            const savedTheme = localStorage.getItem('theme') || 'dark';
            if (savedTheme === 'light') document.body.classList.add('light-theme');
            UIModule.updateThemeIcon();
        }

        // Global Event Listeners (Delegation)
        document.body.addEventListener('click', (e) => {
            // Modal closing on backdrop click
            if (e.target.classList.contains('modal')) {
                e.target.style.display = 'none';
            }

            // Close buttons in modals
            if (e.target.classList.contains('close-modal-btn')) {
                const modal = e.target.closest('.modal');
                if (modal) modal.style.display = 'none';
            }
        });
    },

    toggleTheme: () => {
        document.body.classList.toggle('light-theme');
        const isLight = document.body.classList.contains('light-theme');
        localStorage.setItem('theme', isLight ? 'light' : 'dark');
        UIModule.updateThemeIcon();
    },

    updateThemeIcon: () => {
        const icon = document.getElementById('theme-icon');
        if (icon) {
            icon.textContent = document.body.classList.contains('light-theme') ? '☀️' : '🌙';
        }
    }
};

// --- TABS MODULE ---
const TabsModule = {
    init: () => {
        const tabButtons = document.querySelectorAll('.tab-btn');
        tabButtons.forEach(btn => {
            btn.addEventListener('click', () => {
                const tabName = btn.getAttribute('data-tab') || btn.id.replace('btn-', '');
                TabsModule.switchTab(tabName);
            });
        });

        // Load initial tab (default to dashboard or from URL hash if we implemented that)
        // TabsModule.switchTab('dashboard'); // Already active in HTML usually
    },

    switchTab: (tabName) => {
        console.log('Switching to tab:', tabName);

        // 1. Deactivate all
        document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
        document.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));

        // 2. Activate button
        // Try strict ID first, then loose check
        let btn = document.getElementById(`btn-${tabName}`);
        if (!btn) {
            // Fallback: look for button with data-tab attribute
            btn = document.querySelector(`.tab-btn[data-tab="${tabName}"]`);
        }

        if (btn) btn.classList.add('active');
        else console.warn(`Button for tab "${tabName}" not found`);

        // 3. Activate content
        const content = document.getElementById(`tab-${tabName}`);
        if (content) {
            content.classList.add('active');
            window.scrollTo(0, 0);
        } else {
            console.error(`Content for tab "${tabName}" not found`);
            return;
        }

        // 4. Load Tab Data
        TabsModule.loadTabData(tabName);
    },

    loadTabData: (tab) => {
        switch (tab) {
            case 'favorites':
                FavoritesModule.loadMonitors();
                FavoritesModule.loadAccounts();
                break;
            case 'arizonaai':
                ArizonaModule.loadServers();
                break;
            case 'tempmail':
                TempMailModule.renderList();
                TempMailModule.checkMail(true);
                break;
            case 'monitors': // If there's a monitors tab
            case 'data': // Assuming 'data' contains monitors/accounts
                FavoritesModule.loadAllMonitors();
                FavoritesModule.loadAllAccounts();
                break;
            case 'profile':
                // Load profile specific stuff if needed
                break;
        }
    }
};

// --- WEBSOCKET MODULE ---
const WebSocketModule = {
    socket: null,

    init: () => {
        if (typeof io === 'undefined') {
            console.warn('Socket.IO not loaded');
            return;
        }

        WebSocketModule.socket = io();

        const s = WebSocketModule.socket;

        s.on('connect', () => {
            console.log('WS Connected');
            Utils.showToast('Подключено к серверу', 'success');
        });

        s.on('disconnect', () => {
            console.log('WS Disconnected');
            Utils.showToast('Соединение потеряно', 'error');
        });

        s.on('stats_update', (data) => WebSocketModule.updateStats(data));
        s.on('log_new', (log) => WebSocketModule.addLog(log));
    },

    updateStats: (data) => {
        // Safe update helpers
        const setTxt = (id, val) => {
            const el = document.getElementById(id);
            if (el) el.textContent = val;
        };

        setTxt('bot-servers', data.servers);
        setTxt('bot-users', data.users);
        setTxt('bot-commands', data.commands_today);
        setTxt('bot-memory', `${data.memory_used} MB`);

        if (data.cpu_percent !== undefined) {
            setTxt('bot-cpu', `${data.cpu_percent.toFixed(1)}%`);
        }

        // Uptime
        const hours = Math.floor(data.uptime / 3600);
        const minutes = Math.floor((data.uptime % 3600) / 60);
        const seconds = data.uptime % 60;
        setTxt('bot-uptime', `${hours}:${String(minutes).padStart(2, '0')}:${String(seconds).padStart(2, '0')}`);

        // Status
        const statusEl = document.getElementById('bot-status-text');
        if (statusEl) {
            statusEl.innerHTML = data.running
                ? '<span class="status-running">● Работает</span>'
                : '<span class="status-stopped">● Остановлен</span>';
        }
    },

    addLog: (log) => {
        const container = document.getElementById('log-container');
        if (!container) return;

        const entry = document.createElement('div');
        entry.className = 'log-entry';

        // Colorize level
        let levelClass = log.level || 'info';

        entry.innerHTML = `
            <span class="log-time">${log.timestamp}</span>
            <span class="log-level ${levelClass}">[${levelClass.toUpperCase()}]</span>
            <span>${Utils.escapeHtml(log.message)}</span>
        `;

        container.insertBefore(entry, container.firstChild);

        // Limit entries
        while (container.children.length > 50) {
            container.removeChild(container.lastChild);
        }
    }
};

// --- ARIZONA MODULE ---
const ArizonaModule = {
    init: () => {
        // Bind events if needed, mostly handled by onclick in HTML or rewrite here
        // For now, exposing functions globally for HTML onclick compatibility is easier
        // But better to bind:
        window.selectArizonaTool = ArizonaModule.selectTool;
        window.askArizonaHelper = ArizonaModule.askHelper;
        window.generateComplaint = ArizonaModule.generateComplaint;
        window.generateLegend = ArizonaModule.generateLegend;
        window.checkRules = ArizonaModule.checkRules;
        window.calculateBusiness = ArizonaModule.calculateBusiness;
        window.calculateFaction = ArizonaModule.calculateFaction;
    },

    loadServers: async () => {
        // Placeholder for server loading
        const grid = document.getElementById('arizona-servers-grid');
        const loading = document.getElementById('arizona-loading');
        if (!grid) return;

        if (loading) loading.style.display = 'none';
        grid.style.display = 'grid';
        // In a real app, fetch servers here.
    },

    selectTool: (toolId, element) => {
        // UI Switching
        document.querySelectorAll('.arizona-tool-card').forEach(el => el.classList.remove('active'));
        if (element) element.classList.add('active');

        document.querySelectorAll('.arizona-workspace').forEach(el => el.style.display = 'none');
        const target = document.getElementById(`arizona-tool-${toolId}`);
        if (target) {
            target.style.display = 'block';
            target.classList.add('fade-in');
        }
    },

    // --- Tools Implementation ---
    askHelper: async () => {
        const input = document.getElementById('arizona-helper-input');
        const result = document.getElementById('arizona-helper-result');
        if (!input || !input.value.trim()) return Utils.showToast('Введите вопрос', 'error');

        result.style.display = 'block';
        result.textContent = 'Думаю... (эмуляция)';

        // Mock API call
        setTimeout(() => {
            result.innerHTML = `<strong>Ответ AI:</strong><br>Для вашего вопроса "${Utils.escapeHtml(input.value)}" рекомендуется обратиться к /help в игре.`;
        }, 1000);
    },

    generateComplaint: () => {
        const nick = document.getElementById('arizona-complaint-nick');
        const desc = document.getElementById('arizona-complaint-desc');
        const result = document.getElementById('arizona-complaint-result');

        if (!nick.value || !desc.value) return Utils.showToast('Заполните поля', 'error');

        result.style.display = 'block';
        const template = `
**Жалоба на игрока ${nick.value}**
1. Ваш игровой ник: [Ваш Ник]
2. Игровой ник нарушителя: ${nick.value}
3. Суть жалобы: ${desc.value}
4. Доказательства: [Ссылка]
5. Тайм-код нарушения: [Таймкод]
        `.trim();

        result.innerHTML = `<pre>${Utils.escapeHtml(template)}</pre><button class="btn btn-sm btn-primary mt-2" onclick="Utils.copyToClipboard(\`${template.replace(/`/g, '\\`')}\`)">Копировать</button>`;
    },

    // ... Other Arizona tools (simplified for brevity, can be expanded) 
    generateLegend: () => {
        const name = document.getElementById('arizona-legend-name').value;
        const age = document.getElementById('arizona-legend-age').value;
        const result = document.getElementById('arizona-legend-result');
        result.style.display = 'block';
        result.innerHTML = `Био для ${name}, ${age} лет... (Тут будет текст)`;
    },

    checkRules: () => {
        const q = document.getElementById('arizona-rules-input').value;
        const result = document.getElementById('arizona-rules-result');
        result.style.display = 'block';
        result.innerText = `Поиск правил по запросу: ${q}...`;
    },

    calculateBusiness: () => {
        const type = document.getElementById('calc-business-type').value;
        const level = parseInt(document.getElementById('calc-business-level').value) || 1;

        let baseIncome = 10000;
        if (type === 'casino') baseIncome = 1000000;
        if (type === '24/7') baseIncome = 50000;

        const income = baseIncome * level;

        document.getElementById('calc-biz-income').textContent = `$${income}`;
        document.getElementById('calc-biz-daily').textContent = `$${income * 24}`;
        document.getElementById('calc-biz-upgrade').textContent = `$${level * 5000000}`;
    },

    calculateFaction: () => {
        const rank = parseInt(document.getElementById('calc-faction-rank').value) || 1;
        const base = 50000;
        const salary = base + (rank * 10000);

        document.getElementById('calc-faction-salary').textContent = `$${salary}`;
        document.getElementById('calc-faction-paycheck').textContent = `$${Math.floor(salary / 2)}`; // Payday usually half hourly or full hourly logic
    }
};

// --- TEMP MAIL MODULE ---
const TempMailModule = {
    accounts: JSON.parse(localStorage.getItem('tm_accounts') || '[]'),
    activeIdx: parseInt(localStorage.getItem('tm_active_idx') || '0'),

    init: () => {
        window.createTempMail = TempMailModule.create;
        window.checkCurrentMail = TempMailModule.checkMail;
        window.deleteCurrentAccount = TempMailModule.deleteAccount;
        window.copyActiveEmail = () => Utils.copyToClipboard(TempMailModule.accounts[TempMailModule.activeIdx]?.email);
        window.closeReader = () => document.getElementById('tm-reader').style.display = 'none';

        if (TempMailModule.activeIdx >= TempMailModule.accounts.length) TempMailModule.activeIdx = 0;
    },

    save: () => {
        localStorage.setItem('tm_accounts', JSON.stringify(TempMailModule.accounts));
        localStorage.setItem('tm_active_idx', TempMailModule.activeIdx);
        TempMailModule.renderList();
    },

    renderList: () => {
        const list = document.getElementById('tm-accounts-list');
        if (!list) return; // Tab might not be active

        list.innerHTML = '';

        const content = document.getElementById('tm-content');
        const empty = document.getElementById('tm-empty-state');

        if (TempMailModule.accounts.length === 0) {
            if (empty) empty.style.display = 'flex';
            if (content) content.style.display = 'none';
            return;
        }

        if (empty) empty.style.display = 'none';
        if (content) content.style.display = 'flex';

        TempMailModule.accounts.forEach((acc, idx) => {
            const el = document.createElement('div');
            el.className = `account-item ${idx === TempMailModule.activeIdx ? 'active' : ''}`;
            el.textContent = acc.email;
            el.onclick = () => {
                TempMailModule.activeIdx = idx;
                TempMailModule.save();
                TempMailModule.checkMail();
            };
            list.appendChild(el);
        });

        const activeEmailEl = document.getElementById('tm-active-email');
        if (activeEmailEl && TempMailModule.accounts[TempMailModule.activeIdx]) {
            activeEmailEl.textContent = TempMailModule.accounts[TempMailModule.activeIdx].email;
        }
    },

    create: async () => {
        Utils.showToast('Создание...');
        try {
            const res = await fetch('/api/tempmail/create?count=1');
            const data = await res.json();
            if (data.error) throw new Error(data.error);

            const newAcc = { ...data[0], created: Date.now() };
            TempMailModule.accounts.unshift(newAcc);
            TempMailModule.activeIdx = 0;
            TempMailModule.save();
            Utils.showToast('Почта создана', 'success');
            TempMailModule.checkMail();
        } catch (e) {
            console.error(e);
            Utils.showToast('Ошибка: ' + e.message, 'error');
        }
    },

    checkMail: async (silent = false) => {
        const acc = TempMailModule.accounts[TempMailModule.activeIdx];
        if (!acc) return;

        if (!silent) {
            const btn = document.getElementById('tm-refresh-btn');
            if (btn) btn.innerHTML = '⌛ Check...';
        }

        try {
            const res = await fetch(`/api/tempmail/check?token=${acc.token}`);
            const msgs = await res.json();

            const btn = document.getElementById('tm-refresh-btn');
            if (btn) btn.innerHTML = '🔄 Обновить';

            const inbox = document.getElementById('tm-inbox-list');
            if (!inbox) return;

            inbox.innerHTML = '';
            if (msgs.length === 0) {
                inbox.innerHTML = '<div class="p-4 text-center op-5">Нет писем</div>';
            } else {
                msgs.forEach(msg => {
                    const el = document.createElement('div');
                    el.className = 'mail-item';
                    el.innerHTML = `<div><b>${Utils.escapeHtml(msg.from)}</b></div><div>${Utils.escapeHtml(msg.subject)}</div>`;
                    el.onclick = () => TempMailModule.openMail(msg.id, acc.token);
                    inbox.appendChild(el);
                });
            }

        } catch (e) {
            console.error(e);
            if (!silent) Utils.showToast('Ошибка проверки почты', 'error');
        }
    },

    openMail: async (id, token) => {
        Utils.showToast('Загрузка письма...');
        try {
            const res = await fetch(`/api/tempmail/read?token=${token}&id=${id}`);
            const data = await res.json();

            document.getElementById('tm-read-subject').innerText = data.subject;
            document.getElementById('tm-read-from').innerText = data.from;
            document.getElementById('tm-read-body').innerHTML = data.htmlBody || data.textBody;

            document.getElementById('tm-reader').style.display = 'block';
        } catch (e) {
            Utils.showToast('Ошибка чтения', 'error');
        }
    },

    deleteAccount: () => {
        if (!confirm('Удалить этот ящик?')) return;
        TempMailModule.accounts.splice(TempMailModule.activeIdx, 1);
        TempMailModule.activeIdx = 0;
        TempMailModule.save();
    }
};

// --- FAVORITES MODULE ---
const FavoritesModule = {
    data: JSON.parse(localStorage.getItem('favorites') || '{"monitors": [], "accounts": []}'),

    init: () => {
        window.toggleFavorite = FavoritesModule.toggle;
        window.removeMonitor = FavoritesModule.removeMonitor; // Proxy logic
        window.viewAccount = FavoritesModule.viewAccount; // Proxy logic
    },

    save: () => {
        localStorage.setItem('favorites', JSON.stringify(FavoritesModule.data));
    },

    toggle: (type, id) => {
        const list = FavoritesModule.data[type];
        const idx = list.indexOf(id);

        if (idx > -1) {
            list.splice(idx, 1);
            Utils.showToast('Удалено из избранного');
        } else {
            list.push(id);
            Utils.showToast('Добавлено в избранное', 'success');
        }
        FavoritesModule.save();

        // Reload current view if applicable
        if (type === 'monitors') FavoritesModule.loadMonitors();
        if (type === 'accounts') FavoritesModule.loadAccounts();
    },

    isFavorite: (type, id) => FavoritesModule.data[type].includes(id),

    loadMonitors: () => {
        // Implementation similar to original but clearer
        fetch('/api/monitors').then(r => r.json()).then(monitors => {
            const tbody = document.getElementById('favorites-monitors-body');
            if (!tbody) return;
            tbody.innerHTML = '';

            const favs = monitors.filter(m => FavoritesModule.isFavorite('monitors', m.id));
            if (favs.length === 0) {
                tbody.innerHTML = '<tr><td colspan="6" class="text-center p-4 op-5">Нет избранных</td></tr>';
                return;
            }

            favs.forEach(m => {
                tbody.innerHTML += `<tr>
                    <td>⭐</td>
                    <td>${m.status}</td>
                    <td>${Utils.escapeHtml(m.name)}</td>
                    <td>${Utils.escapeHtml(m.url)}</td>
                    <td><button class="btn btn-sm btn-danger" onclick="toggleFavorite('monitors', '${m.id}')">Удалить</button></td>
                 </tr>`;
            });
        });
    },

    loadAccounts: () => {
        fetch('/api/accounts').then(r => r.json()).then(accs => {
            const tbody = document.getElementById('favorites-accounts-body');
            if (!tbody) return;
            tbody.innerHTML = '';

            const favs = accs.filter(a => FavoritesModule.isFavorite('accounts', a.id));
            if (favs.length === 0) {
                tbody.innerHTML = '<tr><td colspan="6" class="text-center p-4 op-5">Нет избранных</td></tr>';
                return;
            }
            favs.forEach(a => {
                tbody.innerHTML += `<tr>
                    <td>⭐</td>
                    <td>${a.id}</td>
                    <td>${Utils.escapeHtml(a.preview)}</td>
                    <td><button class="btn btn-sm" onclick="viewAccount(${a.id})">🔍</button></td>
                </tr>`;
            });
        });
    },

    // Placeholder function for removing actual monitor (not just favorite)
    removeMonitor: async (id) => {
        if (!confirm('Удалить монитор?')) return;
        await fetch(`/api/monitors/remove/${id}`, { method: 'DELETE' });
        // Reload
        FavoritesModule.loadAllMonitors();
    },

    viewAccount: async (id) => {
        const res = await fetch(`/api/accounts/${id}`);
        const d = await res.json();
        // Basic alert for now, can be modal
        alert(JSON.stringify(d, null, 2));
    },

    loadAllMonitors: () => {
        // Load for the main Data tab
        const tbody = document.getElementById('monitors-body');
        if (!tbody) return;

        fetch('/api/monitors').then(r => r.json()).then(data => {
            tbody.innerHTML = '';
            data.forEach(m => {
                const isFav = FavoritesModule.isFavorite('monitors', m.id);
                tbody.innerHTML += `<tr>
                    <td onclick="toggleFavorite('monitors', '${m.id}')" style="cursor:pointer">${isFav ? '⭐' : '☆'}</td>
                    <td>${m.status === 'online' ? '🟢' : '🔴'}</td>
                    <td>${Utils.escapeHtml(m.name)}</td>
                    <td>${Utils.escapeHtml(m.url)}</td>
                    <td>
                        <button class="btn btn-sm btn-danger" onclick="removeMonitor('${m.id}')">Del</button>
                    </td>
                 </tr>`;
            });
        });
    },

    loadAllAccounts: () => {
        const tbody = document.getElementById('accounts-body');
        if (!tbody) return;

        fetch('/api/accounts').then(r => r.json()).then(data => {
            tbody.innerHTML = '';
            data.forEach(a => {
                const isFav = FavoritesModule.isFavorite('accounts', a.id);
                tbody.innerHTML += `<tr>
                    <td onclick="toggleFavorite('accounts', ${a.id})" style="cursor:pointer">${isFav ? '⭐' : '☆'}</td>
                    <td>${a.id}</td>
                    <td>${Utils.escapeHtml(a.preview)}</td>
                    <td>${a.added_by}</td>
                    <td><button class="btn btn-sm" onclick="viewAccount(${a.id})">View</button></td>
                 </tr>`;
            });
        });
    }
};

// Expose Utils if needed
window.showToast = Utils.showToast;
