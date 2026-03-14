"""Streamlit entry point — page routing and global setup."""

import streamlit as st

st.set_page_config(
    page_title="Revenue Tracker",
    page_icon="favicon.png",
    layout="wide",
    initial_sidebar_state="collapsed",
)

from pages.dashboard import render_dashboard
from pages.data_entry import render_data_entry
from pages.history import render_history

# --- Password gate ---
def check_password():
    if "authenticated" not in st.session_state:
        st.session_state.authenticated = False

    if st.session_state.authenticated:
        return True

    password = st.text_input("Password", type="password")
    if password:
        if password == st.secrets.get("app_password", ""):
            st.session_state.authenticated = True
            st.rerun()
        else:
            st.error("Incorrect password")
    return False

if not check_password():
    st.stop()

# Top navigation
st.title("Revenue Tracker")
col_nav, col_refresh = st.columns([3, 1])
with col_nav:
    page = st.radio("", ["Dashboard", "Data Entry", "History"], horizontal=True, label_visibility="collapsed")
with col_refresh:
    if st.button("Refresh Data"):
        st.cache_data.clear()
        st.rerun()

st.markdown("---")

# Page routing
if page == "Dashboard":
    render_dashboard()
elif page == "Data Entry":
    render_data_entry()
elif page == "History":
    render_history()
