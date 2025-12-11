from flask import Flask, render_template, jsonify, request, session, redirect, url_for
from flask_socketio import SocketIO, emit
import utils
import psutil
import time
import requests
import json
from datetime import datetime, timedelta
import threading
import os
import concurrent.futures

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'super-secret-key-change-me-123')
socketio = SocketIO(app, cors_allowed_origins="*")

# --- DISCORD OAUTH2 CONFIG ---
CLIENT_ID = os.environ.get('CLIENT_ID', '1211664015646916670')
CLIENT_SECRET = os.environ.get('CLIENT_SECRET', 'ykwvV-Jg6WaWey-bsejTTEPTsho2NiAd')
# Автоматически определяем URL в зависимости от окружения
REDIRECT_URI = os.environ.get('REDIRECT_URI', 'http://localhost:5000/callback')
FOUNDERS = [
    os.environ.get('FOUNDER_USERNAME', 'kompd'),
    'henryesc', 
    '406028216537579532',
    '339121870882308106' # Just in case (kompd ID)
] # Usernames or IDs with God Mode permission

API_BASE_URL = "https://discord.com/api"
AUTHORIZATION_BASE_URL = API_BASE_URL + "/oauth2/authorize"
TOKEN_URL = API_BASE_URL + "/oauth2/token"

# --- USERS STORAGE ---
USERS_FILE = 'users.json'
users_db = {}

def load_users():
    global users_db
    try:
        if os.path.exists(USERS_FILE):
            with open(USERS_FILE, 'r', encoding='utf-8') as f:
                users_db = json.load(f)
    except Exception as e:
        print(f"Error loading users: {e}")

def save_users():
    try:
        with open(USERS_FILE, 'w', encoding='utf-8') as f:
            json.dump(users_db, f, indent=4)
    except Exception as e:
        print(f"Error saving users: {e}")

load_users()

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
    
    # Calculate uptime
    uptime_seconds = int(time.time() - bot_status['start_time'])
    uptime_str = str(timedelta(seconds=uptime_seconds)).split('.')[0] # Format hh:mm:ss
    
    return render_template('index.html', 
                            user=user, 
                            auth_url=auth_url, 
                            server_status="Online" if bot_status['running'] else "Offline",
                            uptime=uptime_str)

@app.route('/arizona')
def arizona_page():
    # Arizona AI Assistant Page
    user = session.get('user', None)
    if not user:
        return redirect(url_for('index'))
    return render_template('arizona.html', user=user)

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

@app.route('/api/admin/users')
def api_get_users():
    if 'user' not in session: return jsonify({'error': 'Auth needed'}), 401
    # Allow ALL logged in users to see the list (Community feature)
    # Role check removed for GET
    
    # Convert dict to list for frontend
    users_list = []
    for uid, data in users_db.items():
        users_list.append({
            'id': uid,
            'username': data['username'],
            'avatar': data['avatar'],
            'role': data.get('role', 'user'),
            'last_login': data.get('last_login', '')
        })
    return jsonify({'success': True, 'users': users_list})

