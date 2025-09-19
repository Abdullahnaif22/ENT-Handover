import streamlit as st
from auth import require_auth, logout_button
from db import ensure_schema, DB_PATH, df, exec1
from utils import priority_pill, status_pill

st.set_page_config(page_title="Jobs Board • ENT Handover", page_icon="🩺", layout="wide")
ensure_schema(); require_auth()
st.sidebar.title("🏥 ENT Handover"); st.sidebar.caption(f"DB file: `{DB_PATH}`"); logout_button()

st.subheader("🗂️ Jobs Board")

cols = st.columns(3)
for i, status in enumerate(["Open","In Progress","Done"]):
    with cols[i]:
        st.markdown(f"**{status}**")
        jobs = df("""
            SELECT j.id,j.job_text,j.priority,j.assigned_to,j.due_time,p.patient_name,p.hospital_number,j.patient_id
            FROM jobs j JOIN patients p ON p.id=j.patient_id
            WHERE j.status=? ORDER BY
            CASE j.priority WHEN 'Urgent' THEN 0 WHEN 'Soon' THEN 1 ELSE 2 END,
            j.due_time IS NULL, j.due_time ASC
        """,(status,))
        if jobs.empty: st.caption("— none —")
        for _, row in jobs.iterrows():
            with st.container(border=True):
                st.markdown(f"**{row.job_text}**")
                st.caption(f"{row.patient_name} • {row.hospital_number}")
                st.markdown(priority_pill(row.priority)+" "+status_pill(status), unsafe_allow_html=True)
                st.caption((f"Assigned: {row.assigned_to} • " if row.assigned_to else "")+(f"Due: {row.due_time}" if row.due_time else ""))
                c = st.columns([1,1,1,2])
                if c[0].button("Open ▶︎", key=f"open_{row.id}"):
                    st.session_state.selected_patient_id = int(row.patient_id); st.experimental_rerun()
                if status!="In Progress" and c[1].button("Start ⏳", key=f"start_{row.id}"):
                    exec1("UPDATE jobs SET status='In Progress', updated_at=datetime('now') WHERE id=?", (int(row.id),)); st.rerun()
                if status!="Done" and c[2].button("Done ✅", key=f"done_{row.id}"):
                    exec1("UPDATE jobs SET status='Done', updated_at=datetime('now') WHERE id=?", (int(row.id),)); st.rerun()
