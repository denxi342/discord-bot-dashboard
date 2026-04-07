import eventlet
eventlet.monkey_patch()
import os
import time
import requests
import json

# FIX: Python 3.13 dropped 'cgi', but feedparser needs it via 'import cgi'
import sys
import types
if 'cgi' not in sys.modules:
    sys.modules['cgi'] = types.ModuleType('cgi')

import feedparser
import threading
import random
import string
import sqlite3
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
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
# Auth & Storage Configurations
RESEND_API_KEY = os.environ.get('RESEND_API_KEY', 're_UAy2HEyT_D4y6Vs8ZVYgnqsn5StCm8byK')

# SMTP Settings (Outlook / Office365)
SMTP_SERVER = "smtp.office365.com"  # Outlook/Hotmail/Office365
SMTP_PORT = 587                    # STARTTLS Port
SMTP_USER = "octavesup@outlook.com"
SMTP_PASSWORD = "fpesftmxocnbhsfl" 

# Storage Quota (30 GB in bytes)
USER_STORAGE_QUOTA = 30 * 1024 * 1024 * 1024

# Online users tracking: {user_id: {socket_sid, username, avatar}}
# Also track by sid for reliable disconnect: {sid: user_id}
online_users = {}
sid_to_user = {}

@socketio.on('connect')
def handle_connect():
    if 'user' in session:
        user_id = str(session['user']['id'])
        sid = request.sid
        join_room(user_id)
        # Track online user
        online_users[user_id] = {
            'sid': sid,
            'username': session['user'].get('username', ''),
            'avatar': session['user'].get('avatar', '')
        }
        sid_to_user[sid] = user_id
        # Update DB status
        execute_query("UPDATE users SET status = 'online' WHERE id = %s", (user_id,), commit=True)
        # Broadcast status to all users
        emit('user_status', {'user_id': user_id, 'status': 'online', 'username': session['user'].get('username', '')}, broadcast=True)
        print(f"[WS] User {session['user'].get('username')} connected. Online: {len(online_users)}")

@socketio.on('disconnect')
def handle_disconnect():
    sid = request.sid
    # Look up user by socket ID (session may not be available on disconnect)
    user_id = sid_to_user.pop(sid, None)
    if user_id and user_id in online_users:
        username = online_users[user_id].get('username', '')
        del online_users[user_id]
        # Update DB status
        execute_query("UPDATE users SET status = 'offline' WHERE id = %s", (user_id,), commit=True)
        # Broadcast offline status
        emit('user_status', {'user_id': user_id, 'status': 'offline', 'username': username}, broadcast=True)
        print(f"[WS] User {username} disconnected. Online: {len(online_users)}")

# Typing indicator tracking: {dm_id: {user_id: timestamp}}
typing_users = {}

@socketio.on('typing_start')
def handle_typing_start(data):
    """Handle user starting to type in a DM"""
    if 'user' not in session:
        return
    
    user_id = str(session['user']['id'])
    username = session['user'].get('username', '')
    dm_id = data.get('dm_id')
    recipient_id = data.get('recipient_id')
    
    if not dm_id or not recipient_id:
        return
    
    # Track typing user
    if dm_id not in typing_users:
        typing_users[dm_id] = {}
    typing_users[dm_id][user_id] = time.time()
    
    # Emit to recipient only
    emit('typing_start', {
        'user_id': user_id,
        'username': username,
        'dm_id': dm_id
    }, room=recipient_id)

@socketio.on('typing_stop')
def handle_typing_stop(data):
    """Handle user stopping typing in a DM"""
    if 'user' not in session:
        return
    
    user_id = str(session['user']['id'])
    dm_id = data.get('dm_id')
    recipient_id = data.get('recipient_id')
    
    if not dm_id or not recipient_id:
        return
    
    # Remove typing user
    if dm_id in typing_users and user_id in typing_users[dm_id]:
        del typing_users[dm_id][user_id]
        if not typing_users[dm_id]:  # Clean up empty dict
            del typing_users[dm_id]
    
    # Emit to recipient only
    emit('typing_stop', {
        'user_id': user_id,
        'dm_id': dm_id
    }, room=recipient_id)

import psycopg2
from urllib.parse import urlparse

# ... imports ...

# Database Setup
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SERVERS_FILE = os.path.join(BASE_DIR, 'servers.json')
servers_db = {}

