from flask import Flask, render_template, jsonify, request, session, redirect, url_for
from flask_socketio import SocketIO, emit
import utils
import psutil
import time
import requests
from datetime import datetime, timedelta
import threading
import os

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'super-secret-key-change-me-123')
socketio = SocketIO(app, cors_allowed_origins="*")

# --- DISCORD OAUTH2 CONFIG ---
CLIENT_ID = os.environ.get('CLIENT_ID', '1211664015646916670')
CLIENT_SECRET = os.environ.get('CLIENT_SECRET', 'ykwvV-Jg6WaWey-bsejTTEPTsho2NiAd')
# Автоматически определяем URL в зависимости от окружения
REDIRECT_URI = os.environ.get('REDIRECT_URI', 'http://localhost:5000/callback')
FOUNDERS = [os.environ.get('FOUNDER_USERNAME', 'kompd')] # Usernames or IDs with God Mode permission

API_BASE_URL = "https://discord.com/api"
AUTHORIZATION_BASE_URL = API_BASE_URL + "/oauth2/authorize"
TOKEN_URL = API_BASE_URL + "/oauth2/token"

# Bot status tracking
bot_status = {
    'running': True,
    'start_time': time.time(),
    'servers': 0,
    'users': 0,
    'commands_today': 0
}

# Logs
logs = []
MAX_LOGS = 100

def add_log(level, message):
    log_entry = {
        'timestamp': datetime.now().strftime('%H:%M:%S'),
        'level': level,
        'message': message
    }
    logs.insert(0, log_entry)
    if len(logs) > MAX_LOGS:
        logs.pop()
    socketio.emit('log_new', log_entry)

@app.route('/')
def index():
    # Landing page with auth_url
    user = session.get('user', None)
    
    # Generate OAuth URL for login button
    params = {
        'client_id': CLIENT_ID,
        'redirect_uri': REDIRECT_URI,
        'response_type': 'code',
        'scope': 'identify'
    }
    auth_url = requests.Request('GET', AUTHORIZATION_BASE_URL, params=params).prepare().url
    
    return render_template('landing.html', user=user, auth_url=auth_url)

@app.route('/dashboard')
def dashboard():
    # Dashboard page - requires authentication
    user = session.get('user', None)
    
    # Generate OAuth URL for login button (in case not logged in)
    params = {
        'client_id': CLIENT_ID,
        'redirect_uri': REDIRECT_URI,
        'response_type': 'code',
        'scope': 'identify'
    }
    auth_url = requests.Request('GET', AUTHORIZATION_BASE_URL, params=params).prepare().url
    
    return render_template('index.html', user=user, auth_url=auth_url)

# --- ADMIN API ---
@app.route('/api/admin/set_prefix', methods=['POST'])
def api_set_prefix():
    if 'user' not in session: return jsonify({'error': 'Auth needed'}), 401
    user = session['user']
    is_founder = user['username'] in FOUNDERS or str(user['id']) in FOUNDERS
    if not is_founder: return jsonify({'error': 'Forbidden'}), 403
    
    data = request.json
    uid = data.get('user_id')
    prefix = data.get('prefix')
    
    if utils.set_prefix(uid, prefix):
        add_log('warning', f"Prefix changed for {uid} to {prefix} by {user['username']}")
        return jsonify({'success': True})
    return jsonify({'error': 'Failed'})

@app.route('/api/admin/prefixes')
def api_get_prefixes():
    if 'user' not in session: return jsonify({'error': 'Auth needed'}), 401
    user = session['user']
    is_founder = user['username'] in FOUNDERS or str(user['id']) in FOUNDERS
    if not is_founder: return jsonify({'error': 'Forbidden'}), 403
    return jsonify(utils.get_all_prefixes())


@app.route('/callback')
def callback():
    code = request.args.get('code')
    if not code:
        return "Error: No code provided. <a href='/'>Retry</a>", 400
    
    # Exchange code for token
    data = {
        'client_id': CLIENT_ID,
        'client_secret': CLIENT_SECRET,
        'grant_type': 'authorization_code',
        'code': code,
        'redirect_uri': REDIRECT_URI
    }
    headers = {'Content-Type': 'application/x-www-form-urlencoded'}
    
    try:
        r = requests.post(TOKEN_URL, data=data, headers=headers)
        r.raise_for_status()
        token_data = r.json()
        access_token = token_data['access_token']
        
        # Get User Info
        user_headers = {'Authorization': f'Bearer {access_token}'}
        r_user = requests.get(f"{API_BASE_URL}/users/@me", headers=user_headers)
        r_user.raise_for_status()
        user_data = r_user.json()
        
        session['user'] = {
            'id': user_data['id'],
            'username': user_data['username'],
            'avatar': f"https://cdn.discordapp.com/avatars/{user_data['id']}/{user_data['avatar']}.png" if user_data.get('avatar') else "https://cdn.discordapp.com/embed/avatars/0.png",
            'is_founder': user_data['username'] in FOUNDERS or user_data['id'] in FOUNDERS
        }
        return redirect(url_for('index'))
    except Exception as e:
        return f"Auth Error: {e}. Keys valid? Redirect URI match?<br><a href='/'>Retry</a>", 400

