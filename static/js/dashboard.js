/**
 * Dashboard Pro - Main JavaScript Logic
 * Rewritten for stability and performance
 */

document.addEventListener('DOMContentLoaded', () => {
    console.log('Dashboard Initializing...');

    // Initialize Modules
    try {
        if (typeof TabsModule !== 'undefined') TabsModule.init();
        if (typeof WebSocketModule !== 'undefined') WebSocketModule.init();
        if (typeof ArizonaModule !== 'undefined') ArizonaModule.init();
        if (typeof UIModule !== 'undefined') UIModule.init();
    } catch (e) {
        console.error('Critical Init Error:', e);
        // Fallback for UI if Utils is available
        if (typeof Utils !== 'undefined') {
            Utils.showToast('Ошибка инициализации: ' + e.message, 'error');
        }
    }
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
            try {
                const savedTheme = localStorage.getItem('theme') || 'dark';
                if (savedTheme === 'light') document.body.classList.add('light-theme');
            } catch (e) { console.warn('Theme load error:', e); }

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
        try {
            localStorage.setItem('theme', isLight ? 'light' : 'dark');
        } catch (e) { console.warn('Theme save error:', e); }
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
            case 'arizonaai':
                ArizonaModule.loadServers();
                break;
            case 'profile':
                // Load profile specific stuff if needed
                break;
        }
    }
};

