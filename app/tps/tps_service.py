"""Transaction Processing System (TPS) Service Layer.

Handles operational point-of-sale events, inventory modifications, and ensures
ACID transaction boundaries (commit and rollback).
"""

import sqlite3
from typing import Any, Dict, List, Optional
from app.database.connection import create_connection


class TPSError(Exception):
    """Base exception for TPS operations."""
    pass


class ProductNotFoundError(TPSError):
    """Raised when a specified product_id does not exist."""
    pass


class InsufficientStockError(TPSError):
    """Raised when on-hand stock is less than the requested transaction quantity."""
    pass


class InvalidTransactionDataError(TPSError):
    """Raised when inputs violate business validation rules."""
    pass


class TPSService:
    """Service providing core TPS operational functionality."""

    def __init__(self, db_path: Optional[str] = None):
        self.db_path = db_path

    def _get_connection(self) -> sqlite3.Connection:
        return create_connection(self.db_path)

    # -------------------------------------------------------------------------
    # Product Catalog Management
    # -------------------------------------------------------------------------

    def add_product(
        self,
        product_name: str,
        category: str,
        unit_price: float,
        stock_quantity: int,
        reorder_level: int,
        branch: str
    ) -> int:
        """
        Add a new product to inventory catalog.
        Returns the generated product_id.
        """
        name = product_name.strip()
        cat = category.strip()
        br = branch.strip()

        if not name:
            raise InvalidTransactionDataError("Product name cannot be empty.")
        if not cat:
            raise InvalidTransactionDataError("Category cannot be empty.")
        if not br:
            raise InvalidTransactionDataError("Branch cannot be empty.")
        if unit_price <= 0:
            raise InvalidTransactionDataError(f"Unit price must be positive (received {unit_price}).")
        if stock_quantity < 0:
            raise InvalidTransactionDataError(f"Initial stock cannot be negative (received {stock_quantity}).")
        if reorder_level < 0:
            raise InvalidTransactionDataError(f"Reorder level cannot be negative (received {reorder_level}).")

        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO Products (product_name, category, unit_price, stock_quantity, reorder_level, branch)
                VALUES (?, ?, ?, ?, ?, ?);
                """,
                (name, cat, round(float(unit_price), 2), int(stock_quantity), int(reorder_level), br)
            )
            conn.commit()
            return cursor.lastrowid
        except sqlite3.Error as e:
            conn.rollback()
            raise TPSError(f"Database error adding product: {e}") from e
        finally:
            conn.close()

    def get_all_products(self) -> List[Dict[str, Any]]:
        """Retrieve all products from the catalog."""
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT product_id, product_name, category, unit_price, stock_quantity, reorder_level, branch
                FROM Products
                ORDER BY product_id ASC;
                """
            )
            return [dict(row) for row in cursor.fetchall()]
        finally:
            conn.close()

    def get_product_by_id(self, product_id: int) -> Dict[str, Any]:
        """Fetch a specific product by its primary key."""
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT product_id, product_name, category, unit_price, stock_quantity, reorder_level, branch
                FROM Products
                WHERE product_id = ?;
                """,
                (product_id,)
            )
            row = cursor.fetchone()
            if not row:
                raise ProductNotFoundError(f"Product ID {product_id} not found in inventory catalog.")
            return dict(row)
        finally:
            conn.close()

    def search_products(self, query: str) -> List[Dict[str, Any]]:
        """Search products by name or category matching query keyword."""
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            search_pattern = f"%{query.strip()}%"
            cursor.execute(
                """
                SELECT product_id, product_name, category, unit_price, stock_quantity, reorder_level, branch
                FROM Products
                WHERE product_name LIKE ? OR category LIKE ?
                ORDER BY product_name ASC;
                """,
                (search_pattern, search_pattern)
            )
            return [dict(row) for row in cursor.fetchall()]
        finally:
            conn.close()

    # -------------------------------------------------------------------------
    # Transaction Processing: Atomic Sales Execution
    # -------------------------------------------------------------------------

    def record_sale(
        self,
        product_id: int,
        quantity: int,
        branch: Optional[str] = None,
        custom_date: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Record a retail sale transaction atomically.
        
        ACID Transaction Workflow:
        1. Validates that quantity is positive integer (> 0).
        2. Retrieves product from DB within an explicit transaction.
        3. Validates that product exists and has sufficient stock.
        4. Calculates total_amount = quantity * unit_price_at_sale.
        5. Deducts quantity from Products.stock_quantity.
        6. Inserts transaction record into Sales table.
        7. Issues conn.commit() if both succeed, or conn.rollback() on any error.
        
        Returns receipt dict containing transaction summary.
        """
        if not isinstance(quantity, int) or quantity <= 0:
            raise InvalidTransactionDataError(f"Quantity must be a positive integer greater than 0. Received: {quantity}")

        conn = self._get_connection()
        try:
            # Begin explicit transaction
            conn.execute("BEGIN TRANSACTION;")
            cursor = conn.cursor()

            # Step 1: Check product existence and live stock
            cursor.execute(
                """
                SELECT product_id, product_name, category, unit_price, stock_quantity, branch
                FROM Products
                WHERE product_id = ?;
                """,
                (product_id,)
            )
            product = cursor.fetchone()

            if not product:
                conn.rollback()
                raise ProductNotFoundError(f"Cannot process sale: Product ID {product_id} does not exist.")

            current_stock = product["stock_quantity"]
            unit_price = product["unit_price"]
            product_name = product["product_name"]
            sale_branch = branch.strip() if branch and branch.strip() else product["branch"]

            # Step 2: Validate inventory sufficiency
            if current_stock < quantity:
                conn.rollback()
                raise InsufficientStockError(
                    f"Insufficient inventory for '{product_name}' (ID {product_id}). "
                    f"Available stock: {current_stock}, Requested: {quantity}."
                )

            # Step 3: Compute financial values
            total_amount = round(quantity * unit_price, 2)
            new_stock = current_stock - quantity

            # Step 4: Atomic Step A - Deduct inventory
            cursor.execute(
                """
                UPDATE Products
                SET stock_quantity = ?
                WHERE product_id = ?;
                """,
                (new_stock, product_id)
            )

            # Step 5: Atomic Step B - Insert sales transaction record
            if custom_date:
                cursor.execute(
                    """
                    INSERT INTO Sales (product_id, quantity, unit_price_at_sale, total_amount, branch, sale_date)
                    VALUES (?, ?, ?, ?, ?, ?);
                    """,
                    (product_id, quantity, unit_price, total_amount, sale_branch, custom_date)
                )
            else:
                cursor.execute(
                    """
                    INSERT INTO Sales (product_id, quantity, unit_price_at_sale, total_amount, branch)
                    VALUES (?, ?, ?, ?, ?);
                    """,
                    (product_id, quantity, unit_price, total_amount, sale_branch)
                )

            sale_id = cursor.lastrowid

            # Step 6: Commit transaction to disk
            conn.commit()

            return {
                "sale_id": sale_id,
                "product_id": product_id,
                "product_name": product_name,
                "quantity": quantity,
                "unit_price_at_sale": unit_price,
                "total_amount": total_amount,
                "branch": sale_branch,
                "remaining_stock": new_stock,
                "status": "SUCCESS"
            }

        except Exception as e:
            # If any failure occurs, rollback any partial changes to ensure atomicity
            conn.rollback()
            if isinstance(e, (ProductNotFoundError, InsufficientStockError, InvalidTransactionDataError)):
                raise
            raise TPSError(f"Transaction aborted due to system error: {e}") from e
        finally:
            conn.close()

    def get_recent_sales(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Retrieve recent sales records with joined product details."""
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT 
                    s.sale_id,
                    s.product_id,
                    p.product_name,
                    p.category,
                    s.quantity,
                    s.unit_price_at_sale,
                    s.total_amount,
                    s.branch,
                    s.sale_date
                FROM Sales s
                JOIN Products p ON s.product_id = p.product_id
                ORDER BY s.sale_id DESC
                LIMIT ?;
                """,
                (limit,)
            )
            return [dict(row) for row in cursor.fetchall()]
        finally:
            conn.close()