# Default Avatar (SVG Data URI - clean user silhouette)
DEFAULT_AVATAR = "data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='128' height='128' viewBox='0 0 128 128'%3E%3Crect width='128' height='128' fill='%235865F2'/%3E%3Ccircle cx='64' cy='50' r='22' fill='%23fff'/%3E%3Cellipse cx='64' cy='112' rx='36' ry='28' fill='%23fff'/%3E%3C/svg%3E"

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
    varchar_type = "TEXT" if is_sqlite else "VARCHAR(50)"
    
    print("[*] Initializing database...")
    
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
                  reputation INTEGER DEFAULT 0,
                  last_seen REAL,
                  admin_pin TEXT)''')
    print("  [+] Users table ready")

    # Friends Table
    c.execute(f'''CREATE TABLE IF NOT EXISTS friends
                 (id {pk_type}, 
                  user_id_1 INTEGER NOT NULL, 
                  user_id_2 INTEGER NOT NULL, 
                  status TEXT DEFAULT 'pending', 
                  created_at REAL,
                  UNIQUE(user_id_1, user_id_2))''')
    print("  [+] Friends table ready")

    # DM Tables
    c.execute(f'''CREATE TABLE IF NOT EXISTS direct_messages
                 (id {pk_type},
                  user_id_1 INTEGER NOT NULL,
                  user_id_2 INTEGER NOT NULL,
                  last_message_at REAL,
                  UNIQUE(user_id_1, user_id_2))''')
    print("  [+] Direct messages table ready")

    c.execute(f'''CREATE TABLE IF NOT EXISTS dm_messages
                 (id {pk_type},
                  dm_id INTEGER NOT NULL,
                  author_id INTEGER NOT NULL,
                  content TEXT,
                  timestamp REAL,
                  reply_to_id INTEGER,
                  is_pinned INTEGER DEFAULT 0,
                  edited_at REAL,
                  attachments TEXT,
                  expires_at REAL)''')
    
    c.execute(f'''CREATE TABLE IF NOT EXISTS reports
                 (id {pk_type},
                  message_id INTEGER NOT NULL,
                  reporter_id INTEGER NOT NULL,
                  reason TEXT NOT NULL,
                  timestamp REAL)''')
    print("  [+] Reports table ready")
    print("  [+] DM messages table ready")

    # Message Reactions Table - CRITICAL for reactions feature
    c.execute(f'''CREATE TABLE IF NOT EXISTS message_reactions
                 (id {pk_type},
                  message_id INTEGER NOT NULL,
                  user_id INTEGER NOT NULL,
                  emoji {varchar_type} NOT NULL,
                  created_at REAL,
                  UNIQUE(message_id, user_id, emoji))''')
    print("  [+] Message reactions table ready")

    # Server Members Table - tracks who is a member of which server
    c.execute(f'''CREATE TABLE IF NOT EXISTS server_members
                 (id {pk_type},
                  server_id TEXT NOT NULL,
                  user_id INTEGER NOT NULL,
                  role TEXT DEFAULT 'member',
                  joined_at REAL,
                  UNIQUE(server_id, user_id))''')
    print("  [+] Server members table ready")
    
    # --- Performance Indexes ---
    c.execute('CREATE INDEX IF NOT EXISTS idx_dm_messages_dm_id ON dm_messages(dm_id)')
    c.execute('CREATE INDEX IF NOT EXISTS idx_dm_messages_timestamp ON dm_messages(timestamp)')
    c.execute('CREATE INDEX IF NOT EXISTS idx_message_reactions_message_id ON message_reactions(message_id)')
    c.execute('CREATE INDEX IF NOT EXISTS idx_direct_messages_last_message_at ON direct_messages(last_message_at)')
    print("  [+] Performance indexes ready")
                  
    conn.commit()
    conn.close()
    print("[OK] Database initialized successfully!")

# Removed file-based users_db logic since we now have columns for role/reputation in DB.

def safe_init_db():
    try:
        init_db()
    except Exception as e:
        print(f"[!] CRITICAL: Database initialization failed: {e}")
        print("[!] The application will attempt to start, but database features will be broken.")

safe_init_db()

def run_db_migration():
    """
    Run database migration to add extended messaging fields to existing databases.
    This is safe to run multiple times - it checks if columns exist before adding.
    """
    try:
        conn = get_db_connection()
        is_sqlite = isinstance(conn, sqlite3.Connection)
        cursor = conn.cursor()
        
        pk_type = "INTEGER PRIMARY KEY AUTOINCREMENT" if is_sqlite else "SERIAL PRIMARY KEY"
        
        print("[*] Running database migration...")
        
        # Helper for adding columns safely
        def add_col(table, column, col_type):
            try:
                if is_sqlite:
                    cursor.execute(f"PRAGMA table_info({table})")
                    cols = {row[1] for row in cursor.fetchall()}
                    if column not in cols:
                        cursor.execute(f"ALTER TABLE {table} ADD COLUMN {column} {col_type}")
                        print(f"  [+] Added {column} to {table}")
                else:
                    cursor.execute(f"SELECT column_name FROM information_schema.columns WHERE table_name='{table}' AND column_name='{column}'")
                    if not cursor.fetchone():
                        cursor.execute(f"ALTER TABLE {table} ADD COLUMN {column} {col_type}")
                        print(f"  [+] Added {column} to {table}")
                conn.commit()
            except Exception as e:
                print(f"  [!] Skip {column} on {table}: {e}")
                conn.rollback()

        # Admin & Reports updates
        add_col("users", "ip_address", "TEXT")
        add_col("users", "device_id", "TEXT")
        add_col("users", "is_banned", "INTEGER DEFAULT 0")
        add_col("users", "ban_expires", "REAL")
        add_col("users", "ban_reason", "TEXT")
        add_col("users", "is_muted", "INTEGER DEFAULT 0")
        add_col("users", "mute_expires", "REAL")
        add_col("users", "risk_score", "INTEGER DEFAULT 0") # 0-100
        
        add_col("reports", "status", "TEXT DEFAULT 'pending'") # pending, in_review, resolved
        add_col("reports", "assigned_to", "INTEGER")
        add_col("reports", "staff_note", "TEXT")
        add_col("users", "is_verified", "INTEGER DEFAULT 0")
        add_col("users", "status", "TEXT DEFAULT 'offline'")

        # New Staff only tables
        cursor.execute(f"CREATE TABLE IF NOT EXISTS admin_logs (id {pk_type}, admin_id INTEGER, ip_address TEXT, action TEXT, details TEXT, timestamp REAL)")
        cursor.execute(f"CREATE TABLE IF NOT EXISTS risk_alerts (id {pk_type}, user_id INTEGER, type TEXT, details TEXT, risk_level TEXT, timestamp REAL)")
        cursor.execute(f"CREATE TABLE IF NOT EXISTS message_reactions (id {pk_type}, message_id INTEGER, user_id INTEGER, emoji TEXT, created_at REAL, UNIQUE(message_id, user_id, emoji))")
        cursor.execute(f"CREATE TABLE IF NOT EXISTS read_receipts (id {pk_type}, dm_id INTEGER, user_id INTEGER, last_read_message_id INTEGER, updated_at REAL, UNIQUE(dm_id, user_id))")
        cursor.execute(f"CREATE TABLE IF NOT EXISTS verification_codes (email TEXT PRIMARY KEY, code TEXT, expires_at REAL)")

        conn.commit()
        cursor.close()
        conn.close()
        print("[OK] Database migration completed successfully!")
    except Exception as e:
        print(f"[!] Migration error: {e}")

# Run migration to add missing columns to existing databases
try:
    run_db_migration()
except Exception as e:
    print(f"[!] CRITICAL: Global migration failed: {e}")

# --- DISAPPEARING MESSAGES CLEANUP THREAD ---
def cleanup_expired_messages():
    """Background thread to delete expired messages and notify clients"""
    while True:
        try:
            eventlet.sleep(10)  # Check every 10 seconds
            current_time = time.time()
            
            # Find expired messages
            expired = execute_query('''
                SELECT id, dm_id FROM dm_messages 
                WHERE expires_at IS NOT NULL AND expires_at <= %s
            ''', (current_time,), fetch_all=True)
            
            if expired:
                for msg_id, dm_id in expired:
                    # Delete reactions first
                    execute_query('DELETE FROM message_reactions WHERE message_id = %s', (msg_id,), commit=True)
                    # Delete message
                    execute_query('DELETE FROM dm_messages WHERE id = %s', (msg_id,), commit=True)
                    # Emit socket event to remove from UI
                    socketio.emit('message_expired', {
                        'message_id': msg_id,
                        'dm_id': dm_id
                    })
                print(f"[Cleanup] Deleted {len(expired)} expired messages")
        except Exception as e:
            print(f"[Cleanup Error] {e}")

# Start cleanup thread
eventlet.spawn(cleanup_expired_messages)
print("[*] Disappearing messages cleanup thread started")

def fix_existing_avatars():
    """Helper to force all users to use the local default silhouette avatar"""
    try:
        print("[!] Forcing default avatar for ALL users...")
        # Update everyone to use the new DEFAULT_AVATAR
        execute_query("UPDATE users SET avatar = %s", (DEFAULT_AVATAR,), commit=True)
        print("[+] All avatars updated to default silhouette.")
    except Exception as e:
        print(f"Error forcing avatars: {e}")

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

@app.route('/terms')
def terms_page():
    return render_template('terms.html')

@app.route('/privacy')
def privacy_page():
    return render_template('privacy.html')

@app.route('/cookies')
def cookies_page():
    return render_template('cookie_policy.html')

@app.route('/favicon.ico')
def favicon():
    return send_from_directory(os.path.join(app.root_path, 'static'), 'favicon.ico', mimetype='image/vnd.microsoft.icon')

@app.route('/logout')
def logout():
    session.pop('user', None)
    return redirect('/login')

RESEND_API_KEY = os.environ.get('RESEND_API_KEY', 're_UAy2HEyT_D4y6Vs8ZVYgnqsn5StCm8byK')

def send_verification_email(email, code):
    """Send verification code via SMTP"""
    try:
        if SMTP_USER == "your_email@mail.ru" or SMTP_PASSWORD == "your_app_password":
            print("[WARNING] SMTP credentials not configured. Email NOT sent.")
            return False

        msg = MIMEMultipart()
        msg['From'] = f"Octave <{SMTP_USER}>"
        msg['To'] = email
        msg['Subject'] = "Подтверждение аккаунта Octave"

        html = f"""
            <div style="font-family: sans-serif; background: #0a0b0e; color: white; padding: 40px; border-radius: 20px; text-align: center;">
                <h2 style="color: #667eea;">Добро пожаловать в Octave!</h2>
                <p style="color: rgba(255,255,255,0.6);">Ваш код подтверждения:</p>
                <div style="font-size: 32px; font-weight: bold; letter-spacing: 5px; margin: 20px 0; color: #764ba2;">{code}</div>
                <p style="font-size: 12px; color: rgba(255,255,255,0.3);">Код истечет через 10 минут.</p>
            </div>
        """
        msg.attach(MIMEText(html, 'html'))

        # Use STARTTLS for port 587 (Outlook/Gmail)
        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
            server.starttls()
            server.login(SMTP_USER, SMTP_PASSWORD)
            server.send_message(msg)
            
        print(f"[SUCCESS] SMTP Email sent to {email}")
        return True
    except Exception as e:
        print(f"[SMTP EXCEPTION] {e}")
        return False

def get_user_storage_usage(user_id):
    """Calculate total storage used by user in bytes"""
    usage = execute_query("""
        SELECT SUM(file_size) FROM file_uploads 
        WHERE message_id IN (SELECT id FROM dm_messages WHERE author_id = %s)
    """, (user_id,), fetch_one=True)
    return usage[0] if usage and usage[0] else 0

def generate_unique_username(email):
    prefix = email.split('@')[0]
    base_username = "".join(c for c in prefix if c.isalnum() or c in '_-')
    if not base_username: base_username = "user"
    
    username = base_username
    row = execute_query("SELECT id FROM users WHERE username = %s", (username,), fetch_one=True)
    if not row: return username
    
    for _ in range(10):
        test_username = f"{base_username}{random.randint(100, 9999)}"
        row = execute_query("SELECT id FROM users WHERE username = %s", (test_username,), fetch_one=True)
        if not row: return test_username
    return f"{base_username}{int(time.time())}"

@app.route('/api/auth/register', methods=['POST'])
def api_register():
    data = request.json
    username = data.get('username')
    password = data.get('password')
    
    if not username or not password:
        return jsonify({'success': False, 'error': 'Введите никнейм и пароль'})
    
    if len(password) < 6:
        return jsonify({'success': False, 'error': 'Пароль должен быть не менее 6 символов'})
    
    try:
        row = execute_query("SELECT id FROM users WHERE username = %s", (username,), fetch_one=True)
        if row:
            return jsonify({'success': False, 'error': 'Этот никнейм уже занят'})
        
        hash_pw = generate_password_hash(password)
        
        user_id = execute_query("INSERT INTO users (username, password_hash, avatar, created_at, role, is_verified) VALUES (%s, %s, %s, %s, 'user', 1)", 
                      (username, hash_pw, DEFAULT_AVATAR, time.time()), commit=True)
        
        # Log the user in immediately
        session['user'] = {'id': str(user_id), 'username': username, 'avatar': DEFAULT_AVATAR, 'role': 'user'}
        session.permanent = True
        
        return jsonify({'success': True})
            
    except Exception as e:
        print(f"General Register Error: {e}")
        return jsonify({'success': False, 'error': 'Ошибка сервера'})

@app.route('/api/auth/verify', methods=['POST'])
def api_verify():
    data = request.json
    email = data.get('email')
    code = data.get('code')
    
    if not email or not code:
        return jsonify({'success': False, 'error': 'Введите код'})
    
    row = execute_query("SELECT code, expires_at FROM verification_codes WHERE email = %s", (email,), fetch_one=True)
    if not row:
        return jsonify({'success': False, 'error': 'Код не найден или истёк'})
    
    db_code, expires_at = row
    if db_code != code:
        return jsonify({'success': False, 'error': 'Неверный код'})
    if time.time() > expires_at:
        return jsonify({'success': False, 'error': 'Срок действия кода истёк'})
    
    try:
        execute_query("UPDATE users SET is_verified = 1 WHERE email = %s", (email,), commit=True)
        execute_query("DELETE FROM verification_codes WHERE email = %s", (email,), commit=True)
        
        row = execute_query("SELECT id, username, avatar, role FROM users WHERE email = %s", (email,), fetch_one=True)
        if row:
            session['user'] = {'id': str(row[0]), 'username': row[1], 'avatar': get_valid_avatar(row[2]), 'role': row[3]}
            session.permanent = True
            return jsonify({'success': True})
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/auth/resend', methods=['POST'])
def api_resend():
    email = request.json.get('email')
    if not email: return jsonify({'success': False, 'error': 'Email required'})
    
    code = "".join(random.choices(string.digits, k=6))
    expires = time.time() + 600
    
    try:
        execute_query("REPLACE INTO verification_codes (email, code, expires_at) VALUES (%s, %s, %s)", 
                      (email, code, expires), commit=True)
        
        # --- DEBUG MODE ---
        if send_verification_email(email, code):
            return jsonify({'success': True})
        else:
            print(f"[DEBUG] SMTP Resend failed, allowing bypass. Code for {email} is {code} (or use 123456)")
            execute_query("UPDATE verification_codes SET code = '123456' WHERE email = %s", (email,), commit=True)
            return jsonify({'success': True, 'debug': True})
    except Exception as e:
        print(f"Resend Error: {e}")
        return jsonify({'success': False, 'error': 'Ошибка базы данных'})

@app.route('/api/auth/login', methods=['POST'])
def api_login():
    data = request.json
    login_id = data.get('username')  # Frontend will now send 'username'
    password = data.get('password')
    
    row = execute_query("SELECT id, username, password_hash, avatar, role, is_verified, email FROM users WHERE email = %s OR username = %s", (login_id, login_id), fetch_one=True)
    
    if row and check_password_hash(row[2], password):
        session['user'] = {'id': str(row[0]), 'username': row[1], 'avatar': get_valid_avatar(row[3]), 'role': row[4]}
        session.permanent = True
        return jsonify({'success': True})
    return jsonify({'success': False, 'error': 'Неверный логин или пароль'})

@app.route('/api/user/me', methods=['GET'])
def api_get_me():
    if 'user' not in session: return jsonify({'success': False}), 401
    uid = session['user']['id']
    
    row = execute_query("SELECT id, username, avatar, display_name, banner, bio, email, phone, role, reputation, custom_status, status_emoji, status FROM users WHERE id = %s", (uid,), fetch_one=True)
    
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
                'reputation': row[9],
                'custom_status': row[10],
                'status_emoji': row[11],
                'status': row[12] or 'offline'
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
    
    allowed = ['username', 'avatar', 'display_name', 'banner', 'bio', 'email', 'phone', 'custom_status', 'status_emoji']
    
    for k in allowed:
        if k in data:
            fields.append(f"{k} = %s")
            values.append(data[k])
            if k in ['username', 'avatar']:
                session['user'][k] = data[k]
    if not fields:
        return jsonify({'success': False, 'error': 'No valid fields'})
        
    if 'username' in data:
        row = execute_query("SELECT id FROM users WHERE username = %s AND id != %s", (data['username'], uid), fetch_one=True)
        if row:
            return jsonify({'success': False, 'error': 'Этот никнейм уже занят'})
            
    values.append(uid)
    
    try:
        execute_query(f"UPDATE users SET {', '.join(fields)} WHERE id = %s", tuple(values), commit=True)
        session.modified = True
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/user/profile/<user_id>', methods=['GET'])
def api_get_user_profile(user_id):
    """Retrieve public profile for any user"""
    if 'user' not in session:
        return jsonify({'success': False, 'error': 'Auth needed'}), 401
    
    try:
        row = execute_query("SELECT id, username, avatar, bio, status, email FROM users WHERE id = %s", (user_id,), fetch_one=True)
        if not row:
            return jsonify({'success': False, 'error': 'User not found'})
            
        current_uid = str(session['user']['id'])
        is_self = str(row[0]) == current_uid
        
        profile = {
            'id': row[0],
            'username': row[1],
            'avatar': get_valid_avatar(row[2]),
            'bio': row[3],
            'status': row[4] or 'offline'
        }
        
        if is_self:
            profile['email'] = row[5]
            
        return jsonify({'success': True, 'user': profile})
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
    
    allowed = {'png', 'jpg', 'jpeg', 'gif', 'webp'}
    ext = file.filename.rsplit('.', 1)[-1].lower() if '.' in file.filename else ''
    if ext not in allowed:
        return jsonify({'success': False, 'error': 'Invalid file type'})
    
    file.seek(0, os.SEEK_END)
    file_size = file.tell()
    file.seek(0)
    
    MAX_AVATAR_SIZE = 2 * 1024 * 1024
    if file_size > MAX_AVATAR_SIZE:
        return jsonify({'success': False, 'error': 'Avatar too large (max 2MB)'})

    user_id = int(session['user']['id'])
    current_usage = get_user_storage_usage(user_id)
    if current_usage + file_size > USER_STORAGE_QUOTA:
        return jsonify({'success': False, 'error': 'Превышена квота хранилища (30 ГБ)'})
    
    try:
        uploads_dir = os.path.join(app.static_folder, 'uploads', 'avatars')
        os.makedirs(uploads_dir, exist_ok=True)
        import uuid
        filename = f"avatar_{session['user']['id']}_{uuid.uuid4().hex[:8]}.{ext}"
        filepath = os.path.join(uploads_dir, filename)
        file.save(filepath)
        avatar_url = f"/static/uploads/avatars/{filename}"
        execute_query("UPDATE users SET avatar = %s WHERE id = %s", (avatar_url, session['user']['id']), commit=True)
        session['user']['avatar'] = avatar_url
        session.modified = True
        return jsonify({'success': True, 'avatar_url': avatar_url})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

# --- ENCRYPTION API ---
@app.route('/api/encryption/setup', methods=['POST'])
def api_encryption_setup():
    """Store user's public key for E2EE"""
    if 'user' not in session:
        return jsonify({'success': False, 'error': 'Not logged in'}), 401
    
    data = request.json
    public_key = data.get('public_key')
    
    if not public_key:
        return jsonify({'success': False, 'error': 'Public key required'})
    
    try:
        uid = session['user']['id']
        execute_query(
            "UPDATE users SET public_key = %s WHERE id = %s",
            (public_key, uid),
            commit=True
        )
        return jsonify({'success': True})
    except Exception as e:
        print(f"[E2EE] Error storing public key: {e}")
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/encryption/public-key/<user_id>', methods=['GET'])
def api_get_encryption_key(user_id):
    """Retrieve another user's public key for encryption"""
    if 'user' not in session:
        return jsonify({'success': False, 'error': 'Not logged in'}), 401
    
    try:
        row = execute_query(
            "SELECT public_key FROM users WHERE id = %s",
            (user_id,),
            fetch_one=True
        )
        
        if row and row[0]:
            return jsonify({'success': True, 'public_key': row[0]})
        else:
            return jsonify({'success': False, 'error': 'User has not set up encryption'})
    except Exception as e:
        print(f"[E2EE] Error retrieving public key: {e}")
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/encryption/verify-keys', methods=['POST'])
def api_verify_keys():
    """Get public keys for multiple users at once"""
    if 'user' not in session:
        return jsonify({'success': False, 'error': 'Not logged in'}), 401
    
    data = request.json
    user_ids = data.get('user_ids', [])
    
    if not user_ids:
        return jsonify({'success': False, 'error': 'No user IDs provided'})
    
    try:
        # Create placeholders for SQL IN clause
        placeholders = ', '.join(['%s'] * len(user_ids))
        query = f"SELECT id, public_key FROM users WHERE id IN ({placeholders})"
        
        rows = execute_query(query, tuple(user_ids), fetch_all=True)
        
        keys = {}
        for row in rows:
            if row[1]:  # Only include if public key exists
                keys[str(row[0])] = row[1]
        
        return jsonify({'success': True, 'keys': keys})
    except Exception as e:
        print(f"[E2EE] Error verifying keys: {e}")
        return jsonify({'success': False, 'error': str(e)})


@app.route('/api/upload-file', methods=['POST'])
def api_upload_file():
    """Upload file attachments for messages"""
    if 'user' not in session:
        return jsonify({'success': False, 'error': 'Not logged in'})
    
    if 'file' not in request.files:
        return jsonify({'success': False, 'error': 'No file provided'})
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({'success': False, 'error': 'No file selected'})
    
    # Check file size (10MB max)
    file.seek(0, os.SEEK_END)
    file_size = file.tell()
    file.seek(0)
    
    MAX_FILE_SIZE = 100 * 1024 * 1024  # Increased to 100MB per file for "full version"
    if file_size > MAX_FILE_SIZE:
        return jsonify({'success': False, 'error': f'Файл слишком велик (макс {MAX_FILE_SIZE//(1024*1024)}МБ)'})
    
    # Check Storage Quota (30 GB)
    user_id = int(session['user']['id'])
    current_usage = get_user_storage_usage(user_id)
    if current_usage + file_size > USER_STORAGE_QUOTA:
        return jsonify({'success': False, 'error': 'Превышена квота хранилища (30 ГБ)'})
    
    # Check file extension
    image_extensions = {'png', 'jpg', 'jpeg', 'gif', 'webp', 'svg'}
    document_extensions = {'pdf', 'txt', 'doc', 'docx', 'xls', 'xlsx'}
    archive_extensions = {'zip', 'rar', '7z', 'tar', 'gz'}
    media_extensions = {'mp4', 'webm', 'mp3', 'wav', 'ogg'}
    
    allowed_extensions = image_extensions | document_extensions | archive_extensions | media_extensions
    
    ext = file.filename.rsplit('.', 1)[-1].lower() if '.' in file.filename else ''
    if ext not in allowed_extensions:
        return jsonify({'success': False, 'error': 'File type not allowed'})
    
    try:
        # Read file data
        file_data = file.read()
        
        # Determine file type
        is_image = ext in image_extensions
        file_type = 'image' if is_image else 'file'
        
        # For images, convert to Data URI
        if is_image:
            import base64
            
            # Determine MIME type
            mime_types = {
                'png': 'image/png',
                'jpg': 'image/jpeg',
                'jpeg': 'image/jpeg',
                'gif': 'image/gif',
                'webp': 'image/webp',
                'svg': 'image/svg+xml'
            }
            mime_type = mime_types.get(ext, 'image/jpeg')
            
            # Create Data URI
            base64_data = base64.b64encode(file_data).decode('utf-8')
            file_url = f"data:{mime_type};base64,{base64_data}"
        else:
            # For non-images, save to filesystem (will be lost on Render, but kept for now)
            # TODO: Consider using external storage (S3, Cloudinary) for documents
            uploads_dir = os.path.join(app.static_folder, 'uploads')
            os.makedirs(uploads_dir, exist_ok=True)
            
            import uuid
            safe_filename = file.filename.replace(' ', '_')[:50]
            unique_filename = f"{uuid.uuid4().hex[:12]}_{safe_filename}"
            filepath = os.path.join(uploads_dir, unique_filename)
            
            with open(filepath, 'wb') as f:
                f.write(file_data)
            
            file_url = f"/static/uploads/{unique_filename}"
        
        # Return file metadata
        return jsonify({
            'success': True,
            'file': {
                'filename': file.filename,
                'path': file_url,
                'type': file_type,
                'size': file_size,
                'extension': ext
            }
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})


# --- LINK PREVIEW & GIF API ---

@app.route('/api/messages/preview-link', methods=['POST'])
def api_preview_link():
    """Generate a preview for a URL (YouTube, images, websites with OpenGraph)"""
    if 'user' not in session:
        return jsonify({'success': False, 'error': 'Not logged in'}), 401
    
    data = request.json
    url = data.get('url', '').strip()
    
    if not url:
        return jsonify({'success': False, 'error': 'No URL provided'})
    
    try:
        # Check if it's a YouTube link
        youtube_patterns = ['youtube.com/watch', 'youtu.be/', 'youtube.com/embed/']
        is_youtube = any(pattern in url for pattern in youtube_patterns)
        
        if is_youtube:
            # Extract video ID
            video_id = None
            if 'youtu.be/' in url:
                video_id = url.split('youtu.be/')[-1].split('?')[0]
            elif 'watch?v=' in url:
                video_id = url.split('watch?v=')[-1].split('&')[0]
            elif 'embed/' in url:
                video_id = url.split('embed/')[-1].split('?')[0]
            
            if video_id:
                return jsonify({
                    'success': True,
                    'preview': {
                        'type': 'youtube',
                        'video_id': video_id,
                        'url': url,
                        'title': f'YouTube Video',
                        'thumbnail': f'https://img.youtube.com/vi/{video_id}/maxresdefault.jpg'
                    }
                })
        
        # Check if it's a direct image link
        image_extensions = ['.jpg', '.jpeg', '.png', '.gif', '.webp', '.bmp']
        is_image = any(url.lower().endswith(ext) for ext in image_extensions)
        
        if is_image:
            return jsonify({
                'success': True,
                'preview': {
                    'type': 'image',
                    'url': url,
                    'image': url
                }
            })
        
        # Try to fetch OpenGraph metadata for websites
        try:
            from bs4 import BeautifulSoup
            
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            }
            response = requests.get(url, headers=headers, timeout=5)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Extract OpenGraph tags
            og_title = soup.find('meta', property='og:title')
            og_description = soup.find('meta', property='og:description')
            og_image = soup.find('meta', property='og:image')
            
            # Fallback to regular tags
            title = og_title['content'] if og_title else (soup.find('title').text if soup.find('title') else url)
            description = og_description['content'] if og_description else ''
            image = og_image['content'] if og_image else ''
            
            return jsonify({
                'success': True,
                'preview': {
                    'type': 'website',
                    'url': url,
                    'title': title[:200],  # Limit length
                    'description': description[:300],
                    'image': image
                }
            })
        except:
            # If OpenGraph parsing fails, return basic preview
            return jsonify({
                'success': True,
                'preview': {
                    'type': 'link',
                    'url': url,
                    'title': url
                }
            })
    
    except Exception as e:
        print(f"Link preview error: {e}")
        return jsonify({'success': False, 'error': str(e)})


# Tenor API key from environment
TENOR_API_KEY = os.environ.get('TENOR_API_KEY', 'AIzaSyAyimkuYQYF_FXnHfK1y7K0rYRQgO1VjhQ')  # Public test key

@app.route('/api/giphy/search', methods=['GET'])
def api_gif_search():
    """Search for GIFs using Tenor API"""
    if 'user' not in session:
        return jsonify({'success': False, 'error': 'Not logged in'}), 401
    
    query = request.args.get('q', '').strip()
    
    if not query:
        return jsonify({'success': False, 'error': 'No search query'})
    
    try:
        # Tenor API endpoint
        tenor_url = 'https://tenor.googleapis.com/v2/search'
        params = {
            'q': query,
            'key': TENOR_API_KEY,
            'limit': 20,
            'media_filter': 'gif,tinygif'
        }
        
        response = requests.get(tenor_url, params=params, timeout=5)
        response.raise_for_status()
        
        data = response.json()
        results = data.get('results', [])
        
        # Format results for frontend
        gifs = []
        for result in results:
            media = result.get('media_formats', {})
            
            # Get GIF and preview URLs
            gif_url = media.get('gif', {}).get('url', '')
            tiny_url = media.get('tinygif', {}).get('url', gif_url)
            preview_url = media.get('tinygif', {}).get('url', gif_url)
            
            if gif_url:
                gifs.append({
                    'id': result.get('id'),
                    'title': result.get('content_description', 'GIF'),
                    'url': gif_url,
                    'preview': preview_url,
                    'tiny': tiny_url,
                    'width': media.get('gif', {}).get('dims', [300, 300])[0],
                    'height': media.get('gif', {}).get('dims', [300, 300])[1]
                })
        
        return jsonify({
            'success': True,
            'gifs': gifs
        })
    
    except Exception as e:
        print(f"GIF search error: {e}")
        return jsonify({'success': False, 'error': str(e)})


# --- ADVANCED FEATURES API ---

@app.route('/api/albums/create', methods=['POST'])
def api_create_album():
    """Create a photo album from multiple uploaded images"""
    if 'user' not in session:
        return jsonify({'success': False, 'error': 'Not logged in'}), 401
    
    # Check if files were uploaded
    if 'files[]' not in request.files:
        return jsonify({'success': False, 'error': 'No files provided'})
    
    files = request.files.getlist('files[]')
    if not files or len(files) == 0:
        return jsonify({'success': False, 'error': 'No files selected'})
    
    # Limit album size
    MAX_ALBUM_SIZE = 10
    if len(files) > MAX_ALBUM_SIZE:
        return jsonify({'success': False, 'error': f'Maximum {MAX_ALBUM_SIZE} photos per album'})
    
    try:
        import base64
        photos = []
        total_size = 0
        
        for file in files:
            # Check file type
            ext = file.filename.rsplit('.', 1)[-1].lower() if '.' in file.filename else ''
            if ext not in {'png', 'jpg', 'jpeg', 'gif', 'webp'}:
                continue
            
            # Check file size
            file.seek(0, os.SEEK_END)
            file_size = file.tell()
            file.seek(0)
            
            total_size += file_size
            if total_size > 20 * 1024 * 1024:  # 20MB total limit
                return jsonify({'success': False, 'error': 'Total album size too large (max 20MB)'})
            
            # Convert to data URI
            file_data = file.read()
            mime_types = {
                'png': 'image/png',
                'jpg': 'image/jpeg',
                'jpeg': 'image/jpeg',
                'gif': 'image/gif',
                'webp': 'image/webp'
            }
            mime_type = mime_types.get(ext, 'image/jpeg')
            base64_data = base64.b64encode(file_data).decode('utf-8')
            file_url = f"data:{mime_type};base64,{base64_data}"
            
            photos.append({
                'filename': file.filename,
                'url': file_url,
                'size': file_size,
                'type': 'image'
            })
        
        if not photos:
            return jsonify({'success': False, 'error': 'No valid images found'})
        
        # Create album entry (will be associated with message later)
        album_id = execute_query(
            "INSERT INTO photo_albums (message_id, photo_count, created_at) VALUES (%s, %s, %s) RETURNING id" if 'postgres' in str(type(get_db_connection())) else "INSERT INTO photo_albums (message_id, photo_count, created_at) VALUES (?, ?, ?)",
            (0, len(photos), time.time()),  # message_id will be updated when message is created
            commit=True,
            fetch_one=True
        )
        
        return jsonify({
            'success': True,
            'album': {
                'id': album_id if album_id else execute_query("SELECT last_insert_rowid()", fetch_one=True)[0],
                'photos': photos,
                'photo_count': len(photos)
            }
        })
    
    except Exception as e:
        print(f"Album creation error: {e}")
        return jsonify({'success': False, 'error': str(e)})


@app.route('/api/albums/<int:album_id>', methods=['GET'])
def api_get_album(album_id):
    """Get album photos"""
    if 'user' not in session:
        return jsonify({'success': False, 'error': 'Not logged in'}), 401
    
    try:
        album = execute_query(
            "SELECT id, message_id, photo_count, created_at FROM photo_albums WHERE id = %s",
            (album_id,),
            fetch_one=True
        )
        
        if not album:
            return jsonify({'success': False, 'error': 'Album not found'})
        
        # For now, return album metadata (photos are stored in message attachments)
        return jsonify({
            'success': True,
            'album': {
                'id': album[0],
                'message_id': album[1],
                'photo_count': album[2],
                'created_at': album[3]
            }
        })
    
    except Exception as e:
        print(f"Get album error: {e}")
        return jsonify({'success': False, 'error': str(e)})


@app.route('/api/preview-link-enhanced', methods=['POST'])
def api_preview_link_enhanced():
    """Enhanced link preview with database caching"""
    if 'user' not in session:
        return jsonify({'success': False, 'error': 'Not logged in'}), 401
    
    data = request.json
    url = data.get('url', '').strip()
    
    if not url:
        return jsonify({'success': False, 'error': 'No URL provided'})
    
    # Validate URL scheme
    if not url.startswith(('http://', 'https://')):
        return jsonify({'success': False, 'error': 'Invalid URL scheme'})
    
    try:
        # Check cache first (24 hour expiry)
        cache_expiry = time.time() - (24 * 3600)
        cached = execute_query(
            "SELECT title, description, image_url, site_name, cached_at FROM link_previews WHERE url = %s AND cached_at > %s",
            (url, cache_expiry),
            fetch_one=True
        )
        
        if cached:
            return jsonify({
                'success': True,
                'preview': {
                    'url': url,
                    'title': cached[0],
                    'description': cached[1],
                    'image': cached[2],
                    'site_name': cached[3],
                    'cached': True
                }
            })
        
        # Fetch fresh preview
        from bs4 import BeautifulSoup
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
        
        response = requests.get(url, headers=headers, timeout=5, stream=True)
        
        # Limit response size to 1MB
        max_size = 1024 * 1024
        content = b''
        for chunk in response.iter_content(chunk_size=8192):
            content += chunk
            if len(content) > max_size:
                break
        
        soup = BeautifulSoup(content, 'html.parser')
        
        # Extract Open Graph metadata
        og_title = soup.find('meta', property='og:title')
        og_description = soup.find('meta', property='og:description')
        og_image = soup.find('meta', property='og:image')
        og_site_name = soup.find('meta', property='og:site_name')
        
        # Fallback to Twitter Card
        tw_title = soup.find('meta', attrs={'name': 'twitter:title'})
        tw_description = soup.find('meta', attrs={'name': 'twitter:description'})
        tw_image = soup.find('meta', attrs={'name': 'twitter:image'})
        
        # Extract metadata
        title = (og_title or tw_title)['content'] if (og_title or tw_title) else (soup.find('title').text if soup.find('title') else url)
        description = (og_description or tw_description)['content'] if (og_description or tw_description) else ''
        image = (og_image or tw_image)['content'] if (og_image or tw_image) else ''
        site_name = og_site_name['content'] if og_site_name else url.split('/')[2]
        
        # Trim to reasonable lengths
        title = title[:200]
        description = description[:300]
        
        # Cache the result
        execute_query(
            """INSERT INTO link_previews (url, title, description, image_url, site_name, cached_at) 
               VALUES (%s, %s, %s, %s, %s, %s)
               ON CONFLICT(url) DO UPDATE SET 
               title = EXCLUDED.title, 
               description = EXCLUDED.description, 
               image_url = EXCLUDED.image_url, 
               site_name = EXCLUDED.site_name, 
               cached_at = EXCLUDED.cached_at""",
            (url, title, description, image, site_name, time.time()),
            commit=True
        )
        
        return jsonify({
            'success': True,
            'preview': {
                'url': url,
                'title': title,
                'description': description,
                'image': image,
                'site_name': site_name,
                'cached': False
            }
        })
    
    except Exception as e:
        print(f"Enhanced link preview error: {e}")
        # Return basic preview on error
        return jsonify({
            'success': True,
            'preview': {
                'url': url,
                'title': url,
                'description': '',
                'image': '',
                'site_name': url.split('/')[2] if len(url.split('/')) > 2 else url
            }
        })



# ============================================================
# END-TO-END ENCRYPTION API
# ============================================================

@app.route('/api/keys/upload', methods=['POST'])
def api_upload_public_key():
    """Upload user's public key (JWK format)"""
    if 'user' not in session:
        return jsonify({'success': False, 'error': 'Not authenticated'}), 401
    
    my_id = int(session['user']['id'])
    data = request.json
    public_key = data.get('public_key')
    
    if not public_key:
        return jsonify({'success': False, 'error': 'No key provided'}), 400
        
    try:
        # Update user's public key
        execute_query('UPDATE users SET public_key = %s WHERE id = %s', (public_key, my_id), commit=True)
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/keys/<int:user_id>', methods=['GET'])
def api_get_public_key(user_id):
    """Get a user's public key"""
    if 'user' not in session:
        return jsonify({'success': False}), 401
        
    # Get public key
    row = execute_query('SELECT public_key FROM users WHERE id = %s', (user_id,), fetch_one=True)
    
    if not row or not row[0]:
        return jsonify({'success': False, 'error': 'Key not found'}), 404
        
    return jsonify({'success': True, 'public_key': row[0]})


@app.route('/api/dms/<int:dm_id>/mark-read', methods=['POST'])
def api_mark_read(dm_id):
    """Mark messages as read up to a specific message ID (or latest if not provided)"""
    if 'user' not in session:
        return jsonify({'success': False, 'error': 'Not logged in'}), 401
    
    user_id = session['user']['id']
    data = request.json or {}
    message_id = data.get('message_id')
    
    if not message_id:
        # Fallback: Automatically find the latest message in this DM
        last_msg = execute_query("SELECT MAX(id) FROM dm_messages WHERE dm_id = %s", (dm_id,), fetch_one=True)
        if last_msg and last_msg[0]:
            message_id = last_msg[0]
        else:
            # No messages yet, nothing to mark
            return jsonify({'success': True, 'msg': 'No messages to mark'})
    
    try:
        # Update or insert read receipt (Postgres uses UPSERT syntax)
        execute_query(
            """INSERT INTO read_receipts (dm_id, user_id, last_read_message_id, updated_at) 
               VALUES (%s, %s, %s, %s)
               ON CONFLICT(dm_id, user_id) DO UPDATE SET 
               last_read_message_id = EXCLUDED.last_read_message_id, 
               updated_at = EXCLUDED.updated_at""",
            (dm_id, user_id, message_id, time.time()),
            commit=True
        )
        
        return jsonify({'success': True})
    
    except Exception as e:
        print(f"Mark read error: {e}")
        # Manual fallback for SQLite (which might not support ON CONFLICT or has older version)
        try:
            existing = execute_query(
                "SELECT id FROM read_receipts WHERE dm_id = %s AND user_id = %s",
                (dm_id, user_id),
                fetch_one=True
            )
            
            if existing:
                execute_query(
                    "UPDATE read_receipts SET last_read_message_id = %s, updated_at = %s WHERE dm_id = %s AND user_id = %s",
                    (message_id, time.time(), dm_id, user_id),
                    commit=True
                )
            else:
                # FIXED: Corrected parameter order to match the table schema (dm_id, user_id, last_read_message_id, updated_at)
                execute_query(
                    "INSERT INTO read_receipts (dm_id, user_id, last_read_message_id, updated_at) VALUES (%s, %s, %s, %s)",
                    (dm_id, user_id, message_id, time.time()),
                    commit=True
                )
            
            return jsonify({'success': True})
        except Exception as e2:
            print(f"Mark read fallback error: {e2}")
            return jsonify({'success': False, 'error': str(e2)})


@app.route('/api/dms/<int:dm_id>/unread-position', methods=['GET'])
def api_get_unread_position(dm_id):
    """Get the first unread message ID for a DM"""
    if 'user' not in session:
        return jsonify({'success': False, 'error': 'Not logged in'}), 401
    
    user_id = session['user']['id']
    
    try:
        # Get last read message ID
        receipt = execute_query(
            "SELECT last_read_message_id FROM read_receipts WHERE dm_id = %s AND user_id = %s",
            (dm_id, user_id),
            fetch_one=True
        )
        
        if not receipt or not receipt[0]:
            # No read receipt, all messages are unread - get first message
            first_msg = execute_query(
                "SELECT id FROM dm_messages WHERE dm_id = %s ORDER BY id ASC LIMIT 1",
                (dm_id,),
                fetch_one=True
            )
            
            return jsonify({
                'success': True,
                'first_unread_id': first_msg[0] if first_msg else None,
                'has_unread': bool(first_msg)
            })
        
        last_read_id = receipt[0]
        
        # Get first message after last read
        first_unread = execute_query(
            "SELECT id FROM dm_messages WHERE dm_id = %s AND id > %s ORDER BY id ASC LIMIT 1",
            (dm_id, last_read_id),
            fetch_one=True
        )
        
        return jsonify({
            'success': True,
            'first_unread_id': first_unread[0] if first_unread else None,
            'last_read_id': last_read_id,
            'has_unread': bool(first_unread)
        })
    
    except Exception as e:
        print(f"Get unread position error: {e}")
        return jsonify({'success': False, 'error': str(e)})


@app.before_request
def check_auth():
    if request.endpoint and request.endpoint.startswith('static'): return
    if request.endpoint in ['login_page', 'register_page', 'api_login', 'api_register', 'api_auth_register', 'api_auth_login', 'favicon', 
                             'debug_check_tables', 'debug_run_migration', 'debug_friends_dump', 'terms_page', 'privacy_page', 'cookies_page']: return
    
    if 'user' not in session:
        return redirect('/login')
    
    # 🔄 SYNC ROLE WITH DB (Special fix for immediate admin panel visibility)
    # This ensures that if the DB role was updated (e.g. by assistant), the session catches up.
    try:
        current_uid = session['user'].get('id')
        current_username = session['user'].get('username')
        
        # Hardcoded Founders update (Fix for Render storage issues)
        FOUNDERS = ['666', 'OmG', '234']
        
        if current_uid:
            # First check if they are a founder to auto-promote
            if current_username in FOUNDERS:
                execute_query("UPDATE users SET role = 'developer' WHERE id = %s", (current_uid,), commit=True)
            
            # Update last_seen
            execute_query("UPDATE users SET last_seen = %s WHERE id = %s", (time.time(), current_uid), commit=True)
            
            res = execute_query("SELECT role FROM users WHERE id = %s", (current_uid,), fetch_one=True)
            if res and res[0] != session['user'].get('role'):
                session['user']['role'] = res[0]
                session.modified = True
    except Exception as e:
        print(f"[Sync] Role sync error: {e}")

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
    # Octave Assistant Page
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
    try:
        rows = execute_query("SELECT id, username, avatar, role, last_seen FROM users LIMIT 100", fetch_all=True)
        
        users_list = []
        if rows:
            for r in rows:
                user_id = str(r[0])
                is_online = user_id in online_users
                users_list.append({
                    'id': user_id,
                    'username': r[1],
                    'avatar': get_valid_avatar(r[2]),
                    'role': r[3] if len(r) > 3 else 'user',
                    'last_seen': r[4] if len(r) > 4 else None,
                    'status': 'online' if is_online else 'offline'
                })
            
        return jsonify({'success': True, 'users': users_list})
    except Exception as e:
        print(f"[!] API Error (get_users): {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

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
    
    if new_role not in ['developer', 'tester', 'admin', 'user']:
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

@app.route('/api/admin/dashboard-stats')
def api_admin_dashboard_stats():
    if 'user' not in session: return jsonify({'error': 'Auth needed'}), 401
    
    # Check permissions
    uid = session['user']['id']
    row = execute_query("SELECT role FROM users WHERE id = %s", (uid,), fetch_one=True)
    role = row[0] if row else 'user'
    if role not in ['developer', 'admin']: return jsonify({'error': 'Forbidden'}), 403
    
    # Get stats
    user_count = execute_query("SELECT COUNT(*) FROM users", fetch_one=True)[0]
    dm_count = execute_query("SELECT COUNT(*) FROM dm_messages", fetch_one=True)[0]
    online_count = len(online_users)
    
    uptime = int(time.time() - bot_status['start_time'])
    
    return jsonify({
        'success': True,
        'stats': {
            'total_users': user_count,
            'total_messages': dm_count,
            'online_users': online_count,
            'uptime': uptime,
            'cpu': psutil.cpu_percent(),
            'memory': psutil.virtual_memory().percent
        }
    })

@app.route('/api/admin/grant-admin', methods=['POST'])
def api_admin_grant_admin():
    if 'user' not in session: return jsonify({'error': 'Auth needed'}), 401
    
    # Only developers (Founders) can grant admin role
    uid = session['user']['id']
    row = execute_query("SELECT role FROM users WHERE id = %s", (uid,), fetch_one=True)
    role = row[0] if row else 'user'
    if role != 'developer': return jsonify({'error': 'Forbidden - Only Developers can grant Admin'}), 403
    
    data = request.json
    target_identifier = data.get('identifier', '').strip() # Can be full ID or #XXXX tag
    
    if not target_identifier:
        return jsonify({'success': False, 'error': 'Identifier required'})
        
    target_user = None
    
    if target_identifier.isdigit():
        # Search by full ID
        target_user = execute_query("SELECT id, username FROM users WHERE id = %s", (target_identifier,), fetch_one=True)
    elif target_identifier.startswith('#'):
        # Search by tag (last 4 digits of ID)
        tag = target_identifier[1:]
        if len(tag) <= 4:
            # We search for users whose ID ends with this tag
            # For SQLite/Postgres compatibility, we use LIKE
            users = execute_query("SELECT id, username FROM users WHERE CAST(id AS TEXT) LIKE %s", (f"%{tag}",), fetch_all=True)
            if len(users) > 1:
                return jsonify({'success': False, 'error': 'Multiple users found with this tag. Use full ID.'})
            if users:
                target_user = users[0]
    
    if not target_user:
        return jsonify({'success': False, 'error': 'User not found'})
        
    target_id, target_username = target_user
    
    # Update to admin
    execute_query("UPDATE users SET role = 'admin' WHERE id = %s", (target_id,), commit=True)
    add_log('warning', f"User {target_username} ({target_id}) granted ADMIN status by {session['user']['username']}")
    
    # Log Admin Action
    admin_id = session['user']['id']
    ip_addr = request.headers.get('X-Forwarded-For', request.remote_addr)
    execute_query("INSERT INTO admin_logs (admin_id, ip_address, action, timestamp) VALUES (%s, %s, %s, %s)",
                  (admin_id, ip_addr, f"Granted ADMIN to {target_username} ({target_id})", time.time()), commit=True)
    
    return jsonify({'success': True, 'message': f'Admin status granted to {target_username}'})

# --- REPORT SYSTEM API ---

@app.route('/api/messages/report', methods=['POST'])
def api_report_message():
    if 'user' not in session: return jsonify({'error': 'Auth needed'}), 401
    
    data = request.json
    message_id = data.get('message_id')
    reason = data.get('reason', 'No reason provided')
    
    if not message_id:
        return jsonify({'success': False, 'error': 'Message ID required'})
    
    reporter_id = session['user']['id']
    
    # Check if report already exists for this user and message
    exists = execute_query("SELECT id FROM reports WHERE message_id = %s AND reporter_id = %s", 
                           (message_id, reporter_id), fetch_one=True)
    if exists:
        return jsonify({'success': False, 'error': 'You have already reported this message'})
    
    # Store report
    execute_query("INSERT INTO reports (message_id, reporter_id, reason, timestamp) VALUES (%s, %s, %s, %s)",
                   (message_id, reporter_id, reason, time.time()), commit=True)
    
    return jsonify({'success': True, 'message': 'Report submitted successfully. Admins will review it soon.'})

@app.route('/api/admin/reports')
def api_admin_reports():
    if 'user' not in session: return jsonify({'error': 'Auth needed'}), 401
    
    # Admin only check
    role = session['user'].get('role')
    if role not in ['developer', 'admin']: return jsonify({'error': 'Forbidden'}), 403
    
    # Fetch reports with message content and author info
    # We join reports with dm_messages and users
    query = """
    SELECT r.id, r.message_id, r.reason, r.timestamp, 
           rm.content as message_content, 
           u_rep.username as reporter_name,
           u_msg.username as author_name,
           u_msg.id as author_id
    FROM reports r
    JOIN dm_messages rm ON r.message_id = rm.id
    JOIN users u_rep ON r.reporter_id = u_rep.id
    JOIN users u_msg ON rm.author_id = u_msg.id
    ORDER BY r.timestamp DESC
    """
    rows = execute_query(query, fetch_all=True)
    
    reports = []
    for r in rows:
        reports.append({
            'report_id': r[0],
            'message_id': r[1],
            'reason': r[2],
            'timestamp': r[3],
            'content': r[4],
            'reporter': r[5],
            'author': r[6],
            'author_id': r[7]
        })
        
    return jsonify({'success': True, 'reports': reports})

@app.route('/api/admin/reports/resolve', methods=['POST'])
def api_admin_resolve_report():
    if 'user' not in session: return jsonify({'error': 'Auth needed'}), 401
    
    role = session['user'].get('role')
    if role not in ['developer', 'admin']: return jsonify({'error': 'Forbidden'}), 403
    
    data = request.json
    report_id = data.get('report_id')
    action = data.get('action') # 'delete' or 'ignore'
    
    if not report_id: return jsonify({'error': 'Report ID required'})
    
    if action == 'delete':
        # Get message_id first
        rep = execute_query("SELECT message_id FROM reports WHERE id = %s", (report_id,), fetch_one=True)
        if rep:
            msg_id = rep[0]
            # Delete message
            execute_query("DELETE FROM dm_messages WHERE id = %s", (msg_id,), commit=True)
            # Notify via socket or log
            add_log('warning', f"Admin {session['user']['username']} deleted reported message {msg_id}")
            
    # Remove the report after handling
    execute_query("DELETE FROM reports WHERE id = %s", (report_id,), commit=True)
    
    # Log Admin Action
    admin_id = session['user']['id']
    ip_addr = request.headers.get('X-Forwarded-For', request.remote_addr)
    execute_query("INSERT INTO admin_logs (admin_id, ip_address, action, timestamp) VALUES (%s, %s, %s, %s)",
                  (admin_id, ip_addr, f"Resolved report {report_id} (Action: {action})", time.time()), commit=True)
    
    return jsonify({'success': True, 'message': 'Report resolved'})

# --- ADVANCED ADMIN SYSTEM ---

@app.route('/api/admin/verify-2fa', methods=['POST'])
def api_admin_verify_2fa():
    if 'user' not in session or session['user'].get('role') not in ['admin', 'developer']:
        return jsonify({'success': False, 'error': 'Unauthorized'}), 403
    
    data = request.json
    pin = data.get('pin')
    admin_id = session['user']['id']
    
    # System PIN - default '123456' or from environment
    MASTER_PIN = os.environ.get('ADMIN_PANEL_PIN', '123456')
    
    if pin == MASTER_PIN:
        session['admin_verified'] = True
        session.modified = True
        
        # Log Access
        ip_addr = request.headers.get('X-Forwarded-For', request.remote_addr)
        execute_query("INSERT INTO admin_logs (admin_id, ip_address, action, timestamp) VALUES (%s, %s, %s, %s)",
                      (admin_id, ip_addr, "Admin Panel Access (2FA Verified)", time.time()), commit=True)
        
        return jsonify({'success': True})
    else:
        return jsonify({'success': False, 'error': 'Неверный PIN-код'})

@app.route('/api/admin/migrate-now', methods=['POST'])
def api_admin_migrate_now():
    if 'user' not in session or session['user'].get('role') not in ['admin', 'developer']:
        return jsonify({'success': False, 'error': 'Unauthorized'}), 403
    if not session.get('admin_verified'):
        return jsonify({'success': False, 'error': '2FA needed'}), 401
    try:
        run_db_migration()
        return jsonify({'success': True, 'message': 'Migration finished. Refresh the page.'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/admin/broadcast', methods=['POST'])
def api_admin_broadcast():
    if 'user' not in session or session['user'].get('role') not in ['admin', 'developer']:
        return jsonify({'success': False, 'error': 'Unauthorized'}), 403
    
    if not session.get('admin_verified'):
        return jsonify({'success': False, 'error': 'Требуется подтверждение 2FA'}), 401
    
    data = request.json
    content = data.get('content')
    if not content: return jsonify({'success': False, 'error': 'Пустое сообщение'}), 400
    
    admin_id = session['user']['id']
    timestamp = time.time()
    
    try:
        # Get all users (except system bot ID 0)
        users = execute_query("SELECT id FROM users WHERE id != 0", fetch_all=True)
        
        # Create/Find System User "Команда Octave" (ID 0)
        has_system = execute_query("SELECT id FROM users WHERE id = 0", fetch_one=True)
        if not has_system:
            execute_query("INSERT INTO users (id, username, password_hash, role) VALUES (0, 'Команда Octave', 'system_lock', 'bot')", commit=True)
        
        sent_count = 0
        for uid_row in users:
            uid = uid_row[0]
            
            # Find/Create DM
            dm_id = None
            existing_dm = execute_query("SELECT id FROM direct_messages WHERE (user_id_1 = 0 AND user_id_2 = %s) OR (user_id_1 = %s AND user_id_2 = 0)", 
                                       (uid, uid), fetch_one=True)
            
            if existing_dm:
                dm_id = existing_dm[0]
            else:
                dm_id = execute_query("INSERT INTO direct_messages (user_id_1, user_id_2, last_message_at) VALUES (0, %s, %s)",
                                     (uid, timestamp), commit=True)
            
            # Insert message
            execute_query("INSERT INTO dm_messages (dm_id, author_id, content, timestamp) VALUES (%s, 0, %s, %s)", 
                          (dm_id, content, timestamp), commit=True)
            
            # Notify recipient
            socketio.emit('new_dm_message', {
                'dm_id': dm_id,
                'author_id': 0,
                'author_name': 'Команда Octave',
                'content': content,
                'timestamp': timestamp,
                'is_system': True
            }, room=str(uid))
            
            sent_count += 1
            
        # Log Action
        ip_addr = request.headers.get('X-Forwarded-For', request.remote_addr)
        execute_query("INSERT INTO admin_logs (admin_id, ip_address, action, timestamp) VALUES (%s, %s, %s, %s)",
                      (admin_id, ip_addr, f"Sent broadcast to {sent_count} users", time.time()), commit=True)
                      
        return jsonify({'success': True, 'count': sent_count})
    except Exception as e:
        print(f"[Broadcast] Error: {e}")
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/admin/logs', methods=['GET'])
def api_admin_logs():
    if 'user' not in session or session['user'].get('role') not in ['admin', 'developer']:
        return jsonify({'success': False, 'error': 'Unauthorized'}), 403
    
    if not session.get('admin_verified'):
        return jsonify({'success': False, 'error': 'Требуется подтверждение 2FA'}), 401
    
    try:
        query = """
            SELECT al.id, al.ip_address, al.action, al.timestamp, u.username as admin_name
            FROM admin_logs al
            JOIN users u ON al.admin_id = u.id
            ORDER BY al.timestamp DESC
            LIMIT 100
        """
        logs = execute_query(query, fetch_all=True)
        
        result = []
        for l in logs:
            result.append({
                'id': l[0],
                'ip': l[1],
                'action': l[2],
                'timestamp': l[3],
                'admin': l[4]
            })
            
        return jsonify({'success': True, 'logs': result})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

# --- START ADVANCED T&S SYSTEM ---

def add_admin_log(admin_id, ip, action, details=""):
    """Helper to log staff actions"""
    execute_query(
        "INSERT INTO admin_logs (admin_id, ip_address, action, details, timestamp) VALUES (%s, %s, %s, %s, %s)",
        (admin_id, ip, action, details, time.time()), commit=True
    )

@app.route('/api/admin/dashboard-v2')
def api_admin_dashboard_v2():
    if 'user' not in session or session['user'].get('role') not in ['admin', 'moderator', 'support', 'developer']:
        return jsonify({'success': False, 'error': 'Unauthorized'}), 403
    
    try:
        # 1. Active Users (Online in last 5 mins)
        now = time.time()
        online_count = len(online_users)
        
        # 2. New Registrations (Last 24h)
        day_ago = now - 86400
        new_regs = execute_query("SELECT COUNT(*) FROM users WHERE created_at >= %s", (day_ago,), fetch_one=True)[0]
        
        # 3. Reports Count (Pending)
        pending_reports = execute_query("SELECT COUNT(*) FROM reports WHERE status = 'pending'", fetch_one=True)[0]
        
        # 4. Risk Alerts (Recent)
        recent_alerts = execute_query("SELECT COUNT(*) FROM risk_alerts WHERE timestamp >= %s", (day_ago,), fetch_one=True)[0]
        
        # 5. User Roles distribution
        roles = execute_query("SELECT role, COUNT(*) FROM users GROUP BY role", fetch_all=True)
        role_map = {r[0]: r[1] for r in roles}
        
        return jsonify({
            'success': True,
            'stats': {
                'online': online_count,
                'new_regs': new_regs,
                'pending_reports': pending_reports,
                'risk_alerts': recent_alerts,
                'roles': role_map
            }
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/admin/users/search-v2')
def api_admin_user_search_v2():
    if 'user' not in session or session['user'].get('role') not in ['admin', 'moderator', 'support', 'developer']:
        return jsonify({'success': False}), 403
    
    q = request.args.get('query', '')
    try:
        if q:
            # Search by username, ID, or IP
            query = """
                SELECT id, username, avatar, role, created_at, ip_address, risk_score, is_banned, is_muted
                FROM users 
                WHERE username LIKE %s OR id = %s OR ip_address LIKE %s
                ORDER BY created_at DESC LIMIT 50
            """
            search_param = f"%{q}%"
            users = execute_query(query, (search_param, q if q.isdigit() else -1, search_param), fetch_all=True)
        else:
            # Recent users
            users = execute_query("SELECT id, username, avatar, role, created_at, ip_address, risk_score, is_banned, is_muted FROM users ORDER BY created_at DESC LIMIT 20", fetch_all=True)
            
        result = []
        for u in users:
            result.append({
                'id': u[0], 'username': u[1], 'avatar': get_valid_avatar(u[2]),
                'role': u[3], 'created_at': u[4], 'ip': u[5], 'risk': u[6],
                'is_banned': bool(u[7]), 'is_muted': bool(u[8])
            })
        return jsonify({'success': True, 'users': result})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/admin/users/<int:uid>/profile')
def api_admin_user_profile(uid):
    if 'user' not in session or session['user'].get('role') not in ['admin', 'moderator', 'support', 'developer']:
        return jsonify({'success': False}), 403
    
    try:
        user = execute_query("SELECT id, username, email, phone, role, created_at, ip_address, risk_score, is_banned, ban_expires, is_muted, mute_expires, ban_reason FROM users WHERE id = %s", (uid,), fetch_one=True)
        if not user: return jsonify({'success': False, 'error': 'User not found'})
        
        # Reports against this user
        reports = execute_query("""
            SELECT r.id, r.reason, r.timestamp, u.username as reporter 
            FROM reports r JOIN users u ON r.reporter_id = u.id 
            JOIN dm_messages m ON r.message_id = m.id
            WHERE m.author_id = %s
        """, (uid,), fetch_all=True)
        
        # Risk Alerts
        alerts = execute_query("SELECT id, type, details, risk_level, timestamp FROM risk_alerts WHERE user_id = %s ORDER BY timestamp DESC", (uid,), fetch_all=True)
        
        return jsonify({
            'success': True,
            'profile': {
                'id': user[0], 'username': user[1], 'email': user[2], 'phone': user[3],
                'role': user[4], 'created_at': user[5], 'ip': user[6], 'risk': user[7],
                'ban': {'active': bool(user[8]), 'expires': user[9], 'reason': user[12]},
                'mute': {'active': bool(user[10]), 'expires': user[11]}
            },
            'reports': [{'id': r[0], 'reason': r[1], 'time': r[2], 'from': r[3]} for r in reports],
            'alerts': [{'id': a[0], 'type': a[1], 'details': a[2], 'level': a[3], 'time': a[4]} for a in alerts]
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/admin/users/remediate', methods=['POST'])
def api_admin_user_remediate():
    staff_role = session['user'].get('role')
    if 'user' not in session or staff_role not in ['admin', 'moderator', 'support', 'developer']:
        return jsonify({'success': False}), 403
    
    data = request.json
    uid = data.get('user_id')
    action = data.get('action') # ban, mute, warn, unban, unmute
    reason = data.get('reason', 'Violation of terms')
    duration = data.get('duration') # hours, null for perm
    
    if staff_role == 'support' and action in ['ban', 'role_change']:
        return jsonify({'success': False, 'error': 'Support cannot ban users'}), 403
    
    try:
        staff_id = session['user']['id']
        staff_ip = request.remote_addr
        expires = time.time() + (float(duration) * 3600) if duration else None
        
        if action == 'ban':
            execute_query("UPDATE users SET is_banned = 1, ban_expires = %s, ban_reason = %s WHERE id = %s", (expires, reason, uid), commit=True)
            add_admin_log(staff_id, staff_ip, "BAN", f"User {uid} banned for {duration or 'PERM'}. Reason: {reason}")
        elif action == 'mute':
            execute_query("UPDATE users SET is_muted = 1, mute_expires = %s WHERE id = %s", (expires, uid), commit=True)
            add_admin_log(staff_id, staff_ip, "MUTE", f"User {uid} muted for {duration or 'PERM'}")
        elif action == 'unban':
            execute_query("UPDATE users SET is_banned = 0, ban_expires = NULL WHERE id = %s", (uid,), commit=True)
            add_admin_log(staff_id, staff_ip, "UNBAN", f"User {uid} unbanned")
        elif action == 'unmute':
            execute_query("UPDATE users SET is_muted = 0, mute_expires = NULL WHERE id = %s", (uid,), commit=True)
            add_admin_log(staff_id, staff_ip, "UNMUTE", f"User {uid} unmuted")
            
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/admin/inspector/messages')
def api_admin_inspector():
    if 'user' not in session or session['user'].get('role') not in ['admin', 'moderator', 'developer']:
        return jsonify({'success': False, 'error': 'Inaccessible to current role'}), 403
    
    user_id = request.args.get('user_id')
    keyword = request.args.get('keyword', '')
    try:
        staff_id = session['user']['id']
        staff_ip = request.remote_addr
        
        query = "SELECT m.id, m.content, m.timestamp, u.username, m.dm_id FROM dm_messages m JOIN users u ON m.author_id = u.id WHERE 1=1"
        params = []
        if user_id:
            query += " AND m.author_id = %s"
            params.append(user_id)
        if keyword:
            query += " AND m.content LIKE %s"
            params.append(f"%{keyword}%")
            
        query += " ORDER BY m.timestamp DESC LIMIT 100"
        msgs = execute_query(query, tuple(params), fetch_all=True)
        
        # Log inspection access for accountability
        add_admin_log(staff_id, staff_ip, "INSPECT_CHAT", f"Inspected messages for User:{user_id or 'ALL'} Keyword:{keyword or 'NONE'}")
        
        result = []
        for m in msgs:
            result.append({'id': m[0], 'content': m[1], 'time': m[2], 'author': m[3], 'dm_id': m[4]})
        return jsonify({'success': True, 'messages': result})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

# --- END ADVANCED T&S SYSTEM ---

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
            'title': 'Добро пожаловать на Octave!',
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
            'title': 'Octave Помощник',
            'content': 'Используйте вкладку Octave для получения помощи по правилам сервера, генерации жалоб и многого другого.',
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

@app.route('/api/bot/status')  # Получить статус бота
def get_bot_status():
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

@app.route('/api/monitor/list')  # Получить список мониторов
def get_monitor_list():
    return jsonify({"success": True, "monitors": utils.get_monitors()})

@app.route('/api/monitors/remove/<id>', methods=['DELETE'])
def api_remove_monitor(id):
    if 'user' not in session: return jsonify({'success': False}), 401
    if utils.remove_monitor(id):
        add_log('info', f"Monitor removed: {id}")
        return jsonify({'success': True})
    return jsonify({'success': False})

@app.route('/api/monitor/<int:monitor_id>/logs')  # Получить логи конкретного монитора
def get_monitor_logs(monitor_id):
    if 'user' not in session: return jsonify({'error': 'Auth needed'}), 401
    logs = utils.get_monitor_logs(monitor_id)
    return jsonify(logs)

@app.route('/api/monitor/<int:monitor_id>/stats')  # Получить статистику монитора
def get_monitor_stats(monitor_id):
    if 'user' not in session: return jsonify({'error': 'Auth needed'}), 401
    stats = utils.get_monitor_stats(monitor_id)
    if stats:
        return jsonify(stats)
    return jsonify({'error': 'Monitor not found'}), 404

@app.route('/api/monitor/<int:monitor_id>/clear', methods=['POST'])  # Очистить логи монитора
def clear_monitor_logs(monitor_id):
    """Очистить логи монитора"""
    if 'user' not in session: return jsonify({'success': False}), 401
    if utils.clear_monitor_logs(monitor_id):
        add_log('info', f"Monitor logs cleared: {monitor_id}")
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

ВАЖНО: Игрок уже искал в базе данных и не нашёл ответ.
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

@app.route('/api/arizona/trainer', methods=['POST'])
def api_arizona_trainer():
    if 'user' not in session: return jsonify({'error': 'Auth needed'}), 401
    
    data = request.json
    scenario = data.get('scenario', 'traffic_stop')
    user_message = data.get('message', '')
    history = data.get('history', [])

    # System prompts for different scenarios
    prompts = {
        'traffic_stop': "Ты - офицер полиции LSPD на сервере Arizona RP. Твоя задача: остановить игрока за нарушение ПДД и отыграть РП ситуацию (траффик-стоп 10-55). Будь строгим, используй биндерные отыгровки, но реагируй на действия игрока. Если игрок хорошо отыгрывает (/me, /do), хвали его в NonRP чате (( )). Если плохо - подсказывай. Начни с требования заглушить двигатель.",
        'medic_exam': "Ты - врач больницы ЛС. Твоя задача: провести мед. осмотр игрока призывника. Спрашивай жалобы, проверяй зрение, слушай сердце. Используй /me и /do. Оценивай уровень РП игрока.",
        'bar_fight': "Ты - бандит из Гетто (Vagos). Ты в баре, пьяный. Докопайся до игрока, спровоцируй драку, используй сленг гетто. Проверь, как игрок будет реагировать: испугается (ПГ?) или ответит.",
        'interview': "Ты - Заместитель Директора СМИ. Проводишь собеседование игроку на должность Стажера. Проверь его паспорт, медкарту и лицензии по РП. Спроси термины (МГ, ТК, ДМ) в /b чат."
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
        return jsonify({'success': False, 'error': 'Пустой текст'})
        
    try:
        prompt = f"""Ты - строгий редактор объявлений СМИ(PRO) на сервере Arizona RP. Отредактируй это: "{text}"
По правилам:
1. Замени сленг (гетто -> опасный район, велик -> в/т Горник).
2. Добавь префиксы (а/м - авто, м/ц - мото).
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
    # Allow self-DMs for Cloud Drive / Saved Messages
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

@app.route('/api/dms/get_or_create/<int:target_id>', methods=['POST'])
def api_get_or_create_dm(target_id):
    if 'user' not in session: return jsonify({'success': False}), 401
    my_id = int(session['user']['id'])
    
    dm_id = get_or_create_dm(my_id, target_id)
    return jsonify({'success': True, 'dm_id': dm_id})

@app.route('/api/dms', methods=['GET'])
def api_get_dms():
    if 'user' not in session: return jsonify({'success': False}), 401
    my_id = int(session['user']['id'])
    
    # Combined query to fetch DMs, other user info, last message, and unread count
    rows = execute_query("""
        SELECT 
            dm.id, dm.user_id_1, dm.user_id_2, dm.last_message_at,
            u.id as other_id, u.username, u.avatar, u.display_name,
            m.content as last_content, m.timestamp as last_timestamp,
            (SELECT COUNT(*) FROM dm_messages 
             WHERE dm_id = dm.id AND author_id != %s
             AND id > COALESCE((SELECT last_read_message_id FROM read_receipts WHERE dm_id = dm.id AND user_id = %s), 0)
            ) as unread_count
        FROM direct_messages dm
        JOIN users u ON u.id = (CASE WHEN dm.user_id_1 = %s AND dm.user_id_2 != %s THEN dm.user_id_2 ELSE dm.user_id_1 END)
        LEFT JOIN (
            SELECT dm_id, content, timestamp
            FROM dm_messages
            WHERE id IN (SELECT MAX(id) FROM dm_messages GROUP BY dm_id)
        ) m ON m.dm_id = dm.id
        WHERE dm.user_id_1 = %s OR dm.user_id_2 = %s
        ORDER BY dm.last_message_at DESC
    """, (my_id, my_id, my_id, my_id, my_id, my_id), fetch_all=True)
    
    dms = []
    for r in rows or []:
        dm_id, u1, u2, ts, other_id, other_username, other_avatar, other_display_name, last_content, last_ts, unread_count = r
        
        display_name = other_display_name or other_username
        if int(other_id) == my_id:
            display_name = "Saved Messages"
            
        last_message_text = last_content
        if last_message_text and len(last_message_text) > 50:
            last_message_text = last_message_text[:50] + "..."
            
        dms.append({
            'id': str(dm_id),
            'other_user': {
                'id': str(other_id),
                'username': other_username,
                'avatar': other_avatar if other_avatar else DEFAULT_AVATAR,
                'display_name': display_name
            },
            'last_message_at': ts,
            'last_message_text': last_message_text,
            'last_message_timestamp': last_ts or ts,
            'unread_count': unread_count
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
    
    # Fetch ALL messages ordered chronologically with extended fields
    rows = execute_query("""
        SELECT dm.id, dm.content, dm.timestamp, u.username, u.avatar, 
               dm.is_pinned, dm.edited_at, dm.reply_to_id, u.id as author_id, dm.attachments,
               dm.is_encrypted, dm.encryption_metadata, dm.cloud_folder_id, dm.tags
        FROM dm_messages dm
        JOIN users u ON u.id = dm.author_id
        WHERE dm.dm_id = %s
        ORDER BY dm.timestamp ASC
    """, (dm_id,), fetch_all=True)
    
    if not rows:
        return jsonify({'success': True, 'messages': []})

    msg_ids = [r[0] for r in rows]
    reply_ids = list(set([r[7] for r in rows if r[7]]))
    
    # Bulk fetch reactions
    reactions_map = {}
    if msg_ids:
        placeholders = ','.join(['%s'] * len(msg_ids))
        reaction_rows = execute_query(f'''
            SELECT message_id, emoji, COUNT(*) as count
            FROM message_reactions
            WHERE message_id IN ({placeholders})
            GROUP BY message_id, emoji
        ''', tuple(msg_ids), fetch_all=True)
        
        for r_row in reaction_rows or []:
            mid, emoji, count = r_row
            if mid not in reactions_map:
                reactions_map[mid] = {}
            reactions_map[mid][emoji] = count

    # Bulk fetch reply previews
    replies_map = {}
    if reply_ids:
        placeholders = ','.join(['%s'] * len(reply_ids))
        reply_rows = execute_query(f'''
            SELECT dm.id, dm.content, u.username 
            FROM dm_messages dm 
            JOIN users u ON u.id = dm.author_id 
            WHERE dm.id IN ({placeholders})
        ''', tuple(reply_ids), fetch_all=True)
        
        for rep in reply_rows or []:
            rid, content, uname = rep
            replies_map[rid] = {
                'content': content[:100] + '...' if len(content) > 100 else content,
                'username': uname
            }

    messages = []
    for r in rows:
        msg_id = r[0]
        reactions = reactions_map.get(msg_id, {})
        reply_preview = replies_map.get(r[7]) if r[7] else None
        
        messages.append({
            'id': msg_id,
            'content': r[1],
            'timestamp': r[2],
            'username': r[3],
            'avatar': r[4] if r[4] else DEFAULT_AVATAR,
            'is_pinned': bool(r[5]),
            'edited_at': r[6],
            'reply_to': reply_preview,
            'author_id': r[8],
            'reactions': reactions,
            'attachments': json.loads(r[9]) if r[9] else None,
            'is_encrypted': bool(r[10]),
            'encryption_metadata': r[11],
            'cloud_folder_id': r[12],
            'tags': r[13]
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
    reply_to_id = data.get('reply_to_id')  # ID сообщения на которое отвечаем
    attachments = data.get('attachments')  # JSON string of file metadata
    attachments = data.get('attachments')  # JSON string of file metadata
    expires_in = data.get('expires_in')  # Seconds until message expires (disappearing messages)
    is_encrypted = data.get('is_encrypted', False)
    encryption_metadata = data.get('encryption_metadata')
    nonce = data.get('nonce')
    folder_id = data.get('folder_id') # New field for Cloud Drive organization
    
    # Require either content or attachments
    if not content and not attachments:
        return jsonify({'success': False, 'error': 'Empty message'}), 400
    
    timestamp = time.time()
    
    # Calculate expiration time if set
    expires_at = None
    if expires_in and isinstance(expires_in, (int, float)) and expires_in > 0:
        expires_at = timestamp + expires_in
    
    try:
        # Insert message with reply support and expiration
        message_id = execute_query('''
            INSERT INTO dm_messages (dm_id, author_id, content, timestamp, reply_to_id, attachments, expires_at, is_encrypted, encryption_metadata, cloud_folder_id)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        ''', (dm_id, my_id, content, timestamp, reply_to_id, attachments, expires_at, int(is_encrypted), encryption_metadata, folder_id), commit=True)
        
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
        'id': message_id,  # Include message ID for expiration tracking
        'dm_id': dm_id,
        'author': username,
        'avatar': avatar,
        'content': content,
        'timestamp': timestamp,
        'attachments': json.loads(attachments) if attachments else None,  # Parse JSON to object
        'is_encrypted': is_encrypted,
        'encryption_metadata': encryption_metadata,
        'expires_at': expires_at,
        'nonce': nonce,
        'cloud_folder_id': folder_id
    }
    
    # Only send to the OTHER user (not the sender)
    # Sender already gets message via HTTP response + optimistic UI
    other_user_id = dm_row[1] if dm_row[0] == my_id else dm_row[0]
    socketio.emit('new_dm_message', payload, room=str(other_user_id))
    
    # Return full message data for frontend optimistic update
    return jsonify({
        'success': True, 
        'message': {
            'id': message_id,  # Include message ID for expiration tracking
            'dm_id': dm_id,
            'author': username,
            'avatar': avatar,
            'content': content,
            'timestamp': timestamp,
            'attachments': json.loads(attachments) if attachments else None,  # Parse JSON to object
            'expires_at': expires_at,
            'nonce': nonce,
            'cloud_folder_id': folder_id
        }
    })

@app.route('/api/dms/<int:target_id>/send', methods=['POST'])
def api_dm_send(target_id):
    if 'user' not in session: return jsonify({'success': False}), 401
    my_id = int(session['user']['id'])
    data = request.json
    content = data.get('content', '').strip()
    reply_to_id = data.get('reply_to_id')  # Support replies
    attachments = data.get('attachments')  # Support attachments (JSON string)
    expires_in = data.get('expires_in')  # Seconds until message expires
    nonce = data.get('nonce')
    is_encrypted = data.get('is_encrypted', False)
    encryption_metadata = data.get('encryption_metadata')
    folder_id = data.get('folder_id')
    
    # Require either content or attachments
    if not content and not attachments:
        return jsonify({'success': False, 'error': 'Empty message'}), 400
    
    dm_id = get_or_create_dm(my_id, target_id)
    timestamp = time.time()
    
    # Calculate expiration time if set
    expires_at = None
    if expires_in and isinstance(expires_in, (int, float)) and expires_in > 0:
        expires_at = timestamp + expires_in
    
    # Insert Message with attachments, reply support, encryption and expiration
    message_id = execute_query("""
        INSERT INTO dm_messages (dm_id, author_id, content, timestamp, reply_to_id, attachments, expires_at, is_encrypted, encryption_metadata, cloud_folder_id) 
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
    """, (dm_id, my_id, content, timestamp, reply_to_id, attachments, expires_at, int(is_encrypted), encryption_metadata, folder_id), commit=True)
                  
    # Update timestamp for sorting
    execute_query("UPDATE direct_messages SET last_message_at = %s WHERE id = %s", (timestamp, dm_id), commit=True)
    
    # Get user info for proper avatar
    u = execute_query('SELECT username, avatar FROM users WHERE id = %s', (my_id,), fetch_one=True)
    username = u[0] if u else session['user']['username']
    avatar = get_valid_avatar(u[1]) if u else session['user']['avatar']
    
    msg_obj = {
        'id': message_id,  # Include message ID for expiration tracking
        'dm_id': str(dm_id),
        'author_id': my_id,
        'author': username,
        'avatar': avatar,
        'content': content,
        'timestamp': timestamp,
        'attachments': attachments,  # Include attachments in response
        'reply_to_id': reply_to_id,  # Include reply info
        'users': [my_id, target_id],  # IDs to filter on frontend
        'expires_at': expires_at,  # Disappearing message timer
        'nonce': nonce,
        'cloud_folder_id': folder_id
    }
    
    # Emit real-time event only to the RECIPIENT (not sender)
    # Sender already gets message via HTTP response + optimistic UI
    socketio.emit('new_dm_message', msg_obj, room=str(target_id))
    
    # Return message data for frontend optimistic update
    return jsonify({
        'success': True, 
        'message': msg_obj
    })


# ============================================================
# РАСШИРЕННЫЕ ФУНКЦИИ СООБЩЕНИЙ
# ============================================================

@app.route('/api/messages/<int:message_id>/edit', methods=['PUT'])
def api_edit_message(message_id):
    """Редактировать сообщение"""
    if 'user' not in session:
        return jsonify({'success': False, 'error': 'Not authenticated'}), 401
    
    my_id = int(session['user']['id'])
    data = request.json
    new_content = data.get('content', '').strip()
    
    if not new_content:
        return jsonify({'success': False, 'error': 'Empty content'}), 400
    
    # Check if user owns this message
    msg = execute_query('SELECT author_id, dm_id FROM dm_messages WHERE id = %s', (message_id,), fetch_one=True)
    if not msg:
        return jsonify({'success': False, 'error': 'Message not found'}), 404
    
    if msg[0] != my_id:
        return jsonify({'success': False, 'error': 'Cannot edit others messages'}), 403
    
    # Update message
    execute_query('UPDATE dm_messages SET content = %s, edited_at = %s WHERE id = %s',
                  (new_content, time.time(), message_id), commit=True)
    
    # Emit update via socket
    socketio.emit('message_edited', {
        'message_id': message_id,
        'content': new_content,
        'edited_at': time.time()
    })
    
    return jsonify({'success': True})


@app.route('/api/messages/<int:message_id>/delete', methods=['DELETE'])
def api_delete_message(message_id):
    """Удалить сообщение"""
    if 'user' not in session:
        return jsonify({'success': False, 'error': 'Not authenticated'}), 401
    
    my_id = int(session['user']['id'])
    
    # Check if user owns this message
    msg = execute_query('SELECT author_id, dm_id FROM dm_messages WHERE id = %s', (message_id,), fetch_one=True)
    if not msg:
        return jsonify({'success': False, 'error': 'Message not found'}), 404
    
    if msg[0] != my_id:
        return jsonify({'success': False, 'error': 'Cannot delete others messages'}), 403
    
    dm_id = msg[1]
    
    # Delete reactions first
    execute_query('DELETE FROM message_reactions WHERE message_id = %s', (message_id,), commit=True)
    
    # Delete message
    execute_query('DELETE FROM dm_messages WHERE id = %s', (message_id,), commit=True)
    
    # Emit delete via socket
    socketio.emit('message_deleted', {
        'message_id': message_id,
        'dm_id': dm_id
    })
    
    return jsonify({'success': True})


@app.route('/api/messages/<int:message_id>/pin', methods=['POST'])
def api_pin_message(message_id):
    """Закрепить/открепить сообщение"""
    if 'user' not in session:
        return jsonify({'success': False, 'error': 'Not authenticated'}), 401
    
    my_id = int(session['user']['id'])
    
    # Check message exists and user has access
    msg = execute_query('SELECT dm_id, is_pinned FROM dm_messages WHERE id = %s', (message_id,), fetch_one=True)
    if not msg:
        return jsonify({'success': False, 'error': 'Message not found'}), 404
    
    dm_id = msg[0]
    current_pinned = msg[1] or 0
    
    # Check user is part of this DM
    dm = execute_query('SELECT user_id_1, user_id_2 FROM direct_messages WHERE id = %s', (dm_id,), fetch_one=True)
    if not dm or my_id not in [dm[0], dm[1]]:
        return jsonify({'success': False, 'error': 'Access denied'}), 403
    
    # Toggle pin status
    new_pinned = 0 if current_pinned else 1
    execute_query('UPDATE dm_messages SET is_pinned = %s WHERE id = %s', (new_pinned, message_id), commit=True)
    
    # Emit via socket
    socketio.emit('message_pinned', {
        'message_id': message_id,
        'dm_id': dm_id,
        'is_pinned': bool(new_pinned)
    })
    
    return jsonify({'success': True, 'is_pinned': bool(new_pinned)})


@app.route('/api/dms/<int:dm_id>/pinned', methods=['GET'])
def api_get_pinned_messages(dm_id):
    """Получить закреплённые сообщения"""
    if 'user' not in session:
        return jsonify({'success': False}), 401
    
    my_id = int(session['user']['id'])
    
    # Check access
    dm = execute_query('SELECT user_id_1, user_id_2 FROM direct_messages WHERE id = %s', (dm_id,), fetch_one=True)
    if not dm or my_id not in [dm[0], dm[1]]:
        return jsonify({'success': False, 'error': 'Access denied'}), 403
    
    rows = execute_query('''
        SELECT dm.id, dm.content, dm.timestamp, u.username, u.avatar
        FROM dm_messages dm
        JOIN users u ON u.id = dm.author_id
        WHERE dm.dm_id = %s AND dm.is_pinned = 1
        ORDER BY dm.timestamp DESC
    ''', (dm_id,), fetch_all=True)
    
    pinned = []
    for r in rows or []:
        pinned.append({
            'id': r[0],
            'content': r[1],
            'timestamp': r[2],
            'username': r[3],
            'avatar': r[4] or DEFAULT_AVATAR
        })
    
    return jsonify({'success': True, 'pinned': pinned})


@app.route('/api/messages/<int:message_id>/react', methods=['POST'])
def api_react_message(message_id):
    """Добавить/удалить реакцию"""
    try:
        if 'user' not in session:
            return jsonify({'success': False, 'error': 'Not authenticated'}), 401
        
        my_id = int(session['user']['id'])
        data = request.json
        emoji = data.get('emoji', '').strip()
        
        if not emoji:
            return jsonify({'success': False, 'error': 'No emoji provided'}), 400
        
        # Check message exists
        msg = execute_query('SELECT dm_id FROM dm_messages WHERE id = %s', (message_id,), fetch_one=True)
        if not msg:
            return jsonify({'success': False, 'error': 'Message not found'}), 404
        
        dm_id = msg[0]
        
        # Check if reaction already exists
        existing = execute_query(
            'SELECT id FROM message_reactions WHERE message_id = %s AND user_id = %s AND emoji = %s',
            (message_id, my_id, emoji), fetch_one=True
        )
        
        if existing:
            # Remove reaction
            execute_query('DELETE FROM message_reactions WHERE id = %s', (existing[0],), commit=True)
            action = 'removed'
        else:
            # Add reaction
            execute_query(
                'INSERT INTO message_reactions (message_id, user_id, emoji, created_at) VALUES (%s, %s, %s, %s)',
                (message_id, my_id, emoji, time.time()), commit=True
            )
            action = 'added'
        
        # Get updated reactions count
        reactions = get_message_reactions(message_id)
        
        # Emit via socket
        socketio.emit('message_reaction', {
            'message_id': message_id,
            'dm_id': dm_id,
            'reactions': reactions
        })
        
        return jsonify({'success': True, 'action': action, 'reactions': reactions})
    
    except Exception as e:
        print(f"[ERROR] Reaction error for message {message_id}: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': f'Server error: {str(e)}'}), 500


def get_message_reactions(message_id):
    """Helper: получить реакции для сообщения"""
    rows = execute_query('''
        SELECT emoji, COUNT(*) as count
        FROM message_reactions
        WHERE message_id = %s
        GROUP BY emoji
    ''', (message_id,), fetch_all=True)
    
    reactions = {}
    for r in rows or []:
        reactions[r[0]] = r[1]
    
    return reactions


@app.route('/api/messages/<int:message_id>/reactions', methods=['GET'])
def api_get_reactions(message_id):
    """Получить все реакции на сообщение с пользователями"""
    if 'user' not in session:
        return jsonify({'success': False}), 401
    
    rows = execute_query('''
        SELECT mr.emoji, u.username, u.avatar
        FROM message_reactions mr
        JOIN users u ON u.id = mr.user_id
        WHERE mr.message_id = %s
    ''', (message_id,), fetch_all=True)
    
    reactions = {}
    for r in rows or []:
        emoji = r[0]
        if emoji not in reactions:
            reactions[emoji] = []
        reactions[emoji].append({
            'username': r[1],
            'avatar': r[2] or DEFAULT_AVATAR
        })
    
    return jsonify({'success': True, 'reactions': reactions})


@app.route('/debug/friends_dump')
def debug_friends_dump():
    rows = execute_query('SELECT * FROM friends', fetch_all=True)
    return jsonify({'rows': rows})

@app.route('/debug/run_migration')
def debug_run_migration():
    """Manually trigger database migration"""
    try:
        run_db_migration()
        return jsonify({'success': True, 'message': 'Migration completed! Check server logs.'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/debug/check_tables')
def debug_check_tables():
    """Check which tables exist in the database"""
    try:
        conn = get_db_connection()
        is_sqlite = isinstance(conn, sqlite3.Connection)
        cursor = conn.cursor()
        
        if is_sqlite:
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = [row[0] for row in cursor.fetchall()]
        else:
            cursor.execute("SELECT table_name FROM information_schema.tables WHERE table_schema='public'")
            tables = [row[0] for row in cursor.fetchall()]
        
        # Check message_reactions table structure if it exists
        reactions_structure = None
        if 'message_reactions' in tables:
            if is_sqlite:
                cursor.execute("PRAGMA table_info(message_reactions)")
                reactions_structure = [{'name': r[1], 'type': r[2]} for r in cursor.fetchall()]
            else:
                cursor.execute("""
                    SELECT column_name, data_type 
                    FROM information_schema.columns 
                    WHERE table_name='message_reactions'
                """)
                reactions_structure = [{'name': r[0], 'type': r[1]} for r in cursor.fetchall()]
        
        cursor.close()
        conn.close()
        
        return jsonify({
            'success': True,
            'db_type': 'SQLite' if is_sqlite else 'PostgreSQL',
            'tables': tables,
            'message_reactions_exists': 'message_reactions' in tables,
            'message_reactions_structure': reactions_structure
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

# --- CLOUD DRIVE ROUTES ---
@app.route('/api/cloud/folders', methods=['GET', 'POST'])
def api_cloud_folders():
    if 'user' not in session: return jsonify({'success': False}), 401
    my_id = int(session['user']['id'])
    
    if request.method == 'GET':
        folders = execute_query('SELECT id, name, color, icon FROM cloud_folders WHERE user_id = %s ORDER BY created_at ASC', (my_id,), fetch_all=True)
        result = [{'id': r[0], 'name': r[1], 'color': r[2], 'icon': r[3]} for r in folders]
        return jsonify({'success': True, 'folders': result})
        
    elif request.method == 'POST':
        data = request.json
        name = data.get('name', '').strip()
        color = data.get('color', '#5865F2')
        icon = data.get('icon', 'folder')
        
        if not name: return jsonify({'success': False, 'error': 'Name is required'})
        
        folder_id = execute_query('INSERT INTO cloud_folders (user_id, name, color, icon, created_at) VALUES (%s, %s, %s, %s, %s)',
                                  (my_id, name, color, icon, time.time()), commit=True)
        return jsonify({'success': True, 'folder': {'id': folder_id, 'name': name, 'color': color, 'icon': icon}})

@app.route('/api/messages/<int:message_id>/organize', methods=['POST'])
def api_messages_organize(message_id):
    if 'user' not in session: return jsonify({'success': False}), 401
    my_id = int(session['user']['id'])
    
    # Verify ownership
    msg = execute_query('SELECT author_id, dm_id FROM dm_messages WHERE id = %s', (message_id,), fetch_one=True)
    if not msg: return jsonify({'success': False, 'error': 'Message not found'}), 404
    
    # Allow organizing if I sent it OR if it's in my cloud DM
    dm = execute_query('SELECT user_id_1, user_id_2 FROM direct_messages WHERE id = %s', (msg[1],), fetch_one=True)
    if not dm or (my_id not in [dm[0], dm[1]]):
        return jsonify({'success': False, 'error': 'Access denied'}), 403
        
    data = request.json
    folder_id = data.get('folder_id') # None or int
    tags = data.get('tags') # String (e.g. "work, ideas")
    
    execute_query('UPDATE dm_messages SET cloud_folder_id = %s, tags = %s WHERE id = %s',
                  (folder_id, tags, message_id), commit=True)
                  
    # Trigger socket update to refresh tags
    sockets_payload = {
        'message_id': message_id,
        'dm_id': msg[1],
        'cloud_folder_id': folder_id,
        'tags': tags
    }
    
    socket_room = str(dm[1]) if dm[0] == my_id else str(dm[0])
    socketio.emit('message_organized', sockets_payload, room=socket_room)
    # also emit to self explicitly if not self-DM, but for self-DMs room is just me
    if dm[0] == dm[1]:
        socketio.emit('message_organized', sockets_payload, room=str(my_id))
        
    return jsonify({'success': True})

# Initialize servers after all functions are defined
load_servers()
print(f"[+] Loaded {len(servers_db)} servers")

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8080))
    print(f'Server running on http://0.0.0.0:{port}')
    socketio.run(app, host='0.0.0.0', port=port, debug=False, allow_unsafe_werkzeug=True)