// Expose globally for inline onclicks
window.switchTab = TabsModule.switchTab;

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

        if (toolId === 'news') ArizonaModule.loadNews();
    },

    loadNews: async () => {
        const grid = document.getElementById('arizona-news-grid');
        const loading = document.getElementById('arizona-news-loading');

        // Don't reload if already populated (optional, but good for perf)
        if (grid.children.length > 0) return;

        grid.style.display = 'none';
        loading.style.display = 'block';

        try {
            const res = await fetch('/api/arizona/news');
            const data = await res.json();

            loading.style.display = 'none';
            grid.style.display = 'grid';

            if (data.success && data.news.length > 0) {
                grid.innerHTML = data.news.map(item => `
                    <div class="news-card" style="background:rgba(255,255,255,0.05); border-radius:15px; overflow:hidden; transition:transform 0.3s;" onmouseover="this.style.transform='translateY(-5px)'" onmouseout="this.style.transform='translateY(0)'">
                        <img src="${item.image}" style="width:100%; height:160px; object-fit:cover;">
                        <div style="padding:15px;">
                            <div style="font-size:12px; opacity:0.7; margin-bottom:5px;">
                                <span style="background:${item.tag === 'Обновление' ? '#ef4444' : '#3b82f6'}; padding:2px 8px; border-radius:4px; color:white;">${item.tag}</span>
                                <span style="margin-left:8px;">${item.date}</span>
                            </div>
                            <h4 style="margin:10px 0; font-size:16px;">${item.title}</h4>
                            <p style="font-size:13px; opacity:0.8; line-height:1.4;">${item.summary}</p>
                            <a href="${item.url}" target="_blank" style="display:inline-block; margin-top:10px; color:#60a5fa; font-size:13px;">Читать далее &rarr;</a>
                        </div>
                    </div>
                `).join('');
            } else {
                grid.innerHTML = `<div style="grid-column:1/-1; text-align:center; padding:20px;">Новостей пока нет или ошибка загрузки.</div>`;
            }
        } catch (e) {
            loading.style.display = 'none';
            grid.style.display = 'block';
            grid.innerHTML = `<div style="color:#ff6b6b; text-align:center;">Ошибка загрузки новостей: ${e.message}</div>`;
        }
    },

    // --- Tools Implementation ---
    askHelper: async () => {
        const input = document.getElementById('arizona-helper-input');
        const result = document.getElementById('arizona-helper-result');
        if (!input || !input.value.trim()) return Utils.showToast('Введите вопрос', 'error');

        result.style.display = 'block';
        result.innerHTML = '<div class="loading-spinner"></div> Думаю...';

        try {
            const res = await fetch('/api/arizona/helper', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ question: input.value })
            });
            const data = await res.json();

            if (data.success) {
                result.innerHTML = `<strong>Ответ (${data.source === 'database' ? 'База' : 'AI'}):</strong><br>${Utils.escapeHtml(data.response).replace(/\n/g, '<br>')}`;
            } else {
                result.innerHTML = `<span style="color:#ff6b6b">Ошибка: ${data.error}</span>`;
            }
        } catch (e) {
            result.innerHTML = `<span style="color:#ff6b6b">Ошибка сети: ${e.message}</span>`;
        }
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

    checkRules: async () => {
        const q = document.getElementById('arizona-rules-input').value;
        const result = document.getElementById('arizona-rules-result');
        if (!q.trim()) return Utils.showToast('Введите запрос', 'error');

        result.style.display = 'block';
        result.innerHTML = '<div class="loading-spinner"></div> Поиск правил...';

        try {
            const res = await fetch('/api/arizona/rules', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ question: q })
            });
            const data = await res.json();

            if (data.success) {
                result.innerHTML = `
                    <div class="arizona-result">
                        <h3>Результат поиска:</h3>
                        <div class="rules-content">${Utils.escapeHtml(data.response).replace(/\n/g, '<br>')}</div>
                        <div style="font-size:0.8em; opacity:0.7; margin-top:10px;">Источник: ${data.source === 'database' ? 'Локальная база' : 'AI Assistant'}</div>
                    </div>`;
            } else {
                result.innerHTML = `<span style="color:#ff6b6b">Ошибка: ${data.error}</span>`;
            }
        } catch (e) {
            result.innerHTML = `<span style="color:#ff6b6b">Ошибка сети: ${e.message}</span>`;
        }
    },

    showRulesList: async () => {
        const result = document.getElementById('arizona-rules-result');
        result.style.display = 'block';
        result.innerHTML = '<div class="loading-spinner"></div> Загрузка списка...';

        try {
            const res = await fetch('/api/arizona/rules_list');
            const data = await res.json();

            if (data.success) {
                result.innerHTML = `
                    <div class="arizona-result">
                        <div class="rules-content">${Utils.escapeHtml(data.response).replace(/\n/g, '<br>')}</div>
                    </div>`;
            } else {
                result.innerHTML = `<span style="color:#ff6b6b">Ошибка: ${data.error}</span>`;
            }
        } catch (e) {
            result.innerHTML = `<span style="color:#ff6b6b">Ошибка сети: ${e.message}</span>`;
        }
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


// --- TEMP MAIL MODULE (Stub/Placeholder to fix ReferenceError) ---
const TempMailModule = {
    accounts: [],
    activeIdx: 0,
    init: () => { console.log("TempMail Stub Initialized"); }, // Add real logic if code is found
    create: () => { Utils.showToast('Функция временно отключена для отладки', 'warning'); },
    checkMail: () => { Utils.showToast('Функция временно отключена для отладки', 'warning'); },
    deleteAccount: () => { Utils.showToast('Функция временно отключена для отладки', 'warning'); },
    save: () => { }
};



// --- AI CHAT MODULE ---
const AIChatModule = {
    send: async () => {
        const input = document.getElementById('ai-input');
        const container = document.getElementById('ai-messages');
        const msg = input.value.trim();
        if (!msg) return;

        // User Msg
        AIChatModule.appendMsg(msg, 'user');
        input.value = '';

        // Loading
        const loadId = AIChatModule.appendMsg('Печатает...', 'ai', true);

        try {
            const res = await fetch('/api/ai/chat', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ message: msg })
            });
            const data = await res.json();

            // Remove loading
            const loadEl = document.getElementById(loadId);
            if (loadEl) loadEl.remove();

            if (data.success) {
                AIChatModule.appendMsg(data.response, 'ai');
            } else {
                AIChatModule.appendMsg(`Ошибка: ${data.error}`, 'ai error');
            }
        } catch (e) {
            AIChatModule.appendMsg('Ошибка соединения', 'ai error');
        }
    },

    appendMsg: (text, type, isLoading = false) => {
        const container = document.getElementById('ai-messages');
        if (!container) return;
        const div = document.createElement('div');
        const id = 'msg-' + Date.now();
        div.id = id;
        div.className = `ai-message ${type} ${isLoading ? 'loading' : ''}`;
        div.innerHTML = `<div class="ai-avatar">${type === 'user' ? '👤' : '🤖'}</div><div class="ai-text">${Utils.escapeHtml(text).replace(/\n/g, '<br>')}</div>`;
        container.appendChild(div);
        container.scrollTop = container.scrollHeight;
        return id;
    },

    clear: async () => {
        if (!confirm('Очистить историю чата?')) return;
        document.getElementById('ai-messages').innerHTML = ''; // Keep welcome?
        await fetch('/api/ai/clear', { method: 'POST' });
        Utils.showToast('Чат очищен', 'success');
    },

    quickAction: (text) => {
        const input = document.getElementById('ai-input');
        input.value = text + ' ';
        input.focus();
    }
};

