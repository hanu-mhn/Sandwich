"""
Bank Nifty Monthly Expiry Strategy Implementation

This module implements the core trading strategy logic including:
- Strike calculation based on percentage differences
- Multi-leg position construction
- Entry and exit logic
- Risk management
"""

import logging
from datetime import datetime, time
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass

from src.brokers.broker_factory import BrokerFactory
from src.market_data.data_provider import MarketDataProvider
from src.risk_management.position_manager import PositionManager
from src.utils.expiry_calculator import ExpiryCalculator
from src.utils.notifications import NotificationManager


@dataclass
class Position:
    """Represents a trading position"""
    instrument: str
    action: str  # BUY or SELL
    quantity: int
    price: float
    order_id: Optional[str] = None
    strike: Optional[float] = None
    option_type: Optional[str] = None  # CE or PE


class BankNiftyStrategy:
    """Main strategy implementation class"""
    
    def __init__(self, config: Dict, dry_run: bool = False):
        """
        Initialize the Bank Nifty strategy
        
        Args:
            config: Configuration dictionary
            dry_run: If True, no actual trades will be placed
        """
        self.config = config
        self.dry_run = dry_run
        self.logger = logging.getLogger(__name__)
        
        # Initialize components
        self.broker = BrokerFactory.create(config['broker'], dry_run)
        self.market_data = MarketDataProvider(config['market_data'])
        self.position_manager = PositionManager(config['risk'])
        self.expiry_calc = ExpiryCalculator()
        self.notification_manager = NotificationManager(config.get('notifications', {}))
        
        # Strategy parameters
        self.capital = config['strategy']['capital']
        self.profit_target = config['strategy']['profit_target']
        self.strike_percentages = config['strategy']['strike_percentages']
        self.execution_time = config['strategy']['execution_time']
        
        # Track positions
        self.positions: List[Position] = []
        self.entry_capital = 0
        self.current_pnl = 0
        
    def execute(self) -> bool:
        """
        Execute the main strategy
        
        Returns:
            bool: True if execution was successful, False otherwise
        """
        try:
            self.logger.info("Starting strategy execution")
            
            # Check execution time
            if not self._is_execution_time():
                self.logger.warning("Not the correct execution time (3:00 PM IST)")
                return False
            
            # Get current Bank Nifty futures price
            futures_price = self._get_futures_price()
            if not futures_price:
                self.logger.error("Failed to get futures price")
                return False
                
            self.logger.info(f"Current Bank Nifty futures price: {futures_price}")
            
            # Calculate strike prices
            strikes = self._calculate_strikes(futures_price)
            self.logger.info(f"Calculated strikes: {strikes}")
            
            # Execute trades
            success = self._execute_trades(futures_price, strikes)
            
            if success:
                self.entry_capital = self._calculate_deployed_capital()
                self.logger.info(f"Strategy executed successfully. Capital deployed: ₹{self.entry_capital:,.2f}")
                
                # Send notification
                self.notification_manager.send_entry_notification(
                    self.positions, self.entry_capital
                )
                
                # Start monitoring
                self._start_monitoring()
                
            return success
            
        except Exception as e:
            self.logger.error(f"Strategy execution failed: {str(e)}", exc_info=True)
            return False
    
    def monitor_positions(self) -> None:
        """Monitor existing positions and check exit conditions"""
        try:
            if not self.positions:
                self.logger.info("No positions to monitor")
                return
            
            # Check if we're at current month expiry day (execution day)
            current_date = datetime.now().date()
            current_time = datetime.now().time()
            current_expiry_date = self.expiry_calc.get_current_expiry_date(current_date)
            
            # Check if it's expiry day and market is about to close
            is_expiry_day = current_date == current_expiry_date
            is_exit_time = current_time.hour >= 15 and current_time.minute >= 25  # 3:25 PM
            
            # Calculate current P&L
            self.current_pnl = self._calculate_current_pnl()
            pnl_percentage = (self.current_pnl / self.entry_capital) * 100 if self.entry_capital > 0 else 0
            
            self.logger.info(f"Current P&L: ₹{self.current_pnl:,.2f} ({pnl_percentage:.2f}%)")
            
            # Exit conditions
            exit_reason = None
            
            # 1. Check 10% profit target
            if pnl_percentage >= (self.profit_target * 100):
                exit_reason = f"Profit target of {self.profit_target*100:.1f}% reached"
            
            # 2. Check expiry day exit (at 3:25 PM on expiry day) - market price exit
            elif is_expiry_day and is_exit_time:
                exit_reason = "Expiry day - 3:25 PM market price exit"
            
            # Execute exit if any condition is met
            if exit_reason:
                self.logger.info(f"{exit_reason}. Exiting all positions at market price...")
                success = self._exit_all_positions_at_market()
                
                if success:
                    self.logger.info(f"All positions exited successfully at market price. Reason: {exit_reason}")
                    
                    # Log final performance
                    final_return_pct = (self.current_pnl / self.entry_capital) * 100 if self.entry_capital > 0 else 0
                    self.logger.info(f"Final P&L: ₹{self.current_pnl:,.2f} ({final_return_pct:.2f}%)")
                else:
                    self.logger.error("Failed to exit some positions")
                    
        except Exception as e:
            self.logger.error(f"Error monitoring positions: {str(e)}", exc_info=True)
    
    def _is_execution_time(self) -> bool:
        """Check if current time matches execution time"""
        current_time = datetime.now().time()
        execution_time = time.fromisoformat(self.execution_time)
        
        # Allow execution within 5 minutes of target time
        time_diff = abs(
            (current_time.hour * 60 + current_time.minute) - 
            (execution_time.hour * 60 + execution_time.minute)
        )
        
        return time_diff <= 5
    
    def _get_futures_price(self) -> Optional[float]:
        """Get current Bank Nifty futures price"""
        try:
            # Get current month expiry
            current_date = datetime.now().date()
            expiry_date = self.expiry_calc.get_current_expiry_date(current_date)
            
            # Construct futures symbol
            futures_symbol = f"BANKNIFTY{expiry_date.strftime('%y%m%d')}FUT"
            
            # Get price from market data provider
            price = self.market_data.get_ltp(futures_symbol)
            return price
            
        except Exception as e:
            self.logger.error(f"Failed to get futures price: {str(e)}")
            return None
    
    def _calculate_strikes(self, futures_price: float) -> Dict[str, List[float]]:
        """
        Calculate option strikes based on futures price
        
        Args:
            futures_price: Current futures price
            
        Returns:
            Dictionary with 'puts' and 'calls' strike lists
        """
        strikes = {'puts': [], 'calls': []}
        
        for percentage in self.strike_percentages:
            # Put strikes (below current price)
            put_strike = futures_price * (1 - percentage / 100)
            put_strike = round(put_strike / 100) * 100  # Round to nearest 100
            strikes['puts'].append(put_strike)
            
            # Call strikes (above current price)
            call_strike = futures_price * (1 + percentage / 100)
            call_strike = round(call_strike / 100) * 100  # Round to nearest 100
            strikes['calls'].append(call_strike)
        
        # Sort strikes
        strikes['puts'].sort(reverse=True)  # Highest to lowest for puts
        strikes['calls'].sort()  # Lowest to highest for calls
        
        return strikes
    
    def _execute_trades(self, futures_price: float, strikes: Dict[str, List[float]]) -> bool:
        """
        Execute all trades according to strategy rules
        
        Args:
            futures_price: Current futures price
            strikes: Calculated strike prices
            
        Returns:
            bool: True if all trades executed successfully
        """
        try:
            # Get next month expiry for options and futures (July when executing on June expiry)
            current_date = datetime.now().date()
            current_expiry_date = self.expiry_calc.get_current_expiry_date(current_date)
            
            # Calculate next month's expiry date
            next_month = current_expiry_date.month + 1
            next_year = current_expiry_date.year
            if next_month > 12:
                next_month = 1
                next_year += 1
            
            next_expiry_date = self.expiry_calc.get_monthly_expiry_date(next_year, next_month)
            expiry_str = next_expiry_date.strftime('%y%m%d')
            
            self.logger.info(f"Executing on {current_expiry_date} expiry day")
            self.logger.info(f"Using {next_expiry_date} expiry instruments (next month)")
            
            # 1. Sell Bank Nifty Futures (1 lot) - Next month expiry
            futures_symbol = f"BANKNIFTY{expiry_str}FUT"
            futures_position = self._place_order(
                symbol=futures_symbol,
                action="SELL",
                quantity=1,
                order_type="MARKET"
            )
            if futures_position:
                self.positions.append(futures_position)
            
            # 2. Put Options Strategy (Custom Structure)
            put_strikes = strikes['puts']
            
            # BUY 2 lots at 0.75% strike (farthest OTM)
            if len(put_strikes) >= 3:
                put_075_strike = f"BANKNIFTY{expiry_str}{int(put_strikes[2])}PE"  # 0.75% = index 2
                put_pos1 = self._place_order(put_075_strike, "BUY", 2, "MARKET")
                if put_pos1:
                    self.positions.append(put_pos1)
            
            # SELL 1 lot at 0.25% strike (nearest to CMP)
            put_025_strike = f"BANKNIFTY{expiry_str}{int(put_strikes[0])}PE"  # 0.25% = index 0
            put_pos2 = self._place_order(put_025_strike, "SELL", 1, "MARKET")
            if put_pos2:
                self.positions.append(put_pos2)
            
            # SELL 2 lots at 0.5% strike (middle)
            if len(put_strikes) >= 2:
                put_050_strike = f"BANKNIFTY{expiry_str}{int(put_strikes[1])}PE"  # 0.5% = index 1
                put_pos3 = self._place_order(put_050_strike, "SELL", 2, "MARKET")
                if put_pos3:
                    self.positions.append(put_pos3)
            
            # 3. Call Options Strategy (Custom Structure)
            call_strikes = strikes['calls']
            
            # BUY 1 lot at 0.25% strike (nearest to CMP)
            call_025_strike = f"BANKNIFTY{expiry_str}{int(call_strikes[0])}CE"  # 0.25% = index 0
            call_pos1 = self._place_order(call_025_strike, "BUY", 1, "MARKET")
            if call_pos1:
                self.positions.append(call_pos1)
            
            # SELL 2 lots at 0.5% strike (middle)
            if len(call_strikes) >= 2:
                call_050_strike = f"BANKNIFTY{expiry_str}{int(call_strikes[1])}CE"  # 0.5% = index 1
                call_pos2 = self._place_order(call_050_strike, "SELL", 2, "MARKET")
                if call_pos2:
                    self.positions.append(call_pos2)
            
            # BUY 2 lots at 0.75% strike (farthest OTM)
            if len(call_strikes) >= 3:
                call_075_strike = f"BANKNIFTY{expiry_str}{int(call_strikes[2])}CE"  # 0.75% = index 2
                call_pos3 = self._place_order(call_075_strike, "BUY", 2, "MARKET")
                if call_pos3:
                    self.positions.append(call_pos3)
            
            self.logger.info(f"Executed {len(self.positions)} positions")
            return len(self.positions) > 0
            
        except Exception as e:
            self.logger.error(f"Failed to execute trades: {str(e)}", exc_info=True)
            return False
    
    def _place_order(self, symbol: str, action: str, quantity: int, order_type: str) -> Optional[Position]:
        """
        Place an order through the broker
        
        Args:
            symbol: Trading symbol
            action: BUY or SELL
            quantity: Number of lots
            order_type: Order type (MARKET, LIMIT, etc.)
            
        Returns:
            Position object if successful, None otherwise
        """
        try:
            if self.dry_run:
                # For dry run, create mock position
                mock_price = 100.0  # Mock price
                position = Position(
                    instrument=symbol,
                    action=action,
                    quantity=quantity,
                    price=mock_price,
                    order_id=f"MOCK_{len(self.positions)}"
                )
                self.logger.info(f"DRY-RUN: {action} {quantity} lots of {symbol} at ₹{mock_price}")
                return position
            
            # Place actual order through broker
            order_result = self.broker.place_order(
                symbol=symbol,
                action=action,
                quantity=quantity,
                order_type=order_type
            )
            
            if order_result and order_result.get('status') == 'SUCCESS':
                position = Position(
                    instrument=symbol,
                    action=action,
                    quantity=quantity,
                    price=order_result.get('price', 0),
                    order_id=order_result.get('order_id')
                )
                self.logger.info(f"Order placed: {action} {quantity} lots of {symbol} at ₹{position.price}")
                return position
            
            return None
            
        except Exception as e:
            self.logger.error(f"Failed to place order for {symbol}: {str(e)}")
            return None
    
    def _calculate_deployed_capital(self) -> float:
        """Calculate total capital deployed"""
        total = 0
        for position in self.positions:
            if position.action == "BUY":
                total += position.price * position.quantity * 25  # Bank Nifty lot size
        return total
    
    def _calculate_current_pnl(self) -> float:
        """Calculate current profit/loss"""
        total_pnl = 0
        
        for position in self.positions:
            try:
                current_price = self.market_data.get_ltp(position.instrument)
                if current_price:
                    if position.action == "BUY":
                        pnl = (current_price - position.price) * position.quantity * 25
                    else:  # SELL
                        pnl = (position.price - current_price) * position.quantity * 25
                    
                    total_pnl += pnl
                    
            except Exception as e:
                self.logger.error(f"Error calculating P&L for {position.instrument}: {str(e)}")
        
        return total_pnl
    
    def _exit_all_positions(self) -> bool:
        """Exit all positions"""
        try:
            exit_orders = []
            
            for position in self.positions:
                # Reverse the action to close position
                exit_action = "SELL" if position.action == "BUY" else "BUY"
                
                exit_order = self._place_order(
                    symbol=position.instrument,
                    action=exit_action,
                    quantity=position.quantity,
                    order_type="MARKET"
                )
                
                if exit_order:
                    exit_orders.append(exit_order)
            
            if exit_orders:
                self.logger.info(f"Exited {len(exit_orders)} positions")
                
                # Send exit notification
                final_pnl = self._calculate_current_pnl()
                self.notification_manager.send_exit_notification(
                    final_pnl, self.entry_capital
                )
                
                # Clear positions
                self.positions.clear()
                return True
            
            return False
            
        except Exception as e:
            self.logger.error(f"Failed to exit positions: {str(e)}", exc_info=True)
            return False
    
    def _exit_all_positions_at_market(self) -> bool:
        """Exit all positions at market price with detailed logging"""
        try:
            exit_orders = []
            
            self.logger.info("Exiting all positions at market price...")
            
            for position in self.positions:
                # Reverse the action to close position
                exit_action = "SELL" if position.action == "BUY" else "BUY"
                
                self.logger.info(f"Closing position: {exit_action} {position.quantity} lots of {position.instrument}")
                
                exit_order = self._place_order(
                    symbol=position.instrument,
                    action=exit_action,
                    quantity=position.quantity,
                    order_type="MARKET"
                )
                
                if exit_order:
                    exit_orders.append(exit_order)
                    self.logger.info(f"Exit order placed successfully")
                else:
                    self.logger.error(f"Failed to place exit order for {position.instrument}")
            
            if exit_orders:
                self.logger.info(f"Successfully exited {len(exit_orders)} positions at market price")
                
                # Send exit notification
                final_pnl = self._calculate_current_pnl()
                self.notification_manager.send_exit_notification(
                    final_pnl, self.entry_capital
                )
                
                # Clear positions
                self.positions.clear()
                return True
            else:
                self.logger.error("No positions were successfully exited")
                return False
            
        except Exception as e:
            self.logger.error(f"Failed to exit positions at market price: {str(e)}", exc_info=True)
            return False
    
    def _start_monitoring(self) -> None:
        """Start position monitoring loop"""
        self.logger.info("Starting position monitoring...")
        self.logger.info("Monitoring conditions:")
        self.logger.info("1. Exit at 10% profit target")
        self.logger.info("2. Exit at 3:25 PM on expiry day (current month) at market price")
        self.logger.info("Note: Using next month expiry instruments for longer time to expiry")
        # This would typically run in a separate thread or be called periodically
        # For now, we'll just log that monitoring has started
    
    def should_exit_positions(self) -> tuple[bool, str]:
        """
        Check if positions should be exited based on current conditions
        
        Returns:
            tuple: (should_exit: bool, reason: str)
        """
        try:
            if not self.positions:
                return False, "No positions to exit"
            
            # Check if we're at current month expiry day (execution day)
            current_date = datetime.now().date()
            current_time = datetime.now().time()
            current_expiry_date = self.expiry_calc.get_current_expiry_date(current_date)
            
            # Check if it's expiry day and 3:25 PM
            is_expiry_day = current_date == current_expiry_date
            is_exit_time = current_time.hour >= 15 and current_time.minute >= 25  # 3:25 PM
            
            # Calculate current P&L
            self.current_pnl = self._calculate_current_pnl()
            pnl_percentage = (self.current_pnl / self.entry_capital) * 100 if self.entry_capital > 0 else 0
            
            # 1. Check 10% profit target
            if pnl_percentage >= (self.profit_target * 100):
                return True, f"Profit target of {self.profit_target*100:.1f}% reached ({pnl_percentage:.2f}%)"
            
            # 2. Check expiry day exit (at 3:25 PM on expiry day)
            if is_expiry_day and is_exit_time:
                return True, f"Expiry day - 3:25 PM market price exit (P&L: {pnl_percentage:.2f}%)"
            
            return False, f"Continue monitoring (P&L: {pnl_percentage:.2f}%)"
            
        except Exception as e:
            self.logger.error(f"Error checking exit conditions: {str(e)}", exc_info=True)
            return False, f"Error checking exit conditions: {str(e)}"
