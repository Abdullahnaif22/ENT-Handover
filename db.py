import os
import sqlite3
from pathlib import Path
from contextlib import closing
import pandas as pd
import streamlit as st

DEFAULT_CODESPACES_PATH = "/workspaces/ENT-Handover/ent_handover.db"
this_dir = Path(__file__).resolve().parent
fallback_path = this_dir / "ent_handover.db"

DB_PATH = Path(
    os.environ.get("ENT_DB_PATH")
    or (DEFAULT_CODESPACES_PATH if Path(DEFAULT_CODESPACES_PATH).parent.exists() else fallback_path)
)
DB_PATH.parent.mkdir(parents=True, exist_ok=True)

@st.cache_resource(show_spinner=False)
def get_conn(db_path_str: str):
    conn = sqlite3.connect(db_path_str, check_same_thread=False)
    conn.execute("PRAGMA foreign_keys = ON;")
    conn.execute("PRAGMA journal_mode = WAL;")
    return conn

def conn():
    return get_conn(DB_PATH.as_posix())

def q(sql: str, params: tuple = ()):
    with closing(conn().cursor()) as cur:
        cur.execute(sql, params)
        return cur.fetchall()

def exec1(sql: str, params: tuple = ()):
    with closing(conn().cursor()) as cur:
        cur.execute(sql, params)
        conn().commit()
        return cur.lastrowid

def df(sql: str, params: tuple = ()):
    return pd.read_sql_query(sql, conn(), params=params)

def ensure_schema():
    schema = r"""
    PRAGMA foreign_keys = ON;
    CREATE TABLE IF NOT EXISTS patients (
        id INTEGER PRIMARY KEY,
        patient_name TEXT NOT NULL,
        hospital_number TEXT NOT NULL UNIQUE,
        nhs_number TEXT,
        date_of_birth TEXT NOT NULL,
        reason_for_admission TEXT NOT NULL,
        pmh TEXT, psh TEXT, dh TEXT, allergies TEXT,
        created_at TEXT NOT NULL DEFAULT (datetime('now')),
        updated_at TEXT NOT NULL DEFAULT (datetime('now'))
    );
    CREATE TABLE IF NOT EXISTS progress_notes (
        id INTEGER PRIMARY KEY,
        patient_id INTEGER NOT NULL REFERENCES patients(id) ON DELETE CASCADE,
        note_time TEXT NOT NULL DEFAULT (datetime('now')),
        note TEXT NOT NULL,
        author TEXT,
        created_at TEXT NOT NULL DEFAULT (datetime('now'))
    );
    CREATE TABLE IF NOT EXISTS jobs (
        id INTEGER PRIMARY KEY,
        patient_id INTEGER NOT NULL REFERENCES patients(id) ON DELETE CASCADE,
        job_text TEXT NOT NULL,
        priority TEXT NOT NULL DEFAULT 'Routine',
        status TEXT NOT NULL DEFAULT 'Open',
        due_time TEXT,
        assigned_to TEXT,
        created_at TEXT NOT NULL DEFAULT (datetime('now')),
        updated_at TEXT NOT NULL DEFAULT (datetime('now'))
    );
    CREATE INDEX IF NOT EXISTS idx_patients_name ON patients(patient_name);
    CREATE INDEX IF NOT EXISTS idx_progress_patient_time ON progress_notes(patient_id, note_time DESC);
    CREATE INDEX IF NOT EXISTS idx_jobs_patient_status ON jobs(patient_id, status);
    CREATE INDEX IF NOT EXISTS idx_jobs_due ON jobs(due_time);
    """
    conn().executescript(schema)
    conn().commit()
