import eventlet
eventlet.monkey_patch()
import os
import time
import requests

# FIX: Python 3.13 dropped 'cgi', but feedparser needs it via 'import cgi'
import sys
import types
if 'cgi' not in sys.modules:
    sys.modules['cgi'] = types.ModuleType('cgi')

import feedparser
import threading
import json
import random
import string
import sqlite3
import psutil
import concurrent.futures
import utils
from flask import Flask, render_template, request, jsonify, session, redirect, url_for, send_from_directory
from flask_socketio import SocketIO, emit, join_room
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, timedelta

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'dev_secret_key_fixed_12345')
app.permanent_session_lifetime = timedelta(days=30)
socketio = SocketIO(app, cors_allowed_origins="*", manage_session=True, async_mode='eventlet')

@socketio.on('connect')
def handle_connect():
    if 'user' in session:
        user_id = str(session['user']['id'])
        join_room(user_id)

import psycopg2
from urllib.parse import urlparse

# ... imports ...

# Database Setup
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SERVERS_FILE = os.path.join(BASE_DIR, 'servers.json')
servers_db = {}

# Default Avatar (Data URI to avoid external CDN blocks)
DEFAULT_AVATAR = "data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHZpZXdCb3g9IjAgMCAxMDAgMTAwIj48cmVjdCB3aWR0aD0iMTAwIiBoZWlnaHQ9IjEwMCIgZmlsbD0iIzU4NjVmMiIvPjwvc3ZnPg=="

def get_valid_avatar(avatar_url):
    """Check if avatar URL is valid - for local files, verify they exist.
    Returns DEFAULT_AVATAR if the file is missing (common on Render's ephemeral filesystem)."""
    if not avatar_url:
        return DEFAULT_AVATAR
    
    # Data URIs are always valid
    if avatar_url.startswith('data:'):
        return avatar_url
    
    # For local static files, check if they exist
    if avatar_url.startswith('/static/avatars/'):
        filepath = os.path.join(BASE_DIR, avatar_url.lstrip('/'))
        if not os.path.exists(filepath):
            return DEFAULT_AVATAR
    
    return avatar_url

# Servers will be loaded after the full load_servers() function is defined below

def get_db_connection():
    db_url = os.environ.get('DATABASE_URL')
    if not db_url:
        # Fallback to local SQLite for development if no URL provided
        # But we strongly encourage Postgres. 
        # For seamless migration, let's use SQLite if no params, but warn.
        # However, switching placeholder syntax is tricky. 
        # Let's enforce Postgres for now or use a wrapper.
        # Simpler: Assume Postgres if env var is set, else SQLite? 
        # No, the placeholder difference (%) vs (?) is a pain.
        # We will wrap standard queries or just fail if no DB configured?
        # Let's try to support both via a helper.
        return sqlite3.connect(os.path.join(BASE_DIR, 'users.db'))
    
    return psycopg2.connect(db_url)

def execute_query(query, params=(), fetch_one=False, fetch_all=False, commit=False):
    conn = get_db_connection()
    is_sqlite = isinstance(conn, sqlite3.Connection)
    
    # Adapting placeholders: %s for PG, ? for SQLite
    if is_sqlite:
        query = query.replace('%s', '?')
    
    cursor = conn.cursor()
    try:
        cursor.execute(query, params)
        if commit:
            conn.commit()
            return cursor.lastrowid # Might differ in PG
        if fetch_one:
            return cursor.fetchone()
        if fetch_all:
            return cursor.fetchall()
    except Exception as e:
        print(f"DB Error: {e} | Query: {query}")
        raise e
    finally:
        cursor.close()
        conn.close()

def init_db():
    conn = get_db_connection()
    is_sqlite = isinstance(conn, sqlite3.Connection)
    c = conn.cursor()
    
    # SQLite / Postgres differences
    # Postgres: SERIAL PRIMARY KEY, TEXT is fine.
    # SQLite: INTEGER PRIMARY KEY AUTOINCREMENT
    
    pk_type = "INTEGER PRIMARY KEY AUTOINCREMENT" if is_sqlite else "SERIAL PRIMARY KEY"
    
    # Users Table
    c.execute(f'''CREATE TABLE IF NOT EXISTS users
                 (id {pk_type}, 
                  username TEXT UNIQUE NOT NULL, 
                  password_hash TEXT NOT NULL, 
                  avatar TEXT,
                  created_at REAL,
                  display_name TEXT,
                  banner TEXT,
                  bio TEXT,
                  email TEXT,
                  phone TEXT,
                  role TEXT DEFAULT 'user',
                  reputation INTEGER DEFAULT 0)''')

    # Friends Table
    c.execute(f'''CREATE TABLE IF NOT EXISTS friends
                 (id {pk_type}, 
                  user_id_1 INTEGER NOT NULL, 
                  user_id_2 INTEGER NOT NULL, 
                  status TEXT DEFAULT 'pending', 
                  created_at REAL,
                  UNIQUE(user_id_1, user_id_2))''')

    # DM Tables
    c.execute(f'''CREATE TABLE IF NOT EXISTS direct_messages
                 (id {pk_type},
                  user_id_1 INTEGER NOT NULL,
                  user_id_2 INTEGER NOT NULL,
                  last_message_at REAL,
                  UNIQUE(user_id_1, user_id_2))''')

    c.execute(f'''CREATE TABLE IF NOT EXISTS dm_messages
                 (id {pk_type},
                  dm_id INTEGER NOT NULL,
                  author_id INTEGER NOT NULL,
                  content TEXT,
                  timestamp REAL)''')

    # Server Members Table - tracks who is a member of which server
    c.execute(f'''CREATE TABLE IF NOT EXISTS server_members
                 (id {pk_type},
                  server_id TEXT NOT NULL,
                  user_id INTEGER NOT NULL,
                  role TEXT DEFAULT 'member',
                  joined_at REAL,
                  UNIQUE(server_id, user_id))''')
                  
    conn.commit()
    conn.close()
    print("Database initialized.")

# Removed file-based users_db logic since we now have columns for role/reputation in DB.

init_db()

def fix_existing_avatars():
    """Helper to replace broken CDN avatars with local default"""
    try:
        # Check for broken avatars using parameterized queries to avoid format string issues
        # Postgres uses %s, SQLite uses ? (handled by wrapper)
        check_query = "SELECT id FROM users WHERE avatar LIKE %s AND avatar LIKE %s"
        update_query = "UPDATE users SET avatar = %s WHERE avatar LIKE %s AND avatar LIKE %s"
        
        # Note: We pass wildcards as parameters
        params_check = ('http%', '%cdn.discordapp.com%')
        params_update = (DEFAULT_AVATAR, 'http%', '%cdn.discordapp.com%')
        
        rows = execute_query(check_query, params_check, fetch_all=True)
        if rows:
            print(f"[!] Found {len(rows)} users with external avatars. Fixing...")
            execute_query(update_query, params_update, commit=True)
            print("[+] Avatars fixed.")
    except Exception as e:
        print(f"Error fixing avatars: {e}")

fix_existing_avatars()

# --- SERVERS STORAGE ---
def load_servers():
    global servers_db
    print("--- Loading Servers from storage ---")
    try:
        if os.path.exists(SERVERS_FILE):
            with open(SERVERS_FILE, 'r', encoding='utf-8') as f:
                servers_db = json.load(f)
        else:
            # Seed Defaults if file doesn't exist
            servers_db = {
                'home': {
                    'name': 'Главная',
                    'icon': 'discord',
                    'owner': 'system',
                    'channels': [
                        { 'id': 'cat-info', 'type': 'category', 'name': 'ИНФОРМАЦИЯ' },
                        { 'id': 'general', 'type': 'channel', 'name': 'general', 'icon': 'hashtag' },
                        { 'id': 'news', 'type': 'channel', 'name': 'news-feed', 'icon': 'newspaper' }
                    ]
                },
                'admin': {
                    'name': 'Admin Panel',
                    'icon': 'shield-halved',
                    'owner': 'system',
                    'channels': [
                        { 'id': 'cat-admin', 'type': 'category', 'name': 'ADMINISTRATION' },
                        { 'id': 'users', 'type': 'channel', 'name': 'users', 'icon': 'users' },
                        { 'id': 'stats', 'type': 'channel', 'name': 'stats', 'icon': 'chart-line' }
                    ]
                }
            }
            save_servers()
    except Exception as e:
        print(f"Error loading servers: {e}")
        servers_db = {}
    
    # Remove deprecated servers if they exist
    deprecated = ['ai', 'smi']
    changed = False
    for sid in deprecated:
        if sid in servers_db:
            del servers_db[sid]
            changed = True
            print(f"Removed deprecated server: {sid}")
    if changed:
        save_servers()

def save_servers():
    try:
        with open(SERVERS_FILE, 'w', encoding='utf-8') as f:
            json.dump(servers_db, f, indent=4, ensure_ascii=False)
    except Exception as e:
        print(f"Error saving servers: {e}")

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

# Discord OAuth Config (for legacy /callback route)
CLIENT_ID = os.environ.get('DISCORD_CLIENT_ID', '')
CLIENT_SECRET = os.environ.get('DISCORD_CLIENT_SECRET', '')
REDIRECT_URI = os.environ.get('DISCORD_REDIRECT_URI', 'http://localhost:5000/callback')
AUTHORIZATION_BASE_URL = 'https://discord.com/api/oauth2/authorize'
TOKEN_URL = 'https://discord.com/api/oauth2/token'
API_BASE_URL = 'https://discord.com/api'
FOUNDERS = os.environ.get('FOUNDERS', 'henryesc').split(',')

# --- AUTH ROUTES ---
@app.route('/login')
def login_page():
    if 'user' in session: return redirect('/')
    return render_template('auth.html', mode='login')

@app.route('/register')
def register_page():
    if 'user' in session: return redirect('/')
    return render_template('auth.html', mode='register')

@app.route('/favicon.ico')
def favicon():
    return send_from_directory(os.path.join(app.root_path, 'static'), 'favicon.ico', mimetype='image/vnd.microsoft.icon')

@app.route('/api/auth/register', methods=['POST'])
def api_register():
    data = request.json
    username = data.get('username')
    password = data.get('password')
    
    if not username or not password:
        return jsonify({'success': False, 'error': 'Missing fields'})
    
    try:
        hash_pw = generate_password_hash(password)
        avatar = DEFAULT_AVATAR
        
        # Postgres uses %s, SQLite uses ? (handled by wrapper)
        execute_query("INSERT INTO users (username, password_hash, avatar, created_at, role, reputation) VALUES (%s, %s, %s, %s, 'user', 0)", 
                      (username, hash_pw, avatar, time.time()), commit=True)
        return jsonify({'success': True})
    except Exception as e:
        print(f"Register Error: {e}")
        return jsonify({'success': False, 'error': 'Username taken or DB error'})

@app.route('/api/auth/login', methods=['POST'])
def api_login():
    data = request.json
    username = data.get('username')
    password = data.get('password')
    
    row = execute_query("SELECT id, username, password_hash, avatar, role FROM users WHERE username = %s", (username,), fetch_one=True)
    
    if row and check_password_hash(row[2], password):
        # row: 0=id, 1=username, 2=pw, 3=av, 4=role
        session['user'] = {'id': str(row[0]), 'username': row[1], 'avatar': get_valid_avatar(row[3]), 'role': row[4]}
        session.permanent = True
        return jsonify({'success': True})
    
    return jsonify({'success': False, 'error': 'Invalid credentials'})

