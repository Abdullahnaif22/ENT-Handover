#!/usr/bin/env python3
# app.py — Home (Patients)

from pathlib import Path
import sys
import pandas as pd
import streamlit as st

# Ensure project root importable
ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from auth import require_auth, logout_button
from db import ensure_schema, DB_PATH, df
from utils import dob_to_age

# Page config + CSS
st.set_page_config(page_title="ENT Handover", page_icon="🩺", layout="wide", initial_sidebar_state="expanded")
st.markdown("""
<style>
  .pill{display:inline-block;padding:0.15rem 0.55rem;border-radius:999px;font-size:0.8rem;border:1px solid var(--secondary-border);}
  .login-card{max-width:520px;margin:6rem auto 2rem;padding:1.5rem;border-radius:16px;border:1px solid #eee;background:#0f1116;}
</style>
""", unsafe_allow_html=True)

# Schema + auth on entry
ensure_schema()
require_auth()

# Sidebar (no custom Navigate)
st.sidebar.title("🏥 ENT Handover")
st.sidebar.caption(f"DB file: `{DB_PATH}`")
logout_button()

# Quick search specific to this page
search_term = st.sidebar.text_input("🔎 Name / Hosp No / Reason", placeholder="e.g. Jane or H123...")

# -------- Patients (Home) --------
st.subheader("👥 Patients")

c1, c2, c3 = st.columns([2, 2, 1])
with c1:
    term = st.text_input("Search", value=search_term or "", placeholder="Name, Hosp No, Reason...")
with c2:
    sort_by = st.radio("Sort by", ["Newest first","Patient name (A→Z)","Hospital number (A→Z)"], horizontal=True, index=0)
    sort_sql = {"Newest first":"created_at DESC","Patient name (A→Z)":"patient_name ASC","Hospital number (A→Z)":"hospital_number ASC"}[sort_by]
with c3:
    limit = st.select_slider("Show", options=[20,50,100,500], value=20)

data = df(f"""
    SELECT p.id, p.patient_name, p.hospital_number, COALESCE(p.nhs_number,'') nhs_number,
           p.date_of_birth, p.reason_for_admission, p.created_at,
           (SELECT COUNT(*) FROM jobs j WHERE j.patient_id=p.id AND j.status!='Done') AS open_jobs
    FROM patients p
    WHERE (p.patient_name LIKE ? OR p.hospital_number LIKE ? OR p.reason_for_admission LIKE ?)
    ORDER BY {sort_sql}
    LIMIT ?
""", (f"%{term}%", f"%{term}%", f"%{term}%", limit))

if not data.empty:
    data["Age"] = data["date_of_birth"].apply(dob_to_age)
    data = data.rename(columns={"patient_name":"Patient","hospital_number":"Hosp No","nhs_number":"NHS No","reason_for_admission":"Reason","created_at":"Created","open_jobs":"Open Jobs"})
    data = data[["id","Patient","Hosp No","NHS No","Age","Reason","Open Jobs","Created"]]

st.dataframe(
    data if not data.empty else pd.DataFrame(columns=["id","Patient","Hosp No","NHS No","Age","Reason","Open Jobs","Created"]),
    use_container_width=True, hide_index=True
)

ids_labels = []
if not data.empty:
    for _, r in data.iterrows():
        ids_labels.append((int(r["id"]), f'{r["Patient"]} • {r["Hosp No"]} (ID {int(r["id"])})'))

st.markdown("**Open patient:**")
if ids_labels:
    chosen = st.selectbox("Select", options=ids_labels, format_func=lambda x: x[1], label_visibility="collapsed", key="patients_selectbox_home")
    if st.button("Open details ▶"):
        st.session_state.selected_patient_id = chosen[0]
        st.success("Opened patient details. Go to **Patient Details** from the sidebar.")
else:
    st.caption("No patients match your filters.")

st.caption("Built for ENT handovers • SQLite backend • Login: demo credentials")
