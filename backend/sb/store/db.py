import os
import sqlite3
import threading

# Use config for DB path, default for now
DB_PATH = os.getenv("SB_DB_PATH", os.path.join(os.path.dirname(__file__), "..", "..", "sb.db"))
SCHEMA_PATH = os.path.join(os.path.dirname(__file__), "schema.sql")

_lock = threading.Lock()

def get_connection():
    # WAL mode for better concurrency
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn

def reset_db():
    with _lock:
        if os.path.exists(DB_PATH):
            # Careful closing all connections if we had a pool, but here we just drop and recreate
            pass
        
        with open(SCHEMA_PATH, 'r') as f:
            schema_script = f.read()
            
        # Write over or create new
        conn = get_connection()
        try:
            # Get all tables
            cursor = conn.cursor()
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
            tables = cursor.fetchall()
            for table in tables:
                if table[0] != 'sqlite_sequence':
                    conn.execute(f"DROP TABLE IF EXISTS {table[0]}")
            
            # Execute schema
            conn.executescript(schema_script)
            conn.commit()
        finally:
            conn.close()

# Initialize DB on load if it doesn't exist
if not os.path.exists(DB_PATH):
    with _lock:
        if not os.path.exists(DB_PATH):
            conn = get_connection()
            with open(SCHEMA_PATH, 'r') as f:
                conn.executescript(f.read())
            conn.commit()
            conn.close()
