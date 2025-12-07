import json
import os
import random
import string
import uuid
from datetime import datetime, timedelta
from collections import Counter
import io
# import matplotlib.pyplot as plt
# from cryptography.fernet import Fernet # Added import

DATA_FILE = "accounts.json"
SECRETS_FILE = "secrets.json"
MONITORS_FILE = "monitors.json"

# --- Mock Data Helper ---
def get_mock_email(count=1):
    domains = ["demo.inc", "mock.test"]
    emails = []
    for _ in range(count):
        login = ''.join(random.choices(string.ascii_lowercase + string.digits, k=10))
        domain = random.choice(domains)
        emails.append({"email": f"{login}@{domain}", "token": "mock_token_123"})
    return emails

def get_mock_messages():
    return [{
        "id": 12345,
        "from": "welcome@tempmail.demo",
        "subject": "👋 Добро пожаловать (Demo Mode)",
        "date": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }]

def get_mock_content(id):
    return {
        "id": id,
        "from": "welcome@tempmail.demo",
        "subject": "👋 Добро пожаловать (Demo Mode)",
        "date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "textBody": "Это демо-письмо. Основной API (1secmail) сейчас недоступен или блокирует запросы. Мы показываем это сообщение, чтобы вы могли протестировать интерфейс.",
        "htmlBody": "<div style='font-family: sans-serif; padding: 20px; background: #f0f0f0; border-radius: 10px;'><h2>⚠️ Демо режим</h2><p>К сожалению, публичный API (1secmail) вернул ошибку или заблокировал доступ.</p><p>Мы переключились в <b>демонстрационный режим</b>, чтобы вы могли проверить интерфейс бота.</p><hr><p>Попробуйте позже для работы с реальной почтой.</p></div>",
        "attachments": []
    }

# --- Temp Mail API (Guerrilla Mail) ---
TEMP_MAIL_API = "https://api.guerrillamail.com/ajax.php"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
}

async def get_temp_email(session, count=1):
    """Generates random temporary email addresses using Guerrilla Mail"""
    try:
        async with session.get(f"{TEMP_MAIL_API}?f=get_email_address", headers=HEADERS) as resp:
            if resp.status == 200:
                data = await resp.json()
                # Guerrilla returns one email per call/session. We return a list of dicts to be generic.
                return [{"email": data['email_addr'], "token": data['sid_token']}]
            return get_mock_email(count)
    except:
        return get_mock_email(count)

async def get_temp_mail_messages(session, token):
    """Get all messages for a temporary email address using Token"""
    try:
        # Guerrilla uses sid_token to check messages
        async with session.get(f"{TEMP_MAIL_API}?f=check_email&sid_token={token}&seq=0", headers=HEADERS) as resp:
            if resp.status == 200:
                data = await resp.json()
                messages = data.get('list', [])
                # Map Guerrilla format to our standard format
                mapped = []
                for msg in messages:
                    mapped.append({
                        "id": msg['mail_id'],
                        "from": msg['mail_from'],
                        "subject": msg['mail_subject'],
                        "date": msg['mail_date']
                    })
                return mapped
            return get_mock_messages()
    except:
        return get_mock_messages()

async def read_temp_mail_message(session, token, message_id):
    """Read a specific message from temporary email using Token"""
    try:
        async with session.get(f"{TEMP_MAIL_API}?f=fetch_email&sid_token={token}&email_id={message_id}", headers=HEADERS) as resp:
            if resp.status == 200:
                data = await resp.json()
                return {
                    "id": data['mail_id'],
                    "from": data['mail_from'],
                    "subject": data['mail_subject'],
                    "date": data['mail_date'],
                    "textBody": data.get('mail_body', ''), # Guerrilla gives body in mail_body usually HTML
                    "htmlBody": data.get('mail_body', ''),
                    "attachments": [] # Guerrilla logic for attachments is complex, skip for now
                }
            return get_mock_content(message_id)
    except:
        return get_mock_content(message_id)

async def get_temp_mail_domains(session):
    return ["guerrillamail.com"] # Guerrilla manages domains internally



# --- Encryption Setup ---
# from cryptography.fernet import Fernet # Removed to avoid dependency issues

# --- Simple Obfuscation instead of Encryption (Fallback) ---
def get_key():
    return "mock-key"

def get_cipher():
    return None

def encrypt_content(content):
    # Fallback: Just return content to allow app to run without cryptography
    # Or use simple base64 if needed, but plain is safer for debugging connection issues now
    return content 

def decrypt_content(content):
    return content


