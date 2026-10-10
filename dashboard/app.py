import streamlit as st
import pandas as pd

# -----------------------------
# Page configuration
# -----------------------------
st.set_page_config(
    page_title="RetailPulse",
    page_icon="📊",
    layout="wide"
)

# -----------------------------
# Load dashboard data
# -----------------------------
inventory = pd.read_csv("dashboard/inventory_dashboard.csv")
forecast_history = pd.read_csv("dashboard/forecast_results.csv")
future_forecast = pd.read_csv("dashboard/future_forecast.csv")
rfm = pd.read_csv("dashboard/rfm_dashboard.csv")

# Convert dates
forecast_history["date"] = pd.to_datetime(forecast_history["date"])
future_forecast["date"] = pd.to_datetime(future_forecast["date"])


# -----------------------------
# Sidebar
# -----------------------------
st.sidebar.title("RetailPulse")
st.sidebar.markdown("### Navigation")

page = st.sidebar.radio(
    "Go to",
    [
        "Overview",
        "Inventory Optimization",
        "Demand Forecasting",
        "Customer Segmentation"
    ]
)


# =========================================================
# OVERVIEW
# =========================================================
if page == "Overview":

    st.title("RetailPulse")
    st.subheader(
        "AI-Powered Customer Analytics & Demand Forecasting"
    )

    st.success("RetailPulse dashboard is running!")

    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.metric(
            "Inventory Records",
            f"{len(inventory):,}"
        )

    with col2:
        st.metric(
            "Units On Hand",
            f"{inventory['stock_on_hand'].sum():,.0f}"
        )

    with col3:
        st.metric(
            "Recommended Replenishment",
            f"{inventory['store_recommended_order_qty'].sum():,.0f}"
        )

    with col4:
        st.metric(
            "Stockouts",
            f"{(inventory['final_inventory_status'] == 'Stockout').sum():,}"
        )

    st.divider()

    st.header("RetailPulse Project")

    st.write(
        """
        RetailPulse is an end-to-end retail analytics platform that combines
        demand forecasting, customer segmentation, and inventory optimization
        to support data-driven retail decisions.
        """
    )

    st.subheader("Current Capabilities")

    col1, col2, col3 = st.columns(3)

    with col1:
        st.markdown("### 📦 Inventory")
        st.write(
            "Store-level inventory health and replenishment recommendations."
        )

    with col2:
        st.markdown("### 📈 Forecasting")
        st.write(
            "Machine-learning demand forecasting using historical sales patterns."
        )

    with col3:
        st.markdown("### 👥 Customer Analytics")
        st.write(
            "RFM-based customer segmentation and behavioral analysis."
        )


# =========================================================
# INVENTORY
# =========================================================
elif page == "Inventory Optimization":

    st.title("📦 Inventory Optimization")
    st.subheader("Store-level inventory health and replenishment")

    # KPIs
    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.metric(
            "Inventory Records",
            f"{len(inventory):,}"
        )

    with col2:
        st.metric(
            "Units On Hand",
            f"{inventory['stock_on_hand'].sum():,.0f}"
        )

    with col3:
        st.metric(
            "Recommended Replenishment",
            f"{inventory['store_recommended_order_qty'].sum():,.0f}"
        )

    with col4:
        stockouts = (
            inventory["final_inventory_status"] == "Stockout"
        ).sum()

        st.metric(
            "Stockouts",
            f"{stockouts:,}"
        )

    st.divider()

    # Inventory status
    st.header("Inventory Status")

    status_counts = (
        inventory["final_inventory_status"]
        .value_counts()
        .rename_axis("Status")
        .reset_index(name="Records")
    )

    st.bar_chart(
        status_counts.set_index("Status")
    )

    # Top reorder recommendations
    st.header("Top Reorder Recommendations")

    reorder_columns = [
        "store_id",
        "sku_id",
        "sku_name",
        "category",
        "stock_on_hand",
        "calendar_avg_daily_demand",
        "store_recommended_order_qty"
    ]

    top_reorders = (
        inventory[
            inventory["store_recommended_order_qty"] > 0
        ][reorder_columns]
        .sort_values(
            "store_recommended_order_qty",
            ascending=False
        )
        .head(10)
    )

    st.dataframe(
        top_reorders,
        use_container_width=True,
        hide_index=True
    )

    # Filters
    st.header("Inventory Filters")

    col1, col2 = st.columns(2)

    with col1:
        selected_store = st.selectbox(
            "Select Store",
            ["All"] + sorted(inventory["store_id"].unique())
        )

    with col2:
        selected_category = st.selectbox(
            "Select Category",
            ["All"] + sorted(inventory["category"].unique())
        )

    filtered_inventory = inventory.copy()

    if selected_store != "All":
        filtered_inventory = filtered_inventory[
            filtered_inventory["store_id"] == selected_store
        ]

    if selected_category != "All":
        filtered_inventory = filtered_inventory[
            filtered_inventory["category"] == selected_category
        ]

    st.write(
        f"Showing {len(filtered_inventory):,} inventory records"
    )

    st.dataframe(
        filtered_inventory,
        use_container_width=True,
        hide_index=True
    )