@app.route('/logout')
def logout():
    session.pop('user', None)
    return redirect(url_for('index'))

# --- API ROUTES ---

@app.route('/api/stats')
def api_stats():
    accounts = utils.get_all_accounts()
    monitors = utils.get_monitors()
    return jsonify({
        'total_accounts': len(accounts),
        'total_monitors': len(monitors),
        'monitors_online': sum(1 for m in monitors if m.get('status') == 'online'),
        'monitors_offline': sum(1 for m in monitors if m.get('status') == 'offline')
    })

@app.route('/api/bot/status')
def api_bot_status():
    uptime = int(time.time() - bot_status['start_time'])
    try:
        cpu = psutil.cpu_percent(interval=None) or 0
        mem = psutil.virtual_memory()
        mem_used = mem.used // (1024 * 1024)
        mem_pct = mem.percent
    except:
        cpu = 0
        mem_used = 0
        mem_pct = 0
        
    return jsonify({
        'running': bot_status['running'],
        'uptime': uptime,
        'servers': bot_status['servers'],
        'users': bot_status['users'],
        'commands_today': bot_status['commands_today'],
        'cpu_percent': cpu,
        'memory_used': mem_used,
        'memory_percent': mem_pct
    })

@app.route('/api/bot/control/<action>', methods=['POST'])
def api_bot_control(action):
    # Require Auth for control
    if 'user' not in session: return jsonify({'success': False, 'message': 'Unauthorized'}), 401
    
    username = session['user']['username']
    if action == 'stop':
        bot_status['running'] = False
        add_log('warning', f'Bot stopped by {username}')
        return jsonify({'success': True, 'message': 'Bot stopped'})
    elif action == 'start':
        bot_status['running'] = True
        bot_status['start_time'] = time.time()
        add_log('info', f'Bot started by {username}')
        return jsonify({'success': True, 'message': 'Bot started'})
    elif action == 'restart':
        bot_status['start_time'] = time.time()
        add_log('warning', f'Bot restarted by {username}')
        return jsonify({'success': True, 'message': 'Bot restarted'})
    return jsonify({'success': False, 'message': 'Unknown action'})

@app.route('/api/logs')
def api_logs():
    return jsonify(logs[:50])

@app.route('/api/monitors')
def api_monitors(): return jsonify(utils.get_monitors())

@app.route('/api/monitors/add', methods=['POST'])
def api_add_monitor():
    if 'user' not in session: return jsonify({'success': False}), 401
    data = request.json
    res, msg = utils.add_monitor(data.get('url'), data.get('name'))
    if res:
        add_log('info', f"Monitor added: {data.get('name')}")
        return jsonify({'success': True})
    return jsonify({'success': False, 'error': msg}), 400

@app.route('/api/monitors/remove/<id>', methods=['DELETE'])
def api_remove_monitor(id):
    if 'user' not in session: return jsonify({'success': False}), 401
    if utils.remove_monitor(id):
        add_log('info', f"Monitor removed: {id}")
        return jsonify({'success': True})
    return jsonify({'success': False})

@app.route('/api/monitors/<id>/logs')
def api_monitor_logs(id):
    """Получить логи конкретного монитора"""
    if 'user' not in session: return jsonify({'error': 'Auth needed'}), 401
    logs = utils.get_monitor_logs(id)
    return jsonify(logs)

@app.route('/api/monitors/<id>/stats')
def api_monitor_stats(id):
    """Получить статистику монитора"""
    if 'user' not in session: return jsonify({'error': 'Auth needed'}), 401
    stats = utils.get_monitor_stats(id)
    if stats:
        return jsonify(stats)
    return jsonify({'error': 'Monitor not found'}), 404

@app.route('/api/monitors/<id>/clear-logs', methods=['POST'])
def api_clear_monitor_logs(id):
    """Очистить логи монитора"""
    if 'user' not in session: return jsonify({'success': False}), 401
    if utils.clear_monitor_logs(id):
        add_log('info', f"Monitor logs cleared: {id}")
        return jsonify({'success': True})
    return jsonify({'success': False})


@app.route('/api/accounts')
def api_accounts(): return jsonify(utils.get_all_accounts())

@app.route('/api/accounts/<int:id>')
def api_account(id): 
    # Placeholder for getting specific account
    accs = utils.get_all_accounts()
    acc = next((a for a in accs if a['id'] == id), None)
    return jsonify(acc) if acc else ({'error':'Not found'}, 404)

@app.route('/api/accounts/<int:id>', methods=['DELETE'])
def api_delete_account(id):
    if 'user' not in session: return jsonify({'success': False}), 401
    if utils.delete_account(id):
        add_log('info', f"Account deleted: {id}")
        return jsonify({'success': True})
    return jsonify({'success': False})

