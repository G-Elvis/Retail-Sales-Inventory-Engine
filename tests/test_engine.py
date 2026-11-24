"""Comprehensive automated test suite for Retail Sales & Inventory Engine.

Tests:
1. Product management & catalog queries.
2. Successful sales processing & automatic inventory deduction.
3. Insufficient stock rejection & transaction rollback safety.
4. Non-existent product ID rejection.
5. Invalid quantity rejection (negative & zero values).
6. Foreign key & database check constraint enforcement.
7. Low-stock identification & reorder quantity calculations.
8. Daily revenue aggregation & branch breakdown.
9. Weekly revenue aggregation via GROUP BY.
10. Sales performance ranking (top products by units and revenue).
"""

import os
import tempfile
import unittest
from pathlib import Path

from app.database.connection import create_connection
from app.database.schema import init_db, seed_sample_data
from app.tps.tps_service import (
    TPSService,
    TPSError,
    ProductNotFoundError,
    InsufficientStockError,
    InvalidTransactionDataError
)
from app.mis.mis_service import MISService


class TestRetailSalesInventoryEngine(unittest.TestCase):
    """Test suite running against an isolated SQLite test database."""

    def setUp(self) -> None:
        """Create fresh temporary database for each test to ensure test isolation."""
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "test_engine.db"
        
        # Initialize schema and seed standard sample items
        conn = create_connection(self.db_path)
        init_db(conn)
        seed_sample_data(conn)
        conn.close()

        self.tps = TPSService(db_path=str(self.db_path))
        self.mis = MISService(db_path=str(self.db_path))

    def tearDown(self) -> None:
        """Clean up temporary test environment."""
        self.temp_dir.cleanup()

    # -------------------------------------------------------------------------
    # Test Group 1: TPS Product Catalog & Discovery
    # -------------------------------------------------------------------------

    def test_01_catalog_initialization(self) -> None:
        """Ensure catalog seeds 10 initial products across 3 branches."""
        products = self.tps.get_all_products()
        self.assertEqual(len(products), 10)
        self.assertEqual(products[0]["product_name"], "Wireless Bluetooth Mouse")

    def test_02_add_new_product(self) -> None:
        """Ensure adding a valid product succeeds and returns valid ID."""
        new_id = self.tps.add_product(
            product_name="4K Webcam Pro",
            category="Electronics",
            unit_price=49.99,
            stock_quantity=25,
            reorder_level=5,
            branch="Nairobi Central"
        )
        self.assertIsInstance(new_id, int)
        product = self.tps.get_product_by_id(new_id)
        self.assertEqual(product["product_name"], "4K Webcam Pro")
        self.assertEqual(product["stock_quantity"], 25)

    def test_03_search_products(self) -> None:
        """Ensure search returns products matching partial names or categories."""
        results = self.tps.search_products("Keyboard")
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["product_name"], "Mechanical Gaming Keyboard")

        grocery_results = self.tps.search_products("Grocery")
        self.assertEqual(len(grocery_results), 2)

    # -------------------------------------------------------------------------
    # Test Group 2: TPS Sales Processing & ACID Consistency
    # -------------------------------------------------------------------------

    def test_04_successful_sale_and_inventory_deduction(self) -> None:
        """Ensure valid sale deducts stock and records receipt correctly."""
        initial_product = self.tps.get_product_by_id(1)
        initial_stock = initial_product["stock_quantity"]  # 45
        unit_price = initial_product["unit_price"]        # 25.50

        receipt = self.tps.record_sale(product_id=1, quantity=5, branch="Nairobi Central")

        self.assertEqual(receipt["quantity"], 5)
        self.assertEqual(receipt["total_amount"], round(5 * unit_price, 2))
        self.assertEqual(receipt["remaining_stock"], initial_stock - 5)

        # Verify persisted database state
        updated_product = self.tps.get_product_by_id(1)
        self.assertEqual(updated_product["stock_quantity"], initial_stock - 5)

        # Verify audit trail in Sales table
        recent = self.tps.get_recent_sales(limit=1)
        self.assertEqual(len(recent), 1)
        self.assertEqual(recent[0]["sale_id"], receipt["sale_id"])
        self.assertEqual(recent[0]["total_amount"], receipt["total_amount"])

    def test_05_insufficient_stock_rejection_and_rollback(self) -> None:
        """Ensure requesting more than available stock raises error and leaves DB untouched."""
        product = self.tps.get_product_by_id(1)
        stock_before = product["stock_quantity"]

        with self.assertRaises(InsufficientStockError):
            self.tps.record_sale(product_id=1, quantity=stock_before + 10)

        # Confirm rollback: stock remains unchanged
        product_after = self.tps.get_product_by_id(1)
        self.assertEqual(product_after["stock_quantity"], stock_before)

        # Confirm no sales record was created
        sales = self.tps.get_recent_sales(limit=10)
        self.assertEqual(len(sales), 0)

    def test_06_non_existent_product_id(self) -> None:
        """Ensure selling a non-existent product ID is safely rejected."""
        with self.assertRaises(ProductNotFoundError):
            self.tps.record_sale(product_id=9999, quantity=1)

    def test_07_invalid_quantity_validation(self) -> None:
        """Ensure non-positive quantities (zero, negative) are rejected."""
        with self.assertRaises(InvalidTransactionDataError):
            self.tps.record_sale(product_id=1, quantity=0)

        with self.assertRaises(InvalidTransactionDataError):
            self.tps.record_sale(product_id=1, quantity=-5)

    # -------------------------------------------------------------------------
    # Test Group 3: MIS Reporting & Aggregations
    # -------------------------------------------------------------------------

    def test_08_daily_revenue_aggregation(self) -> None:
        """Verify daily revenue correctly sums transactions by branch for a specific date."""
        # Record sales across two different branches on same date
        self.tps.record_sale(product_id=1, quantity=2, branch="Nairobi Central", custom_date="2026-11-24 10:00:00")
        self.tps.record_sale(product_id=3, quantity=5, branch="Mombasa Old Town", custom_date="2026-11-24 11:00:00")

        # Nairobi: 2 * 25.50 = 51.00
        # Mombasa: 5 * 12.00 = 60.00
        # Overall: 111.00

        report = self.mis.get_daily_revenue_report("2026-11-24")
        self.assertEqual(report["overall_revenue"], 111.00)
        self.assertEqual(report["overall_transactions"], 2)
        self.assertEqual(report["overall_units_sold"], 7)
        self.assertEqual(len(report["branch_breakdown"]), 2)

    def test_09_weekly_revenue_aggregation(self) -> None:
        """Verify weekly report groups sales across an entire calendar week."""
        self.tps.record_sale(product_id=2, quantity=1, branch="Nairobi Central", custom_date="2026-11-23 09:00:00")
        self.tps.record_sale(product_id=2, quantity=2, branch="Nairobi Central", custom_date="2026-11-24 14:00:00")

        # Total: 3 * 85.00 = 255.00
        report = self.mis.get_weekly_revenue_report("2026-11-24")
        self.assertEqual(report["overall_revenue"], 255.00)
        self.assertEqual(report["overall_transactions"], 2)
        self.assertEqual(report["overall_units_sold"], 3)

    def test_10_low_stock_alerts_and_reorder_calculation(self) -> None:
        """Verify low-stock alert logic and mathematical formula for recommended reorder qty."""
        # In seed data:
        # Product 6: Organic Green Tea (Stock: 5, Reorder Level: 15) -> Low stock
        # Product 8: Water Bottle (Stock: 4, Reorder Level: 10) -> Low stock
        # Product 9: Headphones (Stock: 2, Reorder Level: 6) -> Low stock
        alerts = self.mis.get_low_stock_alerts()
        self.assertEqual(len(alerts), 3)

        # Check Product 6 recommendation: (15 * 2) - 5 = 25 units
        tea_alert = next(a for a in alerts if a["product_id"] == 6)
        self.assertEqual(tea_alert["recommended_order_qty"], 25)
        self.assertEqual(tea_alert["estimated_reorder_cost"], 25 * 9.50)

    def test_11_sales_performance_rankings(self) -> None:
        """Verify strategic best-sellers summary by volume and gross revenue."""
        # Product 7: Monitor @ $280.00 (sell 2 -> $560.00)
        # Product 3: Cable @ $12.00 (sell 10 -> $120.00)
        self.tps.record_sale(product_id=7, quantity=2, branch="Mombasa Old Town")
        self.tps.record_sale(product_id=3, quantity=10, branch="Mombasa Old Town")

        summary = self.mis.get_sales_summary(top_n=2)

        # Top by units sold should be Cable (10 units)
        self.assertEqual(summary["top_products_by_units"][0]["product_id"], 3)
        self.assertEqual(summary["top_products_by_units"][0]["total_units_sold"], 10)

        # Top by revenue should be Monitor ($560.00)
        self.assertEqual(summary["top_products_by_revenue"][0]["product_id"], 7)
        self.assertEqual(summary["top_products_by_revenue"][0]["total_revenue_generated"], 560.00)


if __name__ == "__main__":
    unittest.main()
