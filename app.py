"""LocalFlood HPC Lab - analisis dan simulasi risiko banjir berbasis data (Streamlit)."""

from __future__ import annotations

import streamlit as st

from common.config import LOCALFLOOD_NAME, ensure_runtime_dirs
from ui.localflood_app import render_localflood
from ui.shared import inject_css

st.set_page_config(page_title=LOCALFLOOD_NAME, layout="wide", initial_sidebar_state="expanded")
ensure_runtime_dirs()
inject_css()

with st.sidebar:
    st.markdown(f"## {LOCALFLOOD_NAME}")
    st.caption("Bridging Global Infrastructure to Address Local Challenge in HPC")
    st.markdown("**Catatan**\n\n- Alat pembelajaran dan simulasi demonstratif.\n- Bukan sistem peringatan dini resmi.")

render_localflood()