// --- ADMIN MODULE (God Mode) ---
const AdminModule = {
    setPrefix: async () => {
        const uid = document.getElementById('gm-user-id').value;
        const prefix = document.getElementById('gm-prefix').value;
        if (!uid || !prefix) return Utils.showToast('Заполните поля', 'error');

        try {
            const res = await fetch('/api/admin/set_prefix', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ user_id: uid, prefix: prefix })
            });
            const data = await res.json();
            if (data.success) Utils.showToast('Префикс установлен', 'success');
            else Utils.showToast('Ошибка', 'error');
        } catch (e) {
            Utils.showToast('Ошибка сети', 'error');
        }
    }
};

// --- MONITOR LOGS MODULE ---
const MonitorLogsModule = {
    currentId: null,

    show: async (id) => {
        MonitorLogsModule.currentId = id;
        const modal = document.getElementById('monitorLogsModal');
        const content = document.getElementById('monitor-logs-content');
        if (modal) modal.style.display = 'block';
        if (content) content.innerHTML = 'Загрузка...';

        try {
            const res = await fetch(`/api/monitors/${id}/logs`);
            const logs = await res.json();
            if (content) {
                content.innerHTML = logs.map(l => `<div>[${l.time}] ${l.status} (${l.code})</div>`).join('') || 'Нет логов';
            }
        } catch (e) {
            if (content) content.innerHTML = 'Ошибка загрузки';
        }
    },

    close: () => {
        const modal = document.getElementById('monitorLogsModal');
        if (modal) modal.style.display = 'none';
        MonitorLogsModule.currentId = null;
    },

    clear: async () => {
        if (!MonitorLogsModule.currentId) return;
        try {
            await fetch(`/api/monitors/${MonitorLogsModule.currentId}/clear-logs`, { method: 'POST' });
            Utils.showToast('Логи очищены');
            MonitorLogsModule.show(MonitorLogsModule.currentId); // Reload
        } catch (e) { }
    }
};

// --- EXPOSE GLOBALLY ---
// Utils
window.showToast = Utils.showToast;
// Tabs
window.switchTab = TabsModule.switchTab;
// Temp Mail
window.createTempMail = TempMailModule.create;
window.checkCurrentMail = TempMailModule.checkMail;
window.deleteCurrentAccount = TempMailModule.deleteAccount;
window.copyActiveEmail = () => Utils.copyToClipboard(TempMailModule.accounts[TempMailModule.activeIdx]?.email);
window.closeReader = () => document.getElementById('tm-reader').style.display = 'none';
window.clearHistory = () => {
    if (confirm('Очистить историю?')) {
        TempMailModule.accounts = [];
        TempMailModule.activeIdx = 0;
        TempMailModule.save();
        Utils.showToast('История очищена');
    }
};
// Favorites / Data
window.toggleFavorite = FavoritesModule.toggle;
window.removeMonitor = FavoritesModule.removeMonitor;
window.viewAccount = FavoritesModule.viewAccount;
window.addMonitor = async () => {
    const url = document.getElementById('monitor-url').value;
    const name = document.getElementById('monitor-name').value;
    if (!url) return Utils.showToast('URL обязателен');
    const res = await fetch('/api/monitors/add', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ url, name })
    });
    const d = await res.json();
    if (d.success) { Utils.showToast('Монитор добавлен'); FavoritesModule.loadAllMonitors(); }
    else Utils.showToast(d.error || 'Ошибка', 'error');
};
window.exportData = () => window.location.href = '/api/backup'; // Assuming backup route
// Arizona
window.selectArizonaTool = ArizonaModule.selectTool;
window.askArizonaHelper = ArizonaModule.askHelper;
window.generateComplaint = ArizonaModule.generateComplaint;
window.generateLegend = ArizonaModule.generateLegend;
window.checkRules = ArizonaModule.checkRules;
window.showRulesList = ArizonaModule.showRulesList;
window.calculateBusiness = ArizonaModule.calculateBusiness;
window.calculateFaction = ArizonaModule.calculateFaction;
// Control
window.controlBot = ControlModule.controlBot;
// AI Chat
window.sendAiMessage = AIChatModule.send;
window.clearAiChat = AIChatModule.clear;
window.aiQuickAction = AIChatModule.quickAction;
// Admin
window.godSetPrefix = AdminModule.setPrefix;
// Monitor Logs
window.showMonitorLogs = MonitorLogsModule.show; // Need to check if html uses this
window.closeMonitorLogsModal = MonitorLogsModule.close;
window.clearMonitorLogs = MonitorLogsModule.clear;
