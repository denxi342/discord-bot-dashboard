"""
Скрипт для проверки и исправления таблицы реакций в базе данных
"""
import os
import sys
import psycopg2
import sqlite3

def get_db_connection():
    db_url = os.environ.get('DATABASE_URL')
    if not db_url:
        # Local SQLite
        return sqlite3.connect('users.db')
    return psycopg2.connect(db_url)

def check_and_fix_reactions():
    try:
        conn = get_db_connection()
        is_sqlite = isinstance(conn, sqlite3.Connection)
        cursor = conn.cursor()
        
        print("🔍 Проверка базы данных...")
        
        if is_sqlite:
            # Проверить table_info
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='message_reactions'")
            exists = cursor.fetchone()
            
            if not exists:
                print("⚠️  Таблица message_reactions не найдена! Создаю...")
                cursor.execute('''CREATE TABLE message_reactions
                                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                                  message_id INTEGER NOT NULL,
                                  user_id INTEGER NOT NULL,
                                  emoji TEXT NOT NULL,
                                  created_at REAL,
                                  UNIQUE(message_id, user_id, emoji))''')
                conn.commit()
                print("✅ Таблица message_reactions создана!")
            else:
                print("✅ Таблица message_reactions существует")
                
            # Проверить колонки в dm_messages
            cursor.execute("PRAGMA table_info(dm_messages)")
            columns = {row[1] for row in cursor.fetchall()}
            
            print(f"\n📊 Колонки в dm_messages: {columns}")
            
            missing_columns = []
            if 'reply_to_id' not in columns:
                missing_columns.append('reply_to_id')
            if 'is_pinned' not in columns:
                missing_columns.append('is_pinned')
            if 'edited_at' not in columns:
                missing_columns.append('edited_at')
                
            if missing_columns:
                print(f"⚠️  Отсутствующие колонки: {missing_columns}")
                for col in missing_columns:
                    if col == 'reply_to_id':
                        cursor.execute("ALTER TABLE dm_messages ADD COLUMN reply_to_id INTEGER")
                    elif col == 'is_pinned':
                        cursor.execute("ALTER TABLE dm_messages ADD COLUMN is_pinned INTEGER DEFAULT 0")
                    elif col == 'edited_at':
                        cursor.execute("ALTER TABLE dm_messages ADD COLUMN edited_at REAL")
                    print(f"  ✓ Добавлена колонка {col}")
                conn.commit()
            else:
                print("✅ Все колонки в dm_messages на месте")
                
        else:
            # PostgreSQL
            cursor.execute("""
                SELECT table_name 
                FROM information_schema.tables 
                WHERE table_name='message_reactions'
            """)
            exists = cursor.fetchone()
            
            if not exists:
                print("⚠️  Таблица message_reactions не найдена! Создаю...")
                cursor.execute("""CREATE TABLE message_reactions
                                 (id SERIAL PRIMARY KEY,
                                  message_id INTEGER NOT NULL,
                                  user_id INTEGER NOT NULL,
                                  emoji VARCHAR(50) NOT NULL,
                                  created_at REAL,
                                  UNIQUE(message_id, user_id, emoji))""")
                conn.commit()
                print("✅ Таблица message_reactions создана!")
            else:
                print("✅ Таблица message_reactions существует")
                
            # Проверить колонки в dm_messages
            cursor.execute("""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name='dm_messages'
            """)
            columns = {row[0] for row in cursor.fetchall()}
            
            print(f"\n📊 Колонки в dm_messages: {columns}")
            
            missing_columns = []
            if 'reply_to_id' not in columns:
                missing_columns.append('reply_to_id')
            if 'is_pinned' not in columns:
                missing_columns.append('is_pinned')
            if 'edited_at' not in columns:
                missing_columns.append('edited_at')
                
            if missing_columns:
                print(f"⚠️  Отсутствующие колонки: {missing_columns}")
                for col in missing_columns:
                    if col == 'reply_to_id':
                        cursor.execute("ALTER TABLE dm_messages ADD COLUMN reply_to_id INTEGER")
                    elif col == 'is_pinned':
                        cursor.execute("ALTER TABLE dm_messages ADD COLUMN is_pinned INTEGER DEFAULT 0")
                    elif col == 'edited_at':
                        cursor.execute("ALTER TABLE dm_messages ADD COLUMN edited_at REAL")
                    print(f"  ✓ Добавлена колонка {col}")
                conn.commit()
            else:
                print("✅ Все колонки в dm_messages на месте")
        
        cursor.close()
        conn.close()
        print("\n✅ Проверка завершена успешно!")
        return True
        
    except Exception as e:
        print(f"\n❌ Ошибка: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == '__main__':
    success = check_and_fix_reactions()
    sys.exit(0 if success else 1)
