#!/usr/bin/env python3
"""
Demo Script

Demonstrates the Bank Nifty strategy functio        # Mock portfolio summary
        print("
💼 Mock Portfolio Summary:")
        print("   Capital Deployed: ₹40,000.00")
        print("   Number of Positions: 5 (Optimized)")
        print("   Profit Target: 10%")
        print("   Transaction Cost Savings: ~37.5%")ty with mock data.
"""

import sys
from pathlib import Path
from datetime import datetime

# Add src to path
sys.path.append(str(Path(__file__).parent / 'src'))

from src.utils.config_loader import ConfigLoader
from src.utils.logger import setup_logging
from src.utils.expiry_calculator import ExpiryCalculator
from src.strategy.bank_nifty_strategy import BankNiftyStrategy


def main():
    """Run demonstration"""
    print("🚀 Bank Nifty Strategy Demo")
    print("=" * 50)
    
    try:
        # Load test configuration
        config = ConfigLoader.load('config/test_config.yaml')
        setup_logging(config)
        
        print("✅ Configuration loaded successfully")
        
        # Initialize components
        expiry_calc = ExpiryCalculator()
        
        # Display next few expiry dates
        print("\n📅 Upcoming Expiry Dates:")
        for i in range(3):
            year = 2025
            month = 9 + i
            if month > 12:
                year += 1
                month -= 12
            
            expiry_date = expiry_calc.get_monthly_expiry_date(year, month)
            weekday = expiry_date.strftime('%A')
            print(f"   {expiry_date} ({weekday})")
        
        # Initialize strategy in dry-run mode
        print("\n🎯 Initializing Strategy (Dry-Run Mode)")
        strategy = BankNiftyStrategy(config, dry_run=True)
        
        print("✅ Strategy initialized successfully")
        
        # Demonstrate strike calculation
        print("\n📊 Strike Calculation Demo:")
        futures_price = 45000.0
        print(f"   Current Futures Price: ₹{futures_price:,.2f}")
        
        strikes = strategy._calculate_strikes(futures_price)
        print("   Put Strikes:", [int(s) for s in strikes['puts']])
        print("   Call Strikes:", [int(s) for s in strikes['calls']])
        
        # Demonstrate position structure (Calendar Spread Strategy)
        print("\n🏗️  Position Structure (Calendar Spread Strategy):")
        print("   Execution: Current month expiry day (e.g., June)")
        print("   Instruments: Next month expiry (e.g., July)")
        print("   Futures: SELL 1 lot (July expiry)")
        print("   Put Options:")
        print("     - BUY 2 lots (0.75% strike - July expiry)")
        print("     - SELL 1 lot (0.25% strike - July expiry)")
        print("     - SELL 2 lots (0.5% strike - July expiry)")
        print("   Call Options:")
        print("     - BUY 1 lot (0.25% strike - July expiry)")
        print("     - SELL 2 lots (0.5% strike - July expiry)")
        print("     - BUY 2 lots (0.75% strike - July expiry)")
        print("   Total Positions: 7 (with custom lot sizes)")
        print("   Benefits: Longer time to expiry, reduced time decay risk")
        
        # Simulate strategy execution (dry-run)
        print("\n🎮 Simulating Strategy Execution...")
        
        # Mock execution
        print("   📈 Placing futures order...")
        print("   📊 Calculating option strikes...")
        print("   💰 Placing option orders...")
        print("   ✅ All positions placed successfully!")
        
        print(f"\n💼 Mock Portfolio Summary:")
        print(f"   Execution: June expiry day at 3:00 PM")
        print(f"   Instruments: July expiry options & futures")
        print(f"   Capital Deployed: ₹{config['strategy']['capital'] * 0.08:,.2f}")
        print(f"   Number of Positions: 7 (custom lot sizes)")
        print(f"   Profit Target: {config['strategy']['profit_target'] * 100:.0f}% (auto-exit)")
        print(f"   Time Exit: 3:25 PM on June expiry day (market price)")
        print(f"   Strategy: Calendar spread with next month instruments")
        
        print("\n✨ Demo completed successfully!")
        print("\nTo run the actual strategy:")
        print("   1. Configure your broker credentials in config/config.yaml")
        print("   2. Run: python src/main.py --execute")
        print("   3. Or schedule automatic execution: python scheduler.py")
        
        return 0
        
    except Exception as e:
        print(f"❌ Demo failed: {str(e)}")
        return 1


if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)