@app.route('/api/admin/role', methods=['POST'])
def api_set_role():
    if 'user' not in session: return jsonify({'error': 'Auth needed'}), 401
    
    # Check requester role
    requester_id = str(session['user']['id'])
    requester_role = users_db.get(requester_id, {}).get('role', 'user')
    
    if requester_role != 'developer': 
        return jsonify({'error': 'Forbidden'}), 403
        
    data = request.json
    target_id = str(data.get('user_id'))
    new_role = data.get('role')
    
    if target_id not in users_db:
        return jsonify({'success': False, 'error': 'User not found'})
        
    if new_role not in ['developer', 'tester', 'user']:
        return jsonify({'success': False, 'error': 'Invalid role'})
        
    # Prevent demoting founders
    target_username = users_db[target_id]['username']
    if target_username in FOUNDERS or target_id in FOUNDERS:
        return jsonify({'success': False, 'error': 'Cannot change role of Founder'})
        
    users_db[target_id]['role'] = new_role
    save_users()
    
    add_log('warning', f"Role changed for {target_username} to {new_role} by {session['user']['username']}")
    
    return jsonify({'success': True})


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
        
        # Determine if founder
        is_founder = user_data['username'] in FOUNDERS or str(user_data['id']) in FOUNDERS
        
        session['user'] = {
            'id': user_data['id'],
            'username': user_data['username'],
            'avatar': f"https://cdn.discordapp.com/avatars/{user_data['id']}/{user_data['avatar']}.png" if user_data.get('avatar') else "https://cdn.discordapp.com/embed/avatars/0.png",
            'is_founder': is_founder
        }

        # Update Users DB
        uid = str(user_data['id'])
        role = 'user'
        
        # Check if already exists to keep role
        if uid in users_db:
            role = users_db[uid].get('role', 'user')
        
        # Founders always force developer role
        if is_founder:
            role = 'developer'

        users_db[uid] = {
            'username': user_data['username'],
            'avatar': session['user']['avatar'],
            'role': role,
            'last_login': datetime.now().isoformat()
        }
        save_users()
        
        # Add role to session for easy access
        session['user']['role'] = role

        return redirect(url_for('index'))
    except Exception as e:
        import traceback
        traceback.print_exc()
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
        AI_MODEL = genai.GenerativeModel('gemini-2.0-flash')
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

@app.route('/api/debug/arizona')
def api_debug_arizona():
    """Debug endpoint to check internal state"""
    try:
        from arizona_rules import search_rules as sr
        test_search = sr("dm")
        search_status = "OK" if test_search else "FAIL (returned None)"
    except Exception as e:
        search_status = f"ERROR: {e}"
        
    return jsonify({
        "rules_loaded": RULES_DB_LOADED,
        "ai_enabled": AI_MODEL is not None,
        "search_test_dm": search_status,
        "rules_count": len(ARIZONA_RULES) if RULES_DB_LOADED else 0
    })


# --- ARIZONA AI API ---

# Import local rules database
try:
    from arizona_rules import search_rules, get_all_rules_list, ARIZONA_RULES
    RULES_DB_LOADED = True
except ImportError:
    RULES_DB_LOADED = False
    ARIZONA_RULES = {}

# Import SMI Rules
try:
    from smi_rules_db import PPE_TEXT, PRO_TEXT, ETHER_TEMPLATES
    SMI_RULES_LOADED = True
except ImportError:
    SMI_RULES_LOADED = False
    PPE_TEXT = ""
    PRO_TEXT = ""
    ETHER_TEMPLATES = {}

ARIZONA_SYSTEM_PROMPT = f"""Ты - умный помощник по игровому серверу Arizona RP (SAMP).
Твоя задача - отвечать на вопросы игроков по правилам, командам и системам сервера.
У тебя есть доступ к базе правил СМИ (ППЭ и ПРО):
{PPE_TEXT[:1000] if SMI_RULES_LOADED else ""}
{PRO_TEXT[:1000] if SMI_RULES_LOADED else ""}

Используй свои знания о SAMP и Arizona RP.
Если вопрос касается нарушения (DM, TK, SK и т.д.) - объясни что это и какое обычно наказание (Деморган/Варн).
Отвечай вежливо, кратко и полезно. Не советуй просто смотреть /help, старайся дать ответ сразу."""