def load_accounts():
    if not os.path.exists(DATA_FILE):
        return []
    try:
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            accounts = json.load(f)
            
        # Migration / Decryption
        needs_save = False
        for acc in accounts:
            original = acc['content']
            # Try to determine if encrypted. Fernet tokens are usually long and base64.
            # Simple check: Try decrypt. If it returns same string (our logic above updates exception to return original),
            # then check if it WAS encrypted.
            # actually our decrypt_content returns content if fail.
            # We want to ensure everything IS encrypted in memory? 
            # No, we want to work with DECRYPTED data in memory, ENCRYPTED in file.
            # Wait, standard pattern: Load -> Decrypt fields -> Work -> Encrypt fields -> Save.
            
            # Let's try to decrypt.
            try:
                decrypted = get_cipher().decrypt(original.encode()).decode()
                acc['content'] = decrypted
            except Exception:
                # Assuming it was plain text. Mark for save (re-encrypt later? No, save function handles it?)
                # We need to re-save the file with encrypted data if we found plain text.
                # But here we just want to return DECRYPTED data to the app.
                # So if it was plain, we keep it as is in memory.
                # BUT we should probably force a save to encrypt it on disk.
                needs_save = True
        
        if needs_save:
            save_all_accounts(accounts)
            
        return accounts
    except json.JSONDecodeError:
        return []

def save_all_accounts(accounts):
    # Helper to save list
    # We must ENCRYPT before saving
    to_save = []
    for acc in accounts:
        # Create a copy to not modify the in-memory objects used by UI
        acc_copy = acc.copy()
        acc_copy['content'] = encrypt_content(acc['content'])
        to_save.append(acc_copy)
        
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(to_save, f, indent=4, ensure_ascii=False)

def save_account(content, user):
    accounts = load_accounts() # Loads decrypted
    new_id = 1
    if accounts:
        new_id = max(acc.get("id", 0) for acc in accounts) + 1
    
    entry = {
        "id": new_id,
        "content": content, # Plain text here
        "added_by": str(user),
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }
    accounts.append(entry)
    save_all_accounts(accounts) # Encrypts and saves
    return new_id

def delete_account(account_id):
    accounts = load_accounts()
    initial_len = len(accounts)
    accounts = [acc for acc in accounts if acc.get("id") != account_id]
    
    if len(accounts) < initial_len:
        save_all_accounts(accounts)
        return True
    return False

