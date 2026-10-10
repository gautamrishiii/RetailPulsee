# **Synthetic Retail Dataset — 10 Million Transactions**
### **(Clean + Inventory-Anomaly Versions)**

A fully relational, synthetic multi-store retail dataset covering 4 years (2022–2025) of sales across 30 stores, 5,000 SKUs, and 10,000 customers. Built with realistic seasonality, bestseller/loyalty skew, basket structure, and rule-based promotion targeting — not uniform random data.

Ships as **two matched versions of the same business**: a `clean/` version with no injected problems, and an `anomalies/` version — identical stores, SKUs, customers, and promotions — with two realistic inventory problems deliberately injected (stockouts on bestsellers, dead stock on slow movers) plus a ground-truth answer key labeling exactly what was changed.

100% synthetic. No real store, product, customer, or transaction data was used.

---

## Files

### `clean/`

| File | Rows | Columns |
|---|---|---|
| `store_master.csv` | 30 | 5 |
| `sku_master.csv` | 5,000 | 7 |
| `customer_master.csv` | 10,000 | 7 |
| `promotions.csv` | 100 | 8 |
| `inventory_snapshot.csv` | 21,228 | 6 |
| `sales_transactions.csv` | 10,000,000 | 11 |

### `anomalies/`

| File | Rows | Columns |
|---|---|---|
| `store_master.csv` | 30 | 5 |
| `sku_master.csv` | 5,000 | 7 |
| `customer_master.csv` | 10,000 | 7 |
| `promotions.csv` | 100 | 8 |
| `inventory_snapshot.csv` | 21,228 | 6 |
| `sales_transactions.csv` | ~10,000,000* | 11 |
| `sku_inventory_flags.csv` | ~240 | 6 |

*Slightly under 10,000,000 — the transaction rows that fall inside a simulated stockout window are removed as "lost sales" (see below). `store_master.csv`, `sku_master.csv`, `customer_master.csv`, and `promotions.csv` are byte-for-byte identical to `clean/`.

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

---

## Relationships

```ini
store_master.store_id        ──┐
sku_master.sku_id             ─┼──▶ sales_transactions.csv
customer_master.cust_id       ─┤     (store_id, sku_id, customer_id, promo_id)
promotions.promo_id           ─┘

store_master.store_id  ──┐
sku_master.sku_id        ─┴──▶ inventory_snapshot.csv

sku_master.sku_id  ──▶ sku_inventory_flags.csv   (anomalies/ only)
```

Referential integrity was validated across all transaction rows in both versions: zero orphaned foreign keys, zero mismatches between `total_value` and its formula.

## The two versions, and why

`clean/` is the dataset as originally generated — no injected problems, just a realistic four-year retail history.

`anomalies/` starts from the exact same simulated business and deliberately injects two inventory problems that retailers actually deal with:

- __`STOCKOUT_RISK`__ — the chain's real best-sellers (ranked by actual observed sales volume, not a hidden weight) are driven to zero stock at 30–60% of stores for a 10–30 day window sometime in the last ~75 days of the data. Every transaction row that would have occurred in that exact store × SKU × date window is removed, simulating a lost sale that a POS system would never record.
- __`SLOW_MOVER`__ — the chain's real worst-sellers are overstocked at 3–6x their reorder point across 50–100% of stores, with a stale `last_restock_date`, simulating cash tied up in inventory that isn't moving.

Every flagged SKU, the stores it affects, and (for stockouts) the exact date window is recorded in `sku_inventory_flags.csv`, so you always have a known-correct answer key to score your own reorder/clearance rules or anomaly-detection models against — rather than having to eyeball whether your rule "found the right thing."

## What makes this data realistic (not random)

- __Baskets, not isolated rows__ — `receipt_id` groups 1–5 items per visit (avg. 1.93 items/receipt), enabling market-basket analysis.
- **Seasonality & growth** — Nov/Dec sales peaks, a Feb trough, and ~6%/year growth are built into the date distribution.
- **Bestsellers exist** — SKU sales follow a Pareto-style skew rather than uniform random selection, and it's this same skew that determines which SKUs get flagged as stockout-risk (top) or slow-mover (bottom) in `anomalies/`.
- __Loyalty drives frequency__ — Gold/Platinum customers transact more often; each customer favors their `preferred_channel` ~70% of the time.
- **Promotions actually target something** — ~21% of transactions carry a promo, matched by category, brand, specific SKU, or store-wide, against the active date window.

## Things to know before modeling

- Only `sales_transactions` was scaled to 10M rows — the store, SKU, customer, and promotion counts are fixed at realistic sizes and don't grow with transaction volume.
- All stores opened before 2022, so every store has data across the entire 2022–2025 window.
- `registration_date` in `customer_master.csv` is independent of transaction activity — don't assume a customer's first transaction always follows their registration date.
- If you're only using `clean/`, it behaves exactly like the original single-version dataset — nothing about it changes because `anomalies/` exists alongside it.
- `sales_transactions.csv` in `anomalies/` has slightly fewer rows than `clean/` — this is intentional (lost-sale suppression), not missing data.
- `sku_inventory_flags.csv` only exists in `anomalies/`, since `clean/` has nothing to flag.

## Suggested uses

- Sales forecasting and seasonality/trend analysis
- Customer segmentation and RFM modeling
- Market basket analysis
- Inventory optimization and reorder-point tuning
- Promotion effectiveness and discount ROI analysis
- Retail BI dashboards
- Stockout / lost-sale detection and slow-mover (dead stock) identification, scored against `sku_inventory_flags.csv`
- Anomaly-detection benchmarking using `clean/` as the negative class and `anomalies/` as the positive class

## License

Apache License 2.0 — fully synthetic, free to use, modify, and redistribute, with attribution and notice of any changes.
