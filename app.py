import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go

st.set_page_config(
    page_title="Operation Coral Recovery Dashboard",
    page_icon="🚑",
    layout="wide"
)

st.markdown("""
<style>

/* Increase tab size */
div[data-baseweb="tab-list"] button {
    font-size: 22px !important;
    font-weight: 700 !important;
}

/* Increase tab spacing */
div[data-baseweb="tab-list"] {
    gap: 30px;
}

</style>
""", unsafe_allow_html=True)

# -----------------------------
# Load data
# -----------------------------
@st.cache_data
def load_data():
    infra = pd.read_csv("isla_coralina_infrastructure.csv")
    relief = pd.read_csv("isla_coralina_relief_operations.csv")

    infra["date_last_update"] = pd.to_datetime(infra["date_last_update"], errors="coerce")
    relief["date"] = pd.to_datetime(relief["date"], errors="coerce")

    relief["fulfillment_rate"] = np.where(
        relief["quantity_requested"] > 0,
        relief["quantity_delivered"] / relief["quantity_requested"],
        np.nan
    )
    relief["supply_gap"] = relief["quantity_requested"] - relief["quantity_delivered"]

    return infra, relief

infra, relief = load_data()

# -----------------------------
# Sidebar filters
# -----------------------------
st.sidebar.title("Filters")

municipalities = sorted(relief["municipality"].dropna().unique().tolist())
selected_municipalities = st.sidebar.multiselect(
    "Select municipality",
    municipalities,
    default=municipalities
)

min_date = relief["date"].min().date()
max_date = relief["date"].max().date()

selected_dates = st.sidebar.slider(
    "Select date range",
    min_value=min_date,
    max_value=max_date,
    value=(min_date, max_date)
)

supply_types = sorted(relief["supply_type"].dropna().unique().tolist())
selected_supply_types = st.sidebar.multiselect(
    "Select supply type",
    supply_types,
    default=supply_types
)

transport_modes = sorted(relief["transport_mode"].dropna().unique().tolist())
selected_transport_modes = st.sidebar.multiselect(
    "Select transport mode",
    transport_modes,
    default=transport_modes
)

# -----------------------------
# Apply filters
# -----------------------------
relief_f = relief[
    (relief["municipality"].isin(selected_municipalities)) &
    (relief["date"].dt.date >= selected_dates[0]) &
    (relief["date"].dt.date <= selected_dates[1]) &
    (relief["supply_type"].isin(selected_supply_types)) &
    (relief["transport_mode"].isin(selected_transport_modes))
].copy()

infra_f = infra[
    infra["municipality"].isin(selected_municipalities)
].copy()

# -----------------------------
# KPI calculations
# -----------------------------
critical_types = ["Hospital", "Water Treatment Plant"]

total_population_served = int(infra_f["population_served"].sum())
avg_delay = relief_f["delivery_delay_hours"].mean()
pct_under_80 = (relief_f["fulfillment_rate"] < 0.80).mean() * 100 if len(relief_f) > 0 else 0

non_operational_critical = infra_f[
    (infra_f["facility_type"].isin(critical_types)) &
    (infra_f["operational_status"] != "Fully Operational")
]

num_non_operational_critical = non_operational_critical.shape[0]

# -----------------------------
# Header
# -----------------------------
st.title("Operation Coral Recovery: Relief Operations Dashboard")
st.markdown(
    """
    This dashboard integrates infrastructure and relief-delivery data to support
    daily operational decisions for humanitarian coordinators on Isla Coralina.
    Use the filters on the left to narrow conditions by municipality, date, supply type, and transport mode.
    """
)

# -----------------------------
# Summary KPIs
# -----------------------------
st.subheader("Operational Summary")

k1, k2, k3, k4 = st.columns(4)
k1.metric("Total Population Served", f"{total_population_served:,}")
k2.metric("Average Delivery Delay (hrs)", f"{avg_delay:.2f}" if pd.notnull(avg_delay) else "N/A")
k3.metric("% Deliveries Below 80% Fulfillment", f"{pct_under_80:.1f}%")
k4.metric("Non-Operational Critical Facilities", f"{num_non_operational_critical}")

