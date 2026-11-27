"""Entry point for the Global Job Market Streamlit dashboard."""

from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import streamlit as st

st.set_page_config(page_title="Global Job Market Dashboard", layout="wide")

page = st.navigation(
    [
        st.Page(
            "dashboard/market_overview.py",
            title="Market Overview",
            icon=":material/bar_chart:",
            default=True,
            help="All-source job market metrics, category and salary charts, listings, and pipeline status.",
        ),
        st.Page(
            "dashboard/skill_match.py",
            title="Skill Match",
            icon=":material/search:",
            help="Choose tracked skills to compare job matches, related skills, salary data, and current postings.",
        ),
    ],
    position="sidebar",
)

page.run()