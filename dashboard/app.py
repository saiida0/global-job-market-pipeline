"""Local, read-only dashboard for the Remotive job listings database."""

from __future__ import annotations

import streamlit as st

from dashboard.queries import (
    fetch_jobs,
    filter_jobs,
    filter_options,
    jobs_by_category,
    jobs_table,
    postings_per_day,
    salary_by_category,
    skills_counts,
    summary_metrics,
)


@st.cache_data(ttl=300, show_spinner="Loading jobs from PostgreSQL...")
def load_jobs():
    """Cache the read-only database query for five minutes."""
    return fetch_jobs()


st.set_page_config(page_title="Global Job Market Dashboard", layout="wide")
st.title("Global Job Market Dashboard")
st.caption("Remotive job postings collected by the local pipeline.")

try:
    all_jobs = load_jobs()
except Exception:
    st.error(
        "Unable to load jobs from PostgreSQL. Check that the database is "
        "reachable and that the local .env database settings are valid, then "
        "rerun the dashboard."
    )
    st.stop()

with st.sidebar:
    st.header("Filters")
    categories = filter_options(all_jobs, "category")
    job_types = filter_options(all_jobs, "job_type")
    locations = filter_options(all_jobs, "location")

    category_choice = st.selectbox("Category", ["All categories", *categories])
    job_type_choice = st.selectbox("Job type", ["All job types", *job_types])
    location_choice = st.selectbox("Location", ["All locations", *locations])

selected_jobs = filter_jobs(
    all_jobs,
    category=None if category_choice == "All categories" else category_choice,
    job_type=None if job_type_choice == "All job types" else job_type_choice,
    location=None if location_choice == "All locations" else location_choice,
)

metrics = summary_metrics(selected_jobs)
recent_update = metrics["most_recent_update"]
recent_label = (
    recent_update.strftime("%Y-%m-%d %H:%M UTC")
    if recent_update is not None
    else "—"
)

metric_columns = st.columns(4)
metric_columns[0].metric("Total jobs", f"{metrics['total_jobs']:,}")
metric_columns[1].metric("Jobs with salary", f"{metrics['jobs_with_salary']:,}")
metric_columns[2].metric("Categories", f"{metrics['category_count']:,}")
metric_columns[3].metric("Most recent update", recent_label)

if all_jobs.empty:
    st.info("No Remotive jobs are available in the database yet.")
elif selected_jobs.empty:
    st.info("No jobs match these filters. Adjust the sidebar filters to see results.")

st.caption(f"Showing {len(selected_jobs):,} of {len(all_jobs):,} jobs.")

skills_column, category_column = st.columns(2)
with skills_column:
    st.subheader("Most demanded skills")
    skill_data = skills_counts(selected_jobs).head(15)
    if skill_data.empty:
        st.info("No skill tags are available for these jobs.")
    else:
        st.bar_chart(skill_data.set_index("skill")["job_count"])

with category_column:
    st.subheader("Jobs per category")
    category_data = jobs_by_category(selected_jobs)
    if category_data.empty:
        st.info("No category data is available for these jobs.")
    else:
        st.bar_chart(category_data.set_index("category")["job_count"])

salary_column, posting_column = st.columns(2)
with salary_column:
    st.subheader("Salary by category")
    st.caption("Yearly USD only; hourly and non-USD salaries are excluded.")
    salary_data = salary_by_category(selected_jobs)
    if salary_data.empty:
        st.info("No yearly USD salary data is available for these jobs.")
    else:
        st.bar_chart(salary_data.set_index("category")["median_salary_usd"])

with posting_column:
    st.subheader("Postings per day")
    posting_data = postings_per_day(selected_jobs)
    if posting_data.empty:
        st.info("No publication dates are available for these jobs.")
    else:
        posting_data = posting_data.assign(
            publication_day=posting_data["publication_day"].astype(str)
        )
        st.line_chart(posting_data.set_index("publication_day")["job_count"])

st.subheader("Job listings")
table_data = jobs_table(selected_jobs)
if table_data.empty:
    st.info("No job listings to display.")
else:
    st.dataframe(
        table_data,
        use_container_width=True,
        hide_index=True,
        column_config={
            "Original posting": st.column_config.LinkColumn(
                "Original Remotive posting",
                display_text="Open posting",
            )
        },
    )

st.divider()
st.caption(
    "Job data from [Remotive](https://remotive.com) and [Jobicy](https://jobicy.com). "
    "Each listing links to its original posting. Private, non-commercial academic project."
)
