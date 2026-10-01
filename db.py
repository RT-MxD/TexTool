"""
Textile Costing Calculator - PostgreSQL Database for Anonymous Threading
====================================================================
Stores calculation sessions (threads) so users can browse and reload
previous calculations without requiring login.

Tables:
  threads         - Each calculation session
  thread_materials - Material inputs per thread
  thread_results   - Aggregated results per thread
"""

import os
import json
import uuid
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional

import psycopg
from psycopg.rows import dict_row
from dotenv import load_dotenv

# Load environment variables from .env
load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")

def get_connection():
    """Get a Postgres connection with dict_row for dict-like access."""
    if not DATABASE_URL:
        raise ValueError("DATABASE_URL environment variable is not set")
    conn = psycopg.connect(DATABASE_URL, row_factory=dict_row)
    return conn


def init_db():
    """Create tables if they don't exist."""
    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS threads (
                    id TEXT PRIMARY KEY,
                    title TEXT DEFAULT '',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    global_params TEXT NOT NULL,
                    cost REAL DEFAULT 0.0,
                    total_job REAL DEFAULT 0.0,
                    total_job_alt REAL DEFAULT 0.0,
                    total_amt_yarn REAL DEFAULT 0.0,
                    n6 REAL DEFAULT 0.0,
                    total_yarn_job REAL DEFAULT 0.0,
                    total_pick REAL DEFAULT 0.0,
                    sum_amt REAL DEFAULT 0.0,
                    j21 REAL DEFAULT 0.0,
                    j22 REAL DEFAULT 0.0,
                    j23 REAL DEFAULT 0.0,
                    execution_time_ms REAL DEFAULT 0.0
                );

                CREATE TABLE IF NOT EXISTS thread_materials (
                    id SERIAL PRIMARY KEY,
                    thread_id TEXT NOT NULL,
                    material_index INTEGER NOT NULL,
                    material_name TEXT NOT NULL,
                    denier REAL DEFAULT 0.0,
                    peak REAL DEFAULT 0.0,
                    panno REAL DEFAULT 0.0,
                    rate REAL DEFAULT 0.0,
                    has_e_multiplier INTEGER DEFAULT 1,
                    ans REAL DEFAULT 0.0,
                    amt REAL DEFAULT 0.0,
                    yarn_weight REAL DEFAULT 0.0,
                    yarn_price REAL DEFAULT 0.0,
                    FOREIGN KEY (thread_id) REFERENCES threads(id) ON DELETE CASCADE
                );

                CREATE INDEX IF NOT EXISTS idx_thread_materials_thread_id
                    ON thread_materials(thread_id);

                CREATE INDEX IF NOT EXISTS idx_threads_updated
                    ON threads(updated_at DESC);
            """)
        conn.commit()
    finally:
        conn.close()


# ──────────────────────── CRUD Operations ────────────────────────


def save_thread(
    materials_input: List[Dict[str, Any]],
    global_params: Dict[str, Any],
    results: Dict[str, Any],
    title: str = "",
    thread_id: Optional[str] = None,
) -> str:
    """
    Save a calculation as a thread. Returns the thread ID.
    If thread_id is provided, updates that thread; otherwise creates a new one.
    """
    conn = get_connection()
    try:
        now = datetime.utcnow().isoformat()

        if thread_id is None:
            thread_id = str(uuid.uuid4())[:8]  # Short anonymous ID

        # Auto-generate title from first material names if not provided
        if not title:
            mat_names = [m.get("material_name", "?") for m in materials_input[:3]]
            title = f"{' / '.join(mat_names)} — ₹{results.get('cost', 0):.2f}"

        with conn.cursor() as cursor:
            # Upsert the thread
            cursor.execute("""
                INSERT INTO threads (
                    id, title, created_at, updated_at, global_params,
                    cost, total_job, total_job_alt, total_amt_yarn, n6,
                    total_yarn_job, total_pick, sum_amt, j21, j22, j23,
                    execution_time_ms
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (id) DO UPDATE SET
                    title=EXCLUDED.title,
                    updated_at=EXCLUDED.updated_at,
                    global_params=EXCLUDED.global_params,
                    cost=EXCLUDED.cost,
                    total_job=EXCLUDED.total_job,
                    total_job_alt=EXCLUDED.total_job_alt,
                    total_amt_yarn=EXCLUDED.total_amt_yarn,
                    n6=EXCLUDED.n6,
                    total_yarn_job=EXCLUDED.total_yarn_job,
                    total_pick=EXCLUDED.total_pick,
                    sum_amt=EXCLUDED.sum_amt,
                    j21=EXCLUDED.j21,
                    j22=EXCLUDED.j22,
                    j23=EXCLUDED.j23,
                    execution_time_ms=EXCLUDED.execution_time_ms
            """, (
                thread_id, title, now, now,
                json.dumps(global_params),
                results.get("cost", 0),
                results.get("total_job", 0),
                results.get("total_job_alt", 0),
                results.get("total_amt_yarn", 0),
                results.get("n6", 0),
                results.get("total_yarn_job", 0),
                results.get("total_pick", 0),
                results.get("sum_amt", 0),
                results.get("j21", 0),
                results.get("j22", 0),
                results.get("j23", 0),
                results.get("execution_time_ms", 0),
            ))

            # Replace materials for this thread
            cursor.execute("DELETE FROM thread_materials WHERE thread_id = %s", (thread_id,))

            result_materials = results.get("materials", [])
            for idx, mat_in in enumerate(materials_input):
                # Merge input with computed results
                mat_result = result_materials[idx] if idx < len(result_materials) else {}
                cursor.execute("""
                    INSERT INTO thread_materials (
                        thread_id, material_index, material_name,
                        denier, peak, panno, rate, has_e_multiplier,
                        ans, amt, yarn_weight, yarn_price
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """, (
                    thread_id, idx,
                    mat_in.get("material_name", f"Material-{idx+1}"),
                    mat_in.get("denier", 0),
                    mat_in.get("peak", 0),
                    mat_in.get("panno", 0),
                    mat_in.get("rate", 0),
                    1 if mat_in.get("has_e_multiplier", True) else 0,
                    mat_result.get("ans", 0),
                    mat_result.get("amt", 0),
                    mat_result.get("yarn_weight", 0),
                    mat_result.get("yarn_price", 0),
                ))

        conn.commit()
        return thread_id
    finally:
        conn.close()


def list_threads(limit: int = 50) -> List[Dict[str, Any]]:
    """List recent threads, newest first."""
    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                "SELECT * FROM threads ORDER BY updated_at DESC LIMIT %s",
                (limit,)
            )
            rows = cursor.fetchall()
            return rows  # dict_row makes this return dicts already
    finally:
        conn.close()


def get_thread(thread_id: str) -> Optional[Dict[str, Any]]:
    """Get a single thread with its materials."""
    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                "SELECT * FROM threads WHERE id = %s", (thread_id,)
            )
            row = cursor.fetchone()
            if not row:
                return None

            thread = row  # already a dict
            thread["global_params"] = json.loads(thread["global_params"])

            cursor.execute(
                "SELECT * FROM thread_materials WHERE thread_id = %s ORDER BY material_index",
                (thread_id,)
            )
            materials = cursor.fetchall()
            thread["materials"] = materials

            return thread
    finally:
        conn.close()


def delete_thread(thread_id: str) -> bool:
    """Delete a thread and its materials. Returns True if found."""
    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute("DELETE FROM threads WHERE id = %s", (thread_id,))
            deleted = cursor.rowcount > 0
        conn.commit()
        return deleted
    finally:
        conn.close()


def delete_all_threads() -> int:
    """Delete all threads. Returns number deleted."""
    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute("DELETE FROM threads")
            count = cursor.rowcount
        conn.commit()
        return count
    finally:
        conn.close()


# Initialize the database on import
init_db()
