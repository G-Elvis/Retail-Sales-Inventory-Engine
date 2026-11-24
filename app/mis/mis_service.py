"""Management Information System (MIS) Service Layer.

Provides executive, tactical, and managerial reporting by aggregating raw TPS
transaction data directly within SQLite using analytical SQL queries.
"""

import sqlite3
from typing import Any, Dict, List, Optional
from datetime import datetime
from app.database.connection import create_connection


class MISService:
    """Service providing core MIS analytical reporting."""

    def __init__(self, db_path: Optional[str] = None):
        self.db_path = db_path

    def _get_connection(self) -> sqlite3.Connection:
        return create_connection(self.db_path)

    # -------------------------------------------------------------------------
    # 1. Daily Revenue Report
    # -------------------------------------------------------------------------

    def get_daily_revenue_report(self, target_date: Optional[str] = None) -> Dict[str, Any]:
        """
        Generate daily revenue report grouped by branch for a specific date (YYYY-MM-DD).
        If target_date is None, defaults to current date.
        
        SQL Concepts Used:
        - WHERE date(sale_date) = ? : Filters rows by date ignoring timestamp hours.
        - GROUP BY branch : Divides records into discrete branch buckets.
        - SUM(total_amount), SUM(quantity), COUNT(sale_id) : Aggregates branch metrics.
        """
        if not target_date:
            target_date = datetime.now().strftime("%Y-%m-%d")

        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            
            # Branch-wise aggregation query
            cursor.execute(
                """
                SELECT 
                    branch,
                    COUNT(sale_id) AS transaction_count,
                    COALESCE(SUM(quantity), 0) AS total_units_sold,
                    COALESCE(SUM(total_amount), 0.0) AS total_revenue
                FROM Sales
                WHERE date(sale_date) = date(?)
                GROUP BY branch
                ORDER BY total_revenue DESC;
                """,
                (target_date,)
            )
            branch_records = [dict(row) for row in cursor.fetchall()]

            # Overall daily summary query
            cursor.execute(
                """
                SELECT 
                    COUNT(sale_id) AS overall_transactions,
                    COALESCE(SUM(quantity), 0) AS overall_units_sold,
                    COALESCE(SUM(total_amount), 0.0) AS overall_revenue
                FROM Sales
                WHERE date(sale_date) = date(?);
                """,
                (target_date,)
            )
            overall = dict(cursor.fetchone() or {})

            return {
                "report_date": target_date,
                "overall_revenue": round(overall.get("overall_revenue", 0.0), 2),
                "overall_transactions": overall.get("overall_transactions", 0),
                "overall_units_sold": overall.get("overall_units_sold", 0),
                "branch_breakdown": branch_records
            }
        finally:
            conn.close()

    # -------------------------------------------------------------------------
    # 2. Weekly Revenue Report
    # -------------------------------------------------------------------------

    def get_weekly_revenue_report(self, target_date: Optional[str] = None) -> Dict[str, Any]:
        """
        Generate weekly revenue report for the calendar week of the specified target date.
        
        SQL Concepts Used:
        - strftime('%Y-%W', sale_date) : Computes ISO year and week number.
        - GROUP BY branch : Groups weekly revenue by store branch.
        """
        if not target_date:
            target_date = datetime.now().strftime("%Y-%m-%d")

        conn = self._get_connection()
        try:
            cursor = conn.cursor()

            # Identify target week identifier (e.g., '2026-47')
            cursor.execute("SELECT strftime('%Y-%W', ?) AS week_id;", (target_date,))
            week_id = cursor.fetchone()["week_id"]

            cursor.execute(
                """
                SELECT 
                    branch,
                    strftime('%Y-%W', sale_date) AS week_number,
                    COUNT(sale_id) AS transaction_count,
                    COALESCE(SUM(quantity), 0) AS total_units_sold,
                    COALESCE(SUM(total_amount), 0.0) AS total_revenue
                FROM Sales
                WHERE strftime('%Y-%W', sale_date) = ?
                GROUP BY branch
                ORDER BY total_revenue DESC;
                """,
                (week_id,)
            )
            branch_records = [dict(row) for row in cursor.fetchall()]

            # Total for the week
            cursor.execute(
                """
                SELECT 
                    COUNT(sale_id) AS overall_transactions,
                    COALESCE(SUM(quantity), 0) AS overall_units_sold,
                    COALESCE(SUM(total_amount), 0.0) AS overall_revenue
                FROM Sales
                WHERE strftime('%Y-%W', sale_date) = ?;
                """,
                (week_id,)
            )
            overall = dict(cursor.fetchone() or {})

            return {
                "reference_date": target_date,
                "week_identifier": week_id,
                "overall_revenue": round(overall.get("overall_revenue", 0.0), 2),
                "overall_transactions": overall.get("overall_transactions", 0),
                "overall_units_sold": overall.get("overall_units_sold", 0),
                "branch_breakdown": branch_records
            }
        finally:
            conn.close()

    # -------------------------------------------------------------------------
    # 3. Low-Stock Alerts & Automated Reorder Recommendations
    # -------------------------------------------------------------------------

    def get_low_stock_alerts(self) -> List[Dict[str, Any]]:
        """
        Scan inventory for products where stock_quantity <= reorder_level.
        Calculates recommended reorder quantity: (reorder_level * 2) - stock_quantity.
        
        SQL Concepts Used:
        - WHERE stock_quantity <= reorder_level : Filter condition identifying replenishment needs.
        - Mathematical expression in SELECT: ((reorder_level * 2) - stock_quantity)
        - ORDER BY (stock_quantity * 1.0 / NULLIF(reorder_level, 0)) ASC : Prioritize most depleted items.
        """
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT 
                    product_id,
                    product_name,
                    category,
                    unit_price,
                    stock_quantity,
                    reorder_level,
                    branch,
                    CASE 
                        WHEN stock_quantity = 0 THEN 'CRITICAL (OUT OF STOCK)'
                        WHEN stock_quantity <= (reorder_level / 2) THEN 'HIGH (CRITICAL LEVEL)'
                        ELSE 'MEDIUM (REORDER THRESHOLD)'
                    END AS urgency_level,
                    ((reorder_level * 2) - stock_quantity) AS recommended_order_qty,
                    ROUND(((reorder_level * 2) - stock_quantity) * unit_price, 2) AS estimated_reorder_cost
                FROM Products
                WHERE stock_quantity <= reorder_level
                ORDER BY stock_quantity ASC, reorder_level DESC;
                """
            )
            return [dict(row) for row in cursor.fetchall()]
        finally:
            conn.close()

    # -------------------------------------------------------------------------
    # 4. Comprehensive Sales Performance Summaries
    # -------------------------------------------------------------------------

    def get_sales_summary(self, top_n: int = 5) -> Dict[str, Any]:
        """
        Compile strategic performance metrics:
        - Lifetime gross revenue and total transactions.
        - Best-selling products by quantity.
        - Highest revenue-generating products.
        - Branch revenue distribution.
        
        SQL Concepts Used:
        - INNER JOIN Products ON Sales.product_id = Products.product_id
        - GROUP BY Products.product_id
        - ORDER BY total_units DESC / total_revenue DESC LIMIT N
        """
        conn = self._get_connection()
        try:
            cursor = conn.cursor()

            # 1. Macro Summary
            cursor.execute(
                """
                SELECT 
                    COUNT(sale_id) AS total_sales_count,
                    COALESCE(SUM(quantity), 0) AS total_items_sold,
                    COALESCE(SUM(total_amount), 0.0) AS gross_revenue,
                    COALESCE(AVG(total_amount), 0.0) AS avg_transaction_value
                FROM Sales;
                """
            )
            macro = dict(cursor.fetchone() or {})

            # 2. Best Sellers by Units Sold
            cursor.execute(
                """
                SELECT 
                    s.product_id,
                    p.product_name,
                    p.category,
                    SUM(s.quantity) AS total_units_sold,
                    ROUND(SUM(s.total_amount), 2) AS total_revenue_generated
                FROM Sales s
                JOIN Products p ON s.product_id = p.product_id
                GROUP BY s.product_id, p.product_name, p.category
                ORDER BY total_units_sold DESC
                LIMIT ?;
                """,
                (top_n,)
            )
            top_by_units = [dict(row) for row in cursor.fetchall()]

            # 3. Best Sellers by Revenue Generated
            cursor.execute(
                """
                SELECT 
                    s.product_id,
                    p.product_name,
                    p.category,
                    SUM(s.quantity) AS total_units_sold,
                    ROUND(SUM(s.total_amount), 2) AS total_revenue_generated
                FROM Sales s
                JOIN Products p ON s.product_id = p.product_id
                GROUP BY s.product_id, p.product_name, p.category
                ORDER BY total_revenue_generated DESC
                LIMIT ?;
                """,
                (top_n,)
            )
            top_by_revenue = [dict(row) for row in cursor.fetchall()]

            # 4. Branch Distribution
            cursor.execute(
                """
                SELECT 
                    branch,
                    COUNT(sale_id) AS transactions,
                    SUM(quantity) AS units_sold,
                    ROUND(SUM(total_amount), 2) AS branch_revenue,
                    ROUND(AVG(total_amount), 2) AS avg_basket_value
                FROM Sales
                GROUP BY branch
                ORDER BY branch_revenue DESC;
                """
            )
            branch_distribution = [dict(row) for row in cursor.fetchall()]

            return {
                "macro_summary": {
                    "total_sales_count": macro.get("total_sales_count", 0),
                    "total_items_sold": macro.get("total_items_sold", 0),
                    "gross_revenue": round(macro.get("gross_revenue", 0.0), 2),
                    "avg_transaction_value": round(macro.get("avg_transaction_value", 0.0), 2)
                },
                "top_products_by_units": top_by_units,
                "top_products_by_revenue": top_by_revenue,
                "branch_distribution": branch_distribution
            }
        finally:
            conn.close()
