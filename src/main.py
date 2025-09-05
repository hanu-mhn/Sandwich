#!/usr/bin/env python3
"""
Bank Nifty Monthly Expiry Trading Strategy - Main Execution Script

This script serves as the entry point for the automated trading system.
It handles strategy execution, monitoring, and exit conditions.
"""

import argparse
import logging
import sys
from datetime import datetime
from pathlib import Path

# Add src to path
sys.path.append(str(Path(__file__).parent))

from strategy.bank_nifty_strategy import BankNiftyStrategy
from utils.config_loader import ConfigLoader
from utils.logger import setup_logging
from utils.expiry_calculator import ExpiryCalculator


def main():
    """Main execution function"""
    parser = argparse.ArgumentParser(description='Bank Nifty Trading Strategy')
    parser.add_argument('--execute', action='store_true', 
                       help='Execute the trading strategy')
    parser.add_argument('--monitor', action='store_true',
                       help='Monitor existing positions')
    parser.add_argument('--config', type=str, default='config/config.yaml',
                       help='Path to configuration file')
    parser.add_argument('--dry-run', action='store_true',
                       help='Execute in dry-run mode (no actual trades)')
    
    args = parser.parse_args()
    
    # Load configuration
    try:
        config = ConfigLoader.load(args.config)
    except FileNotFoundError:
        print(f"Configuration file not found: {args.config}")
        print("Please copy config/config.example.yaml to config/config.yaml and configure it.")
        return 1
    
    # Setup logging
    setup_logging(config)
    logger = logging.getLogger(__name__)
    
    logger.info("Starting Bank Nifty Trading Strategy")
    logger.info(f"Mode: {'DRY-RUN' if args.dry_run else 'LIVE'}")
    
    try:
        # Initialize strategy
        strategy = BankNiftyStrategy(config, dry_run=args.dry_run)
        
        if args.execute:
            # Check if today is an expiry day
            expiry_calc = ExpiryCalculator()
            current_date = datetime.now().date()
            
            if expiry_calc.is_expiry_day(current_date):
                logger.info(f"Today ({current_date}) is an expiry day. Executing strategy...")
                success = strategy.execute()
                
                if success:
                    logger.info("Strategy executed successfully")
                    return 0
                else:
                    logger.error("Strategy execution failed")
                    return 1
            else:
                logger.info(f"Today ({current_date}) is not an expiry day. No execution.")
                next_expiry = expiry_calc.get_next_expiry_date(current_date)
                logger.info(f"Next expiry date: {next_expiry}")
                return 0
                
        elif args.monitor:
            # Monitor existing positions
            logger.info("Monitoring existing positions...")
            strategy.monitor_positions()
            return 0
            
        else:
            logger.info("No action specified. Use --execute or --monitor")
            return 0
            
    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}", exc_info=True)
        return 1


if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)