# Temp Mail
@app.route('/api/tempmail/create')
def api_tm_create():
    if 'user' not in session: return jsonify({'error': 'Auth needed'}), 401
    try:
        r = requests.get(f"{utils.TEMP_MAIL_API}?f=get_email_address", headers=utils.HEADERS)
        if r.status_code == 200:
            d = r.json()
            return jsonify([{"email": d['email_addr'], "token": d['sid_token']}])
    except: pass
    return jsonify(utils.get_mock_email(1))

@app.route('/api/tempmail/check')
def api_tm_check():
    # Auth probably not needed for polling to avoid spamming 401s if session expires while on page
    # But for creating, yes.
    token = request.args.get('token')
    if not token: return jsonify([])
    try:
        r = requests.get(f"{utils.TEMP_MAIL_API}?f=check_email&sid_token={token}&seq=0", headers=utils.HEADERS)
        if r.status_code == 200:
            msgs = r.json().get('list', [])
            return jsonify([{"id": m['mail_id'], "from": m['mail_from'], "subject": m['mail_subject'], "date": m['mail_date']} for m in msgs])
    except: pass
    return jsonify([])

@app.route('/api/tempmail/read')
def api_tm_read():
    if 'user' not in session: return jsonify({'error': 'Auth needed'}), 401
    token = request.args.get('token')
    mid = request.args.get('id')
    try:
        r = requests.get(f"{utils.TEMP_MAIL_API}?f=fetch_email&sid_token={token}&email_id={mid}", headers=utils.HEADERS)
        if r.status_code == 200:
            d = r.json()
            return jsonify({
                "id": d['mail_id'], "from": d['mail_from'], "subject": d['mail_subject'], "date": d['mail_date'],
                "textBody": d.get('mail_body',''), "htmlBody": d.get('mail_body','')
            })
    except: pass
    return jsonify(utils.get_mock_content(mid))


# --- AI CHAT API ---
try:
    import google.generativeai as genai
    GEMINI_API_KEY = os.environ.get('GEMINI_API_KEY')
    if GEMINI_API_KEY:
        genai.configure(api_key=GEMINI_API_KEY)
        AI_MODEL = genai.GenerativeModel('gemini-1.5-flash')
        print("[+] Gemini AI initialized for Web API!")
    else:
        AI_MODEL = None
        print("[!] GEMINI_API_KEY not set. AI Chat disabled.")
except ImportError:
    AI_MODEL = None
    print("[!] google-generativeai not installed. AI Chat disabled.")

# Store chat sessions per user
AI_WEB_SESSIONS = {}

@app.route('/api/ai/chat', methods=['POST'])
def api_ai_chat():
    """AI Chat API endpoint"""
    if not AI_MODEL:
        return jsonify({
            'success': False, 
            'error': 'AI не настроен. Добавьте GEMINI_API_KEY в переменные окружения.'
        })
    
    data = request.json
    message = data.get('message', '').strip()
    
    if not message:
        return jsonify({'success': False, 'error': 'Пустое сообщение'})
    
    # Get or create session for user
    user_id = session.get('user', {}).get('id', 'anonymous')
    
    if user_id not in AI_WEB_SESSIONS:
        AI_WEB_SESSIONS[user_id] = AI_MODEL.start_chat(history=[])
    
    chat = AI_WEB_SESSIONS[user_id]
    
    try:
        response = chat.send_message(message)
        answer = response.text
        
        # Limit response length
        if len(answer) > 8000:
            answer = answer[:8000] + "\n\n... (ответ обрезан)"
        
        add_log('info', f"AI Chat: {message[:50]}...")
        
        return jsonify({
            'success': True,
            'response': answer
        })
        
    except Exception as e:
        error_msg = str(e)
        add_log('error', f"AI Error: {error_msg[:100]}")
        return jsonify({
            'success': False,
            'error': error_msg[:200]
        })

@app.route('/api/ai/clear', methods=['POST'])
def api_ai_clear():
    """Clear AI chat history for user"""
    user_id = session.get('user', {}).get('id', 'anonymous')
    
    if user_id in AI_WEB_SESSIONS:
        del AI_WEB_SESSIONS[user_id]
    
    return jsonify({'success': True})


# Simulation Thread
def simulate():
    while True:
        time.sleep(5)
        bot_status['servers'] = 10 + int(time.time() % 7)
        bot_status['users'] = 1200 + int(time.time() % 123)
        bot_status['commands_today'] += 1
        if int(time.time()) % 15 == 0:
            # Random log
            import random
            events = ['User joined', 'Command !help', 'Backup started', 'Error in module X', 'Server restart']
            lvls = ['info', 'info', 'info', 'warning', 'error']
            add_log(random.choice(lvls), random.choice(events))

threading.Thread(target=simulate, daemon=True).start()

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    print(f"Server running on http://0.0.0.0:{port}")
    socketio.run(app, host='0.0.0.0', port=port, debug=False, allow_unsafe_werkzeug=True)

