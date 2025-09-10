#!/usr/bin/env python3
"""Demo runner for Sandwich Strategy"""
import logging
from src.utils.config_loader import ConfigLoader
from src.strategy.sandwich_strategy import SandwichStrategy
from src.utils.logger import setup_logging
from datetime import datetime, timedelta


def main():
    config = ConfigLoader.load('config/config.yaml')
    setup_logging(config)
    logging.info("Starting Sandwich Strategy Demo (mock mode)")

    strat = SandwichStrategy(config, dry_run=True)

    # Force simulate being on expiry day at 15:00 by monkey patching dates if needed
    entered = strat.execute_entry()
    if not entered:
        logging.info("Entry conditions not met (likely not expiry day in real calendar). Forcing manual build for demo.")
        # Force attributes for demonstration
        from src.utils.expiry_calculator import ExpiryCalculator
        exp = ExpiryCalculator()
        today = datetime.now().date()
        strat.current_expiry = exp.get_current_expiry_date(today)
        next_month = strat.current_expiry.month + 1
        next_year = strat.current_expiry.year
        if next_month > 12:
            next_month = 1
            next_year += 1
        strat.next_expiry = exp.get_monthly_expiry_date(next_year, next_month)
        strat.month_type = '4W'
        strat.initial_spot = 45000
        strat.initial_future = 45100
        strat._build_initial_positions()
        strat.entry_datetime = datetime.now() - timedelta(days=1)
        strat.state = 'ACTIVE_PASSIVE'

    # Simulate monitoring loop
    for day in range(1, 15):
        strat.monitor()

    logging.info("Demo complete")

if __name__ == '__main__':
    main()