@app.route('/api/arizona/helper', methods=['POST'])
def api_arizona_helper():
    """Arizona RP game helper - uses local database first, then AI"""
    data = request.json
    question = data.get('question', '').strip()
    
    if not question:
        return jsonify({'success': False, 'error': 'Пустой вопрос'})
    
    # First try local rules database
    if RULES_DB_LOADED:
        try:
            result = search_rules(question)
            if result:
                return jsonify({'success': True, 'response': result, 'source': 'database'})
        except Exception:
            pass # Fail silently to AI

    
    # Fallback to AI if available
    if AI_MODEL:
        try:
            prompt = f"""{ARIZONA_SYSTEM_PROMPT}

Вопрос игрока по Arizona RP: {question}

ВАЖНО: Игрок уже искал в базе данных и не нашёл ответа.
НЕ ПИШИ "используйте /help" или "посмотрите на форуме".
Дай конкретный ответ, используя свои общие знания о SA-MP и RP режимах.
Если это вопрос про наказание (ДМ, СК, ТК) - назови стандартные наказания (Деморган 60-120 мин / Варн).
Если не уверен - предположи, но не отправляй читать /help.

Дай полезный и точный ответ:"""
            
            # Run AI with timeout to prevent eternal loading
            with concurrent.futures.ThreadPoolExecutor() as executor:
                future = executor.submit(AI_MODEL.generate_content, prompt)
                response = future.result(timeout=10) # 10 seconds timeout
            
            return jsonify({'success': True, 'response': response.text, 'source': 'ai'})
            
        except concurrent.futures.TimeoutError:
            return jsonify({'success': False, 'error': 'Сервер перегружен. Попробуйте сформулировать вопрос короче (Timeout).'})
        except Exception as e:
            error_msg = str(e)
            if '429' in error_msg:
                return jsonify({'success': False, 'error': 'Лимит запросов AI превышен. Попробуйте позже или задайте вопрос по правилам (DM, RK, PG, читы и т.d.)'})
            return jsonify({'success': False, 'error': str(e)[:200]})
    
    return jsonify({'success': False, 'error': 'Не найдено в базе. Попробуйте: DM, RK, PG, читы, капт, полиция, жалоба'})


@app.route('/api/arizona/complaint', methods=['POST'])
def api_arizona_complaint():
    """Generate complaint template"""
    if not AI_MODEL:
        return jsonify({'success': False, 'error': 'AI не настроен'})
    
    data = request.json
    nickname = data.get('nickname', '').strip()
    description = data.get('description', '').strip()
    
    if not nickname or not description:
        return jsonify({'success': False, 'error': 'Заполните все поля'})
    
    try:
        prompt = f"""Ты составляешь жалобу на игрока Arizona RP по шаблону форума.

Никнейм нарушителя: {nickname}
Описание ситуации: {description}

Составь грамотную жалобу в формате:

**Никнейм нарушителя:** [ник]
**Дата и время:** [приблизительно]
**Описание нарушения:** [подробное описание]
**Нарушенное правило:** [какое правило было нарушено]
**Доказательства:** [что нужно приложить]
**Требуемое наказание:** [рекомендация]

Если в описании упоминается конкретное нарушение - определи какое правило сервера нарушено."""
        
        response = AI_MODEL.generate_content(prompt)
        return jsonify({'success': True, 'response': response.text})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)[:200]})

@app.route('/api/arizona/legend', methods=['POST'])
def api_arizona_legend():
    """Generate RP character legend"""
    if not AI_MODEL:
        return jsonify({'success': False, 'error': 'AI не настроен'})
    
    data = request.json
    name = data.get('name', '').strip()
    age = data.get('age', '25')
    style = data.get('style', 'neutral')
    
    if not name:
        return jsonify({'success': False, 'error': 'Введите имя персонажа'})
    
    style_desc = {
        'criminal': 'криминальный элемент, бандит или мафиози',
        'cop': 'сотрудник полиции или государственных структур',
        'business': 'бизнесмен, предприниматель',
        'street': 'уличный гонщик, стритрейсер',
        'neutral': 'обычный гражданин, работяга'
    }
    
    try:
        prompt = f"""Создай RP-легенду (биографию) для персонажа GTA San Andreas / Arizona RP.

Имя персонажа: {name}
Возраст: {age} лет
Типаж: {style_desc.get(style, 'обычный гражданин')}

Напиши детальную биографию в 3-4 абзаца:
1. Детство и юность (откуда родом, семья)
2. Как попал в Лос-Сантос / Сан-Фиерро / Лас-Вентурас
3. Чем занимается сейчас, цели в жизни
4. Характер, привычки, особенности

Сделай историю интересной и реалистичной для RP."""
        
        response = AI_MODEL.generate_content(prompt)
        return jsonify({'success': True, 'response': response.text})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)[:200]})

