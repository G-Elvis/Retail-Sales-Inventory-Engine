"""Command Line Interface (CLI) for TPS and MIS modules."""

import sys
from datetime import datetime
from typing import Any, Dict, List
from app.tps.tps_service import (
    TPSService,
    TPSError,
    ProductNotFoundError,
    InsufficientStockError,
    InvalidTransactionDataError
)
from app.mis.mis_service import MISService


def print_header(title: str, width: int = 70) -> None:
    """Print standard stylized section header."""
    print("\n" + "=" * width)
    print(title.center(width))
    print("=" * width)


def print_sub_header(title: str, width: int = 70) -> None:
    """Print secondary sub-header."""
    print("\n" + "-" * width)
    print(title.center(width))
    print("-" * width)


def format_currency(amount: float) -> str:
    """Format floating point numbers to currency strings."""
    return f"${amount:,.2f}"


class RetailEngineCLI:
    """CLI orchestrator bridging user interaction with TPS and MIS layers."""

    def __init__(self, tps_service: TPSService, mis_service: MISService):
        self.tps = tps_service
        self.mis = mis_service

    def start(self) -> None:
        """Main interaction loop."""
        while True:
            print_header("RETAIL SALES & INVENTORY MANAGEMENT ENGINE (TPS-to-MIS)")
            print("1. [TPS] Transaction Processing System (Operational Cashier / Inventory)")
            print("2. [MIS] Management Information System (Managerial Reports & Analytics)")
            print("3. Exit System")
            
            choice = input("\nEnter choice [1-3]: ").strip()
            if choice == "1":
                self.tps_menu()
            elif choice == "2":
                self.mis_menu()
            elif choice == "3":
                print("\nExiting system. Have a productive day!")
                break
            else:
                print("\n[!] Invalid selection. Please enter 1, 2, or 3.")

    # -------------------------------------------------------------------------
    # Module A: TPS Operational Submenu
    # -------------------------------------------------------------------------

    def tps_menu(self) -> None:
        """Cashier and inventory management operational menu."""
        while True:
            print_sub_header("TPS: TRANSACTION PROCESSING SYSTEM (OPERATIONAL TIER)")
            print("1. Record New Retail Sale (POS Checkout)")
            print("2. View All Available Products")
            print("3. Search Product by Name/Category")
            print("4. Add New Product to Inventory Catalog")
            print("5. View Recent Sales Transaction Log (Audit Trail)")
            print("6. Return to Main Menu")

            choice = input("\nEnter TPS option [1-6]: ").strip()
            if choice == "1":
                self._handle_record_sale()
            elif choice == "2":
                self._handle_view_products()
            elif choice == "3":
                self._handle_search_products()
            elif choice == "4":
                self._handle_add_product()
            elif choice == "5":
                self._handle_view_recent_sales()
            elif choice == "6":
                break
            else:
                print("\n[!] Invalid choice. Please select 1 through 6.")

    def _handle_record_sale(self) -> None:
        print_sub_header("POS CHECKOUT: RECORD RETAIL SALE")
        try:
            p_id_str = input("Enter Product ID: ").strip()
            if not p_id_str.isdigit():
                print("[!] Error: Product ID must be an integer.")
                return
            product_id = int(p_id_str)

            # Preview product for user verification
            product = self.tps.get_product_by_id(product_id)
            print(f"-> Selected: {product['product_name']} | Branch: {product['branch']}")
            print(f"-> Unit Price: {format_currency(product['unit_price'])} | In Stock: {product['stock_quantity']}")

            qty_str = input("Enter Quantity to purchase: ").strip()
            if not qty_str.isdigit():
                print("[!] Error: Quantity must be a positive integer.")
                return
            quantity = int(qty_str)

            branch_override = input(f"Branch [{product['branch']}]: ").strip()
            branch = branch_override if branch_override else product["branch"]

            # Execute transaction through atomic TPS service
            receipt = self.tps.record_sale(product_id=product_id, quantity=quantity, branch=branch)

            print("\n" + "=" * 50)
            print("          TRANSACTION RECEIPT (TPS AUDIT)")
            print("=" * 50)
            print(f"Sale ID         : #{receipt['sale_id']}")
            print(f"Product         : {receipt['product_name']} (ID: {receipt['product_id']})")
            print(f"Quantity Sold   : {receipt['quantity']}")
            print(f"Price / Unit    : {format_currency(receipt['unit_price_at_sale'])}")
            print(f"Total Amount    : {format_currency(receipt['total_amount'])}")
            print(f"Branch Location : {receipt['branch']}")
            print(f"Updated Stock   : {receipt['remaining_stock']} units remaining")
            print(f"Status          : {receipt['status']} (Committed to Database)")
            print("=" * 50)

        except ProductNotFoundError as e:
            print(f"\n[X] TPS REJECTED: {e}")
        except InsufficientStockError as e:
            print(f"\n[X] TPS REJECTED: {e}")
        except InvalidTransactionDataError as e:
            print(f"\n[X] VALIDATION ERROR: {e}")
        except TPSError as e:
            print(f"\n[X] TRANSACTION ERROR: {e}")

    def _handle_view_products(self) -> None:
        products = self.tps.get_all_products()
        print_sub_header("PRODUCT INVENTORY CATALOG")
        self._display_products_table(products)

    def _handle_search_products(self) -> None:
        query = input("Enter search term (name or category): ").strip()
        if not query:
            print("[!] Please enter a search query.")
            return
        results = self.tps.search_products(query)
        print_sub_header(f"SEARCH RESULTS FOR: '{query}'")
        self._display_products_table(results)

    def _display_products_table(self, products: List[Dict[str, Any]]) -> None:
        if not products:
            print("No products found.")
            return

        header = f"{'ID':<4} | {'Product Name':<30} | {'Category':<14} | {'Price':<10} | {'Stock':<6} | {'Reorder':<8} | {'Branch':<15}"
        print("-" * len(header))
        print(header)
        print("-" * len(header))
        for p in products:
            status = " [!LOW]" if p["stock_quantity"] <= p["reorder_level"] else ""
            print(
                f"{p['product_id']:<4} | "
                f"{p['product_name'][:28]:<30} | "
                f"{p['category'][:12]:<14} | "
                f"{format_currency(p['unit_price']):<10} | "
                f"{str(p['stock_quantity']) + status:<6} | "
                f"{p['reorder_level']:<8} | "
                f"{p['branch']:<15}"
            )
        print("-" * len(header))

    def _handle_add_product(self) -> None:
        print_sub_header("ADD NEW PRODUCT TO INVENTORY")
        try:
            name = input("Product Name: ").strip()
            cat = input("Category: ").strip()
            price_val = float(input("Unit Price ($): ").strip())
            stock_val = int(input("Initial Stock Quantity: ").strip())
            reorder_val = int(input("Reorder Level Threshold: ").strip())
            branch_val = input("Branch Location: ").strip()

            new_id = self.tps.add_product(
                product_name=name,
                category=cat,
                unit_price=price_val,
                stock_quantity=stock_val,
                reorder_level=reorder_val,
                branch=branch_val
            )
            print(f"\n[+] Success: Product '{name}' added with Product ID #{new_id}.")
        except ValueError:
            print("\n[!] Input Error: Price, Stock, and Reorder Level must be valid numeric values.")
        except TPSError as e:
            print(f"\n[X] Failed to add product: {e}")

    def _handle_view_recent_sales(self) -> None:
        limit_str = input("How many recent transactions to display? [Default 15]: ").strip()
        limit = int(limit_str) if limit_str.isdigit() else 15
        sales = self.tps.get_recent_sales(limit=limit)

        print_sub_header(f"TRANSACTION LOG: LAST {len(sales)} SALES")
        if not sales:
            print("No sales transactions recorded yet.")
            return

        header = f"{'Sale ID':<8} | {'Date/Time':<19} | {'Product':<25} | {'Qty':<4} | {'Unit Price':<11} | {'Total':<10} | {'Branch':<15}"
        print("-" * len(header))
        print(header)
        print("-" * len(header))
        for s in sales:
            print(
                f"#{s['sale_id']:<7} | "
                f"{s['sale_date']:<19} | "
                f"{s['product_name'][:23]:<25} | "
                f"{s['quantity']:<4} | "
                f"{format_currency(s['unit_price_at_sale']):<11} | "
                f"{format_currency(s['total_amount']):<10} | "
                f"{s['branch']:<15}"
            )
        print("-" * len(header))

    # -------------------------------------------------------------------------
    # Module B: MIS Managerial Submenu
    # -------------------------------------------------------------------------

    def mis_menu(self) -> None:
        """Managerial and analytical intelligence reporting menu."""
        while True:
            print_sub_header("MIS: MANAGEMENT INFORMATION SYSTEM (DECISION SUPPORT)")
            print("1. Daily Revenue & Branch Breakdown Report")
            print("2. Weekly Revenue & Branch Trend Report")
            print("3. Low-Stock Alerts & Automated Reorder Recommendations")
            print("4. Comprehensive Strategic Sales Summary & Best-Sellers")
            print("5. Return to Main Menu")

            choice = input("\nEnter MIS option [1-5]: ").strip()
            if choice == "1":
                self._handle_daily_report()
            elif choice == "2":
                self._handle_weekly_report()
            elif choice == "3":
                self._handle_low_stock_report()
            elif choice == "4":
                self._handle_sales_summary()
            elif choice == "5":
                break
            else:
                print("\n[!] Invalid choice. Please select 1 through 5.")

    def _handle_daily_report(self) -> None:
        date_str = input(f"Enter target date (YYYY-MM-DD) [Default: Today ({datetime.now().strftime('%Y-%m-%d')})]: ").strip()
        target_date = date_str if date_str else None

        report = self.mis.get_daily_revenue_report(target_date)
        print_sub_header(f"MIS DAILY REVENUE REPORT: {report['report_date']}")
        print(f"Overall Daily Revenue      : {format_currency(report['overall_revenue'])}")
        print(f"Total Transactions Processed: {report['overall_transactions']}")
        print(f"Total Volume of Goods Sold : {report['overall_units_sold']} units")

        print("\nBRANCH PERFORMANCE BREAKDOWN:")
        header = f"{'Branch Location':<22} | {'Transactions':<14} | {'Units Sold':<12} | {'Total Revenue':<15}"
        print("-" * len(header))
        print(header)
        print("-" * len(header))
        for b in report["branch_breakdown"]:
            print(
                f"{b['branch']:<22} | "
                f"{b['transaction_count']:<14} | "
                f"{b['total_units_sold']:<12} | "
                f"{format_currency(b['total_revenue']):<15}"
            )
        print("-" * len(header))

    def _handle_weekly_report(self) -> None:
        date_str = input(f"Enter reference date for target week [Default: Today]: ").strip()
        target_date = date_str if date_str else None

        report = self.mis.get_weekly_revenue_report(target_date)
        print_sub_header(f"MIS WEEKLY REVENUE REPORT (Week: {report['week_identifier']})")
        print(f"Overall Weekly Revenue     : {format_currency(report['overall_revenue'])}")
        print(f"Total Transactions Processed: {report['overall_transactions']}")
        print(f"Total Units Sold           : {report['overall_units_sold']} units")

        print("\nBRANCH PERFORMANCE BREAKDOWN:")
        header = f"{'Branch Location':<22} | {'Transactions':<14} | {'Units Sold':<12} | {'Weekly Revenue':<15}"
        print("-" * len(header))
        print(header)
        print("-" * len(header))
        for b in report["branch_breakdown"]:
            print(
                f"{b['branch']:<22} | "
                f"{b['transaction_count']:<14} | "
                f"{b['total_units_sold']:<12} | "
                f"{format_currency(b['total_revenue']):<15}"
            )
        print("-" * len(header))

    def _handle_low_stock_report(self) -> None:
        alerts = self.mis.get_low_stock_alerts()
        print_sub_header("MIS INVENTORY ALERT: LOW-STOCK & REORDER RECOMMENDATIONS")

        if not alerts:
            print("\n[OK] Inventory levels healthy. No products are currently below reorder thresholds.")
            return

        print(f"-> Attention: {len(alerts)} item(s) require immediate replenishment.\n")
        header = f"{'Product':<25} | {'Stock':<6} | {'Reorder':<8} | {'Branch':<15} | {'Urgency':<25} | {'Recommended Qty':<16} | {'Est. Cost':<10}"
        print("-" * len(header))
        print(header)
        print("-" * len(header))
        total_reorder_cost = 0.0
        for a in alerts:
            total_reorder_cost += a["estimated_reorder_cost"]
            print(
                f"{a['product_name'][:23]:<25} | "
                f"{a['stock_quantity']:<6} | "
                f"{a['reorder_level']:<8} | "
                f"{a['branch']:<15} | "
                f"{a['urgency_level']:<25} | "
                f"{a['recommended_order_qty']:<16} | "
                f"{format_currency(a['estimated_reorder_cost']):<10}"
            )
        print("-" * len(header))
        print(f"Total Projected Replenishment Capital Required: {format_currency(total_reorder_cost)}")

    def _handle_sales_summary(self) -> None:
        summary = self.mis.get_sales_summary(top_n=5)
        print_sub_header("MIS EXECUTIVE STRATEGIC SALES SUMMARY")

        macro = summary["macro_summary"]
        print(f"Gross Lifetime Revenue     : {format_currency(macro['gross_revenue'])}")
        print(f"Total Completed Sales      : {macro['total_sales_count']}")
        print(f"Total Items Sold           : {macro['total_items_sold']}")
        print(f"Average Transaction Value  : {format_currency(macro['avg_transaction_value'])}")

        print("\nTOP PRODUCTS BY QUANTITY SOLD:")
        h1 = f"{'Rank':<5} | {'Product Name':<30} | {'Units Sold':<12} | {'Revenue Generated':<18}"
        print("-" * len(h1))
        print(h1)
        print("-" * len(h1))
        for idx, p in enumerate(summary["top_products_by_units"], 1):
            print(f"{idx:<5} | {p['product_name'][:28]:<30} | {p['total_units_sold']:<12} | {format_currency(p['total_revenue_generated']):<18}")
        print("-" * len(h1))

        print("\nTOP PRODUCTS BY REVENUE GENERATED:")
        h2 = f"{'Rank':<5} | {'Product Name':<30} | {'Revenue Generated':<18} | {'Units Sold':<12}"
        print("-" * len(h2))
        print(h2)
        print("-" * len(h2))
        for idx, p in enumerate(summary["top_products_by_revenue"], 1):
            print(f"{idx:<5} | {p['product_name'][:28]:<30} | {format_currency(p['total_revenue_generated']):<18} | {p['total_units_sold']:<12}")
        print("-" * len(h2))