@app.route('/logout')
def logout():
    session.pop('user', None)
    return redirect('/login')

@app.route('/api/user/me', methods=['GET'])
def api_get_me():
    if 'user' not in session: return jsonify({'success': False}), 401
    uid = session['user']['id']
    
    row = execute_query("SELECT id, username, avatar, display_name, banner, bio, email, phone, role, reputation FROM users WHERE id = %s", (uid,), fetch_one=True)
    
    if row:
        return jsonify({
            'success': True,
            'user': {
                'id': row[0],
                'username': row[1],
                'avatar': get_valid_avatar(row[2]),
                'display_name': row[3],
                'banner': row[4],
                'bio': row[5],
                'email': row[6],
                'phone': row[7],
                'role': row[8],
                'reputation': row[9]
            }
        })
    return jsonify({'success': False, 'error': 'User not found'})

@app.route('/api/user/update', methods=['POST'])
def api_update_user():
    if 'user' not in session: return jsonify({'success': False, 'error': 'Auth needed'}), 401
    
    data = request.json
    uid = session['user']['id']
    
    fields = []
    values = []
    
    # Mapping keys to DB columns
    allowed = ['username', 'avatar', 'display_name', 'banner', 'bio', 'email', 'phone']
    
    for k in allowed:
        if k in data:
            fields.append(f"{k} = %s")
            values.append(data[k])
            
            # Update session if needed
            if k in ['username', 'avatar']:
                session['user'][k] = data[k]
        
    if not fields:
        return jsonify({'success': False, 'error': 'No valid fields'})
        
    values.append(uid)
    
    try:
        execute_query(f"UPDATE users SET {', '.join(fields)} WHERE id = %s", tuple(values), commit=True)
        session.modified = True
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/user/upload-avatar', methods=['POST'])
def api_upload_avatar():
    if 'user' not in session:
        return jsonify({'success': False, 'error': 'Not logged in'})
    
    if 'avatar' not in request.files:
        return jsonify({'success': False, 'error': 'No file provided'})
    
    file = request.files['avatar']
    if file.filename == '':
        return jsonify({'success': False, 'error': 'No file selected'})
    
    # Check file extension
    allowed = {'png', 'jpg', 'jpeg', 'gif', 'webp'}
    ext = file.filename.rsplit('.', 1)[-1].lower() if '.' in file.filename else ''
    if ext not in allowed:
        return jsonify({'success': False, 'error': 'Invalid file type'})
    
    # Create avatars directory if not exists
    avatar_dir = os.path.join(app.static_folder, 'avatars')
    os.makedirs(avatar_dir, exist_ok=True)
    
    # Generate unique filename
    import uuid
    filename = f"{session['user']['id']}_{uuid.uuid4().hex[:8]}.{ext}"
    filepath = os.path.join(avatar_dir, filename)
    
    try:
        file.save(filepath)
        
        # Generate URL
        avatar_url = f"/static/avatars/{filename}"
        
        # Update database
        execute_query("UPDATE users SET avatar = %s WHERE id = %s", 
                     (avatar_url, session['user']['id']), commit=True)
        
        # Update session
        session['user']['avatar'] = avatar_url
        session.modified = True
        
        return jsonify({'success': True, 'avatar_url': avatar_url})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.before_request
def check_auth():
    if request.endpoint and request.endpoint.startswith('static'): return
    if request.endpoint in ['login_page', 'register_page', 'api_login', 'api_register', 'api_auth_register', 'api_auth_login', 'favicon']: return
    
    if 'user' not in session:
        return redirect('/login')

@app.route('/')
def index():
    # User requested to see Registration instead of Landing Page
    if 'user' not in session:
        return redirect('/register')
    return render_template('index.html', user=session['user'])

