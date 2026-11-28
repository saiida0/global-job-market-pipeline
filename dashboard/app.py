"""Entry point for the Global Job Market Streamlit dashboard."""

from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DASHBOARD_DIR = Path(__file__).resolve().parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import streamlit as st

from dashboard.theme import dashboard_css

st.set_page_config(page_title="Remote job market", layout="wide")
st.markdown(dashboard_css(), unsafe_allow_html=True)

page = st.navigation(
    [
        st.Page(
            str(DASHBOARD_DIR / "market_overview.py"),
            title="Market Overview",
            default=True,
            help="All-source job market metrics, category and salary charts, listings, and pipeline status.",
        ),
        st.Page(
            str(DASHBOARD_DIR / "skill_match.py"),
            title="Skill Match",
            help="Choose tracked skills to compare job matches, related skills, salary data, and current postings.",
        ),
    ],
    position="sidebar",
)

page.run()
