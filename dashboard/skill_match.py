"""Visitor-facing skill matching and related market signals."""

from __future__ import annotations

import math

import altair as alt
import pandas as pd
import streamlit as st

from dashboard.insights import skill_match_insight
from dashboard.queries import (
    MIN_SALARY_JOBS_PER_CATEGORY,
    ROLE_FOCUS_OPTIONS,
    fetch_selected_skill_counts,
    fetch_skill_match_jobs,
    fetch_skill_match_salary,
    fetch_skill_match_summary,
    fetch_skill_options,
    fetch_skills_to_learn,
    open_read_only_connection,
    skill_display_name,
    source_display_name,
)
from dashboard.theme import CHART_ACCENT_COLOR, render_chart_heading


@st.cache_data(ttl=300, show_spinner="Loading tracked skills...")
def load_skill_options() -> pd.DataFrame:
    connection = open_read_only_connection()
    try:
        return fetch_skill_options(connection)
    finally:
        connection.close()


@st.cache_data(ttl=300, show_spinner="Calculating skill matches...")
def load_skill_match_results(
    selected_skills: tuple[str, ...], role_focus: str
) -> dict[str, pd.DataFrame]:
    connection = open_read_only_connection()
    try:
        return {
            "summary": fetch_skill_match_summary(
                connection, selected_skills, role_focus
            ),
            "selected_skill_counts": fetch_selected_skill_counts(
                connection, selected_skills, role_focus
            ),
            "skills_to_learn": fetch_skills_to_learn(
                connection, selected_skills, role_focus
            ),
            "salary": fetch_skill_match_salary(
                connection, selected_skills, role_focus
            ),
            "jobs": fetch_skill_match_jobs(connection, selected_skills, role_focus),
        }
    finally:
        connection.close()


st.title("Skill Match")
st.caption("Explore job demand and related skills across Remotive and Jobicy")

try:
    skill_options = load_skill_options()
except Exception:
    st.error(
        "Unable to load tracked skills from PostgreSQL. Check the local database "
        "configuration and try again."
    )
    st.stop()

option_names = skill_options["skill_name"].astype(str).tolist()
display_names = dict(
    zip(skill_options["skill_name"].astype(str), skill_options["display_name"])
)

with st.sidebar:
    st.subheader("Skill match filters")
    selected_skills = st.multiselect(
        "Skills",
        options=option_names,
        format_func=lambda skill: display_names.get(skill, skill_display_name(skill)),
        help="Choose one or more skills to find jobs that ask for them.",
    )
    role_focus = st.radio("Role focus", ROLE_FOCUS_OPTIONS)

try:
    results = load_skill_match_results(tuple(selected_skills), role_focus)
except Exception:
    st.error(
        "Unable to calculate skill matches from PostgreSQL. Check the local "
        "database configuration and try again."
    )
    st.stop()