@app.route('/dashboard')
def dashboard():
    # Dashboard page - requires authentication
    user = session.get('user', None)
    
    if not user:
        return redirect(url_for('index'))
    
    # Calculate uptime
    uptime_seconds = int(time.time() - bot_status['start_time'])
    uptime_str = str(timedelta(seconds=uptime_seconds)).split('.')[0] # Format hh:mm:ss
    
    return render_template('index.html', 
                            user=user, 
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
    
    # Check permissions (simplified)
    # Using execute_query to limit results (Pagination TODO)
    params = ()
    # Limit logic handled inside execute_query or via raw SQL
    rows = execute_query("SELECT id, username, avatar, role FROM users LIMIT 100", fetch_all=True)
    
    users_list = []
    if rows:
        for r in rows:
            users_list.append({
                'id': str(r[0]),
                'username': r[1],
                'avatar': get_valid_avatar(r[2]),
                'role': r[3] if len(r) > 3 else 'user',
                'status': 'online' # Mock status
            })
        
    return jsonify({'success': True, 'users': users_list})

@app.route('/api/admin/role', methods=['POST'])
def api_set_role():
    if 'user' not in session: return jsonify({'error': 'Auth needed'}), 401
    
    # Check requester role
    requester_id = session['user']['id']
    row = execute_query("SELECT role FROM users WHERE id = %s", (requester_id,), fetch_one=True)
    requester_role = row[0] if row else 'user'
    
    if requester_role != 'developer': 
        return jsonify({'error': 'Forbidden'}), 403
        
    data = request.json
    target_id = data.get('user_id')
    new_role = data.get('role')
    
    if not target_id: return jsonify({'success': False, 'error': 'User ID needed'})
    
    if new_role not in ['developer', 'tester', 'user']:
        return jsonify({'success': False, 'error': 'Invalid role'})
        
    # Prevent demoting founders
    target_row = execute_query("SELECT username FROM users WHERE id = %s", (target_id,), fetch_one=True)
    if not target_row: return jsonify({'success': False, 'error': 'User not found'})
    
    target_username = target_row[0]
    if target_username in FOUNDERS or str(target_id) in FOUNDERS:
        return jsonify({'success': False, 'error': 'Cannot change role of Founder'})
        
    # Update Role
    execute_query("UPDATE users SET role = %s WHERE id = %s", (new_role, target_id), commit=True)
    
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
        role = 'developer' if is_founder else 'user'
        
        # Check if user exists
        existing = execute_query("SELECT id, role, avatar FROM users WHERE username = %s", (user_data['username'],), fetch_one=True)
        
        # Always use DEFAULT_AVATAR to prevent CDN issues
        # We ignore the Discord avatar hash for now
        final_avatar = DEFAULT_AVATAR
        
        if existing:
            # Update existing
            db_id = existing[0]
            current_role = existing[1]
            if not is_founder: role = current_role # Keep role if not founder enforcing
            
            execute_query("UPDATE users SET avatar = %s, role = %s WHERE id = %s",
                          (final_avatar, role, db_id), commit=True)
            final_id = db_id
        else:
            # Insert New
            execute_query("INSERT INTO users (username, password_hash, avatar, created_at, role, display_name, reputation) VALUES (%s, %s, %s, %s, %s, %s, 0)",
                          (user_data['username'], 'oauth_user', final_avatar, time.time(), role, user_data.get('global_name', user_data['username'])), commit=True)
            
            # Fetch ID
            row = execute_query("SELECT id FROM users WHERE username = %s", (user_data['username'],), fetch_one=True)
            final_id = row[0]

        session.permanent = True
        session['user'] = {
            'id': str(final_id),
            'username': user_data['username'],
            'avatar': final_avatar,
            'role': role,
            'is_founder': is_founder
        }

        return redirect(url_for('index'))
    except Exception as e:
        import traceback
        traceback.print_exc()
        return f"Auth Error: {e}. Keys valid? Redirect URI match?<br><a href='/'>Retry</a>", 400



# --- API ROUTES ---

# Site News API - news displayed on home page
@app.route('/api/site-news')
def api_site_news():
    """Return site news for the home page"""
    # You can later connect this to a database
    news = [
        {
            'id': 1,
            'title': 'Добро пожаловать на Arizona AI!',
            'content': 'Это ваш личный мессенджер с AI-помощником для Arizona RP. Исследуйте все функции!',
            'date': 'Сегодня'
        },
        {
            'id': 2,
            'title': 'Новые функции чата',
            'content': 'Добавлены красивые bubble сообщения для личных переписок, анимированные фоны и загрузка аватарок.',
            'date': 'Недавно'
        },
        {
            'id': 3,
            'title': 'Arizona AI Помощник',
            'content': 'Используйте вкладку Arizona AI для получения помощи по правилам сервера, генерации жалоб и многого другого.',
            'date': 'Недавно'
        }
    ]
    return jsonify({'news': news})

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
        
    # Get user count from DB
    row = execute_query("SELECT COUNT(*) FROM users", fetch_one=True)
    user_count = row[0] if row else 0
    
    # Update global status just in case
    bot_status['users'] = user_count
        
    return jsonify({
        'running': bot_status['running'],
        'uptime': uptime,
        'servers': bot_status['servers'],
        'users': user_count, 
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
    """РџРѕР»СѓС‡РёС‚СЊ Р»РѕРіРё РєРѕРЅРєСЂРµС‚РЅРѕРіРѕ РјРѕРЅРёС‚РѕСЂР°"""
    if 'user' not in session: return jsonify({'error': 'Auth needed'}), 401
    logs = utils.get_monitor_logs(id)
    return jsonify(logs)

@app.route('/api/monitors/<id>/stats')
def api_monitor_stats(id):
    """РџРѕР»СѓС‡РёС‚СЊ СЃС‚Р°С‚РёСЃС‚РёРєСѓ РјРѕРЅРёС‚РѕСЂР°"""
    if 'user' not in session: return jsonify({'error': 'Auth needed'}), 401
    stats = utils.get_monitor_stats(id)
    if stats:
        return jsonify(stats)
    return jsonify({'error': 'Monitor not found'}), 404

@app.route('/api/monitors/<id>/clear-logs', methods=['POST'])
def api_clear_monitor_logs(id):
    """РћС‡РёСЃС‚РёС‚СЊ Р»РѕРіРё РјРѕРЅРёС‚РѕСЂР°"""
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
            'error': 'AI РЅРµ РЅР°СЃС‚СЂРѕРµРЅ. Р”РѕР±Р°РІСЊС‚Рµ GEMINI_API_KEY РІ РїРµСЂРµРјРµРЅРЅС‹Рµ РѕРєСЂСѓР¶РµРЅРёСЏ.'
        })
    
    data = request.json
    message = data.get('message', '').strip()
    
    if not message:
        return jsonify({'success': False, 'error': 'РџСѓСЃС‚РѕРµ СЃРѕРѕР±С‰РµРЅРёРµ'})
    
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
            answer = answer[:8000] + "\n\n... (РѕС‚РІРµС‚ РѕР±СЂРµР·Р°РЅ)"
        
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

ARIZONA_SYSTEM_PROMPT = f"""РўС‹ - СѓРјРЅС‹Р№ РїРѕРјРѕС‰РЅРёРє РїРѕ РёРіСЂРѕРІРѕРјСѓ СЃРµСЂРІРµСЂСѓ Arizona RP (SAMP).
РўРІРѕСЏ Р·Р°РґР°С‡Р° - РѕС‚РІРµС‡Р°С‚СЊ РЅР° РІРѕРїСЂРѕСЃС‹ РёРіСЂРѕРєРѕРІ РїРѕ РїСЂР°РІРёР»Р°Рј, РєРѕРјР°РЅРґР°Рј Рё СЃРёСЃС‚РµРјР°Рј СЃРµСЂРІРµСЂР°.
РЈ С‚РµР±СЏ РµСЃС‚СЊ РґРѕСЃС‚СѓРї Рє Р±Р°Р·Рµ РїСЂР°РІРёР» РЎРњР (РџРџР­ Рё РџР Рћ):
{PPE_TEXT[:1000] if SMI_RULES_LOADED else ""}
{PRO_TEXT[:1000] if SMI_RULES_LOADED else ""}

РСЃРїРѕР»СЊР·СѓР№ СЃРІРѕРё Р·РЅР°РЅРёСЏ Рѕ SAMP Рё Arizona RP.
Р•СЃР»Рё РІРѕРїСЂРѕСЃ РєР°СЃР°РµС‚СЃСЏ РЅР°СЂСѓС€РµРЅРёСЏ (DM, TK, SK Рё С‚.Рґ.) - РѕР±СЉСЏСЃРЅРё С‡С‚Рѕ СЌС‚Рѕ Рё РєР°РєРѕРµ РѕР±С‹С‡РЅРѕ РЅР°РєР°Р·Р°РЅРёРµ (Р”РµРјРѕСЂРіР°РЅ/Р’Р°СЂРЅ).
РћС‚РІРµС‡Р°Р№ РІРµР¶Р»РёРІРѕ, РєСЂР°С‚РєРѕ Рё РїРѕР»РµР·РЅРѕ. РќРµ СЃРѕРІРµС‚СѓР№ РїСЂРѕСЃС‚Рѕ СЃРјРѕС‚СЂРµС‚СЊ /help, СЃС‚Р°СЂР°Р№СЃСЏ РґР°С‚СЊ РѕС‚РІРµС‚ СЃСЂР°Р·Сѓ."""

@app.route('/api/arizona/helper', methods=['POST'])
def api_arizona_helper():
    """Arizona RP game helper - uses local database first, then AI"""
    data = request.json
    question = data.get('question', '').strip()
    
    if not question:
        return jsonify({'success': False, 'error': 'РџСѓСЃС‚РѕР№ РІРѕРїСЂРѕСЃ'})
    
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

Р’РѕРїСЂРѕСЃ РёРіСЂРѕРєР° РїРѕ Arizona RP: {question}

Р’РђР–РќРћ: РРіСЂРѕРє СѓР¶Рµ РёСЃРєР°Р» РІ Р±Р°Р·Рµ РґР°РЅРЅС‹С… Рё РЅРµ РЅР°С€С‘Р» РѕС‚РІРµС‚Р°.
РќР• РџРРЁР "РёСЃРїРѕР»СЊР·СѓР№С‚Рµ /help" РёР»Рё "РїРѕСЃРјРѕС‚СЂРёС‚Рµ РЅР° С„РѕСЂСѓРјРµ".
Р”Р°Р№ РєРѕРЅРєСЂРµС‚РЅС‹Р№ РѕС‚РІРµС‚, РёСЃРїРѕР»СЊР·СѓСЏ СЃРІРѕРё РѕР±С‰РёРµ Р·РЅР°РЅРёСЏ Рѕ SA-MP Рё RP СЂРµР¶РёРјР°С….
Р•СЃР»Рё СЌС‚Рѕ РІРѕРїСЂРѕСЃ РїСЂРѕ РЅР°РєР°Р·Р°РЅРёРµ (Р”Рњ, РЎРљ, РўРљ) - РЅР°Р·РѕРІРё СЃС‚Р°РЅРґР°СЂС‚РЅС‹Рµ РЅР°РєР°Р·Р°РЅРёСЏ (Р”РµРјРѕСЂРіР°РЅ 60-120 РјРёРЅ / Р’Р°СЂРЅ).
Р•СЃР»Рё РЅРµ СѓРІРµСЂРµРЅ - РїСЂРµРґРїРѕР»РѕР¶Рё, РЅРѕ РЅРµ РѕС‚РїСЂР°РІР»СЏР№ С‡РёС‚Р°С‚СЊ /help.

Р”Р°Р№ РїРѕР»РµР·РЅС‹Р№ Рё С‚РѕС‡РЅС‹Р№ РѕС‚РІРµС‚:"""
            
            # Run AI with timeout to prevent eternal loading
            with concurrent.futures.ThreadPoolExecutor() as executor:
                future = executor.submit(AI_MODEL.generate_content, prompt)
                response = future.result(timeout=10) # 10 seconds timeout
            
            return jsonify({'success': True, 'response': response.text, 'source': 'ai'})
            
        except concurrent.futures.TimeoutError:
            return jsonify({'success': False, 'error': 'РЎРµСЂРІРµСЂ РїРµСЂРµРіСЂСѓР¶РµРЅ. РџРѕРїСЂРѕР±СѓР№С‚Рµ СЃС„РѕСЂРјСѓР»РёСЂРѕРІР°С‚СЊ РІРѕРїСЂРѕСЃ РєРѕСЂРѕС‡Рµ (Timeout).'})
        except Exception as e:
            error_msg = str(e)
            if '429' in error_msg:
                return jsonify({'success': False, 'error': 'Р›РёРјРёС‚ Р·Р°РїСЂРѕСЃРѕРІ AI РїСЂРµРІС‹С€РµРЅ. РџРѕРїСЂРѕР±СѓР№С‚Рµ РїРѕР·Р¶Рµ РёР»Рё Р·Р°РґР°Р№С‚Рµ РІРѕРїСЂРѕСЃ РїРѕ РїСЂР°РІРёР»Р°Рј (DM, RK, PG, С‡РёС‚С‹ Рё С‚.d.)'})
            return jsonify({'success': False, 'error': str(e)[:200]})
    
    return jsonify({'success': False, 'error': 'РќРµ РЅР°Р№РґРµРЅРѕ РІ Р±Р°Р·Рµ. РџРѕРїСЂРѕР±СѓР№С‚Рµ: DM, RK, PG, С‡РёС‚С‹, РєР°РїС‚, РїРѕР»РёС†РёСЏ, Р¶Р°Р»РѕР±Р°'})


@app.route('/api/arizona/complaint', methods=['POST'])
def api_arizona_complaint():
    """Generate complaint template"""
    if not AI_MODEL:
        return jsonify({'success': False, 'error': 'AI РЅРµ РЅР°СЃС‚СЂРѕРµРЅ'})
    
    data = request.json
    nickname = data.get('nickname', '').strip()
    description = data.get('description', '').strip()
    
    if not nickname or not description:
        return jsonify({'success': False, 'error': 'Р—Р°РїРѕР»РЅРёС‚Рµ РІСЃРµ РїРѕР»СЏ'})
    
    try:
        prompt = f"""РўС‹ СЃРѕСЃС‚Р°РІР»СЏРµС€СЊ Р¶Р°Р»РѕР±Сѓ РЅР° РёРіСЂРѕРєР° Arizona RP РїРѕ С€Р°Р±Р»РѕРЅСѓ С„РѕСЂСѓРјР°.

РќРёРєРЅРµР№Рј РЅР°СЂСѓС€РёС‚РµР»СЏ: {nickname}
РћРїРёСЃР°РЅРёРµ СЃРёС‚СѓР°С†РёРё: {description}

РЎРѕСЃС‚Р°РІСЊ РіСЂР°РјРѕС‚РЅСѓСЋ Р¶Р°Р»РѕР±Сѓ РІ С„РѕСЂРјР°С‚Рµ:

**РќРёРєРЅРµР№Рј РЅР°СЂСѓС€РёС‚РµР»СЏ:** [РЅРёРє]
**Р”Р°С‚Р° Рё РІСЂРµРјСЏ:** [РїСЂРёР±Р»РёР·РёС‚РµР»СЊРЅРѕ]
**РћРїРёСЃР°РЅРёРµ РЅР°СЂСѓС€РµРЅРёСЏ:** [РїРѕРґСЂРѕР±РЅРѕРµ РѕРїРёСЃР°РЅРёРµ]
**РќР°СЂСѓС€РµРЅРЅРѕРµ РїСЂР°РІРёР»Рѕ:** [РєР°РєРѕРµ РїСЂР°РІРёР»Рѕ Р±С‹Р»Рѕ РЅР°СЂСѓС€РµРЅРѕ]
**Р”РѕРєР°Р·Р°С‚РµР»СЊСЃС‚РІР°:** [С‡С‚Рѕ РЅСѓР¶РЅРѕ РїСЂРёР»РѕР¶РёС‚СЊ]
**РўСЂРµР±СѓРµРјРѕРµ РЅР°РєР°Р·Р°РЅРёРµ:** [СЂРµРєРѕРјРµРЅРґР°С†РёСЏ]

Р•СЃР»Рё РІ РѕРїРёСЃР°РЅРёРё СѓРїРѕРјРёРЅР°РµС‚СЃСЏ РєРѕРЅРєСЂРµС‚РЅРѕРµ РЅР°СЂСѓС€РµРЅРёРµ - РѕРїСЂРµРґРµР»Рё РєР°РєРѕРµ РїСЂР°РІРёР»Рѕ СЃРµСЂРІРµСЂР° РЅР°СЂСѓС€РµРЅРѕ."""
        
        response = AI_MODEL.generate_content(prompt)
        return jsonify({'success': True, 'response': response.text})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)[:200]})

@app.route('/api/arizona/trainer', methods=['POST'])
def api_arizona_trainer():
    if 'user' not in session: return jsonify({'error': 'Auth needed'}), 401
    
    data = request.json
    scenario = data.get('scenario', 'traffic_stop')
    user_message = data.get('message', '')
    history = data.get('history', [])

    # System prompts for different scenarios
    prompts = {
        'traffic_stop': "РўС‹ - РѕС„РёС†РµСЂ РїРѕР»РёС†РёРё LSPD РЅР° СЃРµСЂРІРµСЂРµ Arizona RP. РўРІРѕСЏ Р·Р°РґР°С‡Р°: РѕСЃС‚Р°РЅРѕРІРёС‚СЊ РёРіСЂРѕРєР° Р·Р° РЅР°СЂСѓС€РµРЅРёРµ РџР”Р” Рё РѕС‚С‹РіСЂР°С‚СЊ Р Рџ СЃРёС‚СѓР°С†РёСЋ (С‚СЂР°С„С„РёРє-СЃС‚РѕРї 10-55). Р‘СѓРґСЊ СЃС‚СЂРѕРіРёРј, РёСЃРїРѕР»СЊР·СѓР№ Р±РёРЅРґРµСЂРЅС‹Рµ РѕС‚С‹РіСЂРѕРІРєРё, РЅРѕ СЂРµР°РіРёСЂСѓР№ РЅР° РґРµР№СЃС‚РІРёСЏ РёРіСЂРѕРєР°. Р•СЃР»Рё РёРіСЂРѕРє С…РѕСЂРѕС€Рѕ РѕС‚С‹РіСЂС‹РІР°РµС‚ (/me, /do), С…РІР°Р»Рё РµРіРѕ РІ NonRP С‡Р°С‚Рµ (( )). Р•СЃР»Рё РїР»РѕС…Рѕ - РїРѕРґСЃРєР°Р·С‹РІР°Р№. РќР°С‡РЅРё СЃ С‚СЂРµР±РѕРІР°РЅРёСЏ Р·Р°РіР»СѓС€РёС‚СЊ РґРІРёРіР°С‚РµР»СЊ.",
        'medic_exam': "РўС‹ - РІСЂР°С‡ Р±РѕР»СЊРЅРёС†С‹ Р›РЎ. РўРІРѕСЏ Р·Р°РґР°С‡Р°: РїСЂРѕРІРµСЃС‚Рё РјРµРґ. РѕСЃРјРѕС‚СЂ РёРіСЂРѕРєР° РїСЂРёР·С‹РІРЅРёРєР°. РЎРїСЂР°С€РёРІР°Р№ Р¶Р°Р»РѕР±С‹, РїСЂРѕРІРµСЂСЏР№ Р·СЂРµРЅРёРµ, СЃР»СѓС€Р°Р№ СЃРµСЂРґС†Рµ. РСЃРїРѕР»СЊР·СѓР№ /me Рё /do. РћС†РµРЅРёРІР°Р№ СѓСЂРѕРІРµРЅСЊ Р Рџ РёРіСЂРѕРєР°.",
        'bar_fight': "РўС‹ - Р±Р°РЅРґРёС‚ РёР· Р“РµС‚С‚Рѕ (Vagos). РўС‹ РІ Р±Р°СЂРµ, РїСЊСЏРЅС‹Р№. Р”РѕРєРѕРїР°Р№СЃСЏ РґРѕ РёРіСЂРѕРєР°, РїСЂРѕРІРѕС†РёСЂСѓР№ РґСЂР°РєСѓ, РёСЃРїРѕР»СЊР·СѓР№ СЃР»РµРЅРі РіРµС‚С‚Рѕ. РџСЂРѕРІРµСЂСЊ, РєР°Рє РёРіСЂРѕРє Р±СѓРґРµС‚ СЂРµР°РіРёСЂРѕРІР°С‚СЊ: РёСЃРїСѓРіР°РµС‚СЃСЏ (РџР“?) РёР»Рё РѕС‚РІРµС‚РёС‚.",
        'interview': "РўС‹ - Р—Р°РјРµСЃС‚РёС‚РµР»СЊ Р”РёСЂРµРєС‚РѕСЂР° РЎРњР. РџСЂРѕРІРѕРґРёС€СЊ СЃРѕР±РµСЃРµРґРѕРІР°РЅРёРµ РёРіСЂРѕРєСѓ РЅР° РґРѕР»Р¶РЅРѕСЃС‚СЊ РЎС‚Р°Р¶РµСЂР°. РџСЂРѕРІРµСЂСЊ РµРіРѕ РїР°СЃРїРѕСЂС‚, РјРµРґРєР°СЂС‚Сѓ Рё Р»РёС†РµРЅР·РёРё РїРѕ Р Рџ. РЎРїСЂРѕСЃРё С‚РµСЂРјРёРЅС‹ (РњР“, РўРљ, Р”Рњ) РІ /b С‡Р°С‚."
    }

    system_instruction = prompts.get(scenario, prompts['traffic_stop'])
    
    # Construct chat context
    import google.generativeai as genai
    import time
    
    # List of models to try (prioritizing experimental/preview as they often have separate quotas)
    candidate_models = [
        'gemini-2.0-flash-exp',  # Experimental often has loose quotas
        'gemini-2.5-flash',      # Newest
        'gemini-2.0-flash',      # Stable
        'gemini-2.0-flash-lite-preview-02-05', # Lite version
        'gemini-2.0-flash-001'
    ]
    
    chat_history = []
    for msg in history:
        role = 'user' if msg['role'] == 'user' else 'model'
        chat_history.append({'role': role, 'parts': [msg['content']]})

    last_error = None
    
    for model_name in candidate_models:
        try:
            # print(f"Trying model: {model_name}") 
            model = genai.GenerativeModel(model_name, system_instruction=system_instruction)
            chat = model.start_chat(history=chat_history)
            response = chat.send_message(user_message)
            return jsonify({'success': True, 'reply': response.text})
            
        except Exception as e:
            last_error = e
            error_str = str(e)
            # If 404 (Not Found) or 429 (Quota), continue to next model
            if '404' in error_str or '429' in error_str or 'quota' in error_str.lower():
                continue
            else:
                # If random other error, probably stop? No, keep trying just in case.
                continue
                
    # If all failed
    import traceback
    traceback.print_exc()
    return jsonify({'error': f"All models failed. Last error: {str(last_error)}"}), 500

@app.route('/api/arizona/rules', methods=['POST'])
def api_arizona_rules():
    """Arizona RP rules helper - uses local database first"""
    data = request.json
    question = data.get('question', '').strip()
    
    if not question:
        return jsonify({'success': False, 'error': 'РџСѓСЃС‚РѕР№ РІРѕРїСЂРѕСЃ'})
    
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
            prompt = f"""РўС‹ - СЌРєСЃРїРµСЂС‚ РїРѕ РїСЂР°РІРёР»Р°Рј Arizona RP. Р—РЅР°РµС€СЊ РІСЃРµ РїСЂР°РІРёР»Р° СЃРµСЂРІРµСЂР°:

- DM (DeathMatch) - СѓР±РёР№СЃС‚РІРѕ Р±РµР· РїСЂРёС‡РёРЅС‹
- RK (RevengeKill) - РјРµСЃС‚СЊ РїРѕСЃР»Рµ СЃРјРµСЂС‚Рё
- PG (PowerGaming) - РЅРµСЂРµР°Р»РёСЃС‚РёС‡РЅС‹Рµ РґРµР№СЃС‚РІРёСЏ
- MG (MetaGaming) - РёСЃРїРѕР»СЊР·РѕРІР°РЅРёРµ OOC РёРЅС„РѕСЂРјР°С†РёРё РІ IC
- VDM (Vehicle DeathMatch) - СѓР±РёР№СЃС‚РІРѕ С‚СЂР°РЅСЃРїРѕСЂС‚РѕРј
- SK (SpawnKill) - СѓР±РёР№СЃС‚РІРѕ РЅР° СЃРїР°РІРЅРµ
- Р—РµР»С‘РЅС‹Рµ Р·РѕРЅС‹ - РјРµСЃС‚Р° РіРґРµ РЅРµР»СЊР·СЏ СЃС‚СЂРµР»СЏС‚СЊ
- Р§РёС‚С‹ - Р±Р°РЅ РЅР°РІСЃРµРіРґР°
- РћСЃРєРѕСЂР±Р»РµРЅРёСЏ - РјСѓС‚/Р±Р°РЅ

Р’РѕРїСЂРѕСЃ: {question}

Р”Р°Р№ С‡С‘С‚РєРёР№ РѕС‚РІРµС‚: СЌС‚Рѕ РЅР°СЂСѓС€РµРЅРёРµ РёР»Рё РЅРµС‚? РљР°РєРѕРµ РїСЂР°РІРёР»Рѕ? РљР°РєРѕРµ РЅР°РєР°Р·Р°РЅРёРµ?"""
            
            # Run AI with timeout to prevent eternal loading
            with concurrent.futures.ThreadPoolExecutor() as executor:
                future = executor.submit(AI_MODEL.generate_content, prompt)
                response = future.result(timeout=10) # 10 seconds timeout
            
            return jsonify({'success': True, 'response': response.text, 'source': 'ai'})
            
        except concurrent.futures.TimeoutError:
            return jsonify({'success': False, 'error': 'РЎРµСЂРІРµСЂ РїРµСЂРµРіСЂСѓР¶РµРЅ. РџРѕРїСЂРѕР±СѓР№С‚Рµ СЃС„РѕСЂРјСѓР»РёСЂРѕРІР°С‚СЊ РІРѕРїСЂРѕСЃ РєРѕСЂРѕС‡Рµ (Timeout).'})
        except Exception as e:
            if '429' in str(e):
                return jsonify({'success': False, 'error': 'Р›РёРјРёС‚ AI. РСЃРїРѕР»СЊР·СѓР№С‚Рµ РєР»СЋС‡РµРІС‹Рµ СЃР»РѕРІР°: DM, RK, PG, С‡РёС‚С‹, РєР°РїС‚'})
            return jsonify({'success': False, 'error': str(e)[:200]})
    
    return jsonify({'success': False, 'error': 'РџСЂР°РІРёР»Рѕ РЅРµ РЅР°Р№РґРµРЅРѕ. РџРѕРїСЂРѕР±СѓР№С‚Рµ: DM, RK, PG, MG, SK, TK, С‡РёС‚С‹'})

@app.route('/api/arizona/rules_list', methods=['GET'])
def api_arizona_rules_list():
    """Get list of all available rules"""
    if RULES_DB_LOADED:
        return jsonify({'success': True, 'response': get_all_rules_list()})
    return jsonify({'success': False, 'error': 'Р‘Р°Р·Р° РїСЂР°РІРёР» РЅРµ Р·Р°РіСЂСѓР¶РµРЅР°'})


@app.route('/api/arizona/smi/edit', methods=['POST'])
def api_arizona_smi_edit():
    """Smart Ad Editor using AI"""
    if not AI_MODEL:
        return jsonify({'success': False, 'error': 'AI РЅРµ РЅР°СЃС‚СЂРѕРµРЅ'})
    
    data = request.json
    text = data.get('text', '').strip()
    
    if not text:
        return jsonify({'success': False, 'error': 'Р’РІРµРґРёС‚Рµ С‚РµРєСЃС‚ РѕР±СЉСЏРІР»РµРЅРёСЏ'})
    
    try:
        prompt = f"""РўС‹ - РїСЂРѕС„РµСЃСЃРёРѕРЅР°Р»СЊРЅС‹Р№ СЃРѕС‚СЂСѓРґРЅРёРє РЎРњР РЅР° СЃРµСЂРІРµСЂРµ Arizona RP.
РўРІРѕСЏ Р·Р°РґР°С‡Р° - РѕС‚СЂРµРґР°РєС‚РёСЂРѕРІР°С‚СЊ РѕР±СЉСЏРІР»РµРЅРёРµ РёРіСЂРѕРєР° СЃРѕРіР»Р°СЃРЅРѕ РџР Рћ (РџСЂР°РІРёР»Р°Рј Р РµРґР°РєС‚РёСЂРѕРІР°РЅРёСЏ РћР±СЉСЏРІР»РµРЅРёР№).

Р’С…РѕРґСЏС‰РёР№ С‚РµРєСЃС‚: "{text}"

РџСЂР°РІРёР»Р°:
1. РСЃРїСЂР°РІСЊ РіСЂР°РјРјР°С‚РёС‡РµСЃРєРёРµ РѕС€РёР±РєРё.
2. РСЃРїРѕР»СЊР·СѓР№ РїРѕР»РЅС‹Рµ РЅР°Р·РІР°РЅРёСЏ С‚СЂР°РЅСЃРїРѕСЂС‚Р°/РіРѕСЂРѕРґРѕРІ (РЅСЂРі -> Рј/С† NRG-500, Р»СЃ -> Рі. Р›РѕСЃ-РЎР°РЅС‚РѕСЃ).
3. Р•СЃР»Рё С†РµРЅР° РЅРµ СѓРєР°Р·Р°РЅР° - РїРёС€Рё "Р¦РµРЅР°: Р”РѕРіРѕРІРѕСЂРЅР°СЏ".
4. Р•СЃР»Рё Р±СЋРґР¶РµС‚ РЅРµ СѓРєР°Р·Р°РЅ - РїРёС€Рё "Р‘СЋРґР¶РµС‚: РЎРІРѕР±РѕРґРЅС‹Р№".
5. Р¤РѕСЂРјР°С‚: [РўРёРї] РўРµРєСЃС‚ РѕР±СЉСЏРІР»РµРЅРёСЏ. Р¦РµРЅР°/Р‘СЋРґР¶РµС‚: ...
6. РќРµ РґРѕР±Р°РІР»СЏР№ "РљРѕРЅС‚Р°РєС‚: ..." РІ РєРѕРЅС†Рµ, СЌС‚Рѕ РґРµР»Р°РµС‚ РёРіСЂР° СЃР°РјР°.

РџСЂРёРјРµСЂС‹:
- "РїСЂРѕРґР°Рј РЅСЂРі 500" -> "РџСЂРѕРґР°Рј Рј/С† NRG-500. Р¦РµРЅР°: Р”РѕРіРѕРІРѕСЂРЅР°СЏ"
- "РєСѓРїР»СЋ РґРѕРј Р»СЃ 50РєРє" -> "РљСѓРїР»СЋ РґРѕРј РІ Рі. Р›РѕСЃ-РЎР°РЅС‚РѕСЃ. Р‘СЋРґР¶РµС‚: 50 РјР»РЅ$"
- "РЅР°Р±РѕСЂ РІ С„Р°РјСѓ" -> "РРґРµС‚ РЅР°Р±РѕСЂ РІ СЃРµРјСЊСЋ. РџСЂРѕСЃСЊР±Р° СЃРІСЏР·Р°С‚СЊСЃСЏ."
- "РїСЂРѕРґР°Рј Р°РєСЃ РїРѕРїСѓРіР°Р№" -> "РџСЂРѕРґР°Рј Р°/СЃ РџРѕРїСѓРіР°Р№ РЅР° РїР»РµС‡Рѕ. Р¦РµРЅР°: Р”РѕРіРѕРІРѕСЂРЅР°СЏ"

Р’РµСЂРЅРё РўРћР›Р¬РљРћ РѕС‚СЂРµРґР°РєС‚РёСЂРѕРІР°РЅРЅС‹Р№ С‚РµРєСЃС‚."""
        
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
                bg_prefix_exists = any(p in prev_word_raw for p in ['Р°/Рј', 'Рј/С†', 'РІ/С‚', 'Р»/С‚', 'СЃ/Рј', 'Р°РІС‚Рѕ', 'РјРѕС‚Рѕ'])
                
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
            r'\bРЅР°Р±РѕСЂ РІ СЃРµРјСЊСЋ\b': 'СЃРµРјСЊСЏ РёС‰РµС‚ СЂРѕРґСЃС‚РІРµРЅРЅРёРєРѕРІ',
            r'\bРЅР°Р±РѕСЂ РІ С„Р°РјСѓ\b': 'СЃРµРјСЊСЏ РёС‰РµС‚ СЂРѕРґСЃС‚РІРµРЅРЅРёРєРѕРІ',
            r'\bРіРµС‚С‚Рѕ\b': 'РѕРїР°СЃРЅС‹Р№ СЂР°Р№РѕРЅ',
            r'\bСЃРєРёРЅ\b': 'РѕРґРµР¶РґР°',
            r'\bС‚С‚\b': 'Twin Turbo',
            r'\bСЃРєР°Р№Рї\b': 'РјР°Р№РєР° "РЎРєР°Р№Рї"',
            r'\bРґРёСЃРєРѕСЂРґ\b': 'РјР°Р№РєР° "Р”РёСЃРєРѕСЂРґ"',
            r'\bС‚РµР»РµРіСЂР°Рј\b': 'РјР°Р№РєР° "РўРµР»РµРіСЂР°Рј"',
            r'\bСЃРєРёРґРѕС‡РЅС‹Р№ С‚Р°Р»РѕРЅ\b': 'РЎРµСЂС‚РёС„РёРєР°С‚ РЅР° СЃРєРёРґРєСѓ',
            r'\bРіСЂР°Р¶РґР°РЅСЃРєРёРµ С‚Р°Р»РѕРЅС‹\b': 'РўР°Р»РѕРЅС‹ РґР»СЏ РіСЂР°Р¶РґР°РЅ',
            r'\bРіСЂР°Р¶РґР°РЅРєРё\b': 'РўР°Р»РѕРЅС‹ РґР»СЏ РіСЂР°Р¶РґР°РЅ',
            r'\bРІС‹С€РєР° СЃ РЅРµС„С‚СЊСЋ\b': 'РќРµС„С‚СЏРЅР°СЏ РІС‹С€РєР°',
            r'\bРЅРµС„С‚РµРІС‹С€РєР°\b': 'РќРµС„С‚СЏРЅР°СЏ РІС‹С€РєР°',
            r'\badd vip\b': 'СЃРµСЂС‚РёС„РёРєР°С‚ "ADD VIP"',
            r'\bР°РґРґ РІРёРї\b': 'СЃРµСЂС‚РёС„РёРєР°С‚ "ADD VIP"',
            r'\bsamp bet\b': 'Р‘СѓРєРјРµРєРµСЂСЃРєР°СЏ РєРѕРЅС‚РѕСЂР°',
            r'\brare box\b': 'Р»Р°СЂРµС†', # Simplification, colors handled if needed
            r'\bРІРёРґРµРѕРєР°СЂС‚Р°\b': 'РРіСЂРѕРІР°СЏ РІРёРґРµРѕРєР°СЂС‚Р°',
            r'\bСЃРјР°Р·РєР° РґР»СЏ РІРёРґРµРѕРєР°СЂС‚С‹\b': 'С‚РµСЂРјРѕРїР°СЃС‚Р°',
            r'\bР»Р°СЂРµС† СЃ РїСЂРµРјРёРµР№\b': 'РїСЂРµРјРёР°Р»СЊРЅС‹Р№ Р»Р°СЂРµС†',
            r'\bР»Р°СЂРµС† СЃСѓРїРµСЂ Р±РѕРєСЃ РєР°СЂ\b': 'СЌРєСЃРєР»СЋР·РёРІРЅС‹Р№ Р»Р°СЂРµС† СЃ С‚/СЃ',
            r'\bС„СѓР»Р» СЃРµРјСЊСЏ\b': 'РЎРµРјСЊСЏ СЃРѕ РІСЃРµРјРё СѓРґРѕР±СЃС‚РІР°РјРё',
            r'\bР±РѕРєСЃС‹ СЃ РѕРґРµР¶РґРѕР№\b': 'РєРѕСЂРѕР±РєР° СЃ РѕРґРµР¶РґРѕР№',
            r'\bР»Р°СЂРµС† РѕСЂРіР°РЅРёР·Р°С†РёРё\b': 'Р»Р°СЂРµС† РѕСЂРіР°РЅРёР·Р°С†РёРё',
            r'\bР±РёР»РµС‚ РЅР° Р°РЅС‚РёРєРѕРјРёСЃСЃРёСЋ\b': 'Р‘РёР»РµС‚ РЅР° Р°РЅС‚РёРєРѕРј',
            r'\bС‚Р°Р»РѕРЅ Р°РЅС‚РёРІР°СЂРЅР°\b': 'РЎРµСЂС‚РёС„РёРєР°С‚ РЅР° СЃРЅСЏС‚РёРµ РїСЂРµРґСѓРїСЂРµР¶РґРµРЅРёСЏ',
            r'\bС‚Р°Р»РѕРЅ Р°РЅС‚РёРґРµРјРѕСЂРіР°РЅР°\b': 'Р‘РёР»РµС‚ РІС‹С…РѕРґР° РёР· РїСЃРёС…. Р±РѕР»СЊРЅРёС†С‹',
            r'\bС‚Р°Р»РѕРЅ РЅР° СЃРјРµРЅСѓ РЅРёРєР°\b': 'СЃРµСЂС‚РёС„РёРєР°С‚ РЅР° СЃРјРµРЅСѓ РёРјРµРЅРё',
            r'\bР·Р°С‚РѕС‡РєРё\b': 'Р“СЂР°РІРёСЂРѕРІРєР°',
            r'\bР·Р°С‚РѕС‡РєР°\b': 'Р“СЂР°РІРёСЂРѕРІРєР°',
            r'\bРѕР±СЉРµРєС‚ РґР»СЏ РґРѕРјР°\b': 'РґРµРєРѕСЂР°С†РёСЏ',
            r'\bРѕР±СЉРµРєС‚\b': 'РґРµРєРѕСЂР°С†РёСЏ',
            r'\bРїРµСЂРµРґР°РІР°РµРјР°СЏ РІРёР·Р°\b': 'СЂР°Р·СЂРµС€РµРЅРёРµ РЅР° СЂР°Р±РѕС‚Сѓ РЅР° РѕСЃС‚СЂРѕРІРµ VC',
            r'\bbattlepass\b': 'Р±РёР»РµС‚ "Р‘Р°С‚Р»РџР°СЃСЃ"',
            r'\bР±Рї\b': 'Р±РёР»РµС‚ "Р‘Р°С‚Р»РџР°СЃСЃ"',
            r'\bexp РґР»СЏ battle pass\b': 'С‚Р°Р»РѕРЅ РЅР° РїРѕР»СѓС‡РµРЅРёРµ "Р‘РѕРµРІРѕРіРѕ РѕРїС‹С‚Р°"',
            r'\bexp Р±Рї\b': 'С‚Р°Р»РѕРЅ РЅР° РїРѕР»СѓС‡РµРЅРёРµ "Р‘РѕРµРІРѕРіРѕ РѕРїС‹С‚Р°"',
            r'\bС„СѓР»Р» СЃРєРёР»Р»С‹\b': 'РјР°РЅСѓР°Р» "РѕР±СѓС‡РµРЅРёРµ РЅР°РІС‹РєР°Рј СЃС‚СЂРµР»СЊР±С‹"',
            r'\bРєРѕРґ С‚СЂРёР»РѕРіРёРё\b': 'Р’РёРґРµРѕРёРіСЂР° С‚СЂРёР»РѕРіРёСЏ',
            r'\bРїРµСЂРµРґР°РІР°РµРјС‹Рµ az\b': 'AZ РјРѕРЅРµС‚С‹',
            r'\bС‚Р°Р»РѕРЅ РЅР° С…4 РїРµР№РґРµР№\b': 'РЎРµСЂС‚РёС„РёРєР°С‚ С…4 РїРµР№РґРµР№',
            r'\bР»Р°РІРєР°\b': 'РўРѕСЂРіРѕРІР°СЏ Р»Р°РІРєР°',
            r'\bРѕРїС‹С‚ РґРµРїРѕР·РёС‚Р°\b': 'РљРѕР»Р»РµРєС†РёРѕРЅРЅР°СЏ РєР°СЂС‚РѕС‡РєР° "РћРїС‹С‚ РґРµРїРѕР·РёС‚Р°"',

            # Abbreviations (General)
            r'\bР°/Рј\b': 'Р°/Рј', # Keep valid ones
            r'\bР°РІС‚Рѕ\b': 'Р°/Рј',
            r'\bРјР°С€РёРЅСѓ\b': 'Р°/Рј',
            r'\bС‚Р°С‡РєСѓ\b': 'Р°/Рј',
            r'\bРјРѕС‚Рѕ\b': 'Рј/С†',
            r'\bР±Р°Р№Рє\b': 'Рј/С†',
            r'\bРІРµР»РёРє\b': 'РІ/С‚',
            r'\bРІРµР»РѕСЃРёРїРµРґ\b': 'РІ/С‚',
            r'\bРІРµСЂС‚РѕР»РµС‚\b': 'РІ/С‚',
            r'\bРјР°РІРµСЂ\b': 'РІ/С‚ Maverick',
            r'\bРіРѕСЂРЅРёРє\b': 'РІ/С‚ Mountain Bike',
            r'\bР»РѕРґРєР°\b': 'Р»/С‚',
            r'\bСЃР°РјРѕР»РµС‚\b': 'СЃ/Рј',
            r'\bР°РєСЃ\b': 'Р°/СЃ',
            r'\bР±СЂРѕРЅ\b': 'Р°/СЃ', # Armor is accessory
            r'\bРїРѕС€РёРІ\b': 'Рѕ/Рї',
            r'\bРѕРґРµР¶РґР°\b': 'Рѕ/Рї', # Sometimes useful
            r'\bРјРѕРґ\b': 'Рј/С„',
            r'\bРјРѕРґРёС„РёРєР°С†РёСЏ\b': 'Рј/С„',
            r'\bРѕР±СЉРµРєС‚С‹\b': 'Рѕ/Р±',
            r'\bР»Р°СЂС†С‹\b': 'Р»/С†',
            r'\bР»Р°СЂРµС†\b': 'Р»/С†',
            r'\bРґРµС‚\b': 'Рґ/С‚',
            r'\bС‚СЋРЅРёРЅРі\b': 'Рґ/С‚',
            r'\bСЂРµСЃС‹\b': 'СЂ/СЃ',
            r'\bСЂРµСЃСѓСЂСЃС‹\b': 'СЂ/СЃ',
            r'\bР±РёР·\b': 'Р±/Р·',
            r'\bР±РёР·РЅРµСЃ\b': 'Р±/Р·',
            r'\bРЅРѕРјРµСЂ\b': 'РЅ/Р·',
            r'\bРЅРѕРјРµСЂР°\b': 'РЅ/Р·',

            # Business Specific
            r'\b24/7\b': 'РјР°РіР°Р·РёРЅ 24/7',
            r'\bР°РјРјРѕ\b': 'РјР°РіР°Р·РёРЅ РѕСЂСѓР¶РёСЏ',
            r'\bР°Р·СЃ\b': 'РђР—РЎ',

            # Locations
            r'\bР»СЃ\b': 'Рі. Р›РѕСЃ-РЎР°РЅС‚РѕСЃ',
            r'\bСЃС„\b': 'Рі. РЎР°РЅ-Р¤РёРµСЂСЂРѕ',
            r'\bР»РІ\b': 'Рі. Р›Р°СЃ-Р’РµРЅС‚СѓСЂР°СЃ',
            r'\bС†СЂ\b': 'С†РµРЅС‚СЂР°Р»СЊРЅРѕРіРѕ СЂС‹РЅРєР°',
            r'\bР°Р±\b': 'Р°РІС‚РѕР±Р°Р·Р°СЂР°',

            # Junk Clean
            r'\bРјР°СЂРєРё\b': '',
            r'\bС„РёСЂРјС‹\b': '',
            r'\bРјРѕРґРµР»Рё\b': '',

            # Actions & Prices
            r'\bРї\b': 'РџСЂРѕРґР°Рј',
            r'\bРє\b': 'РљСѓРїР»СЋ',
            r'\bРѕР±РјРµРЅСЏСЋ\b': 'РћР±РјРµРЅСЏСЋ',
            r'\bС‚РѕСЂРі\b': 'Р¦РµРЅР°: Р”РѕРіРѕРІРѕСЂРЅР°СЏ',
            r'\bР±РµР· С‚РѕСЂРіР°\b': 'Р¦РµРЅР°: РћРєРѕРЅС‡Р°С‚РµР»СЊРЅР°СЏ',
            r'\bСЃРІРѕР±РѕРґРЅС‹Р№\b': 'Р‘СЋРґР¶РµС‚: РЎРІРѕР±РѕРґРЅС‹Р№'
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
        is_buying = any(x in fallback_text.lower() for x in ['РєСѓРїР»СЋ', 'РёС‰Сѓ', 'РІРѕР·СЊРјСѓ'])
        
        # Add prefix if missing
        if not any(x in fallback_text.lower() for x in ['РїСЂРѕРґР°Рј', 'РєСѓРїР»СЋ', 'РѕР±РјРµРЅСЏСЋ', 'СЃРґР°Рј', 'Р°СЂРµРЅРґСѓСЋ']):
            fallback_text = ("РљСѓРїР»СЋ " if is_buying else "РџСЂРѕРґР°Рј ") + fallback_text

        # Add Suffix (Price/Budget)
        has_price = any(x in fallback_text.lower() for x in ['С†РµРЅР°', 'Р±СЋРґР¶РµС‚', 'РґРѕРіРѕРІРѕСЂРЅР°СЏ', 'СЃРІРѕР±РѕРґРЅС‹Р№'])
        if not has_price:
            if is_buying:
                fallback_text += ". Р‘СЋРґР¶РµС‚: РЎРІРѕР±РѕРґРЅС‹Р№"
            else:
                fallback_text += ". Р¦РµРЅР°: Р”РѕРіРѕРІРѕСЂРЅР°СЏ"

        # Capitalize Sentence
        if fallback_text:
            fallback_text = fallback_text[0].upper() + fallback_text[1:]

        # Price Formatting (1Рє -> 1.000$)
        def format_price(match):
            val = match.group(1)
            suffix = match.group(2).lower()
            if suffix == 'Рє': return f"{val}.000$"
            if suffix == 'РєРє': return f"{val}.000.000$"
            return match.group(0)
        
        fallback_text = re.sub(r'(\d+)(Рє{1,2})', format_price, fallback_text, flags=re.IGNORECASE)

        return jsonify({
            'success': True, 
            'response': f"{fallback_text} (Offline Mode v2 - {db_status})", 
            'source': 'fallback_pro_v2'
        })

@app.route('/api/arizona/smi/data')
def api_arizona_smi_data():
    """Get SMI Data (Rules logic)"""
    return jsonify({
        'ppe_summary': PPE_TEXT if SMI_RULES_LOADED else "РџСЂР°РІРёР»Р° РЅРµ Р·Р°РіСЂСѓР¶РµРЅС‹",
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
            tag = 'РќРѕРІРѕСЃС‚Рё'
            lower_text = (title + summary).lower()
            if 'РѕР±РЅРѕРІР»РµРЅРёРµ' in lower_text: tag = 'РћР±РЅРѕРІР»РµРЅРёРµ'
            elif 'x4' in lower_text or 'РєРѕРЅРєСѓСЂСЃ' in lower_text: tag = 'РђРєС†РёСЏ'
            elif 'Р»РёРґРµСЂ' in lower_text or 'Р·Р°СЏРІРєРё' in lower_text: tag = 'РќР°Р±РѕСЂ'

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
                'title': 'РќРѕРІРѕСЃС‚Рё Arizona State',
                'date': datetime.now().strftime('%d.%m.%Y %H:%M'),
                'tag': 'Р’Р°Р¶РЅРѕ',
                'image': '/static/img/arizona_logo.png', 
                'summary': 'РЎР»РµРґРёС‚Рµ Р·Р° РІСЃРµРјРё Р°РєС‚СѓР°Р»СЊРЅС‹РјРё РЅРѕРІРѕСЃС‚СЏРјРё, РѕР±РЅРѕРІР»РµРЅРёСЏРјРё РїСЂР°РІРёР» Рё РІР°Р¶РЅС‹РјРё СЃРѕР±С‹С‚РёСЏРјРё СЃРµСЂРІРµСЂР° РІ РЅР°С€РµР№ РѕС„РёС†РёР°Р»СЊРЅРѕР№ РіСЂСѓРїРїРµ Р’РљРѕРЅС‚Р°РєС‚Рµ.',
                'likes': 100,
                'url': 'https://vk.com/arizonastaterp'
            },
            {
                'id': 'fallback_2',
                'title': 'РўРµС…РЅРёС‡РµСЃРєРёР№ СЂР°Р·РґРµР»',
                'date': (datetime.now()).strftime('%d.%m.%Y %H:%M'),
                'tag': 'Info',
                'image': '/static/img/arizona_logo.png',
                'summary': 'Р•СЃР»Рё Сѓ РІР°СЃ РІРѕР·РЅРёРєР»Рё С‚РµС…РЅРёС‡РµСЃРєРёРµ РїСЂРѕР±Р»РµРјС‹ РёР»Рё РІРѕРїСЂРѕСЃС‹ РїРѕ РґРѕРЅР°С‚Сѓ, РѕР±СЂР°С‚РёС‚РµСЃСЊ РІ С‚РµС…РЅРёС‡РµСЃРєРёР№ СЂР°Р·РґРµР» РЅР° С„РѕСЂСѓРјРµ РёР»Рё РІ РіСЂСѓРїРїРµ.',
                'likes': 50,
                'url': 'https://vk.com/arizonastaterp'
            },
             {
                'id': 'fallback_3',
                'title': 'РљР°Рє РЅР°С‡Р°С‚СЊ РёРіСЂР°С‚СЊ?',
                'date': (datetime.now()).strftime('%d.%m.%Y %H:%M'),
                'tag': 'Р“Р°Р№Рґ',
                'image': '/static/img/arizona_logo.png',
                'summary': 'РЎРєР°С‡РёРІР°Р№С‚Рµ Р»Р°СѓРЅС‡РµСЂ, СЂРµРіРёСЃС‚СЂРёСЂСѓР№С‚РµСЃСЊ РЅР° СЃРµСЂРІРµСЂРµ Arizona State Рё РІРІРѕРґРёС‚Рµ РїСЂРѕРјРѕРєРѕРґС‹ РґР»СЏ Р±С‹СЃС‚СЂРѕРіРѕ СЃС‚Р°СЂС‚Р°!',
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

# --- REPUTATION SYSTEM ---
@app.route('/api/reputation/give', methods=['POST'])
def api_reputation_give():
    if 'user' not in session: return jsonify({'success': False, 'error': 'Auth needed'}), 401
    
    data = request.json
    target_id = data.get('target_id')
    sender_id = session['user']['id']
    
    if not target_id: return jsonify({'success': False, 'error': 'Target required'})
    if str(target_id) == str(sender_id):
        return jsonify({'success': False, 'error': 'РќРµР»СЊР·СЏ РїРѕРІС‹С€Р°С‚СЊ СЂРµРїСѓС‚Р°С†РёСЋ СЃР°РјРѕРјСѓ СЃРµР±Рµ'})
        
    # Check if target exists
    t_row = execute_query("SELECT username, reputation FROM users WHERE id = %s", (target_id,), fetch_one=True)
    if not t_row: return jsonify({'success': False, 'error': 'User not found'})
    
    # Update Reputation
    new_rep = t_row[1] + 1
    execute_query("UPDATE users SET reputation = %s WHERE id = %s", (new_rep, target_id), commit=True)
    
    add_log('info', f"Reputation given: {session['user']['username']} -> {t_row[0]}")
    
    return jsonify({'success': True, 'new_rep': new_rep})

@app.route('/api/reputation/top')
def api_reputation_top():
    # Return top 10 users by reputation
    rows = execute_query("SELECT id, username, avatar, reputation, role FROM users ORDER BY reputation DESC LIMIT 10", fetch_all=True)
    
    top_list = []
    for r in rows:
        top_list.append({
            'id': str(r[0]),
            'username': r[1],
            'avatar': get_valid_avatar(r[2]),
            'reputation': r[3],
            'role': r[4]
        })
        
    return jsonify({'success': True, 'top': top_list})

    return jsonify({'success': True, 'top': top_list})

# --- SERVER MANAGEMENT API ---

@app.route('/api/servers', methods=['GET'])
def api_get_servers():
    """Return all servers for the current user"""
    if 'user' not in session:
        return jsonify({'success': False, 'error': 'Auth required'}), 401
    
    try:
        uid = int(session['user']['id'])
    except:
        uid = 0 # Should not happen if auth valid
    
    # Get user's servers from DB
    # Ensure param is tuple
    rows = execute_query("SELECT server_id FROM server_members WHERE user_id = %s", (uid,), fetch_all=True)
    user_server_ids = [r[0] for r in rows]
    
    # Filter global DB
    user_servers = {}
    
    # 1. Add User's Servers (Validation against server_members)
    for sid, data in servers_db.items():
        if sid in user_server_ids:
            user_servers[sid] = data
            
    # 2. Force Include System Servers (Bypass DB check)
    system_servers = ['home', 'ai', 'smi']
    
    # Check if admin
    is_admin = session['user'].get('role') in ['developer', 'tester', 'admin']
    if is_admin:
        system_servers.append('admin')
        
    for sys_sid in system_servers:
        if sys_sid in servers_db:
            user_servers[sys_sid] = servers_db[sys_sid]
    
    return jsonify({'success': True, 'servers': user_servers})

@app.route('/api/servers/create', methods=['POST'])
def api_create_server():
    if 'user' not in session: return jsonify({'success': False, 'error': 'Auth required'}), 401
    
    data = request.json
    name = data.get('name')
    icon_data = data.get('icon_data') # Base64 string
    
    if not name: return jsonify({'success': False, 'error': 'Name required'})

    sid = f"srv_{int(time.time()*1000)}"
    
    # Process Icon
    icon_url = 'server' # Default icon class (font-awesome) or url
    is_image = False
    
    if icon_data and 'base64,' in icon_data:
        try:
            # Save base64 image
            import base64 as b64
            header, encoded = icon_data.split(",", 1)
            ext = 'png'
            if 'jpeg' in header: ext = 'jpg'
            if 'gif' in header: ext = 'gif'
            
            filename = f"{sid}.{ext}"
            filepath = os.path.join('static', 'uploads', 'icons', filename)
            os.makedirs(os.path.dirname(filepath), exist_ok=True)
            
            with open(filepath, "wb") as f:
                f.write(b64.b64decode(encoded))
            
            icon_url = f"/static/uploads/icons/{filename}"
            is_image = True
        except Exception as e:
            print(f"Icon save error: {e}")

    # Rich Default Structure per User Request
    # Empty Default Structure per User Request
    default_channels = []

    # Default Roles
    default_roles = [
        { 'id': 'role_everyone', 'name': '@everyone', 'color': '#99aab5', 'permissions': 0 },
        { 'id': 'role_admin', 'name': 'Administrator', 'color': '#E91E63', 'permissions': 8, 'hoist': True },
        { 'id': 'role_mod', 'name': 'Moderator', 'color': '#2ECC71', 'permissions': 4, 'hoist': True }
    ]

    # Validating ID type
    try:
        user_id_int = int(session['user']['id'])
    except:
        user_id_int = 0

    servers_db[sid] = {
        'name': name,
        'icon': icon_url, 
        'is_image': is_image,
        'owner': session['user']['id'],
        'roles': default_roles,
        'channels': default_channels
    }
    save_servers()
    
    # Add creator as owner member
    # Use standard execute_query with tuple params and %s for cross-compatibility
    try:
        # Check if already exists (shouldn't for new server)
        # We use %s because execute_query handles SQLite conversion automatically
        execute_query(
            'INSERT INTO server_members (server_id, user_id, role, joined_at) VALUES (%s, %s, %s, %s)',
            (sid, user_id_int, 'owner', time.time()),
            commit=True
        )
        print(f"[+] Server {sid} created by user {user_id_int}")
    except Exception as e:
        print(f"[!] Server member insert error: {e}")
        # Retrying with string ID just in case of schema mismatch in legacy DBs
        try:
             execute_query(
                'INSERT INTO server_members (server_id, user_id, role, joined_at) VALUES (%s, %s, %s, %s)',
                (sid, session['user']['id'], 'owner', time.time()),
                commit=True
            )
        except:
            pass # Fail double safe
    
    return jsonify({'success': True, 'server': servers_db[sid], 'id': sid})

@app.route('/api/servers/<sid>/channels/create', methods=['POST'])
def api_create_channel(sid):
    if 'user' not in session: return jsonify({'success': False, 'error': 'Auth required'}), 401
    if sid not in servers_db: return jsonify({'success': False, 'error': 'Server not found'})
    
    data = request.json
    name = data.get('name')
    ctype = data.get('type', 'channel') 
    cat_id = data.get('category_id') # insert after this
    
    if not name: return jsonify({'success': False, 'error': 'Name required'})

    cid = f"ch_{int(time.time()*1000)}"
    new_chan = {
        'id': cid,
        'type': ctype, 
        'name': name,
        'icon': 'hashtag' if ctype == 'channel' else ('microphone' if ctype == 'voice' else '')
    }
    
    channels = servers_db[sid]['channels']
    
    if cat_id:
        # Find index of category
        idx = -1
        for i, c in enumerate(channels):
            if c['id'] == cat_id:
                idx = i
                break
        
        if idx != -1:
            channels.insert(idx + 1, new_chan)
        else:
             channels.append(new_chan)
    else:
        channels.append(new_chan)
        
    save_servers()
    return jsonify({'success': True, 'channel': new_chan})
        
    save_servers()
    return jsonify({'success': True, 'channel': new_chan})

@app.route('/api/servers/<sid>/channels/<cid>/delete', methods=['POST'])
def api_delete_channel(sid, cid):
     if 'user' not in session: return jsonify({'success': False, 'error': 'Auth required'}), 401
     if sid not in servers_db: return jsonify({'success': False, 'error': 'Server not found'})
     
     servers_db[sid]['channels'] = [c for c in servers_db[sid]['channels'] if c['id'] != cid]
     save_servers()
     return jsonify({'success': True})

@app.route('/api/servers/<sid>/update', methods=['POST'])
def api_update_server(sid):
    if 'user' not in session: return jsonify({'success': False, 'error': 'Auth required'}), 401
    if sid not in servers_db: return jsonify({'success': False, 'error': 'Server not found'}), 404
    
    data = request.json
    name = data.get('name', '').strip()
    description = data.get('description', '').strip()
    
    if not name:
        return jsonify({'success': False, 'error': 'Server name is required'}), 400
    
    # Update server data
    servers_db[sid]['name'] = name
    if description:
        servers_db[sid]['description'] = description
    
    save_servers()
    return jsonify({'success': True, 'server': servers_db[sid]})

@app.route('/api/servers/<sid>/members', methods=['GET'])
def api_get_server_members(sid):
    if 'user' not in session: return jsonify({'success': False, 'error': 'Auth required'}), 401
    if sid not in servers_db: return jsonify({'success': False, 'error': 'Server not found'}), 404
    
    # Get actual members of this server from server_members table
    rows = execute_query('''
        SELECT u.id, u.username, u.avatar, u.display_name, sm.role 
        FROM server_members sm 
        JOIN users u ON sm.user_id = u.id 
        WHERE sm.server_id = ?
    ''', (sid,), fetch_all=True)
    
    members = []
    for r in rows:
        members.append({
            'id': str(r[0]),
            'username': r[1],
            'avatar': get_valid_avatar(r[2]),
            'display_name': r[3],
            'role': r[4] if len(r) > 4 else 'member'
        })
    
    return jsonify({'success': True, 'members': members})

@app.route('/api/servers/<sid>/roles', methods=['GET'])
def api_get_server_roles(sid):
    if 'user' not in session: return jsonify({'success': False, 'error': 'Auth required'}), 401
    if sid not in servers_db: return jsonify({'success': False, 'error': 'Server not found'}), 404
    
    # Get roles from server data
    roles = servers_db[sid].get('roles', [])
    
    # If no roles exist, create default ones
    if not roles:
        roles = [
            {'id': 'everyone', 'name': '@everyone', 'color': '#99aab5', 'permissions': []},
            {'id': 'admin', 'name': 'Admin', 'color': '#e74c3c', 'permissions': ['administrator']},
            {'id': 'moderator', 'name': 'Moderator', 'color': '#3498db', 'permissions': ['manage_channels']}
        ]
        servers_db[sid]['roles'] = roles
        save_servers()
    
    return jsonify({'success': True, 'roles': roles})

threading.Thread(target=simulate, daemon=True).start()




@app.route('/api/channels/<cid>/messages', methods=['GET'])
def api_get_channel_messages(cid):
    if 'user' not in session: return jsonify({'success': False, 'error': 'Auth'}), 401
    
    # Find channel in any server
    target_channel = None
    for sid, sdata in servers_db.items():
        for ch in sdata['channels']:
            if ch['id'] == cid:
                target_channel = ch
                break
        if target_channel: break
    
    if not target_channel: return jsonify({'success': False, 'error': 'Channel not found'})
    
    # Return messages (default [])
    msgs = target_channel.get('messages', [])
    return jsonify({'success': True, 'messages': msgs})

@app.route('/api/channels/<cid>/messages', methods=['POST'])
def api_post_channel_message(cid):
    if 'user' not in session: return jsonify({'success': False, 'error': 'Auth'}), 401
    
    data = request.json
    content = data.get('content')
    if not content: return jsonify({'success': False})
    
    user = session['user']
    
    # Find channel
    target_channel = None
    target_sid = None
    for sid, sdata in servers_db.items():
        for ch in sdata['channels']:
            if ch['id'] == cid:
                target_channel = ch
                target_sid = sid
                break
        if target_channel: break
        
    if not target_channel: return jsonify({'success': False, 'error': 'Not found'})
    
    if 'messages' not in target_channel: target_channel['messages'] = []
    
    msg_obj = {
        'id': f'msg_{int(time.time()*1000)}_{random.randint(100,999)}',
        'author_id': user['id'],
        'author': user['username'], # Snapshot
        'avatar': user['avatar'],
        'content': content,
        'timestamp': time.time()
    }
    
    target_channel['messages'].append(msg_obj)
    # Limit history
    if len(target_channel['messages']) > 50:
        target_channel['messages'] = target_channel['messages'][-50:]
        
    save_servers()
    
    # Socket emit
    socketio.emit('new_channel_message', {'sid': target_sid, 'cid': cid, 'message': msg_obj})
    
    return jsonify({'success': True, 'message': msg_obj})



# --- FRIEND SYSTEM APIs ---
@app.route('/api/friends', methods=['GET'])
def api_get_friends():
    if 'user' not in session: return jsonify({'success': False, 'error': 'Auth needed'}), 401
    uid = int(session['user']['id'])
    
    # Helper to format user
    def fmt_user(row):
        avatar = get_valid_avatar(row[2])
        return {'id': str(row[0]), 'username': row[1], 'avatar': avatar, 'display_name': row[3]}

    friends = []
    incoming = []
    outgoing = []
    
    # 1. Incoming: I am user_2, status pending
    rows_in = execute_query("""
        SELECT u.id, u.username, u.avatar, u.display_name 
        FROM friends f 
        JOIN users u ON u.id = f.user_id_1 
        WHERE f.user_id_2 = %s AND f.status = 'pending'
    """, (uid,), fetch_all=True)
    
    for r in rows_in: incoming.append(fmt_user(r))
        
    # 2. Outgoing: I am user_1, status pending
    rows_out = execute_query("""
        SELECT u.id, u.username, u.avatar, u.display_name 
        FROM friends f 
        JOIN users u ON u.id = f.user_id_2 
        WHERE f.user_id_1 = %s AND f.status = 'pending'
    """, (uid,), fetch_all=True)
    
    for r in rows_out: outgoing.append(fmt_user(r))
         
    # 3. Friends: Accepted
    rows_friends = execute_query("""
        SELECT u.id, u.username, u.avatar, u.display_name
        FROM friends f
        JOIN users u ON (u.id = f.user_id_1 OR u.id = f.user_id_2)
        WHERE (f.user_id_1 = %s OR f.user_id_2 = %s) 
        AND f.status = 'accepted'
        AND u.id != %s
    """, (uid, uid, uid), fetch_all=True)

    for r in rows_friends: friends.append(fmt_user(r))
        
    return jsonify({'success': True, 'friends': friends, 'incoming': incoming, 'outgoing': outgoing})

@app.route('/api/friends/request', methods=['POST'])
def api_friend_request():
    if 'user' not in session: return jsonify({'success': False, 'error': 'Auth needed'}), 401
    
    data = request.json
    target_username = data.get('username')
    sender_id = int(session['user']['id'])
    
    if not target_username: return jsonify({'success': False, 'error': 'Username required'})
    
    # Find target
    row = execute_query('SELECT id FROM users WHERE username = %s', (target_username,), fetch_one=True)
    if not row: return jsonify({'success': False, 'error': 'User not found'})
    target_id = int(row[0])
    
    if target_id == sender_id:
        return jsonify({'success': False, 'error': 'Cannot add yourself'})
        
    # Check existing
    existing = execute_query('SELECT status FROM friends WHERE (user_id_1 = %s AND user_id_2 = %s) OR (user_id_1 = %s AND user_id_2 = %s)', 
                             (sender_id, target_id, target_id, sender_id), fetch_one=True)
    if existing:
        st = existing[0]
        if st == 'accepted': return jsonify({'success': False, 'error': 'Already friends'})
        return jsonify({'success': False, 'error': 'Request already pending'})
    
    # Insert (Sender is 1)
    execute_query('INSERT INTO friends (user_id_1, user_id_2, status, created_at) VALUES (%s, %s, %s, %s)',
                  (sender_id, target_id, 'pending', time.time()), commit=True)
    
    return jsonify({'success': True})

@app.route('/api/friends/accept', methods=['POST'])
def api_friend_accept():
    if 'user' not in session: return jsonify({'success': False}), 401
    data = request.json
    try:
        target_id = int(data.get('id')) # The person who SENT the request
    except:
        return jsonify({'success': False, 'error': 'Invalid ID'})
    my_id = int(session['user']['id'])
    
    chk = execute_query('SELECT id FROM friends WHERE user_id_1 = %s AND user_id_2 = %s AND status = %s', 
                        (target_id, my_id, 'pending'), fetch_one=True)
    if not chk:
        return jsonify({'success': False, 'error': 'No pending request found'})
        
    execute_query('UPDATE friends SET status = %s WHERE id = %s', ('accepted', chk[0]), commit=True)
    
    return jsonify({'success': True})

# --- DM ROUTES ---

def get_or_create_dm(user1_id, user2_id):
    # Prevent self-DMs
    if user1_id == user2_id:
        return None
    
    # Ensure consistent ordering for lookup
    if user1_id > user2_id: user1_id, user2_id = user2_id, user1_id
    
    row = execute_query('SELECT id FROM direct_messages WHERE user_id_1 = %s AND user_id_2 = %s', (user1_id, user2_id), fetch_one=True)
    if row: return row[0]
    
    # Create
    execute_query('INSERT INTO direct_messages (user_id_1, user_id_2, last_message_at) VALUES (%s, %s, %s)',
                  (user1_id, user2_id, time.time()), commit=True)
    
    # Fetch back
    row = execute_query('SELECT id FROM direct_messages WHERE user_id_1 = %s AND user_id_2 = %s', (user1_id, user2_id), fetch_one=True)
    return row[0]

@app.route('/api/dms', methods=['GET'])
def api_get_dms():
    if 'user' not in session: return jsonify({'success': False}), 401
    my_id = int(session['user']['id'])
    
    # 1. Get DMs where I am involved
    rows = execute_query("""
        SELECT dm.id, dm.user_id_1, dm.user_id_2, dm.last_message_at
        FROM direct_messages dm
        WHERE dm.user_id_1 = %s OR dm.user_id_2 = %s
        ORDER BY dm.last_message_at DESC
    """, (my_id, my_id), fetch_all=True)
    
    dms = []
    for r in rows:
        dm_id = r[0]
        u1 = r[1]
        u2 = r[2]
        ts = r[3]
        
        # Determine who the other is
        other_id = u2 if u1 == my_id else u1
        
        # Skip self-DMs (shouldn't exist but filter just in case)
        if other_id == my_id:
            continue
        
        # Get other user info
        u_row = execute_query("SELECT username, avatar, display_name FROM users WHERE id = %s", (other_id,), fetch_one=True)
        if not u_row: continue
        
        dms.append({
            'id': str(dm_id),
            'other_user': {
                'id': str(other_id),
                'username': u_row[0],
                'avatar': u_row[1] if u_row[1] else DEFAULT_AVATAR,
                'display_name': u_row[2]
            },
            'last_message_at': ts
        })
        
    return jsonify({'success': True, 'dms': dms})

@app.route('/api/dms/by_id/<int:dm_id>/messages', methods=['GET'])
def api_dm_messages_by_id(dm_id):
    """Get messages for a specific DM conversation by DM ID"""
    if 'user' not in session: 
        return jsonify({'success': False}), 401
    my_id = int(session['user']['id'])
    
    # Verify user is part of this DM
    dm_row = execute_query('SELECT user_id_1, user_id_2 FROM direct_messages WHERE id = %s', (dm_id,), fetch_one=True)
    if not dm_row:
        return jsonify({'success': False, 'error': 'DM not found'}), 404
    
    if my_id not in [dm_row[0], dm_row[1]]:
        return jsonify({'success': False, 'error': 'Access denied'}), 403
    
    # Fetch ALL messages ordered chronologically
    rows = execute_query("""
        SELECT dm.content, dm.timestamp, u.username, u.avatar 
        FROM dm_messages dm
        JOIN users u ON u.id = dm.author_id
        WHERE dm.dm_id = %s
        ORDER BY dm.timestamp ASC
    """, (dm_id,), fetch_all=True)
    
    messages = []
    for r in rows or []:
        messages.append({
            'content': r[0],
            'timestamp': r[1],
            'username': r[2],
            'avatar': r[3] if r[3] else DEFAULT_AVATAR
        })
    
    return jsonify({'success': True, 'messages': messages})

@app.route('/api/dms/<int:target_id>/messages', methods=['GET'])
def api_dm_messages(target_id):
    if 'user' not in session: return jsonify({'success': False}), 401
    my_id = int(session['user']['id'])
    
    dm_id = get_or_create_dm(my_id, target_id)
    
    # Fetch ALL messages ordered chronologically
    rows = execute_query("""
        SELECT dm.content, dm.timestamp, u.username, u.avatar 
        FROM dm_messages dm
        JOIN users u ON u.id = dm.author_id
        WHERE dm.dm_id = %s
        ORDER BY dm.timestamp ASC
    """, (dm_id,), fetch_all=True)
    
    messages = []
    for r in rows:
        messages.append({
            'content': r[0],
            'timestamp': r[1],
            'timestamp': r[1],
            'username': r[2],
            'avatar': r[3] if r[3] else DEFAULT_AVATAR
        })
        
    return jsonify({'success': True, 'messages': messages, 'dm_id': str(dm_id)})

@app.route('/api/dms/by_id/<int:dm_id>/send', methods=['POST'])
def api_dm_send_by_id(dm_id):
    """Send a message to a DM conversation by DM ID"""
    if 'user' not in session: 
        return jsonify({'success': False, 'error': 'Not authenticated'}), 401
    
    my_id = int(session['user']['id'])
    
    # Verify user is part of this DM
    dm_row = execute_query('SELECT user_id_1, user_id_2 FROM direct_messages WHERE id = %s', (dm_id,), fetch_one=True)
    if not dm_row:
        return jsonify({'success': False, 'error': 'DM not found'}), 404
    
    if my_id not in [dm_row[0], dm_row[1]]:
        return jsonify({'success': False, 'error': 'Access denied'}), 403
    
    data = request.json
    content = data.get('content', '').strip()
    if not content:
        return jsonify({'success': False, 'error': 'Empty message'}), 400
    
    timestamp = time.time()
    
    try:
        # Insert message
        execute_query('''
            INSERT INTO dm_messages (dm_id, author_id, content, timestamp)
            VALUES (%s, %s, %s, %s)
        ''', (dm_id, my_id, content, timestamp), commit=True)
        
        # Update last_message_at
        execute_query('UPDATE direct_messages SET last_message_at = %s WHERE id = %s',
                      (timestamp, dm_id), commit=True)
        
    except Exception as e:
        return jsonify({'success': False, 'error': f'Database error: {str(e)}'}), 500
    
    # Get user info for socket broadcast
    u = execute_query('SELECT username, avatar FROM users WHERE id = %s', (my_id,), fetch_one=True)
    username = u[0] if u else 'Unknown'
    avatar = get_valid_avatar(u[1]) if u else DEFAULT_AVATAR
    
    # Emit via Socket.IO using Rooms
    payload = {
        'dm_id': dm_id,
        'author': username,
        'avatar': avatar,
        'content': content,
        'timestamp': timestamp
    }
    
    # Send to sender and recipient
    socketio.emit('new_dm_message', payload, room=str(dm_row[0]))
    socketio.emit('new_dm_message', payload, room=str(dm_row[1]))
    
    # Return full message data for frontend optimistic update
    return jsonify({
        'success': True, 
        'message': {
            'dm_id': dm_id,
            'author': username,
            'avatar': avatar,
            'content': content,
            'timestamp': timestamp
        }
    })

@app.route('/api/dms/<int:target_id>/send', methods=['POST'])
def api_dm_send(target_id):
    if 'user' not in session: return jsonify({'success': False}), 401
    my_id = int(session['user']['id'])
    data = request.json
    content = data.get('content')
    if not content: return jsonify({'success': False})
    
    dm_id = get_or_create_dm(my_id, target_id)
    
    # Insert Message
    execute_query("INSERT INTO dm_messages (dm_id, author_id, content, timestamp) VALUES (%s, %s, %s, %s)",
                  (dm_id, my_id, content, time.time()), commit=True)
                  
    # Update timestamp for sorting
    execute_query("UPDATE direct_messages SET last_message_at = %s WHERE id = %s", (time.time(), dm_id), commit=True)
    
    msg_obj = {
        'dm_id': str(dm_id),
        'author_id': my_id,
        'author': session['user']['username'],
        'avatar': session['user']['avatar'],
        'content': content,
        'timestamp': time.time(),
        'users': [my_id, target_id] # IDs to filter on frontend
    }
    
    # Emit real-time event SECURELY
    socketio.emit('new_dm_message', msg_obj, room=str(my_id))
    socketio.emit('new_dm_message', msg_obj, room=str(target_id))
    
    # Return message data for frontend optimistic update
    return jsonify({
        'success': True, 
        'message': msg_obj
    })

@app.route('/debug/friends_dump')
def debug_friends_dump():
    rows = execute_query('SELECT * FROM friends', fetch_all=True)
    return jsonify({'rows': rows})

# Initialize servers after all functions are defined
load_servers()
print(f"✓ Loaded {len(servers_db)} servers")

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    print(f'Server running on http://0.0.0.0:{port}')
    socketio.run(app, host='0.0.0.0', port=port, debug=False, allow_unsafe_werkzeug=True)

