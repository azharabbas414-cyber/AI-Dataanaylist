import streamlit as st
import pandas as pd
import json
import numpy as np
import plotly.express as px
import plotly.graph_objects as go

from core.calculated_metrics import _metric_definition, calculate_metric_series

from core.analytics import analyze_dataset
from ai.provider import get_ai_provider


# ============================================================
# PAGE CONFIG
# ============================================================

st.set_page_config(
    page_title="InsightAI | Dashboard",
    page_icon="📊",
    layout="wide",
)


# ============================================================
# CUSTOM CSS
# ============================================================

st.markdown(
    """
    <style>

    .dashboard-header {
        padding: 24px 28px;
        border-radius: 16px;
        margin-bottom: 24px;
        background: linear-gradient(
            135deg,
            rgba(37, 99, 235, 0.14),
            rgba(99, 102, 241, 0.08)
        );
        border: 1px solid rgba(100, 116, 139, 0.18);
    }

    .dashboard-header h1 {
        margin: 0;
        font-size: 32px;
        font-weight: 700;
    }

    .dashboard-header p {
        margin-top: 8px;
        color: #64748b;
        font-size: 15px;
    }

    .section-title {
        font-size: 21px;
        font-weight: 700;
        margin-top: 26px;
        margin-bottom: 12px;
    }

    .kpi-card {
        padding: 18px;
        border-radius: 14px;
        border: 1px solid rgba(100, 116, 139, 0.18);
        background: rgba(255, 255, 255, 0.03);
        min-height: 115px;
    }

    .kpi-label {
        font-size: 13px;
        color: #64748b;
        margin-bottom: 8px;
    }

    .kpi-value {
        font-size: 27px;
        font-weight: 700;
    }

    .insight-card {
        padding: 16px;
        border-radius: 12px;
        border: 1px solid rgba(100, 116, 139, 0.18);
        margin-bottom: 10px;
    }

    .small-muted {
        color: #64748b;
        font-size: 13px;
    }

    </style>
    """,
    unsafe_allow_html=True,
)


# ============================================================
# CHECK ACTIVE DATASET
# ============================================================

if "active_dataframe" not in st.session_state:
    st.session_state.active_dataframe = None

if st.session_state.active_dataframe is None:
    st.warning(
        "No active dataset found. Please select or upload a dataset from the Home page."
    )

    if st.button("🏠 Go to Home", type="primary"):
        st.switch_page("streamlitapp.py")

    st.stop()


raw_df = st.session_state.active_dataframe.copy()

if raw_df.empty:
    st.warning("The active dataset is empty.")
    st.stop()


# ============================================================
# GLOBAL FILTERS / SLICERS
# ============================================================

# Classification is based on the complete dataset so filter controls remain
# stable even when a filter reduces the visible rows to a small subset.
raw_analysis = analyze_dataset(raw_df)
raw_classification = raw_analysis.get("classification", {})
numeric_columns = raw_classification.get("numeric", [])
categorical_columns = raw_classification.get("categorical", [])
datetime_columns = raw_classification.get("datetime", [])

if "dashboard_filter_cat_fields" not in st.session_state:
    st.session_state.dashboard_filter_cat_fields = []
if "dashboard_filter_num_fields" not in st.session_state:
    st.session_state.dashboard_filter_num_fields = []

# Clear All removes the filter widgets themselves, returning the dashboard to
# the full dataset on the next rerun.
_clear_filters = st.button("🧹 Clear All Filters", key="dashboard_clear_all_filters")
if _clear_filters:
    for _key in list(st.session_state.keys()):
        if _key.startswith("dashboard_filter_value_") or _key.startswith("dashboard_filter_date_"):
            del st.session_state[_key]
    st.session_state.dashboard_filter_cat_fields = []
    st.session_state.dashboard_filter_num_fields = []
    st.rerun()

with st.expander("🔎 Global Filters / Slicers", expanded=True):
    st.caption("Filters below apply to KPIs, automatic charts, custom charts, and saved dashboard charts.")

    filter_cat_fields = st.multiselect(
        "Categorical filters",
        categorical_columns,
        default=[c for c in st.session_state.dashboard_filter_cat_fields if c in categorical_columns],
        key="dashboard_filter_cat_fields",
        help="Select one or more category fields to filter across the dashboard.",
    )

    filter_num_fields = st.multiselect(
        "Numeric filters",
        numeric_columns,
        default=[c for c in st.session_state.dashboard_filter_num_fields if c in numeric_columns],
        key="dashboard_filter_num_fields",
        help="Select numeric fields when you need a range filter.",
    )

    # Date range filters are available for every detected date/time column.
    date_filter_values = {}
    if datetime_columns:
        st.markdown("**Date / Time filters**")
        date_cols = st.columns(min(3, len(datetime_columns)))
        for _i, _date_col in enumerate(datetime_columns):
            _parsed = pd.to_datetime(raw_df[_date_col], errors="coerce").dropna()
            if _parsed.empty:
                continue
            _min_date = _parsed.min().date()
            _max_date = _parsed.max().date()
            _date_key = f"dashboard_filter_date_{_date_col}"
            _default_range = st.session_state.get(_date_key, (_min_date, _max_date))
            if not isinstance(_default_range, (tuple, list)) or len(_default_range) != 2:
                _default_range = (_min_date, _max_date)
            _default_range = (
                max(_min_date, _default_range[0]),
                min(_max_date, _default_range[1]),
            )
            with date_cols[_i % len(date_cols)]:
                _selected_range = st.date_input(
                    _date_col,
                    value=_default_range,
                    min_value=_min_date,
                    max_value=_max_date,
                    key=_date_key,
                )
            if isinstance(_selected_range, (tuple, list)) and len(_selected_range) == 2:
                date_filter_values[_date_col] = _selected_range

    # Categorical filters.
    cat_filter_values = {}
    if filter_cat_fields:
        st.markdown("**Category filters**")
        _cat_cols = st.columns(min(3, len(filter_cat_fields)))
        for _i, _col in enumerate(filter_cat_fields):
            _options = raw_df[_col].fillna("Missing").astype(str).drop_duplicates().sort_values().tolist()
            _key = f"dashboard_filter_value_{_col}"
            with _cat_cols[_i % len(_cat_cols)]:
                _selected = st.multiselect(
                    _col,
                    _options,
                    default=st.session_state.get(_key, []),
                    key=_key,
                )
            cat_filter_values[_col] = _selected

    # Numeric range filters.
    num_filter_values = {}
    if filter_num_fields:
        st.markdown("**Numeric range filters**")
        _num_cols = st.columns(min(2, len(filter_num_fields)))
        for _i, _col in enumerate(filter_num_fields):
            _values = pd.to_numeric(raw_df[_col], errors="coerce").dropna()
            if _values.empty:
                continue
            _min_val = float(_values.min())
            _max_val = float(_values.max())
            _key = f"dashboard_filter_value_{_col}"
            _previous = st.session_state.get(_key, (_min_val, _max_val))
            if not isinstance(_previous, (tuple, list)) or len(_previous) != 2:
                _previous = (_min_val, _max_val)
            _previous = (max(_min_val, float(_previous[0])), min(_max_val, float(_previous[1])))
            if _min_val == _max_val:
                _selected_range = _previous
                with _num_cols[_i % len(_num_cols)]:
                    st.number_input(_col, value=_min_val, disabled=True, key=_key + "_display")
            else:
                with _num_cols[_i % len(_num_cols)]:
                    _selected_range = st.slider(
                        _col,
                        min_value=_min_val,
                        max_value=_max_val,
                        value=_previous,
                        key=_key,
                    )
            num_filter_values[_col] = _selected_range

