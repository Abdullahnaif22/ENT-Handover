from datetime import date
import streamlit as st
from auth import require_auth, logout_button
from db import ensure_schema, DB_PATH, exec1

# Page setup, auth, schema
st.set_page_config(page_title="Add Patient • ENT Handover", page_icon="🩺", layout="wide")
ensure_schema(); require_auth()
st.sidebar.title("🏥 ENT Handover"); st.sidebar.caption(f"DB file: `{DB_PATH}`"); logout_button()

st.subheader("➕ Add Patient")

ADD_KEYS = ["add_name","add_hosp","add_nhs","add_dob","add_reason","add_pmh","add_psh","add_dh","add_allergies"]

def _maybe_reset_add_form():
    if st.session_state.get("do_reset_add_form", False):
        for k in ADD_KEYS: st.session_state.pop(k, None)
        st.session_state["do_reset_add_form"] = False

_maybe_reset_add_form()
if "add_success_msg" in st.session_state: st.success(st.session_state.pop("add_success_msg"))

with st.form("add_patient", clear_on_submit=False):
    c1, c2 = st.columns(2)
    with c1:
        name = st.text_input("Patient name*", value="", key="add_name")
        hosp = st.text_input("Hospital number*", value="", key="add_hosp")
        nhs = st.text_input("NHS number (optional)", value="", key="add_nhs")
        dob = st.date_input("Date of birth*", value=date(1980,1,1), key="add_dob")
    with c2:
        reason = st.text_input("Reason for admission*", value="", key="add_reason")
        pmh = st.text_area("Past Medical History", value="", key="add_pmh")
        psh = st.text_area("Past Surgical History", value="", key="add_psh")
        dh = st.text_area("Drug History / meds", value="", key="add_dh")
        allergies = st.text_input("Allergies", value="NKDA", key="add_allergies")

    if st.form_submit_button("Save"):
        if not (name and hosp and reason and dob):
            st.error("Name, Hospital number, Reason, and Date of birth are required.")
        else:
            try:
                exec1("""
                    INSERT INTO patients (patient_name,hospital_number,nhs_number,date_of_birth,reason_for_admission,pmh,psh,dh,allergies)
                    VALUES (?,?,?,?,?,?,?,?,?)
                """, (name.strip(),hosp.strip(),nhs.strip(),dob.strftime("%Y-%m-%d"),reason.strip(),pmh.strip(),psh.strip(),dh.strip(),allergies.strip()))
                st.session_state["add_success_msg"] = f"Added {name}. Form cleared."
                st.session_state["do_reset_add_form"] = True
                st.rerun()
            except Exception as e:
                st.error(f"Could not add patient: {e}")