# =========================================================
# DEMAND FORECASTING
# =========================================================
elif page == "Demand Forecasting":

    st.title("📈 Demand Forecasting")
    st.subheader("Machine-learning based daily demand forecasting")

    # -----------------------------
    # Forecast metrics
    # -----------------------------

    actual = forecast_history["actual"]
    predicted = forecast_history["predicted"]

    mae = (actual - predicted).abs().mean()

    ss_res = ((actual - predicted) ** 2).sum()
    ss_tot = ((actual - actual.mean()) ** 2).sum()

    r2 = 1 - (ss_res / ss_tot)

    col1, col2, col3 = st.columns(3)

    with col1:
        st.metric(
            "Forecast MAE",
            f"{mae:,.2f}"
        )

    with col2:
        st.metric(
            "Forecast R²",
            f"{r2:.3f}"
        )

    with col3:
        st.metric(
            "Forecast Horizon",
            "30 Days"
        )

    st.divider()

    # -----------------------------
    # Historical actual vs predicted
    # -----------------------------

    st.header("Actual vs Predicted Demand")

    historical_chart = forecast_history[
        ["date", "actual", "predicted"]
    ].set_index("date")

    st.line_chart(
        historical_chart
    )

    st.caption(
        "The model was evaluated using a chronological train/test split."
    )

    # -----------------------------
    # Future forecast
    # -----------------------------

    st.header("Next 30 Days Forecast")

    future_chart = future_forecast[
        ["date", "predicted_demand"]
    ].set_index("date")

    st.line_chart(
        future_chart
    )

    # -----------------------------
    # Forecast table
    # -----------------------------

    st.header("Forecast Details")

    display_forecast = future_forecast.copy()

    display_forecast["date"] = (
        display_forecast["date"].dt.strftime("%Y-%m-%d")
    )

    display_forecast["predicted_demand"] = (
        display_forecast["predicted_demand"]
        .round(0)
        .astype(int)
    )

    st.dataframe(
        display_forecast,
        use_container_width=True,
        hide_index=True
    )

    st.info(
        "The current forecast is an operational baseline model. "
        "The recursive 30-day forecast is intentionally conservative "
        "and smoother than individual daily demand fluctuations."
    )
    
    
    # =========================================================
# CUSTOMER SEGMENTATION
# =========================================================
elif page == "Customer Segmentation":

    st.title("👥 Customer Segmentation")
    st.subheader("RFM-based customer behavior analysis")

    # -----------------------------
    # Segment metrics
    # -----------------------------

    total_customers = len(rfm)
    total_value = rfm["Monetary"].sum()

    col1, col2, col3 = st.columns(3)

    with col1:
        st.metric(
            "Total Customers",
            f"{total_customers:,}"
        )

    with col2:
        st.metric(
            "Total Customer Value",
            f"{total_value / 1_000_000:.2f}M"
        )

    with col2:
        st.metric(
        "Total Customer Value",
        f"{total_value / 1_000_000_000:.2f}B"
    )

    st.divider()

    # -----------------------------
    # Segment distribution
    # -----------------------------

    st.header("Customer Segment Distribution")

    segment_counts = (
        rfm["Segment"]
        .value_counts()
        .rename_axis("Segment")
        .reset_index(name="Customers")
    )

    st.bar_chart(
        segment_counts,
        x="Segment",
        y="Customers"
    )

    st.divider()

    # -----------------------------
    # Customer value by segment
    # -----------------------------
    

    st.header("Customer Value by Segment")

    segment_value = (
        rfm.groupby("Segment")["Monetary"]
        .sum()
        .sort_values(ascending=False)
        .rename_axis("Segment")
        .reset_index(name="Customer Value")
    )

    st.bar_chart(
        segment_value,
        x="Segment",
        y="Customer Value"
    )

    st.divider()

    # -----------------------------
    # Segment profile
    # -----------------------------

    st.header("Segment Profile")

    segment_profile = (
        rfm.groupby("Segment")
        .agg(
            Customers=("Segment", "size"),
            Avg_Recency=("Recency", "mean"),
            Avg_Frequency=("Frequency", "mean"),
            Avg_Monetary=("Monetary", "mean")
        )
        .reset_index()
        .sort_values("Avg_Monetary", ascending=False)
    )

    segment_profile["Avg_Recency"] = (
        segment_profile["Avg_Recency"].round(1)
    )

    segment_profile["Avg_Frequency"] = (
        segment_profile["Avg_Frequency"].round(1)
    )

    segment_profile["Avg_Monetary"] = (
        segment_profile["Avg_Monetary"].round(0)
    )

    st.dataframe(
        segment_profile,
        use_container_width=True,
        hide_index=True
    )

    st.divider()

    # -----------------------------
    # Business interpretation
    # -----------------------------

    st.header("Business Insights")

    st.write(
        """
        **VIP / Champions** represent the highest-value customers and should
        receive retention-focused treatment, personalized offers, and loyalty
        benefits.

        **High-Value Regulars** are strong repeat customers and represent an
        important revenue base.

        **At-Risk Customers** have relatively high purchase recency compared
        with other segments and should be targeted with re-engagement campaigns.

        The segmentation is based on Recency, Frequency, and Monetary (RFM)
        behavior using K-Means clustering.
        """
    )
    # BY GAUTAM RISHI 