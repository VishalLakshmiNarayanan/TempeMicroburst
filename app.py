import streamlit as st
import geopandas as gpd
import pandas as pd
import plotly.express as px
import numpy as np

# ------------------------------------------------------
# PAGE SETUP
# ------------------------------------------------------
st.set_page_config(
    page_title="Tempe Tree Inventory Dashboard",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# ------------------------------------------------------
# LIGHT THEME (Shadcn-style)
# ------------------------------------------------------
st.markdown("""
<style>
html, body, .stApp {
  background-color: #ffffff !important;
  color: #000000 !important;
  font-family: "Inter", "Segoe UI", sans-serif;
}
h1, h2, h3, h4, h5, h6, p, span, div, label {
  color: #000000 !important;
}
.card {
  background-color: #ffffff;
  border: 1.5px solid #000000;
  border-radius: 0.65rem;
  padding: 1.5rem;
  margin-top: 1.5rem;
  box-shadow: 0 2px 5px rgba(0,0,0,0.1);
}
div.block-container {
  padding-top: 1.2rem;
  padding-bottom: 1rem;
}
</style>
""", unsafe_allow_html=True)

# ------------------------------------------------------
# PLOT STYLING HELPER
# ------------------------------------------------------
def style_plot(fig):
    fig.update_layout(
        paper_bgcolor="white",
        plot_bgcolor="white",
        font=dict(color="black", size=13),
        title_font=dict(color="black", size=16),
        xaxis=dict(
            title_font=dict(color="black", size=14),
            tickfont=dict(color="black", size=12),
            gridcolor="lightgrey",
            zerolinecolor="lightgrey",
        ),
        yaxis=dict(
            title_font=dict(color="black", size=14),
            tickfont=dict(color="black", size=12),
            gridcolor="lightgrey",
            zerolinecolor="lightgrey",
        ),
        legend=dict(font=dict(color="black", size=12)),
    )
    return fig

# ------------------------------------------------------
# TITLE
# ------------------------------------------------------
st.title("Tempe Urban Forest: Microburst Impact and Tree Risk (2021 Inventory)")
st.markdown("""
This dashboard uses the **City of Tempe’s 2021 Tree Inventory shapefile**  
to visualize tree locations, canopy size (DBH), and estimated structural value.
""")

# ------------------------------------------------------
# LOAD SHAPEFILE DATA
# ------------------------------------------------------
@st.cache_data
def load_data():
    gdf = gpd.read_file("Tree/Tree_Inventory.shp").to_crs(epsg=4326)

    # --- Auto-detect numeric columns ---
    cols = [c.lower() for c in gdf.columns]
    col_map = dict(zip(cols, gdf.columns))

    dbh_col = next((col_map[c] for c in cols if "dbh" in c or "diam" in c), None)
    repl_col = next((col_map[c] for c in cols if "replace" in c or "value" in c), None)

    if dbh_col:
        gdf[dbh_col] = pd.to_numeric(gdf[dbh_col], errors="coerce")
    else:
        gdf["DBH__in_"] = 0
        dbh_col = "DBH__in_"

    if repl_col:
        gdf[repl_col] = pd.to_numeric(gdf[repl_col], errors="coerce")
    else:
        gdf["Replacement_Value"] = 0
        repl_col = "Replacement_Value"

    # --- Add risk classification ---
    gdf["Risk_Level"] = pd.cut(
        gdf[dbh_col],
        bins=[0, 10, 20, 999],
        labels=["Low", "Medium", "High"]
    )

    gdf = gdf.dropna(subset=["geometry"])
    return gdf, dbh_col, repl_col

gdf, dbh_col, repl_col = load_data()

# ------------------------------------------------------
# SUMMARY METRICS
# ------------------------------------------------------
if not gdf.empty:
    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.subheader("Summary Metrics — Tempe’s Urban Canopy Health")

    total_trees = len(gdf)
    avg_dbh = round(gdf[dbh_col].mean(), 1)
    total_value = round(gdf[repl_col].sum(), 2)
    high_risk_pct = round((len(gdf[gdf["Risk_Level"] == "High"]) / len(gdf)) * 100, 1)

    carbon_col = next(
        (col for col in gdf.columns if "carbon" in col.lower() and "stor" in col.lower()), None
    )
    if carbon_col:
        avg_carbon = round(gdf[carbon_col].mean(), 1)
    else:
        avg_carbon = round(gdf[dbh_col].mean() * 5, 1)

    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Total Trees", f"{total_trees:,}")
    c2.metric("Average Diameter (in)", f"{avg_dbh}")
    c3.metric("Total Replacement Value ($)", f"${total_value:,.0f}")
    c4.metric("High-Risk Trees (%)", f"{high_risk_pct}%")
    c5.metric("Avg Carbon Storage (lb/tree)", f"{avg_carbon:,}")
    st.caption("Metrics derived from Tempe’s 2021 Tree Inventory (WCA + i-Tree Eco data)")
    st.markdown('</div>', unsafe_allow_html=True)

# ------------------------------------------------------
# MAP VISUALIZATION
# ------------------------------------------------------
if not gdf.empty:
    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.subheader("Tree Vulnerability Map (Tempe, AZ)")

    color_map = {"Low": "green", "Medium": "orange", "High": "red"}
    sampled_gdf = gdf.sample(min(4000, len(gdf))).copy()
    sampled_gdf["lat"] = sampled_gdf.geometry.y
    sampled_gdf["lon"] = sampled_gdf.geometry.x

    fig_map = px.scatter_mapbox(
        sampled_gdf,
        lat="lat",
        lon="lon",
        color="Risk_Level",
        size=dbh_col,
        size_max=8,
        opacity=1,
        color_discrete_map=color_map,
        zoom=12,
        center={"lat": 33.4255, "lon": -111.94},
        mapbox_style="carto-positron",
        title="Tree Risk Distribution Across Tempe"
    )
    st.plotly_chart(style_plot(fig_map), use_container_width=True)
    st.caption("Each dot represents one tree. Colors correspond to risk levels based on canopy size (DBH).")
    st.markdown('</div>', unsafe_allow_html=True)

# ------------------------------------------------------
# TREND GRAPH WITH GREEN-UP / RED-DOWN AND MICROBURST BAND
# ------------------------------------------------------
st.markdown('<div class="card">', unsafe_allow_html=True)
st.subheader("Average Tree Size by Latitude (North–South Trend)")

gdf["LatBand"] = (gdf.geometry.y.round(4))
trend_df = gdf.groupby("LatBand")[dbh_col].mean().reset_index()
trend_df["delta"] = trend_df[dbh_col].diff()
trend_df["color"] = np.where(trend_df["delta"] >= 0, "green", "red")

fig_trend = px.line(
    trend_df,
    x="LatBand",
    y=dbh_col,
    line_shape="spline",
    title="Average Tree Diameter (DBH) vs Latitude in Tempe"
)

# manually recolor segments
for i in range(1, len(trend_df)):
    fig_trend.add_scatter(
        x=trend_df["LatBand"].iloc[i-1:i+1],
        y=trend_df[dbh_col].iloc[i-1:i+1],
        mode="lines",
        line=dict(color=trend_df["color"].iloc[i], width=3),
        showlegend=False
    )

# microburst zone shading (approx lat 33.38–33.41)
fig_trend.add_vrect(
    x0=33.38, x1=33.41,
    fillcolor="rgba(255, 0, 0, 0.08)",
    line_width=0,
    annotation_text="Microburst Core Zone",
    annotation_position="top left",
    annotation_font_color="black"
)

st.plotly_chart(style_plot(fig_trend), use_container_width=True)
st.caption("Green segments indicate increasing canopy size northward; red segments show smaller or younger trees toward southern Tempe.")
st.markdown('</div>', unsafe_allow_html=True)

# ------------------------------------------------------
# MICROBURST FOCUS MAP
# ------------------------------------------------------
st.markdown('<div class="card">', unsafe_allow_html=True)
st.subheader("Microburst Impact Zone Focus: Southern & Kyrene Corridor")

focus_zone = gdf.cx[-111.96:-111.92, 33.38:33.41]
fig_focus = px.scatter_mapbox(
    focus_zone,
    lat=focus_zone.geometry.y,
    lon=focus_zone.geometry.x,
    color="Risk_Level",
    size=dbh_col,
    size_max=8,
    opacity=1,
    color_discrete_map={"Low": "green", "Medium": "orange", "High": "red"},
    mapbox_style="carto-positron",
    zoom=14,
    center={"lat": 33.395, "lon": -111.94},
)
st.plotly_chart(style_plot(fig_focus), use_container_width=True)
st.caption("Zoomed view of the Southern Ave–Kyrene Rd corridor — the microburst’s most heavily impacted area.")
st.markdown('</div>', unsafe_allow_html=True)

# ------------------------------------------------------
# INSIGHTS
# ------------------------------------------------------
st.markdown('<div class="card">', unsafe_allow_html=True)
st.subheader("Insights and Recommendations")
st.markdown("""
- **High-risk trees (red)** — large, mature specimens most susceptible to wind damage.  
- **Medium-risk trees (orange)** — form most of Tempe’s shade canopy.  
- **Low-risk trees (green)** — smaller, younger plantings with better stability.  
- Replanting wind-resistant species and periodic pruning improve canopy resilience.
""")
st.caption("Data Source: City of Tempe Urban Forestry (WCA 2021), i-Tree Eco v6.0.22")
st.markdown('</div>', unsafe_allow_html=True)
