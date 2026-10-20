from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import streamlit as st
from sqlalchemy import Boolean, DateTime, Integer, String, Text, select
from sqlalchemy.orm import Mapped, mapped_column

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
    .stApp { background: #0b1020; color: #edf2ff; }
    [data-testid="stHeader"] { background: rgba(11,16,32,.92); }
    [data-testid="stSidebar"] { background: #11182a; border-right: 1px solid #263149; }
    [data-testid="stSidebar"] * { color: #e8edfb; }
    .block-container { padding-top: 1.7rem; padding-bottom: 2.5rem; max-width: 1600px; }
    h1, h2, h3 { letter-spacing: -0.025em; }
    h1 { font-weight: 750; }
    [data-testid="stMetric"] { background: linear-gradient(145deg,#17223a,#121a2d); border: 1px solid #2a3855; padding: 17px 18px; border-radius: 15px; }
    [data-testid="stMetricLabel"] { color: #aab8d2; }
    [data-testid="stMetricValue"] { color: #f5f7ff; }
    [data-testid="stMetricDelta"] { font-size: .85rem; }
    div[data-testid="stVerticalBlockBorderWrapper"] { border-color: #2a3855 !important; border-radius: 16px; }
    .rp-eyebrow { color:#93a4c8; font-size:.76rem; font-weight:700; letter-spacing:.13em; text-transform:uppercase; }
    .rp-subtitle { color:#aab8d2; margin-top:-.5rem; }
    .rp-pill { display:inline-block; padding:5px 10px; border-radius:999px; background:#1b2b49; color:#b9caff; font-size:.78rem; border:1px solid #30466e; }
    div.stButton > button, div.stFormSubmitButton > button { border-radius: 10px; font-weight: 650; }
    [data-testid="stDataFrame"] { border: 1px solid #283650; border-radius: 12px; overflow: hidden; }
    hr { border-color: #283650; }
    </style>
    """,
    unsafe_allow_html=True,
)

# -----------------------------------------------------------------------------
# Database / login
# -----------------------------------------------------------------------------
initialize_database()

# Audit logs are additive: existing users and tables are not replaced.
class AuditLog(Base):
    __tablename__ = "audit_logs"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    actor_username: Mapped[str] = mapped_column(String(50), nullable=False)
    action: Mapped[str] = mapped_column(String(100), nullable=False)
    details: Mapped[str] = mapped_column(Text, default="", nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )

Base.metadata.create_all(engine)


def write_audit(actor: str, action: str, details: str = "") -> None:
    try:
        with SessionLocal() as db:
            db.add(AuditLog(actor_username=actor, action=action, details=details[:2000]))
            db.commit()
    except Exception:
        # A logging failure should not expose internals or break dashboard navigation.
        pass


user = require_login()
if user is None:
    st.stop()

st.sidebar.markdown("<div class='rp-eyebrow'>RETAIL INTELLIGENCE</div>", unsafe_allow_html=True)
st.sidebar.title("📊 RetailPulse")
st.sidebar.caption(f"Signed in as **{user['username']}** · {user['role']}")
if st.sidebar.button("↪ Log out", use_container_width=True):
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
    "Inventory Optimization": "inventory",
    "Inventory Alerts": "inventory",
    "Store Performance": "inventory",
    "Demand Forecasting": "forecasting",
    "Customer Segmentation": "segmentation",
    "Admin & Audit Logs": "user_management",
}

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
    st.dataframe(shown, use_container_width=True, hide_index=True)


# -----------------------------------------------------------------------------
# Executive Overview
# -----------------------------------------------------------------------------
if page == "Executive Overview":
    page_heading("Retail intelligence, at a glance", "A consolidated view of inventory health, demand signals, and customer value.", "EXECUTIVE WORKSPACE")
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
                st.dataframe(data.sort_values("date", ascending=False), use_container_width=True, hide_index=True)
            st.caption("This view reports demand units from the forecast dataset. It does not estimate revenue or order counts because those transaction fields are not included in the dashboard CSVs.")
        else:
            st.warning("No valid dates were found in forecast history.")
    else:
        st.warning("Sales trend view requires date, actual, and predicted columns in forecast_results.csv.")

# -----------------------------------------------------------------------------
# Inventory Optimization
# -----------------------------------------------------------------------------
elif page == "Inventory Optimization":
    page_heading("Inventory optimization", "Prioritize replenishment and inspect stock across stores and product categories.", "SUPPLY CHAIN")
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
    st.dataframe(future_forecast, use_container_width=True, hide_index=True)
    st.download_button("Download forecast CSV", future_forecast.to_csv(index=False).encode("utf-8"), "retailpulse_forecast.csv", "text/csv")
    st.caption("Forecast accuracy metrics are calculated from forecast_results.csv; they are not a guarantee of future performance.")

# -----------------------------------------------------------------------------
# Customer Segmentation
# -----------------------------------------------------------------------------
elif page == "Customer Segmentation":
    page_heading("Customer segmentation", "Understand customer groups using Recency, Frequency, and Monetary behavior.", "CUSTOMER INTELLIGENCE")
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
        agg = {"Segment": ("Segment", "size")}
        for col in ["Recency", "Frequency", "Monetary"]:
            if col in rfm.columns:
                agg[{"Recency": "Avg. recency", "Frequency": "Avg. frequency", "Monetary": "Avg. monetary value"}[col]] = (col, "mean")
        profile = rfm.groupby("Segment", dropna=False).agg(**agg).reset_index(drop=True).rename(columns={"Segment": "Customers"})
        st.dataframe(profile.round(2), use_container_width=True, hide_index=True)
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
            st.dataframe(user_frame, use_container_width=True, hide_index=True)
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
                                write_audit(user["username"], "user_updated", f"target={target.username}; role={old_role}->{new_role}; active={old_active}->{active}")
                                st.success("Account updated.")
                                st.rerun()
        else:
            st.info("No user accounts were found.")
    with tab_audit:
        with SessionLocal() as db:
            logs = db.scalars(select(AuditLog).order_by(AuditLog.created_at.desc()).limit(500)).all()
            log_rows = [{"Time": item.created_at, "Actor": item.actor_username, "Action": item.action, "Details": item.details} for item in logs]
        log_frame = pd.DataFrame(log_rows)
        if log_frame.empty:
            st.info("No audit events have been recorded yet. Events are added as users log out or Admins change accounts.")
        else:
            st.dataframe(log_frame, use_container_width=True, hide_index=True)
            st.download_button("Export audit logs CSV", log_frame.to_csv(index=False).encode("utf-8"), "retailpulse_audit_logs.csv", "text/csv")

st.markdown("---")
st.caption(f"RetailPulse · Signed in as {user['username']} · Data views use the existing dashboard datasets")
