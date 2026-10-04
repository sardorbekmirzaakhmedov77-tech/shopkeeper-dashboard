# Rebuild Shopkeeper after Angela Yu's Python course

This project combines skills from the course. It is not an official course
assignment, and finishing the course will not make every line instantly familiar.
The additional concepts below are deliberately small, useful extensions.

## How the pieces fit

```text
Browser opens a page or submits a form
                 |
              app.py                 Flask routes and request handling
             /      \
     services.py    analytics.py     Business rules / Pandas and Plotly
             \      /
               db.py                SQL tables and transactions
                 |
         instance/shop.db           Saved products, sales, restocks

Flask renders templates/*.html with the results.
static/style.css controls presentation.
```

## Course skills used here

| Course topic | Where you use it |
|---|---|
| Variables, numbers, strings, if/else | Validating quantities, formatting money, checking stock |
| Functions and dictionaries | Small business-rule functions and Flask form data |
| Loops and collections | Processing CSV rows and displaying products |
| Exceptions | Helpful error messages and import rejection |
| Files and CSV | Imports, exports, and example files |
| HTML and CSS | Responsive layouts, forms, navigation, and tables |
| Flask and Jinja | Routes and templates; loops and filters inside HTML |
| SQL and databases | Persisting products and sales, joining their records |
| Pandas | Grouping daily sales and finding best sellers |
| Plotly | Interactive revenue and profit chart |

The broad topic mapping follows the publicly advertised curriculum:
https://www.udemy.com/course/100-days-of-code/
Libraries may be newer than the versions used in lessons. This project uses the
standard-library `sqlite3` module directly, rather than an ORM, to keep the
database rules visible as ordinary SQL.

## Small additions beyond the course exercises

1. **Integer cents and Decimal:** $10.25 becomes 1025 in storage. `money()` checks
   input with `Decimal`, then converts it to cents. All sale arithmetic uses
   integers; division by 100 happens only for charts and display.
2. **Transactions:** `with connect(...) as db:` commits only if every operation
   succeeds. An exception rolls back all changes. This is why a bad second CSV
   row cannot leave the first row saved or reduce inventory accidentally.
3. **Historical snapshots:** A sale stores its own unit price and cost. Later
   product changes therefore cannot rewrite historical profit.
4. **Conditional stock updates:** The SQL update only succeeds when stock is
   sufficient. The code checks the affected row count before saving the sale.
5. **CSRF token:** Each form sends a random token checked against the session.
   Flask's `session` stores signed cookie data. This is form protection, not login.
6. **Tests:** Python's built-in `unittest` runs business scenarios against a
   temporary database. The test client's HTTP calls run without a browser.
7. **Application factory:** `create_app()` makes an application. Passing a database
   path makes it easy to test without touching the real shop.

## A practical build sequence

### 1. Build a shop in the terminal

Create a list of product dictionaries. Write `record_sale()` that subtracts a
quantity and calculates revenue and gross profit. Reject insufficient stock.
Try the $20 price / $8 cost / 2-unit example: $40 revenue, $24 gross profit.

### 2. Make it persistent

Create `products` and `sales` tables in SQLite. Use `?` placeholders for SQL
parameters. Write one product, close Python, reopen it, and read it back.
Then store a sale and update its stock inside one transaction.

### 3. Make a simple Flask website

Build `/inventory` with an HTML table. Add a product form and POST route.
After saving, redirect back to the list. Learn this request → validate → save
→ redirect pattern before adding more screens.

### 4. Record sales and restocks

Add a product selector, quantity, date, and unique sale reference. Store price
and cost snapshots. Add a restock form. At this stage, your project is already
useful even without a dashboard.

### 5. Calculate the dashboard

Read sales into Pandas. Add revenue and profit columns. Use `sum()` for totals
and `groupby()` for daily figures and best sellers. Check the results manually
with three known transactions before making charts.

### 6. Add Plotly and date filters

Draw revenue and profit over time. Fill days without sales with zero. Pass
start/end dates from the browser to the query. Clearly distinguish historical
sales figures from current inventory figures.

### 7. Import and export

Read with `csv.DictReader`. Reuse the same `add_product()` and `record_sale()`
functions used by forms. Put the entire import inside one transaction. Test
with a file where the first row is valid and the second row is invalid.

### 8. Polish and verify

Style the pages, add empty states and error messages, and make mobile layouts
readable. Run the test suite. Ask someone to add a product and record a sale
without your help; their confusion tells you what to improve.

## Read the source in this order

1. `db.py`: understand the three tables first; skip demo generation initially.
2. `services.py`: read `money()`, `add_product()`, and `record_sale()`.
3. `app.py`: follow `inventory()`, `sales_page()`, and `action()`.
4. `templates/inventory.html`: connect form field names to Python dictionary keys.
5. `analytics.py`: follow one sale from SQL to Pandas to the chart.
6. `tests/test_app.py`: use test scenarios as small programming exercises.
7. `static/style.css`: study the layout after you understand the app behavior.

## Good next exercises

- Add a category filter to the dashboard.
- Add product editing while preserving sale snapshots.
- Compare revenue against the previous period of equal length.
- Show the restock audit history on a page.
- Add a returns table and explicitly define how refunds affect stock and profit.
- Add login and restrict every page before deploying for multiple users.

Build one extension at a time. The goal is to explain the code and its behavior,
not to memorize the completed source.
