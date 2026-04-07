import sys
import os

# Add the directory to path so we can import web or utils if needed
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

try:
    from web import run_db_migration, execute_query, init_db
    print("[*] Starting manual migration check...")
    
    # Force init_db to ensure tables exist
    init_db()
    print("[+] init_db finished")
    
    # Run migration
    run_db_migration()
    print("[+] run_db_migration finished")
    
    # Check tables
    res = execute_query("SELECT name FROM sqlite_master WHERE type='table'", fetch_all=True)
    print(f"[+] Tables: {[r[0] for r in res]}")
    
    # Check verification_codes specifically
    res = execute_query("PRAGMA table_info(verification_codes)", fetch_all=True)
    if res:
        print(f"[+] verification_codes columns: {[r[1] for r in res]}")
    else:
        print("[!] verification_codes table is MISSING!")
        
    # Check users columns for is_verified
    res = execute_query("PRAGMA table_info(users)", fetch_all=True)
    cols = [r[1] for r in res]
    if 'is_verified' in cols:
        print("[+] 'is_verified' column found in 'users'")
    else:
        print("[!] 'is_verified' column is MISSING in 'users'!")
        
except Exception as e:
    print(f"[ERROR] {e}")