# Municipality-level critical KPI table
critical_table = (
    infra_f[infra_f["facility_type"].isin(critical_types)]
    .assign(
        critical_issue=lambda d: np.where(d["operational_status"] == "Fully Operational", 0, 1)
    )
    .groupby("municipality", as_index=False)["critical_issue"]
    .sum()
    .rename(columns={"critical_issue": "non_operational_critical_facilities"})
)

st.dataframe(critical_table, use_container_width=True)

# -----------------------------
# Tabs
# -----------------------------
tab1, tab2 = st.tabs(["Infrastructure Status", "Relief Distribution Performance"])

# =========================================================
# TAB 1: Infrastructure
# =========================================================
with tab1:
    st.subheader("Infrastructure Situation")

    status_color_map = {
        "Fully Operational": "green",
        "Partially Operational": "orange",
        "Non-Operational": "red"
    }

    # Map
    fig_map = px.scatter_mapbox(
        infra_f,
        lat="latitude",
        lon="longitude",
        color="operational_status",
        color_discrete_map=status_color_map,
        size="population_served",
        hover_name="facility_name",
        hover_data={
            "facility_type": True,
            "municipality": True,
            "damage_severity": True,
            "population_served": True,
            "road_access": True,
            "latitude": False,
            "longitude": False
        },
        zoom=7,
        height=550,
        title="Infrastructure Map by Operational Status"
    )
    fig_map.update_layout(mapbox_style="open-street-map", margin=dict(l=0, r=0, t=50, b=0))
    st.plotly_chart(fig_map, use_container_width=True)

    c1, c2 = st.columns(2)

    with c1:
        # Stacked bar: facility status by municipality
        infra_status = (
            infra_f.groupby(["municipality", "operational_status"])
            .size()
            .reset_index(name="count")
        )

        fig_status = px.bar(
            infra_status,
            x="municipality",
            y="count",
            color="operational_status",
            color_discrete_map=status_color_map,
            barmode="stack",
            title="Facility Status by Municipality"
        )
        st.plotly_chart(fig_status, use_container_width=True)

    with c2:
        # Critical facilities by municipality
        crit_counts = (
            infra_f[infra_f["facility_type"].isin(critical_types)]
            .assign(
                status_group=lambda d: np.where(
                    d["operational_status"] == "Fully Operational",
                    "Fully Operational",
                    "Needs Attention"
                )
            )
            .groupby(["municipality", "status_group"])
            .size()
            .reset_index(name="count")
        )

        fig_crit = px.bar(
            crit_counts,
            x="municipality",
            y="count",
            color="status_group",
            barmode="group",
            title="Critical Facilities by Municipality",
            category_orders={"status_group": ["Fully Operational", "Needs Attention"]}
        )
        st.plotly_chart(fig_crit, use_container_width=True)

    st.markdown("### Infrastructure Analysis")
    st.markdown(
        """
        The infrastructure picture is uneven across the island. Puerto Nuevo has the strongest operational base,
        while Costa Sur and especially Rincon del Este show greater concentrations of partially operational and
        non-operational facilities. Critical infrastructure risk is most concerning where hospitals or water treatment
        plants are not fully operational, because those failures can quickly affect both health outcomes and relief logistics.

        For relief coordinators, the practical implication is to prioritize backup support, generator coverage, and
        route planning toward the municipalities with weaker critical-service resilience. Areas with damaged or
        constrained infrastructure should receive faster contingency planning because they are more likely to experience
        service interruptions during further weather stress.
        """
    )