# Apply every selected filter to a dashboard-local dataframe. The original
# active dataset is never mutated.
df = raw_df.copy()

for _col, _selected in cat_filter_values.items():
    if _selected:
        df = df[df[_col].fillna("Missing").astype(str).isin(_selected)]

for _col, _selected_range in date_filter_values.items():
    if _col in df.columns and _selected_range:
        _parsed = pd.to_datetime(df[_col], errors="coerce")
        _start = pd.Timestamp(_selected_range[0])
        _end = pd.Timestamp(_selected_range[1]) + pd.Timedelta(days=1) - pd.Timedelta(nanoseconds=1)
        df = df[_parsed.between(_start, _end, inclusive="both")]

for _col, _selected_range in num_filter_values.items():
    if _col in df.columns and _selected_range:
        _values = pd.to_numeric(df[_col], errors="coerce")
        df = df[_values.between(float(_selected_range[0]), float(_selected_range[1]), inclusive="both")]

# Keep the active dashboard classification based on the filtered data for
# fields that disappear after filtering, while preserving the original field
# lists for filter controls.
analysis = analyze_dataset(df)
classification = analysis.get("classification", {})
numeric_columns = classification.get("numeric", [])
categorical_columns = classification.get("categorical", [])
datetime_columns = classification.get("datetime", [])

if df.empty:
    st.warning("The current filters return no rows. Use Clear All Filters or broaden your selections.")
    st.stop()


# ============================================================
# HEADER
# ============================================================

st.markdown(
    f"""
    <div class="dashboard-header">
        <h1>📊 Analytics Dashboard</h1>
        <p>
            Interactive overview of
            <b>{st.session_state.get("active_dataset", "Active Dataset")}</b>
            using {len(df):,} rows and {len(df.columns):,} columns.
        </p>
    </div>
    """,
    unsafe_allow_html=True,
)


# ============================================================
# KPI SECTION
# ============================================================

st.markdown('<div class="section-title">📌 Dataset Overview</div>', unsafe_allow_html=True)

total_cells = df.shape[0] * df.shape[1]
missing_cells = int(df.isna().sum().sum())

if total_cells > 0:
    completeness = ((total_cells - missing_cells) / total_cells) * 100
else:
    completeness = 100

duplicate_rows = int(df.duplicated().sum())

numeric_count = len(numeric_columns)
categorical_count = len(categorical_columns)

kpi1, kpi2, kpi3, kpi4, kpi5, kpi6 = st.columns(6)

