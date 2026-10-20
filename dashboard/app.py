from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import streamlit as st
from sqlalchemy import Boolean, Column, DateTime, Integer, String, Table, Text, insert, select

from auth import (
    Base,
    SessionLocal,
    User,
    engine,
    initialize_database,
    require_login,
    logout,
)
from permissions import has_permission, require_permission

# -----------------------------------------------------------------------------
# Page setup and visual system
# -----------------------------------------------------------------------------
st.set_page_config(
    page_title="RetailPulse | Retail Intelligence",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown(
    """
    <style>
    :root { color-scheme: dark; }
    .stApp { background: #101318; color: #e9edf4; }
    [data-testid="stHeader"] { background: rgba(16,19,24,.97); }
    [data-testid="stSidebar"] { background: #171b22; border-right: 1px solid #2b3039; }
    [data-testid="stSidebar"] * { color: #d9dee8; }
    [data-testid="stSidebar"] [data-testid="stRadio"] label { padding: .42rem .6rem; border-radius: 6px; }
    [data-testid="stSidebar"] [data-testid="stRadio"] label:has(input:checked) { background: #ff762b; color: white; }
    [data-testid="stSidebar"] [data-testid="stRadio"] label:has(input:checked) p { color: white; font-weight: 700; }
    .block-container { padding-top: 1.1rem; padding-bottom: 2rem; max-width: 1800px; }
    h1, h2, h3 { letter-spacing: -.025em; }
    h1 { font-weight: 750; font-size: 1.8rem; }
    h2, h3 { font-weight: 680; }
    [data-testid="stMetric"] { background: linear-gradient(145deg,#20252d,#1a1f26); border: 1px solid #303640; padding: 14px 16px; border-radius: 9px; min-height: 108px; }
    [data-testid="stMetricLabel"] { color: #aab2bf; font-size: .82rem; }
    [data-testid="stMetricValue"] { color: #f6f7fa; font-size: 1.55rem; }
    [data-testid="stMetricDelta"] { font-size: .78rem; }
    div[data-testid="stVerticalBlockBorderWrapper"] { background: #191e25; border-color: #303640 !important; border-radius: 10px; }
    .rp-eyebrow { color:#ff8b4b; font-size:.7rem; font-weight:750; letter-spacing:.14em; text-transform:uppercase; }
    .rp-subtitle { color:#9ea7b5; margin-top:-.5rem; font-size:.9rem; }
    .rp-pill { display:inline-block; padding:5px 10px; border-radius:999px; background:#292f38; color:#ffb07e; font-size:.78rem; border:1px solid #3b424d; }
    div.stButton > button, div.stFormSubmitButton > button { border-radius: 7px; font-weight: 650; border: 1px solid #424954; }
    div.stButton > button[kind="primary"], div.stFormSubmitButton > button[kind="primary"] { background:#ff762b; border-color:#ff762b; color:white; }
    [data-testid="stDataFrame"] { border: 1px solid #303640; border-radius: 8px; overflow: hidden; }
    input, textarea, [data-baseweb="select"] > div { background-color:#20252d !important; }
    hr { border-color: #303640; }
    .rp-ticker { overflow:hidden; white-space:nowrap; border:1px solid #343b46; background:linear-gradient(90deg,#1b2028,#252a32,#1b2028); border-radius:8px; padding:10px 0; margin:0 0 1rem; }
    .rp-ticker-track { display:inline-block; padding-left:100%; animation:rp-marquee 32s linear infinite; color:#ffb17e; font-size:.82rem; letter-spacing:.035em; }
    .rp-ticker-track span { margin-right:3rem; }
    .rp-ticker:hover .rp-ticker-track { animation-play-state:paused; }
    @keyframes rp-marquee { 0% { transform:translateX(0); } 100% { transform:translateX(-100%); } }
    @media (prefers-reduced-motion: reduce) { .rp-ticker-track { animation:none; padding-left:0; } }
    </style>
    """,
    unsafe_allow_html=True,
)

# -----------------------------------------------------------------------------
# Database / login
# -----------------------------------------------------------------------------
initialize_database()

# Reuse an existing audit_logs table if another module has already registered it.
# Defining a second ORM class for the same table can trigger InvalidRequestError.
audit_table = Base.metadata.tables.get("audit_logs")
if audit_table is None:
    audit_table = Table(
        "audit_logs",
        Base.metadata,
        Column("id", Integer, primary_key=True),
        Column("actor_username", String(50), nullable=False),
        Column("action", String(100), nullable=False),
        Column("details", Text, nullable=False, default=""),
        Column("created_at", DateTime(timezone=True), nullable=False,
               default=lambda: datetime.now(timezone.utc)),
    )

Base.metadata.create_all(engine)


def write_audit(actor: str, action: str, details: str = "") -> bool:
    """Record an event; return whether persistence succeeded."""
    try:
        with SessionLocal() as db:
            db.execute(insert(audit_table).values(
                actor_username=actor,
                action=action,
                details=details[:2000],
                created_at=datetime.now(timezone.utc),
            ))
            db.commit()
        return True
    except Exception:
        # Avoid exposing database internals; signal failure to the caller for diagnostics.
        return False


user = require_login()
if user is None:
    st.stop()

st.sidebar.markdown("<div class='rp-eyebrow'>RETAIL INTELLIGENCE</div>", unsafe_allow_html=True)
st.sidebar.markdown("<div style='font-size:1.45rem;font-weight:800;letter-spacing:-.04em;margin:.15rem 0 .5rem'>▰ RetailPulse</div>", unsafe_allow_html=True)
st.sidebar.caption(f"Signed in as **{user['username']}** · {user['role']}")
if st.sidebar.button("↪ Log out", width="stretch"):
    write_audit(user["username"], "logout")
    logout()

# -----------------------------------------------------------------------------
# Load the project's existing prepared datasets
# -----------------------------------------------------------------------------
DATA_DIR = Path(__file__).resolve().parent


def load_csv(filename: str, date_columns=None) -> pd.DataFrame:
    path = DATA_DIR / filename
    if not path.exists():
        st.error(f"Required dashboard data file is missing: {filename}")
        st.caption("Keep the existing prepared CSV files inside the dashboard/ folder.")
        st.stop()
    try:
        frame = pd.read_csv(path)
        for column in (date_columns or []):
            if column in frame.columns:
                frame[column] = pd.to_datetime(frame[column], errors="coerce")
        return frame
    except Exception as exc:
        st.error(f"Could not read {filename}. Check the CSV format and try again.")
        st.caption(str(exc))
        st.stop()


inventory = load_csv("inventory_dashboard.csv")
forecast_history = load_csv("forecast_results.csv", ["date"])
future_forecast = load_csv("future_forecast.csv", ["date"])
rfm = load_csv("rfm_dashboard.csv")

# Normalize commonly used numeric columns without changing source files.
for frame, columns in [
    (inventory, ["stock_on_hand", "store_recommended_order_qty", "calendar_avg_daily_demand"]),
    (forecast_history, ["actual", "predicted"]),
    (future_forecast, ["predicted_demand"]),
    (rfm, ["Monetary", "Frequency", "Recency"]),
]:
    for column in columns:
        if column in frame.columns:
            frame[column] = pd.to_numeric(frame[column], errors="coerce").fillna(0)

# -----------------------------------------------------------------------------
# Navigation and server-side permission check
# -----------------------------------------------------------------------------
PAGES = {
    "Executive Overview": ("overview", "⌂"),
    "Sales Analytics": ("sales", "↗"),
    "Product Explorer": ("products", "◈"),
    "Data Health Center": ("data-health", "◉"),
    "Inventory Optimization": ("inventory", "▦"),
    "Inventory Alerts": ("alerts", "!"),
    "Store Performance": ("stores", "⌖"),
    "Demand Forecasting": ("forecasting", "⌁"),
    "Customer Segmentation": ("segmentation", "◎"),
    "Admin & Audit Logs": ("admin", "⚙"),
}

# Map new pages to existing capabilities until finer-grained policies are added.
PAGE_PERMISSIONS = {
    "Executive Overview": "overview",
    "Sales Analytics": "overview",
    "Product Explorer": "inventory",
    "Data Health Center": "overview",
    "Inventory Optimization": "inventory",
    "Inventory Alerts": "inventory",
    "Store Performance": "inventory",
    "Demand Forecasting": "forecasting",
    "Customer Segmentation": "segmentation",
    "Admin & Audit Logs": "user_management",
}

st.markdown(f"<div style='display:flex;justify-content:space-between;align-items:center;gap:1rem;padding:.15rem 0 .8rem;border-bottom:1px solid #2b3039;margin-bottom:1rem'><div><span style='font-weight:800;font-size:1.05rem'>RetailPulse</span> <span style='color:#9ea7b5;font-size:.82rem'>/ Retail intelligence workspace</span></div><div style='color:#9ea7b5;font-size:.8rem'>Prepared datasets · Signed in as {user['username']}</div></div>", unsafe_allow_html=True)
st.markdown("<div class='rp-ticker'><div class='rp-ticker-track'><span>✦ RETAILPULSE INTELLIGENCE</span><span>● Monitor stock levels</span><span>↗ Explore demand trends</span><span>◈ Understand product performance</span><span>✓ Make data-informed decisions</span><span>✦ RETAILPULSE INTELLIGENCE</span></div></div>", unsafe_allow_html=True)
st.sidebar.markdown("---")
st.sidebar.markdown("<div class='rp-eyebrow'>WORKSPACE</div>", unsafe_allow_html=True)
page = st.sidebar.radio(
    "Navigate",
    list(PAGES.keys()),
    format_func=lambda label: f"{PAGES[label][1]}   {label}",
    label_visibility="collapsed",
)

try:
    require_permission(user, PAGE_PERMISSIONS[page])
except PermissionError:
    st.error("You do not have permission to access this page.")
    st.stop()

st.sidebar.markdown("---")
st.sidebar.caption("Retail intelligence · Data-driven decisions")

# -----------------------------------------------------------------------------
# Shared helpers
# -----------------------------------------------------------------------------
def metric_if_column(frame: pd.DataFrame, column: str) -> float:
    if column not in frame.columns:
        return 0.0
    return float(pd.to_numeric(frame[column], errors="coerce").fillna(0).sum())


def status_column() -> str | None:
    return "final_inventory_status" if "final_inventory_status" in inventory.columns else None


def page_heading(title: str, subtitle: str, eyebrow: str = "RETAILPULSE ANALYTICS") -> None:
    st.markdown(f"<div class='rp-eyebrow'>{eyebrow}</div>", unsafe_allow_html=True)
    st.title(title)
    st.markdown(f"<div class='rp-subtitle'>{subtitle}</div>", unsafe_allow_html=True)
    st.write("")


def show_inventory_table(frame: pd.DataFrame, limit: int | None = None) -> None:
    shown = frame.head(limit) if limit else frame
    st.dataframe(shown, width="stretch", hide_index=True)


def explain_metrics(items: list[tuple[str, str]]) -> None:
    """Show plain-language definitions so the dashboard is easier to present."""
    with st.expander("Understand these metrics", expanded=False):
        for label, explanation in items:
            st.markdown(f"**{label}** — {explanation}")


def show_data_quality_note(message: str) -> None:
    st.caption(f"Data note: {message}")


# -----------------------------------------------------------------------------
# Executive Overview
# -----------------------------------------------------------------------------
if page == "Executive Overview":
    page_heading("Retail intelligence, at a glance", "A consolidated view of inventory health, demand signals, and customer value.", "EXECUTIVE WORKSPACE")
    st.markdown("Use this page as the starting point for a daily business review. It combines prepared inventory, forecast-evaluation, and RFM customer datasets; it is not a live point-of-sale feed.")
    explain_metrics([
        ("Inventory records", "Rows in the prepared inventory dashboard. This is not necessarily the number of unique products because the same SKU may appear in multiple stores."),
        ("Units on hand", "Sum of the stock_on_hand field across the loaded inventory records."),
        ("Suggested replenishment", "Sum of the model or business-rule recommended order quantities. Treat this as a review queue, not an automatic purchase order."),
        ("Stockout records", "Rows whose inventory status is exactly 'stockout'. This is a record count, not a count of lost sales."),
        ("Demand trend", "Historical actual demand compared with predicted demand, when both series are available."),
    ])
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Inventory records", f"{len(inventory):,}")
    c2.metric("Units on hand", f"{metric_if_column(inventory, 'stock_on_hand'):,.0f}")
    c3.metric("Suggested replenishment", f"{metric_if_column(inventory, 'store_recommended_order_qty'):,.0f}")
    status_col = status_column()
    stockouts = int(inventory[status_col].astype(str).str.lower().eq("stockout").sum()) if status_col else 0
    c4.metric("Stockout records", f"{stockouts:,}")

    st.write("")
    left, right = st.columns([1.35, 1])
    with left:
        with st.container(border=True):
            st.subheader("Demand trend")
            if {"date", "actual", "predicted"}.issubset(forecast_history.columns):
                trend = forecast_history[["date", "actual", "predicted"]].dropna().sort_values("date")
                st.line_chart(trend.set_index("date"), height=280)
            else:
                st.info("Forecast history needs date, actual, and predicted columns to show this chart.")
    with right:
        with st.container(border=True):
            st.subheader("Inventory health")
            if status_col:
                counts = inventory[status_col].fillna("Unknown").value_counts().rename_axis("Status").to_frame("Records")
                st.bar_chart(counts, height=280)
            else:
                st.info("Inventory status chart is unavailable because the status column is missing.")
    st.write("")
    left, right = st.columns(2)
    with left:
        with st.container(border=True):
            st.subheader("Highest replenishment needs")
            if "store_recommended_order_qty" in inventory.columns:
                cols = [c for c in ["store_id", "sku_id", "sku_name", "category", "stock_on_hand", "store_recommended_order_qty"] if c in inventory.columns]
                show_inventory_table(inventory.sort_values("store_recommended_order_qty", ascending=False)[cols], 8)
            else:
                st.info("Replenishment quantity is not available in this dataset.")
    with right:
        with st.container(border=True):
            st.subheader("Customer segments")
            if "Segment" in rfm.columns:
                st.bar_chart(rfm["Segment"].fillna("Unknown").value_counts().rename_axis("Segment").to_frame("Customers"), height=260)
            else:
                st.info("Customer segment information is not available.")

# -----------------------------------------------------------------------------
# Sales Analytics: use only real available fields; no fabricated revenue/orders
# -----------------------------------------------------------------------------
elif page == "Sales Analytics":
    page_heading("Sales analytics", "Explore demand patterns from the prepared forecast evaluation data.", "COMMERCIAL PERFORMANCE")
    st.markdown("This module currently analyses demand units, not sales revenue. Revenue, transactions, and margin should only be added after transaction-level sales data is connected.")
    explain_metrics([
        ("Actual demand units", "The sum of observed actual values for the selected date range."),
        ("Predicted demand units", "The sum of model predictions over the same selected dates."),
        ("Mean absolute error (MAE)", "The average absolute difference between actual and predicted demand. Lower is generally better; its unit is the same as the demand field."),
        ("Date filter", "Restricts the comparison to dates in forecast_results.csv. If the start date is after the end date, the selected result is empty."),
    ])
    if {"date", "actual", "predicted"}.issubset(forecast_history.columns):
        valid_dates = forecast_history["date"].dropna()
        if not valid_dates.empty:
            start_default, end_default = valid_dates.min().date(), valid_dates.max().date()
            d1, d2 = st.columns(2)
            start_date = d1.date_input("Start date", value=start_default, key="sales_start", min_value=start_default, max_value=end_default)
            end_date = d2.date_input("End date", value=end_default, key="sales_end", min_value=start_default, max_value=end_default)
            data = forecast_history.dropna(subset=["date"]).copy()
            data = data[(data["date"].dt.date >= start_date) & (data["date"].dt.date <= end_date)] if start_date <= end_date else data.iloc[0:0]
            a, b, c = st.columns(3)
            a.metric("Actual demand units", f"{data['actual'].sum():,.0f}")
            b.metric("Predicted demand units", f"{data['predicted'].sum():,.0f}")
            mae = (data["actual"] - data["predicted"]).abs().mean() if not data.empty else 0
            c.metric("Mean absolute error", f"{mae:,.2f}")
            st.write("")
            with st.container(border=True):
                st.subheader("Actual vs predicted demand")
                if not data.empty:
                    st.line_chart(data.sort_values("date").set_index("date")[["actual", "predicted"]], height=340)
                else:
                    st.warning("No records exist for the selected date range.")
            with st.container(border=True):
                st.subheader("Daily detail")
                st.dataframe(data.sort_values("date", ascending=False), width="stretch", hide_index=True)
            st.caption("This view reports demand units from the forecast dataset. It does not estimate revenue or order counts because those transaction fields are not included in the dashboard CSVs.")
        else:
            st.warning("No valid dates were found in forecast history.")
    else:
        st.warning("Sales trend view requires date, actual, and predicted columns in forecast_results.csv.")

# -----------------------------------------------------------------------------
# Product Explorer
# -----------------------------------------------------------------------------
elif page == "Product Explorer":
    page_heading("Product Explorer", "A simple way to find products and understand their stock position.", "PRODUCT CATALOG")
    st.markdown("Search the prepared inventory list, filter by store or category, and sort products by current stock or suggested replenishment. This page describes the available inventory data; it does not estimate sales or profit.")
    view = inventory.copy()
    store_col = next((c for c in ["store_name", "store_id", "store"] if c in view.columns), None)
    category_col = next((c for c in ["category", "product_category", "department"] if c in view.columns), None)
    name_col = next((c for c in ["sku_name", "product_name", "item_name", "product"] if c in view.columns), None)
    f1, f2 = st.columns(2)
    with f1:
        query = st.text_input("Search product or SKU", placeholder="Type a product name or SKU…", key="product_explorer_search")
    with f2:
        sort_options = [c for c in ["stock_on_hand", "store_recommended_order_qty", "calendar_avg_daily_demand"] if c in view.columns]
        sort_col = st.selectbox("Sort products by", sort_options, format_func=lambda c: {"stock_on_hand":"Current stock", "store_recommended_order_qty":"Suggested order quantity", "calendar_avg_daily_demand":"Average daily demand"}.get(c,c)) if sort_options else None
    if store_col:
        stores = sorted(view[store_col].dropna().astype(str).unique().tolist())
        chosen_stores = st.multiselect("Filter by store", stores, default=stores, key="product_explorer_stores")
        view = view[view[store_col].astype(str).isin(chosen_stores)]
    if category_col:
        categories = sorted(view[category_col].dropna().astype(str).unique().tolist())
        chosen_categories = st.multiselect("Filter by category", categories, default=categories, key="product_explorer_categories")
        view = view[view[category_col].astype(str).isin(chosen_categories)]
    if query.strip():
        searchable = [c for c in [name_col, "sku_id", "sku", store_col] if c and c in view.columns]
        if searchable:
            mask = pd.Series(False, index=view.index)
            for col in searchable:
                mask |= view[col].astype(str).str.contains(query.strip(), case=False, na=False)
            view = view[mask]
    m1, m2, m3 = st.columns(3)
    m1.metric("Products / inventory rows", f"{len(view):,}")
    m2.metric("Current stock units", f"{metric_if_column(view, 'stock_on_hand'):,.0f}")
    m3.metric("Suggested replenishment units", f"{metric_if_column(view, 'store_recommended_order_qty'):,.0f}")
    if sort_col:
        view = view.sort_values(sort_col, ascending=(sort_col == "stock_on_hand"), na_position="last")
    st.dataframe(view, width="stretch", hide_index=True)
    st.caption("Tip: use this page to locate a product, check its stock, and review replenishment suggestions before making an order.")

# -----------------------------------------------------------------------------
# Data Health Center
# -----------------------------------------------------------------------------
elif page == "Data Health Center":
    page_heading("Data Health Center", "A simple check of whether the dashboard datasets are present and ready to use.", "DATA QUALITY")
    st.markdown("This page summarizes the four prepared CSV datasets loaded by RetailPulse. Missing values are counted as a quick warning signal; a missing value is not automatically an error because some fields may be optional.")
    datasets = {"Inventory dashboard": inventory, "Historical forecast results": forecast_history, "Future forecast": future_forecast, "Customer segmentation (RFM)": rfm}
    summary_rows = []
    for dataset_name, frame in datasets.items():
        summary_rows.append({"Dataset": dataset_name, "Rows": len(frame), "Columns": len(frame.columns), "Missing cells": int(frame.isna().sum().sum()), "Duplicate rows": int(frame.duplicated().sum()), "Status": "Empty" if frame.empty else ("Review missing values" if frame.isna().any().any() else "Loaded")})
    summary = pd.DataFrame(summary_rows)
    c1, c2, c3 = st.columns(3)
    c1.metric("Datasets loaded", f"{len(datasets)} / 4")
    c2.metric("Total rows", f"{sum(len(frame) for frame in datasets.values()):,}")
    c3.metric("Missing cells", f"{sum(int(frame.isna().sum().sum()) for frame in datasets.values()):,}")
    st.subheader("Dataset status")
    st.dataframe(summary, width="stretch", hide_index=True)
    selected_dataset = st.selectbox("Inspect a dataset", list(datasets.keys()), key="data_health_dataset")
    selected_frame = datasets[selected_dataset]
    st.subheader("Column-by-column check")
    column_summary = pd.DataFrame({"Column": selected_frame.columns, "Data type": [str(selected_frame[c].dtype) for c in selected_frame.columns], "Missing values": [int(selected_frame[c].isna().sum()) for c in selected_frame.columns], "Unique values": [int(selected_frame[c].nunique(dropna=True)) for c in selected_frame.columns]})
    st.dataframe(column_summary, width="stretch", hide_index=True)
    st.download_button("Download dataset health report", summary.to_csv(index=False).encode("utf-8"), "retailpulse_data_health_report.csv", "text/csv")
    st.caption("This is a lightweight data check, not a guarantee that every value is correct. Investigate unusual counts and confirm column meanings before using data for business decisions.")

# -----------------------------------------------------------------------------
# Inventory Optimization
# -----------------------------------------------------------------------------
elif page == "Inventory Optimization":
    page_heading("Inventory optimization", "Prioritize replenishment and inspect stock across stores and product categories.", "SUPPLY CHAIN")
    st.markdown("Use the filters to focus on a store or product category, then review the largest suggested orders first. Validate supplier lead times, pack sizes, and operational constraints before acting on recommendations.")
    explain_metrics([
        ("Units on hand", "Current stock quantity represented in the prepared inventory file."),
        ("Recommended order units", "Quantity suggested for replenishment. A positive quantity indicates a record to review; it does not guarantee that an order should be placed."),
        ("Average daily demand", "Average of the available calendar_avg_daily_demand values for the filtered rows; this is a mean across records, not necessarily a store-wide weighted demand rate."),
        ("Inventory status distribution", "Counts records by their status label. The labels and thresholds come from the prepared dataset."),
    ])
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Inventory records", f"{len(inventory):,}")
    c2.metric("Units on hand", f"{metric_if_column(inventory, 'stock_on_hand'):,.0f}")
    c3.metric("Recommended order units", f"{metric_if_column(inventory, 'store_recommended_order_qty'):,.0f}")
    c4.metric("Average daily demand", f"{inventory['calendar_avg_daily_demand'].mean():,.2f}" if "calendar_avg_daily_demand" in inventory.columns else "N/A")
    filtered = inventory.copy()
    fc1, fc2 = st.columns(2)
    if "store_id" in filtered.columns:
        store_options = sorted(filtered["store_id"].dropna().astype(str).unique().tolist())
        store = fc1.selectbox("Store", ["All stores"] + store_options)
        if store != "All stores":
            filtered = filtered[filtered["store_id"].astype(str) == store]
    if "category" in filtered.columns:
        category_options = sorted(filtered["category"].dropna().astype(str).unique().tolist())
        category = fc2.selectbox("Category", ["All categories"] + category_options)
        if category != "All categories":
            filtered = filtered[filtered["category"].astype(str) == category]
    left, right = st.columns(2)
    with left:
        with st.container(border=True):
            st.subheader("Inventory status distribution")
            if status_column():
                st.bar_chart(filtered[status_column()].fillna("Unknown").value_counts().rename_axis("Status").to_frame("Records"))
            else:
                st.info("Status data is unavailable.")
    with right:
        with st.container(border=True):
            st.subheader("Top replenishment recommendations")
            if "store_recommended_order_qty" in filtered.columns:
                cols = [c for c in ["store_id", "sku_id", "sku_name", "category", "stock_on_hand", "store_recommended_order_qty"] if c in filtered.columns]
                show_inventory_table(filtered[filtered["store_recommended_order_qty"] > 0].sort_values("store_recommended_order_qty", ascending=False)[cols], 10)
            else:
                st.info("Replenishment quantity is unavailable.")
    st.subheader(f"Inventory records · {len(filtered):,} rows")
    show_inventory_table(filtered)
    st.download_button("Download filtered inventory CSV", filtered.to_csv(index=False).encode("utf-8"), "retailpulse_filtered_inventory.csv", "text/csv")

# -----------------------------------------------------------------------------
# Inventory Alerts
# -----------------------------------------------------------------------------
elif page == "Inventory Alerts":
    page_heading("Inventory alerts", "Surface stockout risks and replenishment actions using existing inventory flags.", "EXCEPTIONS & ACTIONS")
    st.markdown("Alerts are a prioritization aid. Start with stockouts, then check low or critical stock and items with a positive suggested order. Confirm the current stock and demand before making operational changes.")
    explain_metrics([
        ("Stockout records", "Rows flagged with the exact status 'stockout'."),
        ("Low/critical status records", "Rows whose status text contains low, critical, or under. This text-based rule may need adjustment to match your dataset's exact status labels."),
        ("Items to reorder", "Inventory rows with a recommended order quantity greater than zero; this is a row count, not a distinct SKU count."),
    ])
    if status_column():
        status = inventory[status_column()].fillna("Unknown").astype(str)
        stockouts_df = inventory[status.str.lower().eq("stockout")].copy()
        low_stock_df = inventory[status.str.lower().str.contains("low|critical|under", regex=True)].copy()
        c1, c2, c3 = st.columns(3)
        c1.metric("Stockout records", f"{len(stockouts_df):,}")
        c2.metric("Low/critical status records", f"{len(low_stock_df):,}")
        c3.metric("Items to reorder", f"{int((inventory['store_recommended_order_qty'] > 0).sum()):,}" if "store_recommended_order_qty" in inventory.columns else "N/A")
        filter_status = st.selectbox("Alert type", ["All alerts", "Stockout", "Low / critical stock", "Reorder recommended"])
        alerts = inventory.copy()
        if filter_status == "Stockout":
            alerts = stockouts_df
        elif filter_status == "Low / critical stock":
            alerts = low_stock_df
        elif filter_status == "Reorder recommended" and "store_recommended_order_qty" in alerts.columns:
            alerts = alerts[alerts["store_recommended_order_qty"] > 0]
        sort_col = "store_recommended_order_qty" if "store_recommended_order_qty" in alerts.columns else alerts.columns[0]
        alerts = alerts.sort_values(sort_col, ascending=False)
        if alerts.empty:
            st.success("No records match this alert filter.")
        else:
            st.warning(f"{len(alerts):,} inventory records match this view. Validate thresholds with your operational team before ordering.")
            show_inventory_table(alerts)
            st.download_button("Export alerts CSV", alerts.to_csv(index=False).encode("utf-8"), "retailpulse_inventory_alerts.csv", "text/csv")
    else:
        st.warning("The inventory dataset does not contain final_inventory_status, so status-based alerts cannot be calculated.")
        if "store_recommended_order_qty" in inventory.columns:
            alerts = inventory[inventory["store_recommended_order_qty"] > 0].sort_values("store_recommended_order_qty", ascending=False)
            st.subheader("Replenishment recommendations")
            show_inventory_table(alerts)

# -----------------------------------------------------------------------------
# Store Performance
# -----------------------------------------------------------------------------
elif page == "Store Performance":
    page_heading("Store performance", "Compare stock coverage and replenishment needs across store locations.", "STORE OPERATIONS")
    st.markdown("This comparison focuses on stock and replenishment by store. It does not rank stores by revenue or profit because transaction-level sales are not part of the loaded dashboard datasets.")
    explain_metrics([
        ("Stores represented", "Number of distinct store_id values in the inventory dataset."),
        ("Units on hand", "Sum of inventory units assigned to each store."),
        ("Recommended order units", "Sum of suggested replenishment quantities for each store."),
        ("Stockout records", "Number of inventory rows flagged as stockouts for each store, where the status field exists."),
    ])
    if "store_id" not in inventory.columns:
        st.warning("Store performance requires a store_id column in inventory_dashboard.csv.")
    else:
        aggregations = {}
        for col in ["stock_on_hand", "store_recommended_order_qty", "calendar_avg_daily_demand"]:
            if col in inventory.columns:
                aggregations[col] = "sum" if col != "calendar_avg_daily_demand" else "mean"
        if status_column():
            inventory = inventory.copy()
            inventory["_stockout_flag"] = inventory[status_column()].astype(str).str.lower().eq("stockout").astype(int)
            aggregations["_stockout_flag"] = "sum"
        stores = inventory.groupby("store_id", dropna=False).agg(aggregations).reset_index()
        stores = stores.rename(columns={"stock_on_hand": "Units on hand", "store_recommended_order_qty": "Recommended order units", "calendar_avg_daily_demand": "Average daily demand", "_stockout_flag": "Stockout records"})
        a, b, c = st.columns(3)
        a.metric("Stores represented", f"{stores['store_id'].nunique():,}")
        b.metric("Total units on hand", f"{metric_if_column(inventory, 'stock_on_hand'):,.0f}")
        c.metric("Total suggested order units", f"{metric_if_column(inventory, 'store_recommended_order_qty'):,.0f}")
        if "Units on hand" in stores.columns:
            with st.container(border=True):
                st.subheader("Units on hand by store")
                st.bar_chart(stores.set_index("store_id")["Units on hand"], height=330)
        if "Recommended order units" in stores.columns:
            with st.container(border=True):
                st.subheader("Replenishment needs by store")
                st.bar_chart(stores.set_index("store_id")["Recommended order units"], height=300)
        st.subheader("Store comparison table")
        show_inventory_table(stores.sort_values("Recommended order units", ascending=False) if "Recommended order units" in stores.columns else stores)
        st.download_button("Download store comparison CSV", stores.to_csv(index=False).encode("utf-8"), "retailpulse_store_performance.csv", "text/csv")
        st.caption("These metrics describe inventory and replenishment, not store revenue. Transaction-level sales by store are not currently loaded in the dashboard.")

# -----------------------------------------------------------------------------
# Demand Forecasting
# -----------------------------------------------------------------------------
elif page == "Demand Forecasting":
    page_heading("Demand forecasting", "Compare historical predictions and review the forward demand outlook.", "FORECAST STUDIO")
    st.markdown("Forecasts help estimate future demand so teams can plan inventory and staffing. Always compare forecasts with recent actuals and review unusual periods before using them for decisions.")
    explain_metrics([
        ("Forecast MAE", "Average absolute error between actual and predicted values in the historical evaluation file. Lower is better when comparing the same dataset and units."),
        ("Forecast R²", "A fit statistic comparing prediction errors with the variation in actual values. It can be negative when predictions perform worse than a simple mean baseline; it is not a percentage accuracy score."),
        ("Forecast horizon", "Number of distinct forecast dates when the date column exists, otherwise the number of forecast rows."),
        ("Forward forecast", "Predicted demand values for future dates in future_forecast.csv. These are estimates, not guarantees."),
    ])
    if {"actual", "predicted"}.issubset(forecast_history.columns):
        actual = forecast_history["actual"]
        predicted = forecast_history["predicted"]
        mae = float((actual - predicted).abs().mean()) if len(forecast_history) else 0
        ss_tot = float(((actual - actual.mean()) ** 2).sum()) if len(forecast_history) else 0
        ss_res = float(((actual - predicted) ** 2).sum()) if len(forecast_history) else 0
        r2 = 1 - ss_res / ss_tot if ss_tot else 0
        horizon = f"{future_forecast['date'].nunique()} days" if "date" in future_forecast.columns else f"{len(future_forecast)} records"
        c1, c2, c3 = st.columns(3)
        c1.metric("Forecast MAE", f"{mae:,.2f}")
        c2.metric("Forecast R²", f"{r2:.3f}")
        c3.metric("Forecast horizon", horizon)
    left, right = st.columns(2)
    with left:
        with st.container(border=True):
            st.subheader("Actual vs predicted")
            if {"date", "actual", "predicted"}.issubset(forecast_history.columns):
                st.line_chart(forecast_history.dropna(subset=["date"]).sort_values("date").set_index("date")[["actual", "predicted"]], height=320)
            else:
                st.info("Required forecast history columns are missing.")
    with right:
        with st.container(border=True):
            st.subheader("Forward forecast")
            if {"date", "predicted_demand"}.issubset(future_forecast.columns):
                st.line_chart(future_forecast.dropna(subset=["date"]).sort_values("date").set_index("date")[["predicted_demand"]], height=320)
            else:
                st.info("Required future forecast columns are missing.")
    st.subheader("Forecast details")
    st.dataframe(future_forecast, width="stretch", hide_index=True)
    st.download_button("Download forecast CSV", future_forecast.to_csv(index=False).encode("utf-8"), "retailpulse_forecast.csv", "text/csv")
    st.caption("Forecast accuracy metrics are calculated from forecast_results.csv; they are not a guarantee of future performance.")

# -----------------------------------------------------------------------------
# Customer Segmentation
# -----------------------------------------------------------------------------
elif page == "Customer Segmentation":
    page_heading("Customer segmentation", "Understand customer groups using Recency, Frequency, and Monetary behavior.", "CUSTOMER INTELLIGENCE")
    st.markdown("RFM analysis groups customers by when they last purchased, how often they purchase, and the monetary value represented in the prepared dataset. Segment names and scoring thresholds are defined by the upstream segmentation process.")
    explain_metrics([
        ("Customers represented", "Number of rows in rfm_dashboard.csv. This equals unique customers only if the file has one row per customer."),
        ("Monetary value", "Sum of the Monetary field as prepared in the RFM dataset. Confirm its currency and aggregation period before presenting it as revenue."),
        ("Recency", "A measure of how long it has been since a customer's most recent purchase; the precise unit depends on the source dataset."),
        ("Frequency", "A measure of purchase frequency over the source dataset's observation window."),
        ("Segment distribution", "Count of rows assigned to each segment label."),
    ])
    total_value = metric_if_column(rfm, "Monetary")
    c1, c2, c3 = st.columns(3)
    c1.metric("Customers represented", f"{len(rfm):,}")
    c2.metric("Total customer monetary value", f"{total_value:,.0f}")
    c3.metric("Customer segments", f"{rfm['Segment'].nunique():,}" if "Segment" in rfm.columns else "N/A")
    left, right = st.columns(2)
    with left:
        with st.container(border=True):
            st.subheader("Segment distribution")
            if "Segment" in rfm.columns:
                st.bar_chart(rfm["Segment"].fillna("Unknown").value_counts().rename_axis("Segment").to_frame("Customers"))
    with right:
        with st.container(border=True):
            st.subheader("Customer value by segment")
            if {"Segment", "Monetary"}.issubset(rfm.columns):
                value = rfm.groupby("Segment", dropna=False)["Monetary"].sum().sort_values(ascending=False)
                st.bar_chart(value)
    if "Segment" in rfm.columns:
        st.subheader("Segment profile")
        agg = {"Customer rows": ("Segment", "size")}
        for col in ["Recency", "Frequency", "Monetary"]:
            if col in rfm.columns:
                agg[{"Recency": "Avg. recency", "Frequency": "Avg. frequency", "Monetary": "Avg. monetary value"}[col]] = (col, "mean")
        profile = rfm.groupby("Segment", dropna=False).agg(**agg).reset_index()
        st.dataframe(profile.round(2), width="stretch", hide_index=True)
    with st.expander("What these segments mean"):
        st.write("Use high-value and frequent-customer groups for loyalty initiatives, and consider appropriate re-engagement campaigns for customers whose last purchase was longer ago. Confirm business definitions against the segmentation model used to generate the RFM dataset.")
    st.download_button("Download customer segments CSV", rfm.to_csv(index=False).encode("utf-8"), "retailpulse_customer_segments.csv", "text/csv")

# -----------------------------------------------------------------------------
# Admin & Audit Logs: authorized Admin only; changes use existing SQLAlchemy DB
# -----------------------------------------------------------------------------
elif page == "Admin & Audit Logs":
    require_permission(user, "user_management")
    page_heading("Administration & audit", "Manage account access and review recorded administrative activity.", "SECURITY CENTER")
    tab_users, tab_audit = st.tabs(["User management", "Audit trail"])
    with tab_users:
        with SessionLocal() as db:
            db_users = db.scalars(select(User).order_by(User.created_at.desc())).all()
            rows = [{"ID": u.id, "Username": u.username, "Role": u.role, "Active": u.is_active, "Created at": u.created_at} for u in db_users]
            user_frame = pd.DataFrame(rows)
        st.metric("Registered users", f"{len(user_frame):,}")
        if not user_frame.empty:
            st.dataframe(user_frame, width="stretch", hide_index=True)
            st.caption("For safety, account creation and password resets remain in the existing authentication flow. This screen currently supports role changes and account deactivation.")
            choices = {f"{row['Username']} (ID {row['ID']})": int(row["ID"]) for _, row in user_frame.iterrows()}
            selected_label = st.selectbox("Select account", list(choices.keys()))
            selected_id = choices[selected_label]
            selected_row = user_frame[user_frame["ID"] == selected_id].iloc[0]
            with st.form("admin_user_update"):
                new_role = st.selectbox("Role", ["Admin", "Analyst", "Viewer"], index=["Admin", "Analyst", "Viewer"].index(selected_row["Role"]) if selected_row["Role"] in {"Admin", "Analyst", "Viewer"} else 2)
                active = st.checkbox("Account active", value=bool(selected_row["Active"]))
                save_user = st.form_submit_button("Save account changes")
            if save_user:
                if selected_id == user["id"] and not active:
                    st.error("You cannot deactivate your own signed-in account.")
                else:
                    with SessionLocal() as db:
                        target = db.get(User, selected_id)
                        if target is None:
                            st.error("That account no longer exists. Refresh and try again.")
                        else:
                            # Do not allow removal/deactivation of the final active Admin.
                            would_remove_admin = target.role == "Admin" and target.is_active and (new_role != "Admin" or not active)
                            active_admins = db.scalars(select(User).where(User.role == "Admin", User.is_active.is_(True))).all()
                            if would_remove_admin and len(active_admins) <= 1:
                                st.error("The last active Admin cannot be demoted or deactivated.")
                            else:
                                old_role, old_active = target.role, target.is_active
                                target.role, target.is_active = new_role, active
                                db.commit()
                                audit_saved = write_audit(user["username"], "user_updated", f"target={target.username}; role={old_role}->{new_role}; active={old_active}->{active}")
                                st.success("Account updated.")
                                if not audit_saved:
                                    st.warning("The account was updated, but the audit event could not be saved. Ask the system administrator to check database access.")
                                st.rerun()
        else:
            st.info("No user accounts were found.")
    with tab_audit:
        with SessionLocal() as db:
            logs = db.execute(select(audit_table).order_by(audit_table.c.created_at.desc()).limit(500)).mappings().all()
            log_rows = [{"Time": item["created_at"], "Actor": item["actor_username"], "Action": item["action"], "Details": item["details"]} for item in logs]
        log_frame = pd.DataFrame(log_rows)
        if log_frame.empty:
            st.info("No audit events have been recorded yet. Events are added as users log out or Admins change accounts.")
        else:
            st.dataframe(log_frame, width="stretch", hide_index=True)
            st.download_button("Export audit logs CSV", log_frame.to_csv(index=False).encode("utf-8"), "retailpulse_audit_logs.csv", "text/csv")

st.markdown("---")
st.caption(f"RetailPulse · Signed in as {user['username']} · Data views use the existing dashboard datasets")
st.caption("Presentation tip: explain what the metric measures, state which source file it comes from, then describe the decision it can support. Avoid describing inventory measures as sales or profit measures.")
