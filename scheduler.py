#!/usr/bin/env python3
"""
Strategy Scheduler

Automatically schedules and executes the Bank Nifty strategy on expiry days.
"""

import schedule
import time
import logging
import sys
from datetime import datetime, date
from pathlib import Path

# Add src to path
sys.path.append(str(Path(__file__).parent / 'src'))

from src.utils.config_loader import ConfigLoader
from src.utils.logger import setup_logging
from src.utils.expiry_calculator import ExpiryCalculator
from src.strategy.bank_nifty_strategy import BankNiftyStrategy


class StrategyScheduler:
    """Handles automatic scheduling of strategy execution"""
    
    def __init__(self, config_path: str = 'config/config.yaml'):
        """
        Initialize scheduler
        
        Args:
            config_path: Path to configuration file
        """
        self.config = ConfigLoader.load(config_path)
        setup_logging(self.config)
        self.logger = logging.getLogger(__name__)
        
        self.expiry_calc = ExpiryCalculator()
        self.strategy = None
        
        # Scheduling configuration
        self.execution_time = self.config['strategy']['execution_time']  # "15:00"
        self.monitoring_interval = 60  # Monitor every 60 seconds
    
    def start(self):
        """Start the scheduler"""
        self.logger.info("Starting Bank Nifty Strategy Scheduler")
        
        # Schedule strategy execution on expiry days
        schedule.every().day.at(self.execution_time).do(self.check_and_execute_strategy)
        
        # Schedule position monitoring every minute during market hours
        schedule.every().minute.do(self.monitor_positions)
        
        # Schedule daily cleanup at market close
        schedule.every().day.at("15:35").do(self.daily_cleanup)
        
        self.logger.info(f"Scheduler configured:")
        self.logger.info(f"- Strategy execution check: Daily at {self.execution_time}")
        self.logger.info(f"- Position monitoring: Every minute")
        self.logger.info(f"- Daily cleanup: 15:35")
        
        try:
            while True:
                schedule.run_pending()
                time.sleep(1)
                
        except KeyboardInterrupt:
            self.logger.info("Scheduler stopped by user")
        except Exception as e:
            self.logger.error(f"Scheduler error: {str(e)}", exc_info=True)
    
    def check_and_execute_strategy(self):
        """Check if today is expiry day and execute strategy"""
        try:
            current_date = date.today()
            
            # Check if today is a strategy execution day (previous month's expiry)
            if self.expiry_calc.is_strategy_execution_day(current_date):
                self.logger.info(f"Today ({current_date}) is strategy execution day")
                
                # Initialize strategy
                self.strategy = BankNiftyStrategy(self.config)
                
                # Execute strategy
                success = self.strategy.execute()
                
                if success:
                    self.logger.info("Strategy executed successfully")
                else:
                    self.logger.error("Strategy execution failed")
            else:
                self.logger.debug(f"Today ({current_date}) is not a strategy execution day")
                
        except Exception as e:
            self.logger.error(f"Error in strategy execution check: {str(e)}", exc_info=True)
    
    def monitor_positions(self):
        """Monitor existing positions"""
        try:
            # Only monitor during market hours
            current_time = datetime.now().time()
            market_start = datetime.strptime("09:15", "%H:%M").time()
            market_end = datetime.strptime("15:30", "%H:%M").time()
            
            if not (market_start <= current_time <= market_end):
                return
            
            # Check if we have an active strategy
            if self.strategy and hasattr(self.strategy, 'positions') and self.strategy.positions:
                self.strategy.monitor_positions()
            
        except Exception as e:
            self.logger.error(f"Error in position monitoring: {str(e)}", exc_info=True)
    
    def daily_cleanup(self):
        """Perform daily cleanup tasks"""
        try:
            self.logger.info("Performing daily cleanup")
            
            # Log daily summary
            if self.strategy:
                self.log_daily_summary()
            
            # Reset daily counters
            self.strategy = None
            
            self.logger.info("Daily cleanup completed")
            
        except Exception as e:
            self.logger.error(f"Error in daily cleanup: {str(e)}", exc_info=True)
    
    def log_daily_summary(self):
        """Log daily trading summary"""
        try:
            if not self.strategy or not hasattr(self.strategy, 'positions'):
                return
            
            total_positions = len(self.strategy.positions)
            current_pnl = self.strategy.current_pnl
            
            self.logger.info("=== Daily Trading Summary ===")
            self.logger.info(f"Total Positions: {total_positions}")
            self.logger.info(f"Current P&L: ₹{current_pnl:,.2f}")
            
            if self.strategy.entry_capital > 0:
                pnl_percentage = (current_pnl / self.strategy.entry_capital) * 100
                self.logger.info(f"Return: {pnl_percentage:.2f}%")
            
            self.logger.info("============================")
            
        except Exception as e:
            self.logger.error(f"Error logging daily summary: {str(e)}")


def main():
    """Main function"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Bank Nifty Strategy Scheduler')
    parser.add_argument('--config', type=str, default='config/config.yaml',
                       help='Path to configuration file')
    parser.add_argument('--test', action='store_true',
                       help='Test mode - run once and exit')
    
    args = parser.parse_args()
    
    try:
        scheduler = StrategyScheduler(args.config)
        
        if args.test:
            # Test mode - run checks once
            print("Running in test mode...")
            scheduler.check_and_execute_strategy()
            scheduler.monitor_positions()
        else:
            # Production mode - run continuously
            scheduler.start()
            
    except FileNotFoundError:
        print(f"Configuration file not found: {args.config}")
        print("Please copy config/config.example.yaml to config/config.yaml and configure it.")
        return 1
    except Exception as e:
        print(f"Scheduler startup failed: {str(e)}")
        return 1
    
    return 0


if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)
