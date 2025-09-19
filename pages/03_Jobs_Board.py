# pages/03_Jobs_Board.py
from datetime import datetime, date, timedelta
import pandas as pd
import streamlit as st

from auth import require_auth, logout_button
from db import ensure_schema, df, exec1
from utils import priority_pill, status_pill

# ---------------- Page setup, auth, schema ----------------
st.set_page_config(page_title="Jobs Board • ENT Handover", page_icon="🩺", layout="wide")
ensure_schema(); require_auth()
st.sidebar.title("🏥 ENT Handover")
logout_button()

st.subheader("🗂️ Jobs Board")

# ---------------- Helpers ----------------
def safe_parse_dt(s: str | None) -> datetime | None:
    if not s:
        return None
    s = s.strip()
    for fmt in ("%Y-%m-%d %H:%M", "%Y-%m-%d", "%d/%m/%Y %H:%M", "%d/%m/%Y"):
        try:
            return datetime.strptime(s, fmt)
        except Exception:
            continue
    ts = pd.to_datetime(s, errors="coerce")
    if pd.isna(ts):
        return None
    return ts.to_pydatetime()

def label_for_date(d: date | None, today: date) -> str:
    if d is None: return "📅 No due date"
    if d < today: return f"⚠️ Overdue — {d.strftime('%Y-%m-%d (%a)')}"
    if d == today: return f"🟩 Today — {d.strftime('%Y-%m-%d (%a)')}"
    if d == today + timedelta(days=1): return f"🟨 Tomorrow — {d.strftime('%Y-%m-%d (%a)')}"
    if today + timedelta(days=2) <= d <= today + timedelta(days=7): return f"🟦 This week — {d.strftime('%Y-%m-%d (%a)')}"
    return f"📆 Later — {d.strftime('%Y-%m-%d (%a)')}"

def render_job_row(row, key_prefix=""):
    """Single-row list item with two actions."""
    with st.container(border=True):
        # Title line
        left, mid, right = st.columns([4, 2, 2])
        with left:
            st.markdown(f"**{row.job_text}**")
            st.caption(f"{row.patient_name} • {row.hospital_number}")
        with mid:
            st.markdown(priority_pill(row.priority) + " " + status_pill(row.status), unsafe_allow_html=True)
        with right:
            meta = []
            if row.assigned_to:
                meta.append(f"Assigned: {row.assigned_to}")
            if row.due_time_str:
                meta.append(f"Due: {row.due_time_str}")
            if meta: st.caption(" • ".join(meta))

        # Actions in a single row (list style)
        b1, b2, spacer = st.columns([1, 1, 6])
        if row.status != "In Progress" and b1.button("In progress ⏳", key=f"{key_prefix}start_{row.id}"):
            exec1("UPDATE jobs SET status='In Progress', updated_at=datetime('now') WHERE id=?", (int(row.id),))
            st.rerun()
        if row.status != "Done" and b2.button("Done ✅", key=f"{key_prefix}done_{row.id}"):
            exec1("UPDATE jobs SET status='Done', updated_at=datetime('now') WHERE id=?", (int(row.id),))
            st.rerun()

# ---------------- Load & prepare data ----------------
jobs = df("""
    SELECT j.id, j.patient_id, j.job_text, j.priority, j.status,
           COALESCE(j.due_time, '') AS due_time, COALESCE(j.assigned_to,'') AS assigned_to,
           p.patient_name, p.hospital_number
    FROM jobs j
    JOIN patients p ON p.id = j.patient_id
""")

if jobs.empty:
    st.info("No jobs yet. Add jobs from the **Patient Details** page.")
    st.stop()

jobs["due_dt"] = jobs["due_time"].apply(safe_parse_dt)
jobs["due_date"] = jobs["due_dt"].apply(lambda d: (None if d is None or pd.isna(d) else d.date()))
jobs["due_time_str"] = jobs["due_dt"].apply(lambda d: "" if (d is None or pd.isna(d)) else d.strftime("%Y-%m-%d %H:%M"))

today = date.today()