# =========================================================
# TAB 2: Relief operations
# =========================================================
with tab2:
    st.subheader("Relief Distribution Performance")

    top1, top2 = st.columns(2)

    with top1:
        # Daily trend line
        daily = (
            relief_f.groupby("date", as_index=False)
            .agg(
                avg_fulfillment_rate=("fulfillment_rate", "mean"),
                avg_delay=("delivery_delay_hours", "mean")
            )
        )

        fig_line = px.line(
            daily,
            x="date",
            y="avg_fulfillment_rate",
            markers=True,
            title="Daily Average Fulfillment Rate"
        )
        fig_line.update_yaxes(range=[0, 1], tickformat=".0%")
        st.plotly_chart(fig_line, use_container_width=True)

    with top2:
        # Histogram of delays
        fig_hist = px.histogram(
            relief_f,
            x="delivery_delay_hours",
            nbins=30,
            title="Distribution of Delivery Delays"
        )
        st.plotly_chart(fig_hist, use_container_width=True)

    bottom1, bottom2 = st.columns(2)

    with bottom1:
        # Box plot by transport mode
        fig_box = px.box(
            relief_f,
            x="transport_mode",
            y="delivery_delay_hours",
            color="transport_mode",
            title="Delivery Delay by Transport Mode"
        )
        st.plotly_chart(fig_box, use_container_width=True)

    with bottom2:
        # Heatmap of weather x road condition
        heat = (
            relief_f.groupby(["road_condition", "weather_on_delivery_day"], as_index=False)
            .agg(avg_fulfillment_rate=("fulfillment_rate", "mean"))
        )

        heat_pivot = heat.pivot(
            index="road_condition",
            columns="weather_on_delivery_day",
            values="avg_fulfillment_rate"
        )

        fig_heat = go.Figure(
            data=go.Heatmap(
                z=heat_pivot.values,
                x=heat_pivot.columns,
                y=heat_pivot.index,
                text=np.round(heat_pivot.values, 2),
                texttemplate="%{text}",
                colorscale="YlOrRd",
                zmin=0,
                zmax=1
            )
        )
        fig_heat.update_layout(
            title="Average Fulfillment Rate: Road Condition vs Weather",
            xaxis_title="Weather",
            yaxis_title="Road Condition"
        )
        st.plotly_chart(fig_heat, use_container_width=True)

    # Extra chart: municipality performance
    muni_perf = (
        relief_f.groupby("municipality", as_index=False)
        .agg(
            avg_fulfillment_rate=("fulfillment_rate", "mean"),
            avg_delay=("delivery_delay_hours", "mean"),
            avg_supply_gap=("supply_gap", "mean")
        )
        .sort_values("avg_fulfillment_rate")
    )

    fig_muni = px.bar(
        muni_perf,
        x="municipality",
        y="avg_fulfillment_rate",
        color="avg_delay",
        title="Municipality Performance: Fulfillment Rate Colored by Delay",
        labels={"avg_fulfillment_rate": "Average Fulfillment Rate", "avg_delay": "Avg Delay (hrs)"}
    )
    fig_muni.update_yaxes(range=[0, 1], tickformat=".0%")
    st.plotly_chart(fig_muni, use_container_width=True)

    st.markdown("### Relief Operations Analysis")
    st.markdown(
        """
        Relief efficiency improves over the 21-day period overall, but performance is not evenly distributed.
        Rincon del Este and Costa Sur remain weaker on fulfillment and experience longer average delays than
        better-performing municipalities. That means aggregate island recovery can appear to improve even while
        some localities continue to face persistent delivery shortfalls.

        Operationally, the strongest risk factor is the combination of degraded road access and bad weather.
        Deliveries under heavy rain and poor road conditions show the lowest fulfillment and the longest delays.
        Coordinators should therefore pre-position critical supplies in vulnerable municipalities, prioritize truck
        routing where roads are serviceable, and use helicopter or boat support selectively for access-constrained areas
        rather than as a default replacement for ground logistics.
        """
    )

# -----------------------------
# Footer
# -----------------------------
st.markdown("---")
st.caption("DSA 506 - Operation Coral Recovery | Streamlit dashboard for Problem 3")

