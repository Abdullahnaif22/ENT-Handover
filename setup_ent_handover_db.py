#!/usr/bin/env python3
"""
Creates an SQLite database for an ENT handover project.

Tables:
- patients
- progress_notes
- jobs

Run: python setup_ent_handover_db.py
"""

import sqlite3
from datetime import datetime
from pathlib import Path

DB_PATH = Path("ent_handover.db")

SCHEMA_SQL = r"""
PRAGMA foreign_keys = ON;

-- =========================
-- Patients (one row per active admission/record)
-- =========================
CREATE TABLE IF NOT EXISTS patients (
    id                  INTEGER PRIMARY KEY,
    patient_name        TEXT    NOT NULL,
    hospital_number     TEXT    NOT NULL,
    nhs_number          TEXT,                      -- optional if you only use hospital number
    date_of_birth       TEXT    NOT NULL,          -- store as ISO date 'YYYY-MM-DD'
    reason_for_admission TEXT   NOT NULL,

    pmh                 TEXT,                      -- Past Medical History
    psh                 TEXT,                      -- Past Surgical History
    dh                  TEXT,                      -- Drug History / medications
    allergies           TEXT,                      -- optional but often needed

    created_at          TEXT    NOT NULL DEFAULT (datetime('now')),
    updated_at          TEXT    NOT NULL DEFAULT (datetime('now')),

    -- Keep hospital_number unique (change to UNIQUE if guaranteed unique in your trust)
    UNIQUE(hospital_number)
);

-- Speed up lookups by identifiers and name searches
CREATE INDEX IF NOT EXISTS idx_patients_hosp_no ON patients(hospital_number);
CREATE INDEX IF NOT EXISTS idx_patients_nhs_no  ON patients(nhs_number);
CREATE INDEX IF NOT EXISTS idx_patients_name    ON patients(patient_name);

-- Auto-update updated_at on row changes
CREATE TRIGGER IF NOT EXISTS trg_patients_updated_at
AFTER UPDATE ON patients
FOR EACH ROW
BEGIN
  UPDATE patients SET updated_at = datetime('now') WHERE id = NEW.id;
END;


-- =========================
-- Progress notes (many per patient)
-- =========================
CREATE TABLE IF NOT EXISTS progress_notes (
    id            INTEGER PRIMARY KEY,
    patient_id    INTEGER NOT NULL REFERENCES patients(id) ON DELETE CASCADE,
    note_time     TEXT    NOT NULL DEFAULT (datetime('now')), -- ISO datetime
    note          TEXT    NOT NULL,                           -- "Progress in the hospital"
    author        TEXT,                                       -- optional (e.g., SHO/Reg/Cons)
    created_at    TEXT    NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_progress_patient_time
ON progress_notes(patient_id, note_time DESC);


-- =========================
-- Jobs / Tasks (many per patient)
-- =========================
CREATE TABLE IF NOT EXISTS jobs (
    id            INTEGER PRIMARY KEY,
    patient_id    INTEGER NOT NULL REFERENCES patients(id) ON DELETE CASCADE,
    job_text      TEXT    NOT NULL,            -- "Jobs to be done"
    priority      TEXT    NOT NULL DEFAULT 'Routine',  -- 'Urgent', 'Soon', 'Routine'
    status        TEXT    NOT NULL DEFAULT 'Open',     -- 'Open', 'In Progress', 'Done'
    due_time      TEXT,                        -- optional ISO datetime
    assigned_to   TEXT,                        -- optional (e.g., "On-call SHO")
    created_at    TEXT    NOT NULL DEFAULT (datetime('now')),
    updated_at    TEXT    NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_jobs_patient_status
ON jobs(patient_id, status);

CREATE INDEX IF NOT EXISTS idx_jobs_due
ON jobs(due_time);

CREATE TRIGGER IF NOT EXISTS trg_jobs_updated_at
AFTER UPDATE ON jobs
FOR EACH ROW
BEGIN
  UPDATE jobs SET updated_at = datetime('now') WHERE id = NEW.id;
END;
"""

DEMO_DATA_SQL = r"""
-- Insert a demo patient (safe to rerun thanks to INSERT OR IGNORE + unique hospital_number)
INSERT OR IGNORE INTO patients (patient_name, hospital_number, nhs_number, date_of_birth, reason_for_admission, pmh, psh, dh, allergies)
VALUES (
    'Jane Doe',
    'H1234567',
    '999 123 4567',
    '1985-04-12',
    'Peritonsillar abscess',
    'Asthma',
    'Appendicectomy (2009)',
    'Salbutamol inhaler PRN',
    'NKDA'
);

-- Add a couple of progress notes
INSERT INTO progress_notes (patient_id, note, author)
SELECT id, 'Admitted via ED with trismus and odynophagia. IV Abx started. ENT review requested.', 'ED SHO'
FROM patients WHERE hospital_number = 'H1234567';

INSERT INTO progress_notes (patient_id, note, author)
SELECT id, 'ENT reviewed. Needle aspiration performed. Marked improvement. Continue IV Abx; switch to PO if stable in AM.', 'ENT Reg'
FROM patients WHERE hospital_number = 'H1234567';

-- Add a few jobs
INSERT INTO jobs (patient_id, job_text, priority, status, due_time, assigned_to)
SELECT id, 'Chase throat swab culture', 'Routine', 'Open', NULL, 'Ward SHO'
FROM patients WHERE hospital_number = 'H1234567';

INSERT INTO jobs (patient_id, job_text, priority, status, due_time, assigned_to)
SELECT id, 'Switch to oral antibiotics in AM ward round', 'Soon', 'Open', datetime('now','+12 hours'), 'Ward SHO'
FROM patients WHERE hospital_number = 'H1234567';

INSERT INTO jobs (patient_id, job_text, priority, status, due_time, assigned_to)
SELECT id, 'Safety-net discharge advice & outpatient follow-up', 'Routine', 'Open', NULL, 'Discharge Co-ordinator'
FROM patients WHERE hospital_number = 'H1234567';
"""

def create_db(db_path: Path = DB_PATH):
    print(f"Creating/Updating database at: {db_path.resolve()}")
    with sqlite3.connect(db_path) as conn:
        conn.executescript(SCHEMA_SQL)
        conn.commit()
    print("Schema ensured.")

def seed_demo_data(db_path: Path = DB_PATH):
    with sqlite3.connect(db_path) as conn:
        conn.executescript(DEMO_DATA_SQL)
        conn.commit()
    print("Inserted demo data.")

def main():
    create_db()
    # Comment out the next line if you don't want example rows
    seed_demo_data()

    print("\nDone ✅")
    print(f"- DB file: {DB_PATH.resolve()}")
    print("- Tables: patients, progress_notes, jobs")
    print("- You can connect with any SQLite client or via Python/Streamlit.")

if __name__ == "__main__":
    main()

