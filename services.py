"""Ordinary functions for validation, CSV imports, and stock changes."""
import csv
import io
from datetime import date
from decimal import Decimal, InvalidOperation


def required(value, label, limit=120):
    value = str(value or '').strip()
    if not value or len(value) > limit:
        raise ValueError(f'{label} must contain 1–{limit} characters.')
    return value


def integer(value, label, minimum=0):
    try:
        number = int(str(value))
    except (ValueError, TypeError):
        raise ValueError(f'{label} must be a whole number.') from None
    if not minimum <= number <= 1_000_000:
        raise ValueError(f'{label} must be between {minimum:,} and 1,000,000.')
    return number


def money(value):
    try:
        number = Decimal(str(value))
        if not number.is_finite() or not 0 <= number <= 1_000_000:
            raise ValueError
        cents = number * 100
        if cents != cents.to_integral_value():
            raise ValueError
        return int(cents)
    except (InvalidOperation, ValueError):
        raise ValueError('Prices and costs must be 0–1,000,000 with at most two decimal places.') from None


def add_product(db, data):
    sku = required(data.get('sku'), 'SKU', 40).upper()
    if db.execute('SELECT 1 FROM products WHERE sku=?', (sku,)).fetchone():
        raise ValueError(f'SKU {sku} already exists. Use Restock to add inventory.')
    db.execute('INSERT INTO products VALUES (?, ?, ?, ?, ?, ?, ?)', (
        sku, required(data.get('name'), 'Product name'),
        required(data.get('category'), 'Category', 50), money(data.get('price')),
        money(data.get('cost')), integer(data.get('stock'), 'Opening stock'),
        integer(data.get('reorder_level'), 'Reorder level')))


def record_sale(db, data):
    reference = required(data.get('reference'), 'Sale reference', 60)
    if db.execute('SELECT 1 FROM sales WHERE reference=?', (reference,)).fetchone():
        raise ValueError(f'Sale reference {reference} already exists. Nothing was imported twice.')
    sku = required(data.get('sku'), 'SKU', 40).upper()
    product = db.execute('SELECT * FROM products WHERE sku=?', (sku,)).fetchone()
    if not product:
        raise ValueError(f'Unknown SKU: {sku}. Add the product first.')
    try:
        sold_on = date.fromisoformat(str(data.get('sold_on', '')))
    except ValueError:
        raise ValueError('Sale date must be a valid YYYY-MM-DD date.') from None
    if sold_on > date.today():
        raise ValueError('Sale date cannot be in the future.')
    quantity = integer(data.get('quantity'), 'Quantity', 1)
    price = money(data['unit_price']) if str(data.get('unit_price', '')).strip() else product['price_cents']
    cost = money(data['unit_cost']) if str(data.get('unit_cost', '')).strip() else product['cost_cents']
    updated = db.execute('UPDATE products SET stock=stock-? WHERE sku=? AND stock>=?',
                         (quantity, sku, quantity))
    if updated.rowcount != 1:
        raise ValueError(f'Not enough stock for {sku}: {product["stock"]} available.')
    db.execute('''INSERT INTO sales
        (reference, sku, sold_on, quantity, price_cents, cost_cents)
        VALUES (?, ?, ?, ?, ?, ?)''', (reference, sku, sold_on.isoformat(), quantity, price, cost))


def restock(db, data):
    quantity = integer(data.get('quantity'), 'Restock quantity', 1)
    sku = required(data.get('sku'), 'SKU', 40)
    if db.execute('UPDATE products SET stock=stock+? WHERE sku=?', (quantity, sku)).rowcount != 1:
        raise ValueError('Product not found.')
    db.execute('INSERT INTO restocks(sku, quantity) VALUES (?, ?)', (sku, quantity))


def import_csv(db, upload, kind):
    if kind not in ('products', 'sales'):
        raise ValueError('Choose products or sales.')
    if not upload or not upload.filename:
        raise ValueError('Choose a CSV file first.')
    try:
        contents = upload.read().decode('utf-8-sig')
    except UnicodeDecodeError:
        raise ValueError('Save your file as a UTF-8 CSV.') from None
    reader = csv.DictReader(io.StringIO(contents), strict=True)
    columns = {'products': {'sku', 'name', 'category', 'price', 'cost', 'stock', 'reorder_level'},
               'sales': {'reference', 'sku', 'sold_on', 'quantity', 'unit_price', 'unit_cost'}}
    if not columns[kind].issubset(reader.fieldnames or []):
        raise ValueError('Missing columns. Download the matching example CSV and keep its headers.')
    count = 0
    for row in reader:
        count += 1
        if count > 2000:
            raise ValueError('Import at most 2,000 rows at a time.')
        if None in row or any(value is None for value in row.values()):
            raise ValueError(f'CSV row {reader.line_num}: column count does not match the headers.')
        try:
            (add_product if kind == 'products' else record_sale)(db, row)
        except ValueError as error:
            raise ValueError(f'CSV row {reader.line_num}: {error}') from None
    if not count:
        raise ValueError('This CSV has no data rows.')
    return count
