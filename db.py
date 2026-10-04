"""SQLite storage. Each sale keeps its original price and cost in cents."""
import random
import sqlite3
from contextlib import contextmanager
from datetime import date, timedelta
from pathlib import Path


@contextmanager
def connect(path):
    db = sqlite3.connect(path)
    db.row_factory = sqlite3.Row
    db.execute('PRAGMA foreign_keys = ON')
    try:
        with db:
            yield db
    finally:
        db.close()


def initialize(path, demo=True):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with connect(path) as db:
        # Only seed a brand-new database, never an existing empty shop.
        new = not db.execute("SELECT name FROM sqlite_master WHERE name='products'").fetchone()
        db.executescript('''
            CREATE TABLE IF NOT EXISTS products (
                sku TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                category TEXT NOT NULL,
                price_cents INTEGER NOT NULL CHECK(price_cents >= 0),
                cost_cents INTEGER NOT NULL CHECK(cost_cents >= 0),
                stock INTEGER NOT NULL CHECK(stock >= 0),
                reorder_level INTEGER NOT NULL CHECK(reorder_level >= 0)
            );
            CREATE TABLE IF NOT EXISTS sales (
                id INTEGER PRIMARY KEY,
                reference TEXT NOT NULL UNIQUE,
                sku TEXT NOT NULL REFERENCES products(sku),
                sold_on TEXT NOT NULL,
                quantity INTEGER NOT NULL CHECK(quantity > 0),
                price_cents INTEGER NOT NULL CHECK(price_cents >= 0),
                cost_cents INTEGER NOT NULL CHECK(cost_cents >= 0)
            );
            CREATE TABLE IF NOT EXISTS restocks (
                id INTEGER PRIMARY KEY,
                sku TEXT NOT NULL REFERENCES products(sku),
                quantity INTEGER NOT NULL CHECK(quantity > 0),
                recorded_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );
        ''')
        if new and demo:
            seed_demo(db)


def seed_demo(db):
    products = [
        ('MUG-01', 'Everyday ceramic mug', 'Home', 1800, 700, 32, 10),
        ('TOTE-01', 'Canvas market tote', 'Accessories', 2400, 900, 8, 12),
        ('NOTE-01', 'Dotted notebook', 'Stationery', 1400, 450, 46, 15),
        ('CANDLE-01', 'Amber & cedar candle', 'Home', 3200, 1300, 5, 8),
        ('BOTTLE-01', 'Everyday water bottle', 'Accessories', 2800, 1100, 21, 10),
        ('PEN-01', 'Fine-line pen set', 'Stationery', 1200, 400, 0, 15),
    ]
    db.executemany('INSERT INTO products VALUES (?, ?, ?, ?, ?, ?, ?)', products)
    rng = random.Random(42)
    # These are historical sales; the stock above is the current opening snapshot.
    for days_ago in range(59, -1, -1):
        for index in range(rng.randint(2, 5)):
            product = rng.choice(products)
            db.execute('''INSERT INTO sales
                (reference, sku, sold_on, quantity, price_cents, cost_cents)
                VALUES (?, ?, ?, ?, ?, ?)''', (
                f'DEMO-{days_ago:02}-{index}', product[0],
                (date.today() - timedelta(days=days_ago)).isoformat(),
                rng.randint(1, 4), product[3], product[4]))
