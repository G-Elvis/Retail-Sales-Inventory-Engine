"""Database schema definition, initialization, and sample data population."""

import sqlite3
from typing import Sequence
from app.database.connection import create_connection

CREATE_PRODUCTS_TABLE = """
CREATE TABLE IF NOT EXISTS Products (
    product_id INTEGER PRIMARY KEY AUTOINCREMENT,
    product_name TEXT NOT NULL CHECK(length(trim(product_name)) > 0),
    category TEXT NOT NULL CHECK(length(trim(category)) > 0),
    unit_price REAL NOT NULL CHECK(unit_price > 0),
    stock_quantity INTEGER NOT NULL CHECK(stock_quantity >= 0),
    reorder_level INTEGER NOT NULL CHECK(reorder_level >= 0),
    branch TEXT NOT NULL CHECK(length(trim(branch)) > 0)
);
"""

CREATE_SALES_TABLE = """
CREATE TABLE IF NOT EXISTS Sales (
    sale_id INTEGER PRIMARY KEY AUTOINCREMENT,
    product_id INTEGER NOT NULL,
    quantity INTEGER NOT NULL CHECK(quantity > 0),
    unit_price_at_sale REAL NOT NULL CHECK(unit_price_at_sale > 0),
    total_amount REAL NOT NULL CHECK(total_amount > 0),
    branch TEXT NOT NULL CHECK(length(trim(branch)) > 0),
    sale_date TEXT NOT NULL DEFAULT (strftime('%Y-%m-%d %H:%M:%S', 'now', 'localtime')),
    FOREIGN KEY (product_id) REFERENCES Products(product_id) ON DELETE RESTRICT
);
"""

# Indexes for MIS analytical query acceleration
CREATE_INDEXES = """
CREATE INDEX IF NOT EXISTS idx_sales_date ON Sales(sale_date);
CREATE INDEX IF NOT EXISTS idx_sales_branch ON Sales(branch);
CREATE INDEX IF NOT EXISTS idx_products_stock ON Products(stock_quantity, reorder_level);
"""

SAMPLE_PRODUCTS = [
    ("Wireless Bluetooth Mouse", "Electronics", 25.50, 45, 10, "Nairobi Central"),
    ("Mechanical Gaming Keyboard", "Electronics", 85.00, 18, 5, "Nairobi Central"),
    ("USB-C Fast Charging Cable 2m", "Electronics", 12.00, 60, 15, "Mombasa Old Town"),
    ("Ergonomic Mesh Office Chair", "Furniture", 195.00, 8, 4, "Kisumu City"),
    ("Premium Arabica Coffee Beans 1kg", "Grocery", 22.00, 75, 20, "Nairobi Central"),
    ("Organic Green Tea 100 Bags", "Grocery", 9.50, 5, 15, "Nairobi Central"),  # Low stock
    ("Ultra-HD 27-inch Monitor", "Electronics", 280.00, 12, 5, "Mombasa Old Town"),
    ("Stainless Steel Water Bottle 1L", "Accessories", 15.00, 4, 10, "Kisumu City"),  # Low stock
    ("Noise-Cancelling Headphones", "Electronics", 150.00, 2, 6, "Nairobi Central"),  # Low stock
    ("Heavy-Duty Standing Desk", "Furniture", 340.00, 15, 3, "Kisumu City")
]


def init_db(conn: sqlite3.Connection | None = None) -> None:
    """Initialize schema tables and indexes."""
    should_close = False
    if conn is None:
        conn = create_connection()
        should_close = True

    try:
        with conn:
            conn.execute(CREATE_PRODUCTS_TABLE)
            conn.execute(CREATE_SALES_TABLE)
            conn.executescript(CREATE_INDEXES)
    finally:
        if should_close:
            conn.close()


def seed_sample_data(conn: sqlite3.Connection | None = None) -> int:
    """
    Insert initial sample inventory products if table is empty.
    Returns number of products seeded.
    """
    should_close = False
    if conn is None:
        conn = create_connection()
        should_close = True

    try:
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) AS cnt FROM Products;")
        count = cursor.fetchone()["cnt"]
        if count == 0:
            cursor.executemany(
                """
                INSERT INTO Products (product_name, category, unit_price, stock_quantity, reorder_level, branch)
                VALUES (?, ?, ?, ?, ?, ?);
                """,
                SAMPLE_PRODUCTS
            )
            conn.commit()
            return len(SAMPLE_PRODUCTS)
        return 0
    finally:
        if should_close:
            conn.close()


if __name__ == "__main__":
    init_db()
    seeded = seed_sample_data()
    print(f"Database initialized. Seeded {seeded} sample products.")
