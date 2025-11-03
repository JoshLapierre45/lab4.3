import streamlit as st
import pandas as pd
import altair as alt
import plotly.express as px

import streamlit as st
import pandas as pd
import numpy as np
import altair as alt
from datetime import datetime, timedelta

st.set_page_config(page_title="Drone Flight Dashboard", layout="wide")

# ---------- Load Data (local CSVs) ----------
@st.cache_data
def load_data():
    flights = pd.read_csv("data/flights.csv", parse_dates=["date"])
    drones = pd.read_csv("data/drones.csv")
    projects = pd.read_csv("data/projects.csv", parse_dates=["start_date","end_date"])
    finance = pd.read_csv("data/finance.csv")
    return flights, drones, projects, finance

flights, drones, projects, finance = load_data()

# ---------- Sidebar Filters ----------
st.sidebar.header("Filters")
min_d, max_d = flights["date"].min(), flights["date"].max()
default_start = max_d - pd.Timedelta(days=90)
date_range = st.sidebar.date_input(
    "Date range", (default_start.date(), max_d.date()),
    min_value=min_d.date(), max_value=max_d.date()
)
selected_drones = st.sidebar.multiselect(
    "Choose drones", options=drones["drone_id"].tolist(), default=drones["drone_id"].tolist()
)
proj_status = st.sidebar.multiselect(
    "Project status", options=["active","completed"], default=["active","completed"]
)

# Filter data
if isinstance(date_range, tuple) and len(date_range) == 2:
    start, end = pd.to_datetime(date_range[0]), pd.to_datetime(date_range[1])
else:
    start, end = min_d, max_d

df = flights[(flights["date"].between(start, end)) & (flights["drone_id"].isin(selected_drones))]
proj_ids = projects[projects["status"].isin(proj_status)]["project_id"]
df = df[df["project_id"].isin(proj_ids)]

# ---------- Header ----------
st.title("Drone Flight Dashboard")
st.caption("Alt text / description: Overview of drone utilization, flight metrics, financial KPIs, and project status for a drone photography business.")

# ---------- KPI Row ----------
col1, col2, col3, col4 = st.columns(4)
with col1:
    st.metric("Total Flights", f"{len(df):,}")
with col2:
    avg_time = df["flight_time_min"].mean() if len(df) else np.nan
    st.metric("Avg Flight Time (min)", f"{avg_time:0.1f}" if pd.notna(avg_time) else "—")
with col3:
    avg_photos = df["photos_taken"].mean() if len(df) else np.nan
    st.metric("Avg Photos / Flight", f"{avg_photos:0.0f}" if pd.notna(avg_photos) else "—")
with col4:
    total_dist = df["distance_km"].sum() if len(df) else 0
total_miles = total_dist * 0.621371
st.metric("Total Distance (miles)", f"{total_miles:0.1f}")

st.markdown("---")

# ---------- Charts ----------
# ---------- Charts ----------
left, right = st.columns([3, 2])

# Donut chart: Flights by drone
with left:
    st.subheader("Flights by Drone")
    donut = (
        df.groupby("drone_id", as_index=False)["flight_id"]
        .count()
        .rename(columns={"flight_id": "flights"})
    )
    if donut.empty:
        st.info("No data for selected filters.")
    else:
        base = alt.Chart(donut)
        arc = base.mark_arc(innerRadius=70, outerRadius=130).encode(
            theta=alt.Theta("flights:Q", stack=True, sort=None, title=None),
            color=alt.Color("drone_id:N", legend=alt.Legend(title="Drone")),
            tooltip=[alt.Tooltip("drone_id:N", title="Drone"),
                     alt.Tooltip("flights:Q", title="Flights")]
        )
        labels = (
            base
            .transform_joinaggregate(total="sum(flights)")
            .transform_calculate(pct="datum.flights / datum.total")
            .transform_filter("datum.pct >= 0.08")
            .mark_text(radius=100, size=12)
            .encode(
                theta=alt.Theta("flights:Q", stack=True, sort=None),
                text=alt.Text("label:N"),
            )
            .transform_calculate(label='datum.drone_id + " (" + format(datum.pct, ".0%") + ")"')
        )
        st.altair_chart(arc + labels, use_container_width=True)
        st.caption("Caption: Donut chart showing distribution of flights by drone. Labels are centered and include percentages; all drones remain in the legend.")