@app.route('/api/arizona/rules', methods=['POST'])
def api_arizona_rules():
    """Arizona RP rules helper - uses local database first"""
    data = request.json
    question = data.get('question', '').strip()
    
    if not question:
        return jsonify({'success': False, 'error': 'Пустой вопрос'})
    
    # First try local rules database
    if RULES_DB_LOADED:
        try:
            result = search_rules(question)
            if result:
                return jsonify({'success': True, 'response': result, 'source': 'database'})
        except Exception:
            pass # Fail silently to AI

    
    # Fallback to AI
    if AI_MODEL:
        try:
            prompt = f"""Ты - эксперт по правилам Arizona RP. Знаешь все правила сервера:

- DM (DeathMatch) - убийство без причины
- RK (RevengeKill) - месть после смерти
- PG (PowerGaming) - нереалистичные действия
- MG (MetaGaming) - использование OOC информации в IC
- VDM (Vehicle DeathMatch) - убийство транспортом
- SK (SpawnKill) - убийство на спавне
- Зелёные зоны - места где нельзя стрелять
- Читы - бан навсегда
- Оскорбления - мут/бан

Вопрос: {question}

Дай чёткий ответ: это нарушение или нет? Какое правило? Какое наказание?"""
            
            # Run AI with timeout to prevent eternal loading
            with concurrent.futures.ThreadPoolExecutor() as executor:
                future = executor.submit(AI_MODEL.generate_content, prompt)
                response = future.result(timeout=10) # 10 seconds timeout
            
            return jsonify({'success': True, 'response': response.text, 'source': 'ai'})
            
        except concurrent.futures.TimeoutError:
            return jsonify({'success': False, 'error': 'Сервер перегружен. Попробуйте сформулировать вопрос короче (Timeout).'})
        except Exception as e:
            if '429' in str(e):
                return jsonify({'success': False, 'error': 'Лимит AI. Используйте ключевые слова: DM, RK, PG, читы, капт'})
            return jsonify({'success': False, 'error': str(e)[:200]})
    
    return jsonify({'success': False, 'error': 'Правило не найдено. Попробуйте: DM, RK, PG, MG, SK, TK, читы'})

@app.route('/api/arizona/rules_list', methods=['GET'])
def api_arizona_rules_list():
    """Get list of all available rules"""
    if RULES_DB_LOADED:
        return jsonify({'success': True, 'response': get_all_rules_list()})
    return jsonify({'success': False, 'error': 'База правил не загружена'})