with kpi1:
    st.markdown(
        f"""
        <div class="kpi-card">
            <div class="kpi-label">Rows</div>
            <div class="kpi-value">{len(df):,}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

with kpi2:
    st.markdown(
        f"""
        <div class="kpi-card">
            <div class="kpi-label">Columns</div>
            <div class="kpi-value">{len(df.columns):,}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

with kpi3:
    st.markdown(
        f"""
        <div class="kpi-card">
            <div class="kpi-label">Numeric Fields</div>
            <div class="kpi-value">{numeric_count:,}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

with kpi4:
    st.markdown(
        f"""
        <div class="kpi-card">
            <div class="kpi-label">Category Fields</div>
            <div class="kpi-value">{categorical_count:,}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

with kpi5:
    st.markdown(
        f"""
        <div class="kpi-card">
            <div class="kpi-label">Completeness</div>
            <div class="kpi-value">{completeness:.1f}%</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

with kpi6:
    st.markdown(
        f"""
        <div class="kpi-card">
            <div class="kpi-label">Duplicates</div>
            <div class="kpi-value">{duplicate_rows:,}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


# ============================================================
# DATASET SNAPSHOT
# ============================================================

st.markdown('<div class="section-title">🔎 Dataset Snapshot</div>', unsafe_allow_html=True)

snapshot_col1, snapshot_col2 = st.columns([1.5, 1])

with snapshot_col1:

    preview_columns = list(df.columns[:8])

    st.dataframe(
        df[preview_columns].head(10),
        use_container_width=True,
        hide_index=True,
    )

with snapshot_col2:

    structure_data = []

    for column in df.columns:
        structure_data.append(
            {
                "Column": column,
                "Type": str(df[column].dtype),
                "Missing": int(df[column].isna().sum()),
                "Unique": int(df[column].nunique(dropna=True)),
            }
        )

    structure_df = pd.DataFrame(structure_data)

    st.dataframe(
        structure_df,
        use_container_width=True,
        hide_index=True,
        height=330,
    )



# ============================================================
# CUSTOM VISUALIZATION BUILDER
# ============================================================

st.markdown(
    '<div class="section-title">🎨 Custom Visualization Builder</div>',
    unsafe_allow_html=True,
)

st.info(
    "The standard dashboard sections below are automatic. Use this builder when you want to choose the graph type yourself. "
    "It supports comparison, trend, composition, distribution, correlation and hierarchy charts."
)

all_columns = [str(c) for c in df.columns]

# ============================================================
# CALCULATED METRICS
# ============================================================
# Keep calculated metrics deterministic and shared with the Query Engine.
# These labels are exposed in the Dashboard Builder so the same formulas
# used by AI Analyst can also be used directly in charts.

_calculated_metric_candidates = {
    "Sales Value": "What is the total sales value",
    "Calculated Revenue": "What is the total calculated revenue",
    "ARPU": "What is the ARPU",
}

calculated_metric_options = {}
for _label, _question in _calculated_metric_candidates.items():
    try:
        _definition = _metric_definition(df, _question)
        if _definition:
            calculated_metric_options[_label] = _definition
    except Exception:
        pass

# Existing numeric fields + deterministic calculated metrics.
metric_options = ["Row Count"] + numeric_columns + [
    label for label in calculated_metric_options if label not in numeric_columns
]

def _is_calculated_metric(value):
    return value in calculated_metric_options

def _metric_series(dataframe, metric):
    if metric == "Row Count":
        return pd.Series(1, index=dataframe.index, dtype="int64")
    if _is_calculated_metric(metric):
        return calculate_metric_series(dataframe, calculated_metric_options[metric])
    return pd.to_numeric(dataframe[metric], errors="coerce")

optional_color_columns = ["None"] + categorical_columns
chart_types = [
    "Bar",
    "Line",
    "Area",
    "Pie",
    "Donut",
    "Scatter",
    "Histogram",
    "Box",
    "Violin",
    "Strip",
    "Heatmap",
    "Treemap",
    "Sunburst",
    "Funnel",
]

builder_top = st.columns([1.25, 1.25, 1.0, 1.0])
with builder_top[0]:
    custom_chart_type = st.selectbox(
        "Graph Type",
        chart_types,
        key="dashboard_custom_chart_type",
        help="Choose the visualization instead of using only the dashboard's fixed charts.",
    )
with builder_top[1]:
    custom_title = st.text_input(
        "Chart Title",
        value="InsightAI Custom Chart",
        key="dashboard_custom_chart_title",
    )
with builder_top[2]:
    custom_color = st.selectbox(
        "Color / Group",
        optional_color_columns,
        key="dashboard_custom_color",
    )
with builder_top[3]:
    custom_aggregation = st.selectbox(
        "Aggregation",
        ["Sum", "Mean", "Median", "Min", "Max", "Count"],
        key="dashboard_custom_aggregation",
        help="Used for charts that aggregate a metric by a dimension.",
    )

# Field selectors change slightly according to the selected chart.
if custom_chart_type in {"Bar", "Line", "Area", "Funnel"}:
    c1, c2 = st.columns(2)
    with c1:
        custom_x = st.selectbox("Category / X-axis", all_columns, key="dashboard_custom_x")
    with c2:
        custom_y = st.selectbox("Metric / Y-axis", metric_options, key="dashboard_custom_y")

elif custom_chart_type in {"Pie", "Donut"}:
    # Pie/Donut charts represent a part-to-whole relationship.
    # Use a categorical field for the slices and a numeric field (or Row Count)
    # for the slice size. Avoid allowing the same field to be selected twice.
    pie_category_options = categorical_columns if categorical_columns else all_columns
    pie_value_options = metric_options

    c1, c2 = st.columns(2)
    with c1:
        custom_x = st.selectbox(
            "Category",
            pie_category_options,
            key="dashboard_custom_x",
            help="Each category becomes a slice of the pie/donut.",
        )
    with c2:
        custom_y = st.selectbox(
            "Value",
            pie_value_options,
            key="dashboard_custom_y",
            help="Use Row Count for number of records, or a numeric field for Sum/Mean/etc.",
        )
    if custom_color != "None":
        st.caption("Color / Group is not used for Pie/Donut charts; the Category field controls the slices.")

elif custom_chart_type == "Scatter":
    c1, c2 = st.columns(2)
    with c1:
        custom_x = st.selectbox("X-axis (numeric)", numeric_columns, key="dashboard_custom_x") if numeric_columns else None
    with c2:
        custom_y = st.selectbox("Y-axis (numeric)", numeric_columns, key="dashboard_custom_y") if numeric_columns else None

elif custom_chart_type == "Histogram":
    custom_x = st.selectbox("Numeric field", numeric_columns, key="dashboard_custom_x") if numeric_columns else None
    custom_y = None

elif custom_chart_type in {"Box", "Violin", "Strip"}:
    c1, c2 = st.columns(2)
    with c1:
        custom_x = st.selectbox("Category (optional)", ["None"] + categorical_columns, key="dashboard_custom_x")
    with c2:
        custom_y = st.selectbox("Numeric field", numeric_columns, key="dashboard_custom_y") if numeric_columns else None

elif custom_chart_type == "Heatmap":
    custom_x = None
    custom_y = None

else:  # Treemap / Sunburst
    hierarchy_options = ["None"] + categorical_columns
    h1, h2, h3 = st.columns(3)
    with h1:
        level_1 = st.selectbox("Level 1", hierarchy_options, key="dashboard_custom_level_1")
    with h2:
        level_2 = st.selectbox("Level 2", hierarchy_options, key="dashboard_custom_level_2")
    with h3:
        level_3 = st.selectbox("Level 3", hierarchy_options, key="dashboard_custom_level_3")
    custom_x = level_1
    custom_y = st.selectbox("Size / Value", metric_options, key="dashboard_custom_y")

# Optional ranking for aggregated charts. This is applied after aggregation so
# Top/Bottom N always uses the actual calculated metric values.
ranking_enabled_types = {"Bar", "Line", "Area", "Pie", "Donut", "Funnel", "Treemap", "Sunburst"}
if custom_chart_type in ranking_enabled_types:
    rank_c1, rank_c2 = st.columns([1.2, 1.0])
    with rank_c1:
        custom_ranking = st.selectbox(
            "Ranking",
            ["None", "Top N", "Bottom N"],
            key="dashboard_custom_ranking",
            help="Limit the chart to the highest or lowest N aggregated values.",
        )
    with rank_c2:
        custom_rank_n = st.number_input(
            "Number of items",
            min_value=1,
            max_value=100,
            value=10,
            step=1,
            key="dashboard_custom_rank_n",
        )
else:
    custom_ranking = "None"
    custom_rank_n = 10

def _apply_ranking(grouped, value_field):
    """Apply Top/Bottom N after deterministic aggregation."""
    if custom_ranking == "None" or grouped is None or grouped.empty:
        return grouped
    values = pd.to_numeric(grouped[value_field], errors="coerce")
    grouped = grouped.assign(__ranking_value__=values)
    ascending = custom_ranking == "Bottom N"
    grouped = (
        grouped.sort_values("__ranking_value__", ascending=ascending, kind="stable")
        .head(int(custom_rank_n))
        .drop(columns=["__ranking_value__"])
        .reset_index(drop=True)
    )
    return grouped

def _apply_ranking(grouped, value_field, ranking, rank_n):
    """Apply Top/Bottom N after deterministic aggregation."""
    if ranking == "None" or grouped is None or grouped.empty:
        return grouped
    values = pd.to_numeric(grouped[value_field], errors="coerce")
    grouped = grouped.assign(__ranking_value__=values)
    ascending = ranking == "Bottom N"
    grouped = (
        grouped.sort_values("__ranking_value__", ascending=ascending, kind="stable")
        .head(int(rank_n))
        .drop(columns=["__ranking_value__"])
        .reset_index(drop=True)
    )
    return grouped


def _build_chart_evidence(dataframe, config):
    """Create compact, deterministic evidence for Explain This Chart."""
    fig = _build_custom_figure(dataframe, config)
    records = []
    for trace in fig.data:
        x_values = list(trace.x) if trace.x is not None else []
        y_values = list(trace.y) if trace.y is not None else []
        n = max(len(x_values), len(y_values))
        for i in range(n):
            row = {}
            if i < len(x_values):
                row["x"] = x_values[i]
            if i < len(y_values):
                row["y"] = y_values[i]
            if getattr(trace, "name", None):
                row["series"] = trace.name
            records.append(row)
    evidence = pd.DataFrame(records)
    if not evidence.empty and "y" in evidence.columns:
        evidence["y_numeric"] = pd.to_numeric(evidence["y"], errors="coerce")
    return fig, evidence


def _fallback_chart_explanation(dataframe, config, evidence):
    """Deterministic explanation used when no AI provider is configured."""
    title = config.get("title", "Chart")
    lines = ["### What happened?", f"**{title}** is based on **{len(dataframe):,} filtered rows**."]
    if evidence.empty or "y_numeric" not in evidence.columns:
        lines.append("No numeric chart series is available for deeper ranking analysis.")
        return "\n\n".join(lines)
    valid = evidence.dropna(subset=["y_numeric"]).copy()
    if valid.empty:
        return "\n\n".join(lines + ["No valid numeric values are available in the chart evidence."])
    max_row = valid.loc[valid["y_numeric"].idxmax()]
    min_row = valid.loc[valid["y_numeric"].idxmin()]
    total = valid["y_numeric"].sum()
    lines.extend([
        f"- Highest value: **{max_row.get('x', 'N/A')}** ({max_row['y_numeric']:,.2f})",
        f"- Lowest value: **{min_row.get('x', 'N/A')}** ({min_row['y_numeric']:,.2f})",
        f"- Total displayed value: **{total:,.2f}**",
        "",
        "### What should I investigate next?",
        "- Examine the highest-value category or period in more detail.",
        "- Compare the result against the active dashboard filters.",
        "- Drill into the underlying product, customer, or time dimension if available.",
    ])
    return "\n".join(lines)


def _explain_chart(dataframe, config):
    """Explain a chart using actual chart data and current dashboard filters."""
    _, evidence = _build_chart_evidence(dataframe, config)
    compact = evidence.head(30).to_dict(orient="records") if not evidence.empty else []
    prompt = f"""
You are InsightAI explaining a dashboard chart.

Chart configuration:
{json.dumps(config, default=str, indent=2)}

Current filtered dataset:
- Rows: {len(dataframe):,}
- Columns: {len(dataframe.columns):,}

Actual chart evidence calculated from the filtered dataframe:
{json.dumps(compact, default=str, indent=2)}

Instructions:
1. Explain only what the supplied chart evidence supports.
2. Start with 'What happened?' and identify the most important pattern.
3. Add 'What stands out?' with concrete values where useful.
4. Add 'What should I investigate next?' with 2-4 actionable follow-ups.
5. Do not invent causes. If a cause is not proven, describe it as something to investigate.
6. Keep it concise and professional.
""".strip()
    try:
        provider = get_ai_provider()
        if provider.is_available():
            return provider.analyze(prompt)
    except Exception:
        pass
    return _fallback_chart_explanation(dataframe, config, evidence)


def _build_custom_figure(dataframe, config):
    """Build a custom Plotly figure from a chart specification and dataframe."""
    chart_type = config["chart_type"]
    title = config["title"]
    color = config.get("color", "None")
    aggregation = config.get("aggregation", "Sum")
    x = config.get("x")
    y = config.get("y")
    ranking = config.get("ranking", "None")
    rank_n = int(config.get("rank_n", 10))

    color_arg = None if color == "None" else color

    # Re-detect calculated metrics against the current filtered dataframe so
    # saved charts always use the same deterministic formulas on filtered data.
    local_metric_options = {}
    for label, question in _calculated_metric_candidates.items():
        try:
            definition = _metric_definition(dataframe, question)
            if definition:
                local_metric_options[label] = definition
        except Exception:
            pass

    def is_calc(metric):
        return metric in local_metric_options

    def metric_series(metric):
        if metric == "Row Count":
            return pd.Series(1, index=dataframe.index, dtype="int64")
        if is_calc(metric):
            return calculate_metric_series(dataframe, local_metric_options[metric])
        return pd.to_numeric(dataframe[metric], errors="coerce")

    if chart_type == "Heatmap":
        local_numeric = dataframe.select_dtypes(include=np.number).columns.tolist()
        if len(local_numeric) < 2:
            raise ValueError("Heatmap requires at least two numeric columns.")
        matrix = dataframe[local_numeric].apply(pd.to_numeric, errors="coerce").corr()
        return px.imshow(matrix, text_auto=".2f", aspect="auto", title=title)

    if chart_type == "Scatter":
        if not x or not y:
            raise ValueError("Scatter requires two numeric fields.")
        cols = [x, y] + ([color] if color_arg and color not in [x, y] else [])
        plot_df = dataframe[cols].copy()
        plot_df[x] = pd.to_numeric(plot_df[x], errors="coerce")
        plot_df[y] = pd.to_numeric(plot_df[y], errors="coerce")
        plot_df = plot_df.dropna(subset=[x, y])
        if plot_df.empty:
            raise ValueError("No valid numeric rows are available for the selected scatter plot.")
        return px.scatter(plot_df, x=x, y=y, color=color_arg, title=title,
                          trendline="ols" if len(plot_df) >= 3 else None)

    if chart_type == "Histogram":
        if not x:
            raise ValueError("Histogram requires a numeric field.")
        values = pd.to_numeric(dataframe[x], errors="coerce")
        plot_df = pd.DataFrame({x: values}).dropna()
        if plot_df.empty:
            raise ValueError("No valid numeric values are available for the histogram.")
        return px.histogram(plot_df, x=x, nbins=30, marginal="box", title=title)

    if chart_type in {"Box", "Violin", "Strip"}:
        if not y:
            raise ValueError(f"{chart_type} requires a numeric field.")
        cols = [y]
        if x and x != "None":
            cols.insert(0, x)
        if color_arg and color_arg not in cols:
            cols.append(color_arg)
        plot_df = dataframe[cols].copy()
        plot_df[y] = pd.to_numeric(plot_df[y], errors="coerce")
        plot_df = plot_df.dropna(subset=[y])
        if plot_df.empty:
            raise ValueError("No valid values are available for this distribution chart.")
        x_arg = None if x == "None" else x
        if chart_type == "Box":
            return px.box(plot_df, x=x_arg, y=y, color=color_arg, title=title, points="outliers")
        if chart_type == "Violin":
            return px.violin(plot_df, x=x_arg, y=y, color=color_arg, box=True, points=False, title=title)
        return px.strip(plot_df, x=x_arg, y=y, color=color_arg, title=title)

    if chart_type in {"Treemap", "Sunburst"}:
        levels = [level for level in config.get("levels", []) if level and level != "None"]
        levels = list(dict.fromkeys(levels))
        if not levels:
            raise ValueError(f"{chart_type} requires at least one category level.")
        cols = levels + ([] if y == "Row Count" or is_calc(y) else [y])
        work = dataframe[cols].copy()
        if is_calc(y):
            work[y] = metric_series(y)
        for level in levels:
            work[level] = work[level].fillna("Missing").astype(str)
        if y == "Row Count":
            work["__value__"] = 1
            value_field = "__value__"
        else:
            if not is_calc(y):
                work[y] = pd.to_numeric(work[y], errors="coerce")
            work = work.dropna(subset=[y])
            value_field = y
        if work.empty:
            raise ValueError("No valid rows are available for this hierarchy chart.")
        grouped = work.groupby(levels, as_index=False)[value_field].agg(aggregation.lower())
        grouped = _apply_ranking(grouped, value_field, ranking, rank_n)
        if chart_type == "Treemap":
            return px.treemap(grouped, path=levels, values=value_field, color=value_field, title=title)
        return px.sunburst(grouped, path=levels, values=value_field, color=value_field, title=title)

    if not x:
        raise ValueError("A category / X-axis field is required.")

    cols = []
    for col in [x, (y if y != "Row Count" and not is_calc(y) else None), color_arg]:
        if col and col not in cols:
            cols.append(col)
    work = dataframe[cols].copy()
    if is_calc(y):
        work[y] = metric_series(y)
    work[x] = work[x].fillna("Missing").astype(str)

    if chart_type in {"Pie", "Donut"}:
        if y == x:
            raise ValueError("Category and Value must be different fields.")
        if y == "Row Count":
            grouped = work.groupby(x, as_index=False).size().rename(columns={"size": "Row Count"})
            value_field = "Row Count"
        else:
            if not is_calc(y):
                work[y] = pd.to_numeric(work[y], errors="coerce")
            work = work.dropna(subset=[y])
            if work.empty:
                raise ValueError("No valid numeric values are available for this chart.")
            grouped = work.groupby(x, as_index=False)[y].agg(aggregation.lower())
            value_field = y
        grouped = _apply_ranking(grouped, value_field, ranking, rank_n)
        if (pd.to_numeric(grouped[value_field], errors="coerce") < 0).any():
            raise ValueError("Pie and donut charts require non-negative values.")
        return px.pie(grouped, names=x, values=value_field, title=title,
                      hole=0.45 if chart_type == "Donut" else 0)

    group_cols = [x] + ([color_arg] if color_arg and color_arg != x else [])
    if y == "Row Count":
        grouped = work.groupby(group_cols, as_index=False).size().rename(columns={"size": "Row Count"})
        value_field = "Row Count"
    else:
        if not is_calc(y):
            work[y] = pd.to_numeric(work[y], errors="coerce")
        work = work.dropna(subset=[y])
        if work.empty:
            raise ValueError("No valid numeric values are available for this chart.")
        grouped = work.groupby(group_cols, as_index=False)[y].agg(aggregation.lower())
        value_field = y
    grouped = _apply_ranking(grouped, value_field, ranking, rank_n)

    if chart_type == "Bar":
        return px.bar(grouped, x=x, y=value_field, color=color_arg, title=title)
    if chart_type == "Line":
        return px.line(grouped, x=x, y=value_field, color=color_arg, markers=True, title=title)
    if chart_type == "Area":
        return px.area(grouped, x=x, y=value_field, color=color_arg, title=title)
    if chart_type == "Funnel":
        return px.funnel(grouped, x=value_field, y=x, color=color_arg, title=title)
    raise ValueError("Unsupported chart type.")


_current_config = {
    "chart_type": custom_chart_type,
    "title": custom_title,
    "color": custom_color,
    "aggregation": custom_aggregation,
    "x": custom_x,
    "y": custom_y,
    "ranking": custom_ranking,
    "rank_n": int(custom_rank_n),
}
if custom_chart_type in {"Treemap", "Sunburst"}:
    _current_config["levels"] = [level_1, level_2, level_3]

if st.button("📊 Generate Custom Visualization", type="primary", use_container_width=True, key="dashboard_generate_custom_chart"):
    try:
        fig = _build_custom_figure(df, _current_config)
        fig.update_layout(height=520, margin=dict(l=20, r=20, t=70, b=20))
        st.session_state["dashboard_custom_chart_figure"] = fig
        st.session_state["dashboard_custom_chart_config"] = _current_config.copy()
        st.session_state["dashboard_custom_chart_title_value"] = custom_title
    except Exception as exc:
        st.error(f"Unable to generate the selected visualization: {exc}")

# Recalculate the last generated custom chart whenever a global filter changes.
# This keeps the preview synchronized with the filtered dataset without
# requiring the user to press Generate again.
if st.session_state.get("dashboard_custom_chart_config") is not None:
    try:
        _live_fig = _build_custom_figure(df, st.session_state["dashboard_custom_chart_config"])
        _live_fig.update_layout(height=520, margin=dict(l=20, r=20, t=70, b=20))
        st.session_state["dashboard_custom_chart_figure"] = _live_fig
    except Exception:
        pass

if st.session_state.get("dashboard_custom_chart_figure") is not None:
    st.plotly_chart(
        st.session_state["dashboard_custom_chart_figure"],
        use_container_width=True,
        key="dashboard_custom_chart_output",
    )
    st.caption("Custom visualization generated from the currently filtered dataset.")

    if st.button("➕ Add to My Dashboard", type="secondary", use_container_width=True, key="dashboard_add_saved_chart"):
        if "dashboard_saved_charts" not in st.session_state:
            st.session_state["dashboard_saved_charts"] = []
        config = st.session_state.get("dashboard_custom_chart_config", _current_config.copy())
        st.session_state["dashboard_saved_charts"].append({"config": config.copy()})
        st.success("Chart added to My Dashboard.")

    if st.button("🤖 Explain This Chart", type="secondary", use_container_width=True, key="dashboard_explain_custom_chart"):
        with st.spinner("Analyzing chart evidence..."):
            try:
                st.session_state["dashboard_custom_chart_explanation"] = _explain_chart(
                    df, st.session_state.get("dashboard_custom_chart_config", _current_config)
                )
            except Exception as exc:
                st.session_state["dashboard_custom_chart_explanation"] = f"Unable to explain this chart: {exc}"

    if st.session_state.get("dashboard_custom_chart_explanation"):
        with st.expander("🤖 Explain This Chart", expanded=True):
            st.markdown(st.session_state["dashboard_custom_chart_explanation"])


# ============================================================
# SAVED DASHBOARD
# ============================================================

if st.session_state.get("dashboard_saved_charts"):
    st.markdown('<div class="section-title">📌 My Dashboard</div>', unsafe_allow_html=True)
    st.caption("Saved charts automatically recalculate when Global Filters / Slicers change.")

    saved = st.session_state["dashboard_saved_charts"]
    for _idx, _saved in enumerate(saved):
        _config = _saved.get("config", {})
        _left, _right = st.columns([6, 1])
        with _left:
            st.markdown(f"**{_config.get('title', 'Saved Chart')}**")
        with _right:
            if st.button("🗑️ Remove", key=f"dashboard_remove_saved_{_idx}"):
                st.session_state["dashboard_saved_charts"].pop(_idx)
                st.rerun()
        try:
            if _config:
                _saved_fig = _build_custom_figure(df, _config)
                _saved_fig.update_layout(height=460, margin=dict(l=20, r=20, t=70, b=20))
                st.plotly_chart(_saved_fig, use_container_width=True, key=f"dashboard_saved_chart_{_idx}")
            elif _saved.get("figure"):
                # Backward compatibility for charts saved by the previous
                # session-state format. They remain viewable until removed.
                st.plotly_chart(go.Figure(_saved["figure"]), use_container_width=True, key=f"dashboard_saved_chart_{_idx}")
            else:
                st.info("This saved chart has no reusable configuration. Remove it and save it again.")
        except Exception as _exc:
            st.warning(f"Saved chart could not be recalculated with the current filters: {_exc}")
        if st.button("🤖 Explain This Chart", key=f"dashboard_explain_saved_{_idx}"):
            with st.spinner("Analyzing chart evidence..."):
                try:
                    st.session_state[f"dashboard_saved_explanation_{_idx}"] = _explain_chart(df, _config)
                except Exception as _exc:
                    st.session_state[f"dashboard_saved_explanation_{_idx}"] = f"Unable to explain this chart: {_exc}"
        if st.session_state.get(f"dashboard_saved_explanation_{_idx}"):
            with st.expander("🤖 AI Explanation", expanded=True):
                st.markdown(st.session_state[f"dashboard_saved_explanation_{_idx}"])
        st.divider()


# ============================================================
# PIE CHARTS
# ============================================================

st.markdown(
    '<div class="section-title">🥧 Composition Analysis</div>',
    unsafe_allow_html=True,
)

pie_col1, pie_col2 = st.columns(2)


# ------------------------------------------------------------
# PIE 1 — CATEGORY DISTRIBUTION
# ------------------------------------------------------------

with pie_col1:

    if categorical_columns:

        selected_category = st.selectbox(
            "Category",
            categorical_columns,
            key="dashboard_pie_category",
        )

        category_counts = (
            df[selected_category]
            .fillna("Missing")
            .astype(str)
            .value_counts()
            .reset_index()
        )

        category_counts.columns = ["Category", "Count"]

        # Keep pie charts readable
        if len(category_counts) > 8:

            top_values = category_counts.head(7).copy()

            other_count = category_counts.iloc[7:]["Count"].sum()

            if other_count > 0:
                top_values.loc[len(top_values)] = [
                    "Other",
                    other_count,
                ]

            category_counts = top_values

        fig = px.pie(
            category_counts,
            names="Category",
            values="Count",
            hole=0.42,
            title=f"Distribution of {selected_category}",
        )

        fig.update_layout(
            height=400,
            margin=dict(l=20, r=20, t=60, b=20),
            legend_title_text="",
        )

        fig.update_traces(
            textposition="inside",
            textinfo="percent+label",
        )

        st.plotly_chart(
            fig,
            use_container_width=True,
        )

    else:

        st.info(
            "No categorical columns are available for a distribution pie chart."
        )


# ------------------------------------------------------------
# PIE 2 — NUMERIC CONTRIBUTION BY CATEGORY
# ------------------------------------------------------------

with pie_col2:

    if categorical_columns and numeric_columns:

        selected_category_2 = st.selectbox(
            "Category for contribution",
            categorical_columns,
            key="dashboard_pie_category_2",
        )

        selected_metric = st.selectbox(
            "Numeric metric",
            numeric_columns,
            key="dashboard_pie_metric",
        )

        contribution_df = df[
            [selected_category_2, selected_metric]
        ].copy()

        contribution_df[selected_category_2] = (
            contribution_df[selected_category_2]
            .fillna("Missing")
            .astype(str)
        )

        contribution_df[selected_metric] = pd.to_numeric(
            contribution_df[selected_metric],
            errors="coerce",
        )

        contribution_df = contribution_df.dropna(
            subset=[selected_metric]
        )

        contribution_df = (
            contribution_df
            .groupby(selected_category_2, as_index=False)[selected_metric]
            .sum()
            .sort_values(selected_metric, ascending=False)
        )

        if not contribution_df.empty:

            if len(contribution_df) > 8:

                top_values = contribution_df.head(7).copy()

                other_value = contribution_df.iloc[7:][
                    selected_metric
                ].sum()

                if other_value != 0:

                    other_row = pd.DataFrame(
                        {
                            selected_category_2: ["Other"],
                            selected_metric: [other_value],
                        }
                    )

                    top_values = pd.concat(
                        [top_values, other_row],
                        ignore_index=True,
                    )

                contribution_df = top_values

            fig = px.pie(
                contribution_df,
                names=selected_category_2,
                values=selected_metric,
                hole=0.42,
                title=f"{selected_metric} Contribution by {selected_category_2}",
            )

            fig.update_layout(
                height=400,
                margin=dict(l=20, r=20, t=60, b=20),
                legend_title_text="",
            )

            fig.update_traces(
                textposition="inside",
                textinfo="percent+label",
            )

            st.plotly_chart(
                fig,
                use_container_width=True,
            )

        else:

            st.info(
                "No valid numeric data is available for this contribution chart."
            )

    else:

        st.info(
            "A categorical and numeric column are required for contribution analysis."
        )


# ============================================================
# TREND ANALYSIS
# ============================================================

st.markdown(
    '<div class="section-title">📈 Trend Analysis</div>',
    unsafe_allow_html=True,
)

if datetime_columns and numeric_columns:

    trend_date = st.selectbox(
        "Date / Time Field",
        datetime_columns,
        key="dashboard_trend_date",
    )

    trend_metric = st.selectbox(
        "Metric",
        numeric_columns,
        key="dashboard_trend_metric",
    )

    trend_df = df[[trend_date, trend_metric]].copy()

    trend_df[trend_date] = pd.to_datetime(
        trend_df[trend_date],
        errors="coerce",
    )

    trend_df[trend_metric] = pd.to_numeric(
        trend_df[trend_metric],
        errors="coerce",
    )

    trend_df = trend_df.dropna()

    if not trend_df.empty:

        trend_df = (
            trend_df
            .groupby(trend_date, as_index=False)[trend_metric]
            .sum()
            .sort_values(trend_date)
        )

        fig = px.line(
            trend_df,
            x=trend_date,
            y=trend_metric,
            markers=True,
            title=f"{trend_metric} Over Time",
        )

        fig.update_layout(
            height=430,
            margin=dict(l=20, r=20, t=60, b=20),
        )

        st.plotly_chart(
            fig,
            use_container_width=True,
        )

    else:

        st.info("The selected date and metric do not contain enough valid data.")

else:

    st.info(
        "A recognizable date/time column and numeric column are required for trend analysis."
    )


# ============================================================
# CATEGORY PERFORMANCE
# ============================================================

st.markdown(
    '<div class="section-title">📊 Category Performance</div>',
    unsafe_allow_html=True,
)

if categorical_columns and numeric_columns:

    category_col, metric_col = st.columns(2)

    with category_col:

        performance_category = st.selectbox(
            "Category",
            categorical_columns,
            key="dashboard_performance_category",
        )

    with metric_col:

        performance_metric = st.selectbox(
            "Metric",
            numeric_columns,
            key="dashboard_performance_metric",
        )

    performance_df = df[
        [performance_category, performance_metric]
    ].copy()

    performance_df[performance_category] = (
        performance_df[performance_category]
        .fillna("Missing")
        .astype(str)
    )

    performance_df[performance_metric] = pd.to_numeric(
        performance_df[performance_metric],
        errors="coerce",
    )

    performance_df = performance_df.dropna(
        subset=[performance_metric]
    )

    performance_df = (
        performance_df
        .groupby(performance_category, as_index=False)[performance_metric]
        .sum()
        .sort_values(performance_metric, ascending=False)
    )

    if not performance_df.empty:

        fig = px.bar(
            performance_df,
            x=performance_category,
            y=performance_metric,
            text_auto=".2s",
            title=f"{performance_metric} by {performance_category}",
        )

        fig.update_layout(
            height=430,
            margin=dict(l=20, r=20, t=60, b=20),
        )

        st.plotly_chart(
            fig,
            use_container_width=True,
        )

else:

    st.info(
        "Categorical and numeric fields are required for category performance."
    )


# ============================================================
# NUMERIC DISTRIBUTION
# ============================================================

st.markdown(
    '<div class="section-title">📦 Numeric Distribution</div>',
    unsafe_allow_html=True,
)

if numeric_columns:

    distribution_metric = st.selectbox(
        "Select numeric field",
        numeric_columns,
        key="dashboard_distribution_metric",
    )

    distribution_values = pd.to_numeric(
        df[distribution_metric],
        errors="coerce",
    ).dropna()

    if not distribution_values.empty:

        distribution_df = pd.DataFrame(
            {
                distribution_metric: distribution_values
            }
        )

        fig = px.histogram(
            distribution_df,
            x=distribution_metric,
            marginal="box",
            nbins=30,
            title=f"Distribution of {distribution_metric}",
        )

        fig.update_layout(
            height=430,
            margin=dict(l=20, r=20, t=60, b=20),
        )

        st.plotly_chart(
            fig,
            use_container_width=True,
        )

    else:

        st.info("No valid numeric values available.")

else:

    st.info("No numeric columns detected.")


# ============================================================
# CORRELATION HEATMAP
# ============================================================

st.markdown(
    '<div class="section-title">🔥 Correlation Analysis</div>',
    unsafe_allow_html=True,
)

if len(numeric_columns) >= 2:

    correlation_df = df[numeric_columns].apply(
        pd.to_numeric,
        errors="coerce",
    )

    corr_matrix = correlation_df.corr()

    fig = px.imshow(
        corr_matrix,
        text_auto=".2f",
        aspect="auto",
        title="Numeric Correlation Matrix",
    )

    fig.update_layout(
        height=500,
        margin=dict(l=20, r=20, t=60, b=20),
    )

    st.plotly_chart(
        fig,
        use_container_width=True,
    )

else:

    st.info(
        "At least two numeric columns are required for correlation analysis."
    )


# ============================================================
# ANOMALY SUMMARY
# ============================================================

st.markdown(
    '<div class="section-title">🚨 Anomaly Summary</div>',
    unsafe_allow_html=True,
)

try:

    outliers = analysis.get("outliers", {})

    if isinstance(outliers, dict) and outliers:

        anomaly_rows = []

        for column, values in outliers.items():

            if isinstance(values, pd.DataFrame):

                count = len(values)

            elif isinstance(values, (list, tuple, np.ndarray, pd.Series)):

                count = len(values)

            elif isinstance(values, int):

                count = values

            else:

                count = 0

            anomaly_rows.append(
                {
                    "Column": column,
                    "Anomalies": count,
                }
            )

        anomaly_df = pd.DataFrame(anomaly_rows)

        if not anomaly_df.empty:

            anomaly_df = anomaly_df.sort_values(
                "Anomalies",
                ascending=False,
            )

            fig = px.bar(
                anomaly_df,
                x="Column",
                y="Anomalies",
                text_auto=True,
                title="Potential Outliers by Column",
            )

            fig.update_layout(
                height=400,
                margin=dict(l=20, r=20, t=60, b=20),
            )

            st.plotly_chart(
                fig,
                use_container_width=True,
            )

        else:

            st.success("No significant anomalies detected.")

    else:

        st.success("No significant anomalies detected.")

except Exception:

    st.info(
        "Anomaly information is not available for this dataset."
    )


# ============================================================
# AUTOMATIC INSIGHTS
# ============================================================

st.markdown(
    '<div class="section-title">💡 Automatic Insights</div>',
    unsafe_allow_html=True,
)

findings = analysis.get("findings", [])

if findings:

    for finding in findings[:8]:

        st.markdown(
            f"""
            <div class="insight-card">
                💡 {finding}
            </div>
            """,
            unsafe_allow_html=True,
        )

else:

    # Generate a few generic insights when the analytics engine
    # does not return findings.

    if duplicate_rows > 0:

        st.markdown(
            f"""
            <div class="insight-card">
                ⚠️ The dataset contains {duplicate_rows:,} duplicate rows.
            </div>
            """,
            unsafe_allow_html=True,
        )

    if missing_cells > 0:

        st.markdown(
            f"""
            <div class="insight-card">
                ⚠️ The dataset contains {missing_cells:,} missing cells.
            </div>
            """,
            unsafe_allow_html=True,
        )

    if not duplicate_rows and not missing_cells:

        st.markdown(
            """
            <div class="insight-card">
                ✅ No duplicate rows or missing cells were detected.
            </div>
            """,
            unsafe_allow_html=True,
        )


# ============================================================
# DATA STRUCTURE
# ============================================================

st.markdown(
    '<div class="section-title">🧬 Data Structure</div>',
    unsafe_allow_html=True,
)

structure_cols = st.columns(3)

with structure_cols[0]:

    st.metric(
        "Numeric Fields",
        len(numeric_columns),
    )

    if numeric_columns:
        st.caption(", ".join(numeric_columns[:10]))

with structure_cols[1]:

    st.metric(
        "Categorical Fields",
        len(categorical_columns),
    )

    if categorical_columns:
        st.caption(", ".join(categorical_columns[:10]))

with structure_cols[2]:

    st.metric(
        "Date / Time Fields",
        len(datetime_columns),
    )

    if datetime_columns:
        st.caption(", ".join(datetime_columns[:10]))


# ============================================================
# FOOTER
# ============================================================

st.divider()

st.caption(
    "InsightAI • AI-Powered Data Analytics & Decision Intelligence Platform"
)
