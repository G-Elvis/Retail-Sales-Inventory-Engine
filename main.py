#!/usr/bin/env python3
"""
Retail Sales & Inventory Engine (TPS-to-MIS)
Main Entry Point
"""

import sys
from app.database.schema import init_db, seed_sample_data
from app.tps.tps_service import TPSService
from app.mis.mis_service import MISService
from app.cli.menu import RetailEngineCLI


def main() -> None:
    """Bootstrap database and launch the interactive engine CLI."""
    # Ensure database schema and seed data exist
    init_db()
    seed_sample_data()

    # Instantiate decoupled service layers
    tps = TPSService()
    mis = MISService()

    # Launch CLI
    cli = RetailEngineCLI(tps_service=tps, mis_service=mis)
    cli.start()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\nOperation cancelled by user. Exiting gracefully...")
        sys.exit(0)
