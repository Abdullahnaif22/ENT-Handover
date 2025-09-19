import streamlit as st
from auth import require_auth, logout_button
from db import ensure_schema, conn, df, q

st.set_page_config(page_title="Admin • ENT Handover", page_icon="🩺", layout="wide")
ensure_schema(); require_auth()
st.sidebar.title("🏥 ENT Handover")
logout_button()

st.subheader("🛠️ Admin")

# ---- Simple password gate (per-session) ----
if "admin_ok" not in st.session_state:
    st.session_state.admin_ok = False

if not st.session_state.admin_ok:
    with st.form("admin_login"):
        pw = st.text_input("Enter admin password", type="password")
        if st.form_submit_button("Unlock"):
            if pw == "admin":
                st.session_state.admin_ok = True
                st.success("Admin unlocked.")
                st.rerun()
            else:
                st.error("Incorrect password.")
    st.stop()

# ---- Admin content (unchanged except DB path hidden) ----
counts = {
    "patients": q("SELECT COUNT(*) FROM patients")[0][0],
    "progress_notes": q("SELECT COUNT(*) FROM progress_notes")[0][0],
    "jobs": q("SELECT COUNT(*) FROM jobs")[0][0],
}
c1, c2, c3 = st.columns(3)
c1.metric("Patients", counts["patients"])
c2.metric("Progress notes", counts["progress_notes"])
c3.metric("Jobs", counts["jobs"])

if st.button("Flush to disk (checkpoint WAL)"):
    conn().execute("PRAGMA wal_checkpoint(FULL);")
    conn().commit()
    st.success("Flushed WAL to DB file.")

st.divider()
st.markdown("**CSV exports**")
st.download_button("Patients.csv", df("SELECT * FROM patients").to_csv(index=False).encode(), "patients.csv", "text/csv")
st.download_button("ProgressNotes.csv", df("SELECT * FROM progress_notes").to_csv(index=False).encode(), "progress_notes.csv", "text/csv")
st.download_button("Jobs.csv", df("SELECT * FROM jobs").to_csv(index=False).encode(), "jobs.csv", "text/csv")