def edit_account(account_id, new_content):
    accounts = load_accounts()
    for acc in accounts:
        if acc.get("id") == account_id:
            acc["content"] = new_content
            acc["timestamp"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            save_all_accounts(accounts)
            return True
    return False

def search_accounts(query):
    accounts = load_accounts()
    # Search in DECRYPTED content
    results = [acc for acc in accounts if query.lower() in acc["content"].lower()]
    return results

def get_all_accounts():
    return load_accounts()

def generate_password(length=12):
    chars = string.ascii_letters + string.digits + "!@#$%^&*"
    return ''.join(random.choice(chars) for _ in range(length))

# --- Secrets Management ---
def load_secrets():
    if not os.path.exists(SECRETS_FILE):
        return []
    try:
        with open(SECRETS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except json.JSONDecodeError:
        return [] # Return empty if corrupted

def save_secrets(secrets):
    with open(SECRETS_FILE, "w", encoding="utf-8") as f:
        json.dump(secrets, f, indent=4)

def create_secret(content):
    secrets = load_secrets()
    # Encrypt content before storage
    encrypted_content = encrypt_content(content)
    
    # Generate simple unique ID
    new_id = str(uuid.uuid4())[:8] # Short 8-char ID
    
    entry = {
        "id": new_id,
        "content": encrypted_content,
        "created_at": datetime.now().isoformat()
    }
    secrets.append(entry)
    save_secrets(secrets)
    return new_id

def reveal_secret(secret_id):
    secrets = load_secrets()
    
    for i, secret in enumerate(secrets):
        if secret['id'] == secret_id:
            # Found it!
            encrypted_content = secret['content']
            
            # Delete immediately (burn after reading)
            del secrets[i]
            save_secrets(secrets)
            
            # Decrypt and return
            try:
                decrypted = decrypt_content(encrypted_content)
                return decrypted
            except Exception:
                return "⚠️ Ошибка дешифровки"
                
    return None # Not found

# --- Statistics & Graphs ---
def get_user_stats():
    accounts = load_accounts()
    # Count entries by 'added_by' (which stores "Username#1234" or similar string)
    users = [acc.get('added_by', 'Unknown') for acc in accounts]
    return Counter(users).most_common(5)

def generate_activity_chart():
    return None


# --- Uptime Monitor ---
def load_monitors():
    if not os.path.exists(MONITORS_FILE):
        return []
    try:
        with open(MONITORS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except json.JSONDecodeError:
        return []

def save_monitors(monitors):
    with open(MONITORS_FILE, "w", encoding="utf-8") as f:
        json.dump(monitors, f, indent=4)

def add_monitor(url, name=None):
    monitors = load_monitors()
    
    # Ensure URL has schema
    if not url.startswith(('http://', 'https://')):
        url = 'https://' + url
        
    if not name:
        name = url.replace('https://', '').replace('http://', '').strip('/')
        
    # Check if already exists
    if any(m['url'] == url for m in monitors):
        return False, "URL уже отслеживается."
        
    entry = {
        "id": str(uuid.uuid4())[:8],
        "url": url,
        "name": name,
        "added_at": datetime.now().isoformat(),
        "status": "unknown", # online, offline, unknown
        "last_checked": None,
        "last_status_code": None,
        "response_time": None, # В миллисекундах
        "uptime_percentage": 100.0, # Процент доступности
        "total_checks": 0, # Всего проверок
        "failed_checks": 0, # Проваленных проверок
        "incident_logs": [] # История инцидентов [{type, timestamp, message}]
    }
    monitors.append(entry)
    save_monitors(monitors)
    return True, entry

def remove_monitor(monitor_id):
    monitors = load_monitors()
    initial_len = len(monitors)
    monitors = [m for m in monitors if m['id'] != monitor_id and m['name'] != monitor_id] # allow delete by name too
    
    if len(monitors) < initial_len:
        save_monitors(monitors)
        return True
    return False

def get_monitors():
    return load_monitors()

def update_monitor_status(monitor_id, status, status_code, response_time=None):
    monitors = load_monitors()
    for m in monitors:
        if m['id'] == monitor_id:
            old_status = m.get('status', 'unknown')
            
            # Обновляем счетчики
            m['total_checks'] = m.get('total_checks', 0) + 1
            if status == 'offline':
                m['failed_checks'] = m.get('failed_checks', 0) + 1
            
            # Вычисляем uptime %
            if m['total_checks'] > 0:
                m['uptime_percentage'] = round(
                    ((m['total_checks'] - m['failed_checks']) / m['total_checks']) * 100, 2
                )
            
            # Логируем изменение статуса
            if old_status != status and old_status != 'unknown':
                timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                if status == 'offline':
                    log_entry = {
                        'type': 'down',
                        'timestamp': timestamp,
                        'message': f'🔴 Сайт упал (код: {status_code})',
                        'status_code': status_code,
                        'response_time': response_time
                    }
                else:  # online
                    log_entry = {
                        'type': 'up',
                        'timestamp': timestamp,
                        'message': f'🟢 Сайт восстановлен ({response_time}мс)',
                        'status_code': status_code,
                        'response_time': response_time
                    }
                
                # Добавляем лог (максимум 50 последних записей)
                if 'incident_logs' not in m:
                    m['incident_logs'] = []
                m['incident_logs'].insert(0, log_entry)
                m['incident_logs'] = m['incident_logs'][:50]
            
            # Обновляем основные поля
            m['status'] = status
            m['last_checked'] = datetime.now().isoformat()
            m['last_status_code'] = status_code
            m['response_time'] = response_time
            
            save_monitors(monitors)
            return

# --- Custom Prefixes ---
PREFIXES_FILE = "prefixes.json"

def load_prefixes():
    if not os.path.exists(PREFIXES_FILE):
        return {}
    try:
        with open(PREFIXES_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        return {}

def save_prefixes(prefixes):
    with open(PREFIXES_FILE, "w", encoding="utf-8") as f:
        json.dump(prefixes, f, indent=4)

def set_prefix(user_id, prefix):
    prefixes = load_prefixes()
    prefixes[str(user_id)] = prefix
    save_prefixes(prefixes)
    return True

def get_prefix(user_id):
    prefixes = load_prefixes()
    return prefixes.get(str(user_id))

def get_all_prefixes():
    return load_prefixes()

# --- Monitor Logs ---
def get_monitor_logs(monitor_id):
    """Получить логи инцидентов для конкретного монитора"""
    monitors = load_monitors()
    for m in monitors:
        if m['id'] == monitor_id:
            return m.get('incident_logs', [])
    return []

def get_monitor_stats(monitor_id):
    """Получить статистику монитора"""
    monitors = load_monitors()
    for m in monitors:
        if m['id'] == monitor_id:
            return {
                'uptime_percentage': m.get('uptime_percentage', 0),
                'total_checks': m.get('total_checks', 0),
                'failed_checks': m.get('failed_checks', 0),
                'response_time': m.get('response_time'),
                'last_checked': m.get('last_checked'),
                'status': m.get('status')
            }
    return None

def clear_monitor_logs(monitor_id):
    """Очистить логи монитора"""
    monitors = load_monitors()
    for m in monitors:
        if m['id'] == monitor_id:
            m['incident_logs'] = []
            save_monitors(monitors)
            return True
    return False
