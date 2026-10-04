# Shopkeeper

A small-business sales and inventory dashboard made with Python, Flask, SQLite,
Pandas, Plotly, and Jinja templates. Designed as a project you can rebuild after
Angela Yu's Python bootcamp. No frontend framework or handwritten JavaScript is
needed. Plotly supplies its own interactive chart code locally.

## Quick start

Install **Python 3.11 or later**. Download this repository using **Code → Download
ZIP**, extract it, and open a terminal inside the extracted project folder.

### macOS / Linux

```sh
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python app.py
```

### Windows (Command Prompt)

```bat
py -m venv .venv
.venv\Scripts\activate.bat
python -m pip install -r requirements.txt
python app.py
```

Open **http://127.0.0.1:5000**. Keep the terminal running; stop it with **Ctrl+C**.
The first launch creates a local database with six demo products and 60 days of
sample sales. No account, API key, or external service is required.

For later launches, activate the virtual environment and run `python app.py` again.
If port 5000 is occupied, use `PORT=5050 python app.py` on macOS/Linux, or run
`set PORT=5050` before `python app.py` in Windows Command Prompt. Then open
http://127.0.0.1:5050.

Tested with Python 3.14 on macOS.

## Features

- Revenue, gross profit, margin, and units sold for an inclusive date range.
- Interactive daily chart and top five products by revenue.
- Current inventory value at cost and low-stock alerts.
- Product creation, inventory search, restocking, and sale entry.
- Sale price/cost overrides and preserved historical costs.
- Atomic product/sales CSV imports: one bad row rolls back the whole file.
- Duplicate SKU and sale-reference rejection; no negative inventory.
- Complete CSV exports and working example files.
- Persistent local SQLite database, responsive pages, local chart assets.

## Try it: a ten-minute test

1. **Overview:** The new database starts with six demo products and 60 days of
   sample sales. Change the dates and hover over the chart. Its legend lets you
   hide or show a line. Sales totals and best sellers use the date filter;
   low-stock alerts and inventory value always show current stock.
2. **Inventory:** Add `TEST-MUG`, name `My test mug`, category `Home`, price
   `20.00`, cost `8.00`, opening stock `10`, reorder level `3`.
3. **Sales history:** Record a sale of **2** test mugs dated today. Leave unit
   price and cost blank. Expect **$40 revenue**, **$24 gross profit**, and
   **8 mugs remaining**. If the overview includes demo sales, its existing totals
   increase by these amounts; the new sale row shows the exact values.
4. Try selling **9** more test mugs. Expect an error and unchanged stock of **8**.
5. **Inventory:** Restock the mug by **5**. Expect **13** units.
6. **Import & export:** Download both examples. Import products, then sales.
   Expect tea stock **23** and coffee stock **17**. The example sales are dated
   January 10–11, 2026: filter the overview to those two days to see **$98
   revenue**, **$59 gross profit**, and **5 units** (unless you add other sales
   to those dates). Historical samples do not appear in today's default range.
7. Import the same sales file again. Expect a duplicate-reference error and no
   additional stock reduction.
8. Download your sales CSV and check the references and monetary values.
9. Restart the server. Your additions should still exist.

## Automated tests

With your virtual environment activated:

```sh
python -m unittest discover -s tests -v
```

Tests use temporary databases, never your shop data. They cover profit arithmetic,
stock updates, overselling, restocking, duplicate imports, transaction rollback,
historical costs, exports, date filters, persistence, CSRF, and page rendering.

## Data and business rules

- All amounts are **USD**, stored as integer cents. This avoids binary floating
   point errors during money calculations. Inputs support two decimal places.
- Revenue = quantity × unit selling price. Gross profit = quantity ×
   (selling price − recorded unit cost). Margin = gross profit / revenue.
   The displayed margin is zero when revenue is zero.
- Gross profit excludes taxes, refunds, shipping, rent, wages, and other expenses.
   It is not net profit. This is a learning dashboard, not accounting software.
- One sale row represents one product, not a multi-product customer order.
- Stock decreases for every recorded/imported sale, including backdated sales.
   Restocks increase stock and have an audit record in the database.
- Product imports add **new** SKUs. They do not overwrite existing products.
- Sale CSV columns: `reference,sku,sold_on,quantity,unit_price,unit_cost`.
   A blank price or cost uses the product default. Historical imports should
   provide actual historical prices and costs.
- Product CSV columns: `sku,name,category,price,cost,stock,reorder_level`.
- Import files must be UTF-8 CSV, at most 2 MB and 2,000 rows. Import products
   before sales, with enough opening stock to cover imported quantities.
- Exports include every record, regardless of dashboard date filters. Spreadsheet
   formula-like text is prefixed with an apostrophe for safe viewing. Exports are
   reports, not a lossless backup/restore mechanism.

## Back up or start fresh

Data lives in `instance/shop.db`. Stop the server and copy that file to back up
the entire shop. To start a fresh demo without losing data, stop the server,
**rename** the database to a backup name, then restart.

For a fresh empty shop, first move any existing database aside, then start with:

```sh
SHOP_DEMO=0 python app.py
```

On Windows Command Prompt, run `set SHOP_DEMO=0` then `python app.py` instead.
Activate your virtual environment first.

This option affects only a brand-new database; it never clears existing records.

## Scope

This is a local, single-user application bound to 127.0.0.1. It has no login,
payments, taxes, refunds, product editing/deletion, or multiple warehouses.
Add those as later learning projects. Before hosting publicly, add authentication,
authorization, production hosting, and a stable environment `SECRET_KEY`.

See [LEARNING_GUIDE.md](LEARNING_GUIDE.md) for the course mapping and a step-by-step rebuild plan.
