"""Local, read-only dashboard for jobs from all configured sources."""

from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import altair as alt
import streamlit as st

from dashboard.queries import (
    MIN_SALARY_JOBS_PER_CATEGORY,
    ROLE_FOCUS_OPTIONS,
    compact_utc_timestamp,
    fetch_extracted_job_skills,
    fetch_jobs,
    fetch_pipeline_runs,
    filter_jobs,
    filter_options,
    filter_role_focus,
    jobs_by_category,
    jobs_table,
    pipeline_runs_table,
    postings_per_day,
    salary_by_category,
    search_jobs,
    skills_counts,
    summary_metrics,
    tracked_skill_job_count,
)


@st.cache_data(ttl=300, show_spinner="Loading jobs from PostgreSQL...")
def load_jobs():
    """Cache the read-only job query for five minutes."""
    return fetch_jobs()


@st.cache_data(ttl=300, show_spinner="Loading extracted skills...")
def load_extracted_skills():
    """Cache the read-only extracted-skill query for five minutes."""
    return fetch_extracted_job_skills()


@st.cache_data(ttl=60, show_spinner="Loading pipeline status...")
def load_pipeline_runs():
    """Cache recent pipeline runs for one minute."""
    return fetch_pipeline_runs()



st.title("Global Job Market Dashboard")
st.caption("Remote job postings from Remotive and Jobicy")

try:
    all_jobs = load_jobs()
    extracted_skills = load_extracted_skills()
    pipeline_runs = load_pipeline_runs()
except Exception:
    st.error(
        "Unable to load dashboard data from PostgreSQL. Check that the database is "
        "reachable and that the local .env database settings are valid, then "
        "rerun the dashboard."
    )
    st.stop()

with st.sidebar:
    st.header("Filters")
    role_focus_choice = st.radio("Role focus", ROLE_FOCUS_OPTIONS)
    source_options = filter_options(all_jobs, "source")
    categories = filter_options(all_jobs, "category")
    job_types = filter_options(all_jobs, "job_type")
    locations = filter_options(all_jobs, "location")

    selected_sources = st.multiselect(
        "Source", source_options, default=source_options
    )
    category_choice = st.selectbox("Category", ["All categories", *categories])
    job_type_choice = st.selectbox("Job type", ["All job types", *job_types])
    location_choice = st.selectbox("Location", ["All locations", *locations])
    search_term = st.text_input("Search title or company", placeholder="Search jobs")

selected_jobs = filter_jobs(
    all_jobs,
    category=None if category_choice == "All categories" else category_choice,
    job_type=None if job_type_choice == "All job types" else job_type_choice,
    location=None if location_choice == "All locations" else location_choice,
    sources=selected_sources,
)
selected_jobs = filter_role_focus(selected_jobs, role_focus_choice)
selected_jobs = search_jobs(selected_jobs, search_term)

metrics = summary_metrics(selected_jobs)
recent_update = metrics["most_recent_update"]
recent_label = (
    recent_update.strftime("%Y-%m-%d %H:%M UTC")
    if recent_update is not None
    else "—"
)

metric_columns = st.columns([1, 1, 1, 2])
metric_columns[0].metric("Total jobs", f"{metrics['total_jobs']:,}")
metric_columns[1].metric("Jobs with salary", f"{metrics['jobs_with_salary']:,}")
metric_columns[2].metric("Categories", f"{metrics['category_count']:,}")
metric_columns[3].metric("Most recent update", recent_label)

if all_jobs.empty:
    st.info("No jobs are available in the database yet.")
elif selected_jobs.empty:
    st.info("No jobs match these filters. Adjust the sidebar filters to see results.")

st.caption(f"Showing {len(selected_jobs):,} of {len(all_jobs):,} jobs.")

skills_column, category_column = st.columns(2)
with skills_column:
    st.subheader("Most demanded skills")
    skill_data = skills_counts(selected_jobs, extracted_skills).head(15)
    if skill_data.empty:
        st.info("No tracked skills are available for these jobs.")
    else:
        skill_chart = (
            alt.Chart(skill_data)
            .mark_bar()
            .encode(
                x=alt.X(
                    "job_count:Q",
                    title="Number of jobs",
                    scale=alt.Scale(domainMin=0),
                ),
                y=alt.Y(
                    "skill:N",
                    title="Skill",
                    axis=alt.Axis(labelLimit=240),
                    sort=alt.SortField(field="job_count", order="descending"),
                ),
                tooltip=[
                    alt.Tooltip("skill:N", title="Skill"),
                    alt.Tooltip("job_count:Q", title="Number of jobs", format=","),
                ],
            )
        )
        st.altair_chart(
            skill_chart,
            width="stretch",
            alt="Top extracted skills sorted by the number of matching jobs",
        )
    tracked_jobs = tracked_skill_job_count(selected_jobs, extracted_skills)
    st.caption(
        f"Based on {tracked_jobs:,} jobs with at least one tracked skill "
        f"(of {len(selected_jobs):,} jobs)"
    )

