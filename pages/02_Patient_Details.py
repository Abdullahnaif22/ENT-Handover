from datetime import datetime, time
import streamlit as st
from auth import require_auth, logout_button
from db import ensure_schema, DB_PATH, q, df, exec1
from utils import dob_to_age, priority_pill, status_pill

st.set_page_config(page_title="Patient Details • ENT Handover", page_icon="🩺", layout="wide")
ensure_schema(); require_auth()
st.sidebar.title("🏥 ENT Handover"); st.sidebar.caption(f"DB file: `{DB_PATH}`"); logout_button()

st.subheader("🧾 Patient Details")

def _get_patient(pid: int):
    rows = q("""SELECT id,patient_name,hospital_number,nhs_number,date_of_birth,reason_for_admission,pmh,psh,dh,allergies,created_at,updated_at FROM patients WHERE id=?""",(pid,))
    return rows[0] if rows else None

pid = st.session_state.get("selected_patient_id")
if not pid:
    all_df = df("SELECT id, patient_name, hospital_number FROM patients ORDER BY created_at DESC")
    choices = [(int(r["id"]), f'{r["patient_name"]} • {r["hospital_number"]} (ID {int(r["id"])})') for _, r in all_df.iterrows()]
    if choices:
        pick = st.selectbox("Choose a patient", options=choices, format_func=lambda x: x[1])
        if st.button("Load ▶"):
            st.session_state.selected_patient_id = pick[0]
            st.rerun()
    else:
        st.info("No patients found. Add one in **Add Patient**.")
        st.stop()

pid = st.session_state.get("selected_patient_id")
p = _get_patient(pid)
if not p:
    st.info("Select a valid patient from Patients page.")
    st.stop()

pid, name, hosp, nhs, dob, reason, pmh, psh, dh, allergies, created_at, updated_at = p
age = dob_to_age(dob)
st.markdown(f"### {name}  •  {hosp}  •  Age {age if age is not None else '?'}")
c = st.columns(4)
c[0].metric("Reason for admission", reason); c[1].metric("NHS No", nhs or "—"); c[2].metric("Allergies", allergies or "—"); c[3].metric("DOB", dob)

with st.expander("History (PMH / PSH / Drug History)", expanded=False):
    c1,c2,c3 = st.columns(3)
    with c1: st.markdown("**PMH**"); st.write(pmh or "—")
    with c2: st.markdown("**PSH**"); st.write(psh or "—")
    with c3: st.markdown("**Drug History**"); st.write(dh or "—")

st.divider()
st.markdown("#### 📝 Progress in hospital")
notes_df = df("SELECT id, note_time, author, note FROM progress_notes WHERE patient_id=? ORDER BY note_time DESC",(pid,))
st.dataframe(notes_df, use_container_width=True, hide_index=True)
with st.form("add_note"):
    ncol = st.columns([4,1])
    note = ncol[0].text_area("Add progress note", placeholder="e.g., ENT reviewed, needle aspiration performed...")
    author = ncol[1].text_input("Author", value="")
    if st.form_submit_button("Add note") and note.strip():
        exec1("INSERT INTO progress_notes (patient_id,note,author) VALUES (?,?,?)", (pid, note.strip(), author.strip()))
        st.success("Note added."); st.rerun()

st.divider()
st.markdown("#### ✅ Jobs to be done")
jobs = df("""
    SELECT id,job_text,priority,status,COALESCE(due_time,'') due_time,COALESCE(assigned_to,'') assigned_to
    FROM jobs WHERE patient_id=?
    ORDER BY CASE priority WHEN 'Urgent' THEN 0 WHEN 'Soon' THEN 1 ELSE 2 END, created_at ASC
""",(pid,))
if jobs.empty: st.info("No jobs yet.")

for _, row in jobs.iterrows():
    jb = st.columns([5,1.2,1.2,1.8,1.8,1])
    jb[0].markdown(f"**{row.job_text}**")
    jb[0].markdown(priority_pill(row.priority)+" "+status_pill(row.status), unsafe_allow_html=True)
    new_status = jb[1].selectbox("Status", ["Open","In Progress","Done"], index=["Open","In Progress","Done"].index(row.status), key=f"status_{row.id}")
    new_prio   = jb[2].selectbox("Priority", ["Urgent","Soon","Routine"], index=["Urgent","Soon","Routine"].index(row.priority), key=f"prio_{row.id}")
    assigned   = jb[3].text_input("Assigned to", value=row.assigned_to, key=f"ass_{row.id}")
    due        = jb[4].text_input("Due (YYYY-MM-DD HH:MM)", value=row.due_time, key=f"due_{row.id}")
    if jb[5].button("💾", key=f"save_{row.id}"):
        exec1("UPDATE jobs SET status=?, priority=?, assigned_to=?, due_time=?, updated_at=datetime('now') WHERE id=?",
              (new_status, new_prio, assigned.strip(), due.strip() or None, int(row.id)))
        st.toast("Job updated")

with st.form("add_job"):
    st.markdown("**Add a new job**")
    c1,c2,c3,c4 = st.columns([4,1.2,1.8,2])
    text = c1.text_input("Job description*", "")
    prio = c2.selectbox("Priority", ["Urgent","Soon","Routine"], index=2)
    assign_to = c3.text_input("Assigned to", "")
    due_date = c4.date_input("Due date", value=None)
    due_time_val = c4.time_input("Due time", value=time(12,0))
    if st.form_submit_button("Add job") and text.strip():
        due_iso = f"{due_date.strftime('%Y-%m-%d')} {due_time_val.strftime('%H:%M')}" if due_date else None
        exec1("INSERT INTO jobs (patient_id,job_text,priority,assigned_to,due_time) VALUES (?,?,?,?,?)",
              (pid, text.strip(), prio, assign_to.strip(), due_iso))
        st.success("Job added."); st.rerun()
