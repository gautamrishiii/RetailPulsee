# RetailPulse – AI-Powered Customer Analytics & Demand Forecasting Platform

RetailPulse is a retail analytics project that helps businesses analyze sales, customer behavior, demand patterns, and inventory.

## Features

- Sales and revenue analytics
- Customer segmentation and RFM analysis
- Demand forecasting visualizations
- Inventory analytics
- Interactive Streamlit dashboard
- Docker deployment

## Technology Stack

- Python
- Pandas and NumPy
- Streamlit and Plotly
- Docker
- Git and GitHub

## Relationships

```ini
store_master.store_id        ──┐
sku_master.sku_id             ─┼──▶ sales_transactions.csv
customer_master.cust_id       ─┤     (store_id, sku_id, customer_id, promo_id)
promotions.promo_id           ─┘

## Column Reference

__store_master.csv__
| Column | Description |
|---|---|
| store_id | Unique store identifier (e.g. `ST01`) |
| store_name | Store display name |
| city | City the store operates in |
| store_type | Hypermarket / Supermarket / Convenience Store / Express Store |
| opening_date | Date the store opened |

__sku_master.csv__
| Column | Description |
|---|---|
| sku_id | Unique product identifier (e.g. `SKU00001`) |
| sku_name | Product display name |
| category | Top-level product category |
| subcategory | Product subcategory |
| unit_price | Retail selling price |
| cost_price | Cost to the retailer (always < unit_price) |
| brand | Product brand |

__customer_master.csv__
| Column | Description |
|---|---|
| cust_id | Unique customer identifier (e.g. `CUST00001`) |
| age | Customer age |
| gender | Male / Female / Other |
| city | Customer's city |
| loyalty_segment | Bronze / Silver / Gold / Platinum |
| preferred_channel | In-Store / Online / Mobile App |
| registration_date | Date the customer registered |

__promotions.csv__
| Column | Description |
|---|---|
| promo_id | Unique promotion identifier |
| promo_name | Campaign name |
| start_date / end_date | Active date range |
| discount_pct | Discount percentage applied |
| promo_type | Percentage Discount / Flat Discount / BOGO / Bundle Offer / Clearance |
| target_type | What the promo applies to: Category / Brand / SKU / All |
| target_value | The specific category, brand, sku_id, or "All" being targeted |

__inventory_snapshot.csv__
| Column | Description |
|---|---|
| store_id / sku_id | Which store and product this row describes |
| stock_on_hand | Current units in stock |
| reorder_point | Stock level that should trigger a reorder |
| safety_stock | Minimum buffer stock |
| last_restock_date | Date of the most recent restock |

__sales_transactions.csv__
| Column | Description |
|---|---|
| date | Transaction date |
| receipt_id | Groups line items purchased in the same basket/visit (1–5 items) |
| store_id | Store where the sale occurred |
| sku_id | Product sold |
| customer_id | Customer who made the purchase |
| quantity | Units purchased |
| unit_price | Price per unit at time of sale |
| total_value | `quantity × unit_price × (1 − discount_pct/100)` |
| channel | In-Store / Online / Mobile App |
| discount_pct | Discount applied (0 if none) |
| promo_id | Promotion applied, blank if none |

__sku_inventory_flags.csv__ _(anomalies/ only — the ground-truth answer key)_
| Column | Description |
|---|---|
| sku_id | The flagged product |
| flag | `STOCKOUT_RISK` or `SLOW_MOVER` |
| affected_stores | `;`-separated list of `store_id`s where the anomaly was applied |
| window_start / window_end | Stockout date window (blank for `SLOW_MOVER` rows) |
| notes | Plain-language reason the SKU was flagged |




## Dataset

The project uses synthetic retail datasets. Large datasets are hosted on Hugging Face:

https://huggingface.co/datasets/gautamrishiii/zidio-data

## Run Locally

Install dependencies from the project root:

```bash
python -m pip install -r requirements.txt
```

Start the dashboard:

```bash
streamlit run dashboard/app.py
```

Open http://localhost:8501 in your browser.

## Run with Docker

```bash
docker build -t retailpulse .
docker run --rm -p 8501:8501 retailpulse
```

Docker Hub: https://hub.docker.com/r/gautamrishiii/retailpulse

## Live Demo

Explore the deployed RetailPulse dashboard:

**[🚀 Open RetailPulse Dashboard](https://retailpulse-latest.onrender.com)**

The live dashboard provides interactive sales and revenue analytics, customer segmentation, demand forecasting visualizations, and inventory analytics.



## Author

Gautam Rishi