summary = results["summary"].iloc[0]
tracked_jobs = int(summary["tracked_jobs"])
if selected_skills:
    jobs_any = int(summary["jobs_any"])
    jobs_all = int(summary["jobs_all"])
    match_percent = 100 * jobs_any / tracked_jobs if tracked_jobs else 0.0
    st.write(
        f"Your skills match {jobs_any:,} of {tracked_jobs:,} jobs with tracked "
        f"skills ({match_percent:.1f}%)."
    )

    metric_columns = st.columns(2)
    metric_columns[0].metric("Jobs matching at least one chosen skill", f"{jobs_any:,}")
    metric_columns[1].metric("Jobs matching all chosen skills", f"{jobs_all:,}")

    if jobs_any == 0:
        st.info("No jobs match these skills and role focus. Try a different selection.")

    selected_counts = results["selected_skill_counts"]
    render_chart_heading("Chosen skills by job demand", jobs_any)
    if selected_counts.empty:
        st.info("No chosen skills are available to chart.")
    else:
        max_job_count = int(
            pd.to_numeric(selected_counts["job_count"], errors="coerce").max()
        )
        tick_step = max(1, math.ceil(max_job_count / 7))
        tick_values = list(range(0, max_job_count + 1, tick_step))
        selected_skill_chart = (
            alt.Chart(selected_counts)
            .mark_bar(color=CHART_ACCENT_COLOR)
            .encode(
                x=alt.X(
                    "job_count:Q",
                    title="Number of jobs",
                    axis=alt.Axis(format="d", values=tick_values),
                    scale=alt.Scale(domainMin=0),
                ),
                y=alt.Y(
                    "display_name:N",
                    title="Skill",
                    sort=alt.SortField(field="job_count", order="descending"),
                ),
                tooltip=[
                    alt.Tooltip("display_name:N", title="Skill"),
                    alt.Tooltip("job_count:Q", title="Jobs", format=","),
                ],
            )
            .properties(height=min(500, max(140, 34 * len(selected_counts))))
        )
        st.altair_chart(
            selected_skill_chart,
            width="stretch",
            alt="Chosen skills ranked by the number of jobs that request each skill",
        )
    st.subheader("Skills to learn next")
    next_skills = results["skills_to_learn"]
    if jobs_any == 0:
        st.info("No matching jobs are available to identify related skills.")
    elif next_skills.empty:
        st.info("No other tracked skills were found in these matching jobs.")
    else:
        learning_table = next_skills[
            ["display_name", "job_count", "percent_jobs"]
        ].rename(
            columns={
                "display_name": "Skill",
                "job_count": "Jobs",
                "percent_jobs": "Share of matching jobs",
            }
        )
        learning_table["Share of matching jobs"] = learning_table[
            "Share of matching jobs"
        ].map(lambda value: f"{float(value):.1f}%")
        st.dataframe(
            learning_table,
            width="stretch",
            hide_index=True,
            alt="Ten most common unchosen skills among jobs matching the selected skills",
        )
        st.caption(
            f"Shares use {jobs_any:,} jobs matching at least one chosen skill as the sample"
        )

    match_insight_rows = next_skills.copy()
    if match_insight_rows.empty:
        match_insight_rows = pd.DataFrame(
            [{"skill_name": None, "display_name": None, "job_count": 0}]
        )
    match_insight_rows["matching_job_count"] = jobs_any
    match_sources = summary.get("matched_sources", [])
    match_insight_rows["sources"] = [match_sources] * len(match_insight_rows)
    st.caption(skill_match_insight(match_insight_rows))

    st.subheader("Salary signal")
    salary = results["salary"].iloc[0]
    salary_job_count = int(salary["salary_job_count"])
    if salary_job_count < MIN_SALARY_JOBS_PER_CATEGORY:
        st.info(f"Not enough salary data (n={salary_job_count:,})")
    else:
        st.metric(
            "Median yearly USD salary",
            f"${float(salary['median_salary_usd']):,.0f}",
        )
        st.caption(
            f"Based on {salary_job_count:,} matching jobs with yearly USD salary data"
        )

    st.subheader("Matching jobs")
    matching_jobs = results["jobs"]
    if matching_jobs.empty:
        st.info("No matching job listings to display.")
    else:
        jobs_table = matching_jobs[
            ["title", "company_name", "source", "url"]
        ].rename(
            columns={
                "title": "Title",
                "company_name": "Company",
                "url": "Original posting",
            }
        )
        jobs_table["Source"] = jobs_table["source"].map(source_display_name)
        jobs_table = jobs_table[["Title", "Company", "Source", "Original posting"]]
        st.dataframe(
            jobs_table,
            width="stretch",
            hide_index=True,
            alt="Newest job postings matching at least one chosen skill",
            column_config={
                "Original posting": st.column_config.LinkColumn(
                    "Original posting",
                    display_text="Open posting",
                )
            },
        )
        st.caption(
            f"Showing {len(jobs_table):,} of {jobs_any:,} jobs matching at least one chosen skill; "
            "at most 20 postings are shown"
        )
else:
    st.info("Choose at least one tracked skill to see matching jobs and related skills.")

st.divider()
st.caption(
    f"Only jobs with at least one tracked skill can match ({tracked_jobs:,} jobs in this role focus). "
    "Data comes from Remotive and Jobicy."
)