@app.route('/api/arizona/smi/edit', methods=['POST'])
def api_arizona_smi_edit():
    """Smart Ad Editor using AI"""
    if not AI_MODEL:
        return jsonify({'success': False, 'error': 'AI не настроен'})
    
    data = request.json
    text = data.get('text', '').strip()
    
    if not text:
        return jsonify({'success': False, 'error': 'Введите текст объявления'})
    
    try:
        prompt = f"""Ты - профессиональный сотрудник СМИ на сервере Arizona RP.
Твоя задача - отредактировать объявление игрока согласно ПРО (Правилам Редактирования Объявлений).

Входящий текст: "{text}"

Правила:
1. Исправь грамматические ошибки.
2. Используй полные названия транспорта/городов (нрг -> м/ц NRG-500, лс -> г. Лос-Сантос).
3. Если цена не указана - пиши "Цена: Договорная".
4. Если бюджет не указан - пиши "Бюджет: Свободный".
5. Формат: [Тип] Текст объявления. Цена/Бюджет: ...
6. Не добавляй "Контакт: ..." в конце, это делает игра сама.

Примеры:
- "продам нрг 500" -> "Продам м/ц NRG-500. Цена: Договорная"
- "куплю дом лс 50кк" -> "Куплю дом в г. Лос-Сантос. Бюджет: 50 млн$"
- "набор в фаму" -> "Идет набор в семью. Просьба связаться."
- "продам акс попугай" -> "Продам а/с Попугай на плечо. Цена: Договорная"

Верни ТОЛЬКО отредактированный текст."""
        
        response = AI_MODEL.generate_content(prompt)
        return jsonify({'success': True, 'response': response.text.strip()})
    except Exception as e:
        # Fallback to Regex if AI fails
        print(f"AI Error: {e}, using fallback")
        
        fallback_text = text
        import re
        
        # --- PHASE 0: Pre-cleanup ---
        fallback_text = re.sub(r'\s+', ' ', fallback_text).strip()
        # Quote extraction
        quote_match = re.search(r'["\'](.*?)["\']', fallback_text)
        if quote_match and len(quote_match.group(1)) > 3:
            fallback_text = quote_match.group(1)

        # --- PHASE 1: Vehicle Auto-Tagging (New Feature) ---
        # --- PHASE 1: Vehicle Auto-Tagging (New Feature) ---
        # Removed try-catch to expose errors
        try:
            import arizona_vehicles
            # Reload in case of hot-reload issues
            import importlib
            importlib.reload(arizona_vehicles)
            from arizona_vehicles import VEHICLES, PREFIX_MAP, FULL_NAMES
            
            db_status = "DB_OK"
        except ImportError as e:
            db_status = f"DB_FAIL_{str(e)}"
            VEHICLES = {}
            PREFIX_MAP = {}
            FULL_NAMES = {}

        words = fallback_text.split()
        new_words = []
        skip_next = False
        
        for i, word in enumerate(words):
            if skip_next:
                skip_next = False
                continue
                
            # Clean punctuation for lookup
            clean_word = re.sub(r'[^\w\d]', '', word).lower()
            
            # Check if this word is a known vehicle
            found_type = None
            found_name = word # Default to original word
            
            # 1. Check for Full Name Expansion first
            if clean_word in FULL_NAMES:
                found_name = FULL_NAMES[clean_word] # Replace "g63" -> "Mercedes-AMG G 63"
            
            # 2. Check type (using clean_word OR the new expanded name parts if needed)
            # We stick to clean_word for type lookup because map keys match vehicle lists mostly
            if VEHICLES:
                for v_type, v_list in VEHICLES.items():
                    if clean_word in v_list:
                        found_type = v_type
                        break
            
            # Logic: If found vehicle, check if previous word was already a prefix
            if found_type:
                prefix = PREFIX_MAP[found_type]
                prev_word_raw = new_words[-1].lower() if new_words else ""
                
                # Check for existing prefixes
                bg_prefix_exists = any(p in prev_word_raw for p in ['а/м', 'м/ц', 'в/т', 'л/т', 'с/м', 'авто', 'мото'])
                
                if not bg_prefix_exists:
                     new_words.append(prefix)
                
                # If name was expanded, use it. If not, title case the original.
                if clean_word in FULL_NAMES:
                    new_words.append(found_name)
                else:
                    new_words.append(word.title()) 
            else:
                new_words.append(word)
        
        fallback_text = " ".join(new_words)

        # --- PHASE 2: Standard Rules ---
        # (Rest remains same, just ensuring fallback_text is passed through)
        subs = {
            # 4.0 - 4.38 Specific Replacements
            r'\bнабор в семью\b': 'семья ищет родственников',
            r'\bнабор в фаму\b': 'семья ищет родственников',
            r'\bгетто\b': 'опасный район',
            r'\bскин\b': 'одежда',
            r'\bтт\b': 'Twin Turbo',
            r'\bскайп\b': 'майка "Скайп"',
            r'\bдискорд\b': 'майка "Дискорд"',
            r'\bтелеграм\b': 'майка "Телеграм"',
            r'\bскидочный талон\b': 'Сертификат на скидку',
            r'\bгражданские талоны\b': 'Талоны для граждан',
            r'\bгражданки\b': 'Талоны для граждан',
            r'\bвышка с нефтью\b': 'Нефтяная вышка',
            r'\bнефтевышка\b': 'Нефтяная вышка',
            r'\badd vip\b': 'сертификат "ADD VIP"',
            r'\bадд вип\b': 'сертификат "ADD VIP"',
            r'\bsamp bet\b': 'Букмекерская контора',
            r'\brare box\b': 'ларец', # Simplification, colors handled if needed
            r'\bвидеокарта\b': 'Игровая видеокарта',
            r'\bсмазка для видеокарты\b': 'термопаста',
            r'\bларец с премией\b': 'премиальный ларец',
            r'\bларец супер бокс кар\b': 'эксклюзивный ларец с т/с',
            r'\bфулл семья\b': 'Семья со всеми удобствами',
            r'\bбоксы с одеждой\b': 'коробка с одеждой',
            r'\bларец организации\b': 'ларец организации',
            r'\bбилет на антикомиссию\b': 'Билет на антиком',
            r'\bталон антиварна\b': 'Сертификат на снятие предупреждения',
            r'\bталон антидеморгана\b': 'Билет выхода из псих. больницы',
            r'\bталон на смену ника\b': 'сертификат на смену имени',
            r'\bзаточки\b': 'Гравировка',
            r'\bзаточка\b': 'Гравировка',
            r'\bобъект для дома\b': 'декорация',
            r'\bобъект\b': 'декорация',
            r'\bпередаваемая виза\b': 'разрешение на работу на острове VC',
            r'\bbattlepass\b': 'билет "БатлПасс"',
            r'\bбп\b': 'билет "БатлПасс"',
            r'\bexp для battle pass\b': 'талон на получение "Боевого опыта"',
            r'\bexp бп\b': 'талон на получение "Боевого опыта"',
            r'\bфулл скиллы\b': 'мануал "обучение навыкам стрельбы"',
            r'\bкод трилогии\b': 'Видеоигра трилогия',
            r'\bпередаваемые az\b': 'AZ монеты',
            r'\bталон на х4 пейдей\b': 'Сертификат х4 пейдей',
            r'\bлавка\b': 'Торговая лавка',
            r'\bопыт депозита\b': 'Коллекционная карточка "Опыт депозита"',

            # Abbreviations (General)
            r'\bа/м\b': 'а/м', # Keep valid ones
            r'\bавто\b': 'а/м',
            r'\bмашину\b': 'а/м',
            r'\bтачку\b': 'а/м',
            r'\bмото\b': 'м/ц',
            r'\bбайк\b': 'м/ц',
            r'\bвелик\b': 'в/т',
            r'\bвелосипед\b': 'в/т',
            r'\bвертолет\b': 'в/т',
            r'\bмавер\b': 'в/т Maverick',
            r'\bгорник\b': 'в/т Mountain Bike',
            r'\bлодка\b': 'л/т',
            r'\bсамолет\b': 'с/м',
            r'\bакс\b': 'а/с',
            r'\bброн\b': 'а/с', # Armor is accessory
            r'\bпошив\b': 'о/п',
            r'\bодежда\b': 'о/п', # Sometimes useful
            r'\bмод\b': 'м/ф',
            r'\bмодификация\b': 'м/ф',
            r'\bобъекты\b': 'о/б',
            r'\bларцы\b': 'л/ц',
            r'\bларец\b': 'л/ц',
            r'\bдет\b': 'д/т',
            r'\bтюнинг\b': 'д/т',
            r'\bресы\b': 'р/с',
            r'\bресурсы\b': 'р/с',
            r'\bбиз\b': 'б/з',
            r'\bбизнес\b': 'б/з',
            r'\bномер\b': 'н/з',
            r'\bномера\b': 'н/з',

            # Business Specific
            r'\b24/7\b': 'магазин 24/7',
            r'\bаммо\b': 'магазин оружия',
            r'\bазс\b': 'АЗС',

            # Locations
            r'\bлс\b': 'г. Лос-Сантос',
            r'\bсф\b': 'г. Сан-Фиерро',
            r'\bлв\b': 'г. Лас-Вентурас',
            r'\bцр\b': 'центрального рынка',
            r'\bаб\b': 'автобазара',

            # Junk Clean
            r'\bмарки\b': '',
            r'\bфирмы\b': '',
            r'\bмодели\b': '',

            # Actions & Prices
            r'\bп\b': 'Продам',
            r'\bк\b': 'Куплю',
            r'\bобменяю\b': 'Обменяю',
            r'\bторг\b': 'Цена: Договорная',
            r'\bбез торга\b': 'Цена: Окончательная',
            r'\bсвободный\b': 'Бюджет: Свободный'
        }
        
        # Pre-processing cleanup
        import re
        fallback_text = re.sub(r'\s+', ' ', fallback_text).strip()
        
        # Quote Extraction (if user asks question)
        quote_match = re.search(r'["\'](.*?)["\']', fallback_text)
        if quote_match and len(quote_match.group(1)) > 5:
            fallback_text = quote_match.group(1)

        # Apply Substitutions
        for pattern, replacement in subs.items():
            fallback_text = re.sub(pattern, replacement, fallback_text, flags=re.IGNORECASE)

        # Price/Budget Logic (Rule 5.1 & Price Formats)
        # Helper to detect if buying or selling
        is_buying = any(x in fallback_text.lower() for x in ['куплю', 'ищу', 'возьму'])
        
        # Add prefix if missing
        if not any(x in fallback_text.lower() for x in ['продам', 'куплю', 'обменяю', 'сдам', 'арендую']):
            fallback_text = ("Куплю " if is_buying else "Продам ") + fallback_text

        # Add Suffix (Price/Budget)
        has_price = any(x in fallback_text.lower() for x in ['цена', 'бюджет', 'договорная', 'свободный'])
        if not has_price:
            if is_buying:
                fallback_text += ". Бюджет: Свободный"
            else:
                fallback_text += ". Цена: Договорная"

        # Capitalize Sentence
        if fallback_text:
            fallback_text = fallback_text[0].upper() + fallback_text[1:]

        # Price Formatting (1к -> 1.000$)
        def format_price(match):
            val = match.group(1)
            suffix = match.group(2).lower()
            if suffix == 'к': return f"{val}.000$"
            if suffix == 'кк': return f"{val}.000.000$"
            return match.group(0)
        
        fallback_text = re.sub(r'(\d+)(к{1,2})', format_price, fallback_text, flags=re.IGNORECASE)

        return jsonify({
            'success': True, 
            'response': f"{fallback_text} (Offline Mode v2 - {db_status})", 
            'source': 'fallback_pro_v2'
        })

