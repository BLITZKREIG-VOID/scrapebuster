import os
import sys

# Ensure we can import the backend package
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../")))

from sb.store.db import get_connection, reset_db


def test_reset_and_tables_exist():
    reset_db()
    
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = [row[0] for row in cursor.fetchall()]
        
        expected_tables = {
            "demo_state", "traffic_events", "sessions", "trap_hits",
            "canaries", "publications", "exposures", "datasets",
            "probe_runs", "probe_results", "cases", "evidence_objects"
        }
        
        for table in expected_tables:
            assert table in tables, f"Table {table} missing from DB"
    finally:
        conn.close()

def test_insert_and_query():
    reset_db()
    
    conn = get_connection()
    try:
        conn.execute(
            "INSERT INTO demo_state (key, value) VALUES (?, ?)",
            ("run_id", "RUN-TEST-123")
        )
        conn.commit()
        
        cursor = conn.cursor()
        cursor.execute("SELECT value FROM demo_state WHERE key=?", ("run_id",))
        row = cursor.fetchone()
        assert row is not None
        assert row["value"] == "RUN-TEST-123"
    finally:
        conn.close()

def test_reset_db_empties_tables():
    # Setup data
    conn = get_connection()
    try:
        conn.execute("INSERT INTO demo_state (key, value) VALUES (?, ?)", ("phase", "TESTING"))
        conn.commit()
    finally:
        conn.close()
        
    # Reset
    reset_db()
    
    # Verify empty
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) as count FROM demo_state")
        assert cursor.fetchone()["count"] == 0
    finally:
        conn.close()
