import streamlit as st

VALID_USER = "gen079477"
VALID_PASS = "wardstaff"

def login_view():
    st.markdown("<div class='login-card'>", unsafe_allow_html=True)
    st.markdown("## 🏥 ENT Handover — Login", unsafe_allow_html=True)
    with st.form("login_form", clear_on_submit=False):
        u = st.text_input("Username")
        p = st.text_input("Password", type="password")
        if st.form_submit_button("Log in"):
            if u == VALID_USER and p == VALID_PASS:
                st.session_state.auth = True
                st.rerun()
            else:
                st.error("Invalid credentials.")
    st.markdown("</div>", unsafe_allow_html=True)

def require_auth():
    if "auth" not in st.session_state:
        st.session_state.auth = False
    if not st.session_state.auth:
        login_view()
        st.stop()

def logout_button():
    if st.sidebar.button("Logout"):
        st.session_state.clear()
        st.rerun()
