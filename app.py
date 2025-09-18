#!/usr/bin/env python3
# app.py — ENT Handover Streamlit App
import sqlite3
from contextlib import closing
from datetime import datetime, date, time
from pathlib import Path
from typing import Optional, List, Tuple

import pandas as pd
import streamlit as st

# ------------------------------------------------------------
# App settings
# ------------------------------------------------------------
st.set_page_config(
    page_title="ENT Handover",
    page_icon="🩺",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Subtle mobile-friendly polish
st.markdown(
    """
    <style>
      .small { font-size: 0.9rem; opacity: 0.9; }
      .tight .st-emotion-cache-13k62yr { gap: 0.25rem !important; }
      @media (max-width: 768px) {
        .element-container { padding-left: 0.25rem; padding-right: 0.25rem; }
      }
      .pill {
        display:inline-block; padding:0.15rem 0.55rem; border-radius:999px;
        font-size:0.8rem; border:1px solid var(--secondary-border);
      }
    </style>
    """,
    unsafe_allow_html=True,
)

DB_PATH = Path("ent_handover.db")

# ------------------------------------------------------------
# DB helpers
# ------------------------------------------------------------
@st.cache_resource(show_spinner=False)
def get_conn():
    # check_same_thread=False so Streamlit threads can share the connection
    conn = sqlite3.connect(DB_PATH.as_posix(), check_same_thread=False)
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn

def q(query: str, params: Tuple = ()) -> List[tuple]:
    with closing(get_conn().cursor()) as cur:
        cur.execute(query, params)
        rows = cur.fetchall()
    return rows

def execmany(query: str, seq_of_params: List[Tuple]):
    with closing(get_conn().cursor()) as cur:
        cur.executemany(query, seq_of_params)
        get_conn().commit()

def exec1(query: str, params: Tuple = ()) -> int:
    with closing(get_conn().cursor()) as cur:
        cur.execute(query, params)
        get_conn().commit()
        return cur.lastrowid

def df(query: str, params: Tuple = ()) -> pd.DataFrame:
    return pd.read_sql_query(query, get_conn(), params=params)

def ensure_schema():
    # If you used the setup script I gave earlier, this is a no-op.
    # Safe to run: will (re)create missing tables/indexes only.
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
    get_conn().executescript(schema)
    get_conn().commit()

ensure_schema()

# ------------------------------------------------------------
# UI helpers
# ------------------------------------------------------------
def dob_to_age(dob_str: str) -> Optional[int]:
    try:
        d = datetime.strptime(dob_str, "%Y-%m-%d").date()
        today = date.today()
        return today.year - d.year - ((today.month, today.day) < (d.month, d.day))
    except Exception:
        return None

def priority_pill(p: str) -> str:
    colour = {
        "Urgent": "#e11d48",
        "Soon": "#f59e0b",
        "Routine": "#10b981",
    }.get(p, "#64748b")
    return f"<span class='pill' style='border-color:{colour}; color:{colour}'>{p}</span>"

def status_pill(s: str) -> str:
    colour = {
        "Open": "#3b82f6",
        "In Progress": "#a855f7",
        "Done": "#10b981",
    }.get(s, "#64748b")
    return f"<span class='pill' style='border-color:{colour}; color:{colour}'>{s}</span>"

# ------------------------------------------------------------
# Sidebar
# ------------------------------------------------------------
st.sidebar.title("🏥 ENT Handover")
page = st.sidebar.radio(
    "Navigate",
    ["Patients", "Patient Details", "Jobs Board", "Add Patient"],
    index=0,
)

# persistent state for selected patient
if "selected_patient_id" not in st.session_state:
    st.session_state.selected_patient_id = None

# Quick search
with st.sidebar:
    st.markdown("### 🔎 Quick search")
    search_term = st.text_input("Name / Hosp No / Reason", placeholder="e.g. Jane or H123...")
    if st.button("Search"):
        page = "Patients"

# ------------------------------------------------------------
# Page: Patients
# ------------------------------------------------------------
def render_patients():
    st.subheader("👥 Patients")
    filters = st.columns([2, 1, 1, 1])
    with filters[0]:
        term = st.text_input("Search", value=search_term or "", placeholder="Name, Hosp No, Reason...")
    with filters[1]:
        only_open_jobs = st.checkbox("Only with Open jobs", value=False)
    with filters[2]:
        sort_by = st.selectbox("Sort by", ["created_at DESC", "patient_name ASC", "hospital_number ASC"], index=0)
    with filters[3]:
        limit = st.selectbox("Show", [20, 50, 100, 500], index=0)

    sql = """
    SELECT
      p.id, p.patient_name, p.hospital_number, COALESCE(p.nhs_number,'') nhs_number,
      p.date_of_birth, p.reason_for_admission, p.created_at,
      (SELECT COUNT(*) FROM jobs j WHERE j.patient_id = p.id AND j.status != 'Done') AS open_jobs
    FROM patients p
    WHERE 1=1
      AND (p.patient_name LIKE ? OR p.hospital_number LIKE ? OR p.reason_for_admission LIKE ?)
    """
    params = (f"%{term}%", f"%{term}%", f"%{term}%")
    if only_open_jobs:
        sql += " AND (SELECT COUNT(*) FROM jobs j WHERE j.patient_id = p.id AND j.status != 'Done') > 0 "
    sql += f" ORDER BY {sort_by} LIMIT ?"
    params += (limit,)
    data = df(sql, params)

    # derived columns
    if not data.empty:
        data["Age"] = data["date_of_birth"].apply(lambda s: dob_to_age(s))
        data.rename(
            columns={
                "patient_name": "Patient",
                "hospital_number": "Hosp No",
                "nhs_number": "NHS No",
                "reason_for_admission": "Reason",
                "created_at": "Created",
                "open_jobs": "Open Jobs",
            },
            inplace=True,
        )
        data = data[["id", "Patient", "Hosp No", "NHS No", "Age", "Reason", "Open Jobs", "Created"]]

    st.dataframe(
        data,
        use_container_width=True,
        hide_index=True,
    )

    selected = st.text_input("Go to patient by ID", value=st.session_state.get("selected_patient_id") or "")
    go_cols = st.columns([1,1,6])
    with go_cols[0]:
        if st.button("Open"):
            try:
                st.session_state.selected_patient_id = int(selected)
                st.success("Opened patient details.")
            except Exception:
                st.warning("Enter a numeric patient ID shown in the table.")
    with go_cols[1]:
        if st.button("Refresh"):
            st.rerun()

# ------------------------------------------------------------
# Page: Add Patient
# ------------------------------------------------------------
def render_add_patient():
    st.subheader("➕ Add Patient")
    with st.form("add_patient"):
        cols = st.columns(2)
        with cols[0]:
            name = st.text_input("Patient name*", "")
            hosp = st.text_input("Hospital number*", "")
            nhs = st.text_input("NHS number (optional)", "")
            dob = st.date_input("Date of birth*", value=date(1980,1,1))
        with cols[1]:
            reason = st.text_input("Reason for admission*", "")
            pmh = st.text_area("Past Medical History")
            psh = st.text_area("Past Surgical History")
            dh = st.text_area("Drug History / meds")
            allergies = st.text_input("Allergies", "NKDA")

        submitted = st.form_submit_button("Save")
        if submitted:
            if not (name and hosp and reason and dob):
                st.error("Name, Hospital number, Reason, and Date of birth are required.")
            else:
                try:
                    exec1(
                        """
                        INSERT INTO patients
                        (patient_name, hospital_number, nhs_number, date_of_birth, reason_for_admission, pmh, psh, dh, allergies)
                        VALUES (?,?,?,?,?,?,?,?,?)
                        """,
                        (
                            name.strip(), hosp.strip(), nhs.strip(),
                            dob.strftime("%Y-%m-%d"), reason.strip(),
                            pmh.strip(), psh.strip(), dh.strip(), allergies.strip()
                        ),
                    )
                    st.success(f"Added {name}.")
                except sqlite3.IntegrityError as e:
                    st.error(f"Could not add patient: {e}")

# ------------------------------------------------------------
# Page: Patient Details
# ------------------------------------------------------------
def get_patient(pid: int) -> Optional[tuple]:
    rows = q(
        """
        SELECT id, patient_name, hospital_number, nhs_number, date_of_birth,
               reason_for_admission, pmh, psh, dh, allergies, created_at, updated_at
        FROM patients WHERE id=?
        """,
        (pid,),
    )
    return rows[0] if rows else None

def render_patient_details():
    st.subheader("🧾 Patient Details")
    pid = st.session_state.get("selected_patient_id")

    # Pick patient
    pick_cols = st.columns([2, 3])
    with pick_cols[0]:
        pid = st.number_input("Patient ID", min_value=1, step=1, value=int(pid) if pid else 1)
    with pick_cols[1]:
        if st.button("Load"):
            st.session_state.selected_patient_id = int(pid)

    patient = get_patient(pid)
    if not patient:
        st.info("Select a valid Patient ID from the Patients page.")
        return

    (
        pid, name, hosp, nhs, dob, reason,
        pmh, psh, dh, allergies, created_at, updated_at
    ) = patient

    # Header card
    age = dob_to_age(dob)
    st.markdown(f"### {name}  •  {hosp}  •  Age {age if age is not None else '?'}")
    top_cols = st.columns(4)
    top_cols[0].metric("Reason for admission", reason)
    top_cols[1].metric("NHS No", nhs or "—")
    top_cols[2].metric("Allergies", allergies or "—")
    top_cols[3].metric("DOB", dob)

    with st.expander("History (PMH / PSH / Drug History)", expanded=False):
        c1, c2, c3 = st.columns(3)
        with c1: st.markdown("**PMH**"); st.write(pmh or "—")
        with c2: st.markdown("**PSH**"); st.write(psh or "—")
        with c3: st.markdown("**Drug History**"); st.write(dh or "—")

    st.divider()

    # Progress notes
    st.markdown("#### 📝 Progress in hospital")
    notes_df = df(
        "SELECT id, note_time, author, note FROM progress_notes WHERE patient_id=? ORDER BY note_time DESC",
        (pid,),
    )
    st.dataframe(notes_df, use_container_width=True, hide_index=True)

    with st.form("add_note"):
        c = st.columns([4,1])
        with c[0]:
            note = st.text_area("Add progress note", placeholder="e.g., ENT reviewed, needle aspiration performed...")
        with c[1]:
            author = st.text_input("Author", value="")
        submitted = st.form_submit_button("Add note")
        if submitted and note.strip():
            exec1(
                "INSERT INTO progress_notes (patient_id, note, author) VALUES (?,?,?)",
                (pid, note.strip(), author.strip()),
            )
            st.success("Note added.")
            st.rerun()

    st.divider()

    # Jobs
    st.markdown("#### ✅ Jobs to be done")
    jobs = df(
        """
        SELECT id, job_text, priority, status, COALESCE(due_time,'') AS due_time, COALESCE(assigned_to,'') AS assigned_to
        FROM jobs WHERE patient_id=? ORDER BY
        CASE priority WHEN 'Urgent' THEN 0 WHEN 'Soon' THEN 1 ELSE 2 END,
        created_at ASC
        """,
        (pid,),
    )

    if jobs.empty:
        st.info("No jobs yet.")

    for _, row in jobs.iterrows():
        jb_cols = st.columns([5, 1.2, 1.2, 1.8, 1.8, 1])
        with jb_cols[0]:
            st.markdown(f"**{row.job_text}**")
            st.markdown(
                priority_pill(row.priority) + " " + status_pill(row.status),
                unsafe_allow_html=True,
            )
        with jb_cols[1]:
            new_status = st.selectbox(
                "Status",
                ["Open", "In Progress", "Done"],
                index=["Open", "In Progress", "Done"].index(row.status),
                key=f"status_{row.id}",
            )
        with jb_cols[2]:
            new_prio = st.selectbox(
                "Priority",
                ["Urgent", "Soon", "Routine"],
                index=["Urgent", "Soon", "Routine"].index(row.priority),
                key=f"prio_{row.id}",
            )
        with jb_cols[3]:
            assigned = st.text_input("Assigned to", value=row.assigned_to, key=f"ass_{row.id}")
        with jb_cols[4]:
            due = st.text_input("Due (YYYY-MM-DD HH:MM)", value=row.due_time, key=f"due_{row.id}")
        with jb_cols[5]:
            if st.button("💾", key=f"save_{row.id}"):
                exec1(
                    "UPDATE jobs SET status=?, priority=?, assigned_to=?, due_time=?, updated_at=datetime('now') WHERE id=?",
                    (new_status, new_prio, assigned.strip(), due.strip() or None, int(row.id)),
                )
                st.toast("Job updated")

    with st.form("add_job"):
        st.markdown("**Add a new job**")
        c1, c2, c3, c4 = st.columns([4,1.2,1.8,2])
        with c1: text = st.text_input("Job description*", "")
        with c2: prio = st.selectbox("Priority", ["Urgent", "Soon", "Routine"], index=2)
        with c3: assign_to = st.text_input("Assigned to", "")
        with c4:
            due_date = st.date_input("Due date", value=None)
            due_time = st.time_input("Due time", value=time(12,0))
        submitted = st.form_submit_button("Add job")
        if submitted and text.strip():
            due_iso = None
            if due_date:
                due_iso = datetime.combine(due_date, due_time).strftime("%Y-%m-%d %H:%M")
            exec1(
                "INSERT INTO jobs (patient_id, job_text, priority, assigned_to, due_time) VALUES (?,?,?,?,?)",
                (pid, text.strip(), prio, assign_to.strip(), due_iso),
            )
            st.success("Job added.")
            st.rerun()

# ------------------------------------------------------------
# Page: Jobs Board
# ------------------------------------------------------------
def render_jobs_board():
    st.subheader("🗂️ Jobs Board")
    cols = st.columns(3)
    statuses = ["Open", "In Progress", "Done"]
    for i, status in enumerate(statuses):
        with cols[i]:
            st.markdown(f"**{status}**")
            jobs = df(
                """
                SELECT j.id, j.job_text, j.priority, j.assigned_to, j.due_time,
                       p.patient_name, p.hospital_number, j.patient_id
                FROM jobs j
                JOIN patients p ON p.id = j.patient_id
                WHERE j.status=?
                ORDER BY
                  CASE j.priority WHEN 'Urgent' THEN 0 WHEN 'Soon' THEN 1 ELSE 2 END,
                  j.due_time IS NULL, j.due_time ASC
                """,
                (status,),
            )
            if jobs.empty:
                st.caption("— none —")
            for _, row in jobs.iterrows():
                with st.container(border=True):
                    st.markdown(f"**{row.job_text}**")
                    st.caption(f"{row.patient_name} • {row.hospital_number}")
                    st.markdown(
                        priority_pill(row.priority) + " " + status_pill(status),
                        unsafe_allow_html=True,
                    )
                    st.caption(
                        (f"Assigned: {row.assigned_to}  •  " if row.assigned_to else "")
                        + (f"Due: {row.due_time}" if row.due_time else "")
                    )
                    c = st.columns([1,1,1,2])
                    with c[0]:
                        if st.button("Open ▶︎", key=f"open_{row.id}"):
                            st.session_state.selected_patient_id = int(row.patient_id)
                            st.switch_page("app.py") if hasattr(st, "switch_page") else None
                            st.experimental_rerun()
                    with c[1]:
                        if status != "In Progress" and st.button("Start ⏳", key=f"start_{row.id}"):
                            exec1("UPDATE jobs SET status='In Progress', updated_at=datetime('now') WHERE id=?", (int(row.id),))
                            st.rerun()
                    with c[2]:
                        if status != "Done" and st.button("Done ✅", key=f"done_{row.id}"):
                            exec1("UPDATE jobs SET status='Done', updated_at=datetime('now') WHERE id=?", (int(row.id),))
                            st.rerun()

# ------------------------------------------------------------
# Router
# ------------------------------------------------------------
if page == "Patients":
    render_patients()
elif page == "Add Patient":
    render_add_patient()
elif page == "Patient Details":
    render_patient_details()
elif page == "Jobs Board":
    render_jobs_board()

st.caption("Built for ENT handovers • SQLite backend • Mobile friendly")