# Bar chart: Weekly flights
with right:
    st.subheader("Flights in Selected Range (Weekly)")
    if df.empty:
        st.info("No data for selected filters.")
    else:
        weekly = df.resample("W-MON", on="date").size().reset_index(name="flights")
        bar = alt.Chart(weekly, title="Weekly Flights").mark_bar().encode(
            x=alt.X("date:T", title="Week (Mon)"),
            y=alt.Y("flights:Q", title="Flights"),
            tooltip=[alt.Tooltip("date:T", title="Week of"), "flights"]
        ).interactive()
        st.altair_chart(bar, use_container_width=True)
        st.caption("Caption: Interactive bar chart of weekly flight counts with tooltips.")


# Line: cumulative distance by drone (multiple encodings: color + dash)
st.subheader("Cumulative Distance by Drone (miles)")
if df.empty:
    st.info("No data for selected filters.")
else:
    cum = (
        df.sort_values("date")
          .groupby(["drone_id", "date"], as_index=False)["distance_km"]
          .sum()
    )
    # cumulative km per drone
    cum["cum_km"] = cum.groupby("drone_id")["distance_km"].cumsum()
    # convert to miles
    cum["cum_miles"] = cum["cum_km"] * 0.621371

    line = (
        alt.Chart(cum, title="Cumulative Distance")
        .mark_line(point=True)
        .encode(
            x=alt.X("date:T", title="Date"),
            y=alt.Y("cum_miles:Q", title="Cumulative Distance (miles)"),
            color=alt.Color("drone_id:N", legend=alt.Legend(title="Drone")),
            strokeDash="drone_id:N",
            tooltip=[
                alt.Tooltip("drone_id:N", title="Drone"),
                alt.Tooltip("date:T", title="Date"),
                alt.Tooltip("cum_miles:Q", title="Cum. miles", format=".1f"),
            ],
        )
        .interactive()
    )

    st.altair_chart(line, use_container_width=True)
    st.caption(
        "Caption: Line chart with both color and stroke pattern to avoid color-only encoding."
    )

# ---------- Finance KPIs ----------
st.subheader("Finance Snapshot")
fin_col1, fin_col2 = st.columns(2)
with fin_col1:
    # Monthly budget (expense) vs simple monthly budget target (derived from annual goal as example)
    finance["month_dt"] = pd.to_datetime(finance["month"] + "-01")
    current_month = finance["month_dt"].max()
    row = finance[finance["month_dt"]==current_month].iloc[0]
    monthly_budget_target = 9000  # example target
    st.metric(
        label=f"Current Month Expense vs Budget",
        value=f"${row['expense']:,}",
        delta=f"Target ${monthly_budget_target:,}"
    )
    st.caption("Caption: Summary KPI showing current month expenses versus a fixed budget target.")

with fin_col2:
    ytd_revenue = finance["revenue"].sum()
    annual_goal = int(finance["goal_annual"].iloc[0])
    pct = 0 if annual_goal==0 else int(100*ytd_revenue/annual_goal)
    st.metric("YTD Revenue Progress", f"${ytd_revenue:,}", delta=f"{pct}% of ${annual_goal:,}")
    st.caption("Caption: KPI showing progress toward the annual revenue goal.")

# ---------- Insights / Takeaways ----------
# ---------- Insights / Takeaways ----------
st.markdown("### Insights")
if df.empty:
    st.write("No insights: try broadening your filters.")
else:
    # top drone
    top_drone = donut.sort_values("flights", ascending=False).iloc[0]["drone_id"] if len(donut) else "—"

    # busiest day
    fastest_day = df.groupby("date")["flight_id"].count().sort_values(ascending=False).head(1)
    if not fastest_day.empty:
        best_day = fastest_day.index[0].strftime("%Y-%m-%d")
        most_flights = int(fastest_day.iloc[0])
    else:
        best_day, most_flights = "—", 0

    # convert total km → miles for insight
    total_miles = total_dist * 0.621371

    st.write(f"- **Utilization:** Drone **{top_drone}** has the most flights in the selected period.")
    st.write(f"- **Operational load:** Peak day was **{best_day}** with **{most_flights}** flights.")
    st.write(f"- **Efficiency:** Average flight time is **{avg_time:0.1f} min** and average photos per flight is **{avg_photos:0.0f}**.")
    st.write(f"- **Distance:** Total distance flown is **{total_miles:0.1f} miles** across all selected drones.")
    st.caption("Notes: Titles/axes include units; captions describe charts; interactive tooltips aid accessibility.")