# ---------------- Filters (dropdowns) ----------------
status_options = ["All", "Open", "In Progress", "Done"]
priority_options = ["All", "Urgent", "Soon", "Routine"]
date_filter_mode = st.selectbox("Date filter", ["All dates", "Today", "Tomorrow", "Pick a date"], index=0)

# Optional date picker
picked_date = None
if date_filter_mode == "Pick a date":
    picked_date = st.date_input("Choose a date", value=today)

status_choice = st.selectbox("Status", status_options, index=0)
priority_choice = st.selectbox("Priority", priority_options, index=0)

patients = sorted(jobs["patient_name"].unique().tolist())
patient_choice = st.selectbox("Patient", ["All"] + patients, index=0)

assignees = sorted([a for a in jobs["assigned_to"].unique().tolist() if str(a).strip()])
assignee_choice = st.selectbox("Assigned to", ["All"] + assignees, index=0)

text_choice = st.text_input("Search text", value="", placeholder="job / patient / hosp no")

# Apply filters
mask = pd.Series(True, index=jobs.index)
if status_choice != "All":
    mask &= jobs["status"].eq(status_choice)
if priority_choice != "All":
    mask &= jobs["priority"].eq(priority_choice)
if patient_choice != "All":
    mask &= jobs["patient_name"].str.lower().eq(patient_choice.lower())
if assignee_choice != "All":
    mask &= jobs["assigned_to"].str.lower().eq(assignee_choice.lower())
if text_choice.strip():
    t = text_choice.strip()
    mask &= (
        jobs["job_text"].str.contains(t, case=False, na=False) |
        jobs["patient_name"].str.contains(t, case=False, na=False) |
        jobs["hospital_number"].str.contains(t, case=False, na=False)
    )

# Date filter
if date_filter_mode == "Today":
    mask &= jobs["due_date"].eq(today)
elif date_filter_mode == "Tomorrow":
    mask &= jobs["due_date"].eq(today + timedelta(days=1))
elif date_filter_mode == "Pick a date" and picked_date:
    mask &= jobs["due_date"].eq(picked_date)
# (All dates = no constraint)

jobs_f = jobs[mask].copy()

# ---------------- Metrics ----------------
open_count = int((jobs_f["status"] != "Done").sum())
inprog_count = int((jobs_f["status"] == "In Progress").sum())
done_count = int((jobs_f["status"] == "Done").sum())
overdue_count = int(((jobs_f["due_date"].notna()) & (jobs_f["due_date"] < today) & (jobs_f["status"] != "Done")).sum())

m1, m2, m3, m4 = st.columns(4)
m1.metric("Open (filtered)", open_count)
m2.metric("In Progress", inprog_count)
m3.metric("Done", done_count)
m4.metric("Overdue", overdue_count)

st.divider()

# ---------------- List view grouped by date ----------------
if jobs_f.empty:
    st.caption("No jobs match the current filters.")
    st.stop()

# Sort dates asc with None at end
unique_dates = sorted([d for d in jobs_f["due_date"].unique() if pd.notna(d)])
if jobs_f["due_date"].isna().any():
    unique_dates += [None]

for d in unique_dates:
    group = jobs_f[jobs_f["due_date"].isna()] if d is None else jobs_f[jobs_f["due_date"].eq(d)]
    if group.empty:
        continue

    st.markdown(f"### {label_for_date(d, today)}  &nbsp;&nbsp; <span class='pill'>{len(group)}</span>", unsafe_allow_html=True)

    # Within the date, show a flat LIST sorted by (status rank, priority, time, id)
    status_rank = {"Open": 0, "In Progress": 1, "Done": 2}
    prio_rank = {"Urgent": 0, "Soon": 1, "Routine": 2}
    group["status_rank"] = group["status"].map(status_rank)
    group["prio_rank"] = group["priority"].map(prio_rank)
    group["due_sort"] = group["due_dt"].apply(lambda x: x if (x is not None and not pd.isna(x)) else datetime.max)
    group = group.sort_values(["status_rank", "prio_rank", "due_sort", "id"])

    for _, row in group.iterrows():
        render_job_row(row, key_prefix=f"{str(d) if d else 'none'}_")
