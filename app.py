"""
Streamlit Web Application for Automated Insight Generation Engine
Interactive Auto-Analytics Dashboard with Live Filtering, Visualizations, and Dynamic Insights.
"""

import io
import os
import altair as alt
import numpy as np
import pandas as pd
import streamlit as st

from src.analyzer import (
    compute_correlation_matrix,
    detect_outliers_iqr,
    detect_outliers_zscore,
    detect_trends,
    flag_high_correlations,
)
from src.data_loader import (
    get_missing_values_report,
    get_numeric_indicators,
    load_dataset,
    validate_schema,
)
from src.insight_generator import format_indicator_name, generate_all_insights

# ----------------------------------------------------
# Page Configuration & Styling
# ----------------------------------------------------
st.set_page_config(
    page_title="Auto-Analytics Engine | Healthcare Insights",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Custom CSS for polished styling
st.markdown(
    """
    <style>
    .main-header {
        font-size: 2.2rem;
        font-weight: 700;
        color: #1E293B;
        margin-bottom: 0.2rem;
    }
    .sub-header {
        font-size: 1.05rem;
        color: #64748B;
        margin-bottom: 1.5rem;
    }
    .metric-card {
        background-color: #F8FAFC;
        border-radius: 8px;
        padding: 16px;
        border: 1px solid #E2E8F0;
        box-shadow: 0 1px 3px rgba(0,0,0,0.05);
    }
    .stAlert {
        border-radius: 8px;
    }
    .badge-high {
        background-color: #FEE2E2;
        color: #991B1B;
        padding: 4px 8px;
        border-radius: 4px;
        font-weight: 600;
    }
    .badge-med {
        background-color: #FEF3C7;
        color: #92400E;
        padding: 4px 8px;
        border-radius: 4px;
        font-weight: 600;
    }
    .badge-low {
        background-color: #DCFCE7;
        color: #166534;
        padding: 4px 8px;
        border-radius: 4px;
        font-weight: 600;
    }
    </style>
    """,
    unsafe_allow_html=True,
)


# ----------------------------------------------------
# Sidebar: Data Source & Configurable Parameters
# ----------------------------------------------------
st.sidebar.title("⚙️ Control Panel")
st.sidebar.markdown("Configure analytical thresholds and data filters.")

# Data Source
st.sidebar.subheader("📁 Data Source")
uploaded_file = st.sidebar.file_uploader(
    "Upload custom CSV (optional)", type=["csv"], help="Upload district healthcare performance CSV."
)

default_csv_path = os.path.join(os.path.dirname(__file__), "data", "healthcare_data.csv")

try:
    if uploaded_file is not None:
        raw_df = load_dataset(uploaded_file)
        st.sidebar.success(f"Uploaded: {uploaded_file.name}")
    else:
        raw_df = load_dataset(default_csv_path)
        st.sidebar.info("Using default sample dataset.")
except Exception as e:
    st.error(f"Failed to load dataset: {e}")
    st.stop()

# Validate Schema
is_valid_schema, missing_cols = validate_schema(raw_df)
if not is_valid_schema:
    st.sidebar.warning(f"Missing expected schema columns: {', '.join(missing_cols)}")

# Live Filters (Part A)
st.sidebar.subheader("🔍 Live Filters (Part A)")
available_districts = sorted(raw_df["district"].unique().tolist())
selected_districts = st.sidebar.multiselect(
    "Select District(s)",
    options=available_districts,
    default=available_districts,
)

available_months = sorted(raw_df["month"].unique().tolist())
selected_months = st.sidebar.multiselect(
    "Select Month(s)",
    options=available_months,
    default=available_months,
)

numeric_indicators = get_numeric_indicators(raw_df)
selected_indicators = st.sidebar.multiselect(
    "Select Indicator(s)",
    options=numeric_indicators,
    default=numeric_indicators,
    format_func=format_indicator_name,
)

# Sliders for Thresholds (Technical Constraints)
st.sidebar.subheader("🎛️ Analytical Thresholds")

trend_threshold = st.sidebar.slider(
    "Trend Significance Threshold (±%)",
    min_value=5.0,
    max_value=50.0,
    value=10.0,
    step=1.0,
    help="Flags indicator change if |pct_change| >= threshold (Default: 10%).",
)

outlier_method = st.sidebar.selectbox(
    "Outlier Algorithm",
    options=["both", "zscore", "iqr"],
    index=0,
    format_func=lambda x: "Both (Z-Score & IQR)" if x == "both" else ("Z-Score" if x == "zscore" else "IQR Rule"),
)

col_out1, col_out2 = st.sidebar.columns(2)
with col_out1:
    z_threshold = st.number_input(
        "Z-Score (|z|)",
        min_value=1.5,
        max_value=5.0,
        value=2.5,
        step=0.1,
    )
with col_out2:
    iqr_multiplier = st.number_input(
        "IQR Multiplier",
        min_value=1.0,
        max_value=3.0,
        value=1.5,
        step=0.1,
    )

corr_threshold = st.sidebar.slider(
    "Correlation Threshold (|r|)",
    min_value=0.50,
    max_value=0.99,
    value=0.70,
    step=0.05,
    help="Flags indicator pairs with absolute Pearson r >= threshold (Default: 0.70).",
)

anc_breach_threshold = st.sidebar.slider(
    "ANC Benchmark Target (%)",
    min_value=50.0,
    max_value=90.0,
    value=70.0,
    step=5.0,
    help="Target threshold for ANC Coverage breach alerts.",
)

# Apply Filtered View to Data
filtered_df = raw_df[
    (raw_df["district"].isin(selected_districts)) &
    (raw_df["month"].isin(selected_months))
].copy()

# ----------------------------------------------------
# Main Dashboard Header
# ----------------------------------------------------
st.markdown('<div class="main-header">Automated Insight Generation Engine</div>', unsafe_allow_html=True)
st.markdown(
    '<div class="sub-header">General-purpose analytics engine detecting trends, statistical outliers, '
    'and correlation patterns in district-level healthcare performance.</div>',
    unsafe_allow_html=True,
)

if filtered_df.empty:
    st.warning("No records match the selected filters. Please adjust the sidebar filters.")
    st.stop()

# ----------------------------------------------------
# Compute Pipeline
# ----------------------------------------------------
insights_df = generate_all_insights(
    df=filtered_df,
    trend_threshold_pct=trend_threshold,
    outlier_method=outlier_method,
    z_threshold=z_threshold,
    iqr_multiplier=iqr_multiplier,
    corr_threshold=corr_threshold,
    anc_breach_threshold=anc_breach_threshold,
)

# Filter insights by indicator selection if applicable
if selected_indicators and not insights_df.empty:
    def matches_indicator(ind_str):
        if ":" in ind_str:
            parts = ind_str.split(":")
            return any(p in selected_indicators for p in parts)
        return ind_str in selected_indicators
    insights_df = insights_df[insights_df["indicator"].apply(matches_indicator)].reset_index(drop=True)

# ----------------------------------------------------
# Key Metrics Overview Cards
# ----------------------------------------------------
m1, m2, m3, m4, m5 = st.columns(5)
total_insights = len(insights_df)
high_count = len(insights_df[insights_df["severity"] == "High"]) if not insights_df.empty else 0
med_count = len(insights_df[insights_df["severity"] == "Medium"]) if not insights_df.empty else 0
low_count = len(insights_df[insights_df["severity"] == "Low"]) if not insights_df.empty else 0

with m1:
    st.metric("Total Records", len(filtered_df))
with m2:
    st.metric("Total Insights", total_insights)
with m3:
    st.metric("🚨 High Severity", high_count)
with m4:
    st.metric("⚠️ Medium Severity", med_count)
with m5:
    st.metric("ℹ️ Low Severity", low_count)

# ----------------------------------------------------
# Tabs for Structured Navigation
# ----------------------------------------------------
tab_insights, tab_viz, tab_matrix, tab_data = st.tabs([
    "💡 Automated Insights",
    "📈 Visualizations & Trends",
    "🔗 Correlation Matrix",
    "📋 Raw Data & Validation",
])

# ====================================================
# TAB 1: AUTOMATED INSIGHTS
# ====================================================
with tab_insights:
    st.subheader("Generated Actionable Insights")
    st.markdown(
        "Dynamic, data-driven narratives with automatically evaluated severity levels. "
        "No hardcoded text; numbers and thresholds are evaluated directly from ingested data."
    )

    if insights_df.empty:
        st.info("No insights flagged with current filter and threshold parameters.")
    else:
        # Filter insight list by type
        col_f1, col_f2 = st.columns([2, 2])
        with col_f1:
            type_filter = st.multiselect(
                "Filter by Insight Type",
                options=insights_df["type"].unique().tolist(),
                default=insights_df["type"].unique().tolist(),
            )
        with col_f2:
            sev_filter = st.multiselect(
                "Filter by Severity",
                options=["High", "Medium", "Low"],
                default=["High", "Medium", "Low"],
            )

        displayed_insights = insights_df[
            (insights_df["type"].isin(type_filter)) &
            (insights_df["severity"].isin(sev_filter))
        ]

        # Display formatted table
        st.dataframe(
            displayed_insights,
            column_config={
                "insight_id": st.column_config.TextColumn("ID", width="small"),
                "type": st.column_config.TextColumn("Type", width="small"),
                "indicator": st.column_config.TextColumn("Indicator"),
                "entity": st.column_config.TextColumn("District / Entity"),
                "period": st.column_config.TextColumn("Period"),
                "value": st.column_config.TextColumn("Current"),
                "prev_value": st.column_config.TextColumn("Previous / Bench"),
                "change_pct": st.column_config.TextColumn("Δ %"),
                "severity": st.column_config.TextColumn("Severity", width="small"),
                "explanation": st.column_config.TextColumn("Auto-Generated Explanation", width="large"),
            },
            hide_index=True,
            use_container_width=True,
        )

        # Download button for Insights CSV
        csv_buffer = io.StringIO()
        displayed_insights.to_csv(csv_buffer, index=False)
        st.download_button(
            label="📥 Download Insights CSV (insights.csv)",
            data=csv_buffer.getvalue(),
            file_name="insights.csv",
            mime="text/csv",
        )

# ====================================================
# TAB 2: VISUALIZATIONS (Part F)
# ====================================================
with tab_viz:
    st.subheader("Data Visualizations")

    v_col1, v_col2 = st.columns(2)

    with v_col1:
        st.markdown("#### 1. Insights by Severity Breakdown")
        if not insights_df.empty:
            sev_summary = (
                insights_df.groupby(["severity", "type"])
                .size()
                .reset_index(name="count")
            )
            color_scale = alt.Scale(
                domain=["High", "Medium", "Low"],
                range=["#EF4444", "#F59E0B", "#10B981"],
            )
            chart_sev = (
                alt.Chart(sev_summary)
                .mark_bar(cornerRadiusTopLeft=4, cornerRadiusTopRight=4)
                .encode(
                    x=alt.X("severity:N", title="Severity Level", sort=["High", "Medium", "Low"]),
                    y=alt.Y("count:Q", title="Number of Insights"),
                    color=alt.Color("severity:N", scale=color_scale, legend=None),
                    tooltip=["severity", "type", "count"],
                )
                .properties(height=320)
            )
            st.altair_chart(chart_sev, use_container_width=True)
        else:
            st.info("No insights to plot.")

    with v_col2:
        st.markdown("#### 2. Indicator Distribution & Outlier Spread")
        selected_box_ind = st.selectbox(
            "Select Indicator for Outlier Spread",
            options=selected_indicators if selected_indicators else numeric_indicators,
            format_func=format_indicator_name,
            key="box_ind",
        )
        if selected_box_ind in filtered_df.columns:
            chart_box = (
                alt.Chart(filtered_df)
                .mark_boxplot(extent=1.5, color="#3B82F6")
                .encode(
                    x=alt.X("district:N", title="District"),
                    y=alt.Y(f"{selected_box_ind}:Q", title=format_indicator_name(selected_box_ind)),
                    color=alt.Color("district:N", legend=None),
                )
                .properties(height=320)
            )
            st.altair_chart(chart_box, use_container_width=True)

    st.markdown("---")
    st.markdown("#### 3. Per-District Temporal Indicator Trend Line Chart")
    trend_ind_choice = st.selectbox(
        "Select Metric for Per-District Trend Lines",
        options=selected_indicators if selected_indicators else numeric_indicators,
        format_func=format_indicator_name,
        key="line_ind",
    )

    if trend_ind_choice in filtered_df.columns:
        chart_line = (
            alt.Chart(filtered_df)
            .mark_line(point=alt.OverlayMarkDef(filled=True, size=60))
            .encode(
                x=alt.X("month:N", title="Month"),
                y=alt.Y(f"{trend_ind_choice}:Q", title=format_indicator_name(trend_ind_choice)),
                color=alt.Color("district:N", title="District"),
                tooltip=["district", "month", f"{trend_ind_choice}:Q"],
            )
            .properties(height=380)
        )
        st.altair_chart(chart_line, use_container_width=True)

# ====================================================
# TAB 3: CORRELATION MATRIX (Part D)
# ====================================================
with tab_matrix:
    st.subheader("Pearson Correlation Matrix (Part D)")

    active_numeric = [col for col in selected_indicators if col in filtered_df.columns]
    if len(active_numeric) >= 2:
        corr_matrix = compute_correlation_matrix(filtered_df, indicators=active_numeric)

        col_m1, col_m2 = st.columns([3, 2])

        with col_m1:
            st.markdown("#### Correlation Heatmap")
            # Melt for Altair heatmap
            corr_melted = corr_matrix.reset_index().melt(id_vars="index")
            corr_melted.columns = ["Indicator_1", "Indicator_2", "Correlation"]

            heatmap = (
                alt.Chart(corr_melted)
                .mark_rect()
                .encode(
                    x=alt.X("Indicator_1:N", title=None),
                    y=alt.Y("Indicator_2:N", title=None),
                    color=alt.Color("Correlation:Q", scale=alt.Scale(scheme="redblue", domain=[-1, 1])),
                    tooltip=["Indicator_1", "Indicator_2", "Correlation"],
                )
            )
            text_labels = (
                alt.Chart(corr_melted)
                .mark_text(baseline="middle")
                .encode(
                    x=alt.X("Indicator_1:N"),
                    y=alt.Y("Indicator_2:N"),
                    text=alt.Text("Correlation:Q", format=".2f"),
                    color=alt.condition(
                        "datum.Correlation > 0.5 || datum.Correlation < -0.5",
                        alt.value("white"),
                        alt.value("black"),
                    ),
                )
            )
            st.altair_chart((heatmap + text_labels).properties(height=350), use_container_width=True)

        with col_m2:
            st.markdown(f"#### Flagged Indicator Pairs (|r| ≥ {corr_threshold})")
            flagged_corr = flag_high_correlations(corr_matrix, threshold=corr_threshold)
            if not flagged_corr.empty:
                st.dataframe(
                    flagged_corr[["indicator_pair", "correlation_r", "abs_r"]],
                    column_config={
                        "indicator_pair": "Indicator Pair",
                        "correlation_r": "Pearson r",
                        "abs_r": "|r|",
                    },
                    hide_index=True,
                    use_container_width=True,
                )
            else:
                st.info(f"No indicator pairs meet threshold |r| ≥ {corr_threshold}")

            # Download correlation matrix
            corr_csv_buff = io.StringIO()
            corr_matrix.to_csv(corr_csv_buff)
            st.download_button(
                label="📥 Download Correlation Matrix CSV",
                data=corr_csv_buff.getvalue(),
                file_name="correlation_matrix.csv",
                mime="text/csv",
            )
    else:
        st.info("Select at least 2 numerical indicators to compute correlation.")

# ====================================================
# TAB 4: RAW DATA & VALIDATION (Part A)
# ====================================================
with tab_data:
    st.subheader("Data Loading & Validation Diagnostics (Part A)")

    col_d1, col_d2 = st.columns(2)

    with col_d1:
        st.markdown("#### First 5 Rows (head)")
        st.dataframe(filtered_df.head(), use_container_width=True)

        st.markdown("#### Missing-Value Count per Column")
        missing_report = get_missing_values_report(filtered_df)
        st.dataframe(missing_report, hide_index=True, use_container_width=True)

    with col_d2:
        st.markdown("#### Summary Statistics (describe)")
        st.dataframe(filtered_df.describe().round(2), use_container_width=True)

        st.markdown("#### Schema Conformance")
        if is_valid_schema:
            st.success("✅ Dataset strictly conforms to required healthcare schema.")
        else:
            st.warning(f"⚠️ Missing columns: {missing_cols}")

# Footer
st.markdown("---")
st.caption(
    "Automated Insight Generation Engine | Auto-Analytics for District-Level Healthcare Performance."
)