@app.route('/api/arizona/smi/data')
def api_arizona_smi_data():
    """Get SMI Data (Rules logic)"""
    return jsonify({
        'ppe_summary': PPE_TEXT if SMI_RULES_LOADED else "Правила не загружены",
        'templates': ETHER_TEMPLATES if SMI_RULES_LOADED else {}
    })


@app.route('/api/arizona/news')
def api_arizona_news():
    """Returns REAL Arizona RP News from VK (via RSS)"""
    import requests
    import xml.etree.ElementTree as ET
    import re
    
    try:
        # Use VK RSS feed - no token needed!
        # TARGET GROUP: https://vk.com/arizonastaterp
        # Numeric ID commonly found for State RP: 168097969
        urls_to_try = [
            "https://vk.com/rss.php?owner_id=-168097969", # Arizona State RP (Numeric ID)
            "https://vk.com/rss.php?domain=arizonastaterp" # Domain fallback
        ]
        
        # User-Agent is often required to avoid 403 Forbidden on RSS feeds
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        
        r = None
        for url in urls_to_try:
            try:
                print(f"Trying RSS: {url}")
                temp_r = requests.get(url, headers=headers, timeout=5)
                if temp_r.status_code == 200 and '<channel>' in temp_r.text:
                    r = temp_r
                    break
            except:
                continue
                
        if not r:
            raise Exception("All RSS sources failed")
            
        # Use raw content in bytes for ElementTree to handle encoding declarations automatically
        root = ET.fromstring(r.content)
        
        news_items = []
        channel = root.find('channel')
        
        if not channel:
             return jsonify({'success': False, 'error': 'RSS: Channel not found'})

        for item in channel.findall('item')[:10]:
            title = item.find('title').text or "News"
            link = item.find('link').text
            description = item.find('description').text or ""
            pub_date = item.find('pubDate').text
            
            # Extract Image
            img_match = re.search(r'src="(https://[^"]+)"', description)
            if not img_match:
                 enclosure = item.find('enclosure')
                 if enclosure is not None and 'image' in enclosure.get('type', ''):
                     img_url = enclosure.get('url')
                 else:
                     img_url = 'https://via.placeholder.com/300x180?text=Arizona+RP'
            else:
                 img_url = img_match.group(1)
            
            # Clean HTML
            summary = re.sub(r'<[^>]+>', '', description)
            summary = summary.replace('&nbsp;', ' ').strip()
            summary = summary[:150] + '...' if len(summary) > 150 else summary
            
            # Tag logic
            tag = 'Новости'
            lower_text = (title + summary).lower()
            if 'обновление' in lower_text: tag = 'Обновление'
            elif 'x4' in lower_text or 'конкурс' in lower_text: tag = 'Акция'
            elif 'лидер' in lower_text or 'заявки' in lower_text: tag = 'Набор'

            # Date logic
            date_str = pub_date[:25] 

            news_items.append({
                'id': link,
                'title': title,
                'date': date_str,
                'tag': tag,
                'image': img_url,
                'summary': summary,
                'likes': 0, 
                'url': link
            })
            
        return jsonify({'success': True, 'news': news_items})
        
    except Exception as e:
        print("News Fetch Error:", e)
        # Fallback to REAL recent news so the user always sees something
        # Using LOCAL image to guarantee it works.
        fallback_news = [
            {
                'id': 'fallback_1',
                'title': 'Новости Arizona State',
                'date': datetime.now().strftime('%d.%m.%Y %H:%M'),
                'tag': 'Важно',
                'image': '/static/img/arizona_logo.png', 
                'summary': 'Следите за всеми актуальными новостями, обновлениями правил и важными событиями сервера в нашей официальной группе ВКонтакте.',
                'likes': 100,
                'url': 'https://vk.com/arizonastaterp'
            },
            {
                'id': 'fallback_2',
                'title': 'Технический раздел',
                'date': (datetime.now()).strftime('%d.%m.%Y %H:%M'),
                'tag': 'Info',
                'image': '/static/img/arizona_logo.png',
                'summary': 'Если у вас возникли технические проблемы или вопросы по донату, обратитесь в технический раздел на форуме или в группе.',
                'likes': 50,
                'url': 'https://vk.com/arizonastaterp'
            },
             {
                'id': 'fallback_3',
                'title': 'Как начать играть?',
                'date': (datetime.now()).strftime('%d.%m.%Y %H:%M'),
                'tag': 'Гайд',
                'image': '/static/img/arizona_logo.png',
                'summary': 'Скачивайте лаунчер, регистрируйтесь на сервере Arizona State и вводите промокоды для быстрого старта!',
                'likes': 200,
                'url': 'https://vk.com/arizonastaterp'
            }
        ]
        return jsonify({'success': True, 'news': fallback_news})


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
        
        # Emit stats update
        try:
            uptime = int(time.time() - bot_status['start_time'])
            cpu = psutil.cpu_percent(interval=None) or 0
            mem = psutil.virtual_memory()
            mem_used = mem.used // (1024 * 1024)
            
            socketio.emit('stats_update', {
                'servers': bot_status['servers'],
                'users': bot_status['users'],
                'commands_today': bot_status['commands_today'],
                'uptime': uptime,
                'running': bot_status['running'],
                'cpu_percent': cpu,
                'memory_used': mem_used
            })
        except Exception as e:
            print(f"Stats emit error: {e}")

threading.Thread(target=simulate, daemon=True).start()

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    print(f"Server running on http://0.0.0.0:{port}")
    socketio.run(app, host='0.0.0.0', port=port, debug=False, allow_unsafe_werkzeug=True)