with category_column:
    st.subheader("Jobs per category")
    category_data = jobs_by_category(selected_jobs)
    if category_data.empty:
        st.info("No category data is available for these jobs.")
    else:
        category_chart = (
            alt.Chart(category_data)
            .mark_bar()
            .encode(
                x=alt.X(
                    "job_count:Q",
                    title="Number of jobs",
                    scale=alt.Scale(domainMin=0),
                ),
                y=alt.Y(
                    "category_label:N",
                    title="Category",
                    axis=alt.Axis(labelLimit=360),
                    sort=alt.SortField(field="job_count", order="descending"),
                ),
                tooltip=[
                    alt.Tooltip("category:N", title="Category"),
                    alt.Tooltip("job_count:Q", title="Number of jobs", format=","),
                ],
            )
        )
        st.altair_chart(
            category_chart,
            width="stretch",
            alt="Job counts by shared category, highest count first",
        )
    st.caption(f"Based on {len(selected_jobs):,} jobs")

salary_column, posting_column = st.columns(2)
with salary_column:
    st.subheader("Salary by category")
    salary_data = salary_by_category(selected_jobs)
    if salary_data.empty:
        if salary_data.attrs.get("eligible_jobs", 0):
            st.info(f"No category has at least {MIN_SALARY_JOBS_PER_CATEGORY} yearly USD salary jobs.")
        else:
            st.info("No yearly USD salary data is available for these jobs.")
    else:
        salary_axis_max = max(
            1.0, float(salary_data["median_salary_usd"].max()) * 1.1
        )
        salary_chart = (
            alt.Chart(salary_data)
            .mark_bar()
            .encode(
                x=alt.X(
                    "median_salary_usd:Q",
                    title="Median yearly salary (USD)",
                    scale=alt.Scale(domain=[0, salary_axis_max], nice=False),
                ),
                y=alt.Y(
                    "category_label:N",
                    title="Category",
                    axis=alt.Axis(labelLimit=360),
                    sort=alt.SortField(
                        field="median_salary_usd", order="descending"
                    ),
                ),
                tooltip=[
                    alt.Tooltip("category_label:N", title="Category"),
                    alt.Tooltip(
                        "salary_job_count:Q", title="Salary jobs", format=","
                    ),
                    alt.Tooltip(
                        "median_salary_usd:Q",
                        title="Median yearly salary (USD)",
                        format=",.0f",
                    ),
                ],
            )
        )
        st.altair_chart(
            salary_chart,
            width="stretch",
            alt="Median yearly USD salary by category with salary job counts",
        )
    st.caption(
        f"Based on {salary_data.attrs.get('jobs_used', 0):,} yearly USD salary jobs "
        "in the displayed categories. Each job uses the midpoint of min and max "
        "when both are listed, or its available bound when only one is listed. "
        f"Categories with fewer than {MIN_SALARY_JOBS_PER_CATEGORY} salary jobs are hidden."
    )

with posting_column:
    st.subheader("Postings per day")
    posting_data = postings_per_day(selected_jobs)
    if posting_data.empty:
        st.info("No publication dates are available for these jobs.")
    else:
        postings_chart = (
            alt.Chart(posting_data)
            .mark_line()
            .encode(
                x=alt.X("publication_day:T", title="Date posted"),
                y=alt.Y(
                    "job_count:Q",
                    title="Number of jobs",
                    scale=alt.Scale(zero=True),
                ),
                tooltip=[
                    alt.Tooltip("source:N", title="Source"),
                    alt.Tooltip(
                        "publication_day:T",
                        title="Date posted",
                        format="%Y-%m-%d",
                    ),
                    alt.Tooltip("job_count:Q", title="Number of jobs", format=","),
                ],
            )
            .properties(height=95)
            .facet(row=alt.Row("source:N", title=None))
            .resolve_scale(y="independent")
        )
        st.altair_chart(
            postings_chart,
            width="stretch",
            alt="Daily job postings by source in separate panels",
        )
    dated_jobs = int(posting_data["job_count"].sum()) if not posting_data.empty else 0
    st.caption(
        f"Based on {dated_jobs:,} jobs with a publication date. Counts reflect each "
        "source's fetch window, not total market volume."
    )

st.subheader("Job listings")
table_data = jobs_table(selected_jobs)
if table_data.empty:
    st.info("No job listings to display.")
else:
    st.dataframe(
        table_data,
        width="stretch",
        hide_index=True,
        alt="Newest job listings with source and original posting links",
        column_config={
            "Original posting": st.column_config.LinkColumn(
                "Original posting",
                display_text="Open posting",
            )
        },
    )

st.subheader("Pipeline status")
run_table = pipeline_runs_table(pipeline_runs)
if run_table.empty:
    st.info("No pipeline runs are recorded yet.")
else:
    latest_run = run_table.iloc[0]
    latest_time_label = compact_utc_timestamp(latest_run["Finished at"]) or "—"
    run_metrics = st.columns([2, 1, 1, 1, 1, 1])
    run_metrics[0].metric("Latest run", latest_time_label)
    run_metrics[1].metric("Status", str(latest_run["Status"]).title())
    run_metrics[2].metric("Jobs fetched", f"{latest_run['Jobs fetched']:,}")
    run_metrics[3].metric("Jobs cleaned", f"{latest_run['Jobs cleaned']:,}")
    run_metrics[4].metric("Jobs skipped", f"{latest_run['Jobs skipped']:,}")
    run_metrics[5].metric("Jobs upserted", f"{latest_run['Jobs upserted']:,}")
    st.caption("Last 5 runs")
    st.dataframe(
        run_table,
        width="stretch",
        hide_index=True,
        alt="The five most recent pipeline runs and their job counts",
    )

st.divider()
st.caption(
    "Job data from [Remotive](https://remotive.com) and [Jobicy](https://jobicy.com). "
    "Each listing links to its original posting. Private, non-commercial academic project."
)
