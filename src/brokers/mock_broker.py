"""
Mock Broker Implementation

For testing and dry-run mode. Simulates broker operations without actual trading.
"""

import logging
import random
from datetime import datetime
from typing import Dict, Any, Optional, List
from src.brokers.base_broker import BaseBroker, OrderResult, Position, Quote


class MockBroker(BaseBroker):
    """Mock broker for testing and dry-run mode"""
    
    def __init__(self, config: Dict[str, Any]):
        """Initialize mock broker"""
        super().__init__(config)
        self.logger = logging.getLogger(__name__)
        self.orders = {}
        self.positions = {}
        self.order_counter = 0
        
        # Mock prices for common symbols
        self.mock_prices = {
            'BANKNIFTY': 45000.0,
            'NIFTY': 19500.0
        }
    
    def connect(self) -> bool:
        """Simulate connection"""
        self.logger.info("MockBroker: Simulating connection to broker API")
        self.is_connected = True
        return True
    
    def disconnect(self) -> None:
        """Simulate disconnection"""
        self.logger.info("MockBroker: Disconnecting from broker API")
        self.is_connected = False
    
    def place_order(self, symbol: str, action: str, quantity: int, 
                   order_type: str, price: float = None) -> OrderResult:
        """
        Simulate order placement
        
        Args:
            symbol: Trading symbol
            action: BUY or SELL
            quantity: Number of shares/lots
            order_type: MARKET, LIMIT, etc.
            price: Limit price
            
        Returns:
            OrderResult: Simulated order result
        """
        try:
            self.order_counter += 1
            order_id = f"MOCK_{self.order_counter:06d}"
            
            # Simulate order price
            if order_type == "MARKET":
                execution_price = self._get_mock_price(symbol)
            else:
                execution_price = price or self._get_mock_price(symbol)
            
            # Add some random variation to simulate market conditions
            variation = random.uniform(-0.002, 0.002)  # ±0.2%
            execution_price *= (1 + variation)
            execution_price = round(execution_price, 2)
            
            # Store order details
            order_details = {
                'order_id': order_id,
                'symbol': symbol,
                'action': action,
                'quantity': quantity,
                'order_type': order_type,
                'price': execution_price,
                'status': 'COMPLETED',
                'timestamp': datetime.now().isoformat()
            }
            
            self.orders[order_id] = order_details
            
            # Update positions
            self._update_position(symbol, action, quantity, execution_price)
            
            self.logger.info(
                f"MockBroker: Order placed - {action} {quantity} {symbol} @ ₹{execution_price} "
                f"(Order ID: {order_id})"
            )
            
            return OrderResult(
                status="SUCCESS",
                order_id=order_id,
                price=execution_price,
                message="Order executed successfully",
                timestamp=order_details['timestamp']
            )
            
        except Exception as e:
            self.logger.error(f"MockBroker: Order placement failed - {str(e)}")
            return OrderResult(
                status="FAILED",
                message=f"Order placement failed: {str(e)}"
            )
    
    def cancel_order(self, order_id: str) -> bool:
        """Simulate order cancellation"""
        if order_id in self.orders:
            self.orders[order_id]['status'] = 'CANCELLED'
            self.logger.info(f"MockBroker: Order cancelled - {order_id}")
            return True
        
        self.logger.warning(f"MockBroker: Order not found for cancellation - {order_id}")
        return False
    
    def get_order_status(self, order_id: str) -> Dict[str, Any]:
        """Get simulated order status"""
        if order_id in self.orders:
            return self.orders[order_id]
        
        return {
            'order_id': order_id,
            'status': 'NOT_FOUND',
            'message': 'Order not found'
        }
    
    def get_positions(self) -> List[Position]:
        """Get simulated positions"""
        position_list = []
        
        for symbol, pos_data in self.positions.items():
            if pos_data['quantity'] != 0:
                current_price = self._get_mock_price(symbol)
                
                # Calculate unrealized P&L
                if pos_data['quantity'] > 0:  # Long position
                    unrealized_pnl = (current_price - pos_data['avg_price']) * abs(pos_data['quantity'])
                else:  # Short position
                    unrealized_pnl = (pos_data['avg_price'] - current_price) * abs(pos_data['quantity'])
                
                position = Position(
                    symbol=symbol,
                    quantity=pos_data['quantity'],
                    average_price=pos_data['avg_price'],
                    last_price=current_price,
                    unrealized_pnl=unrealized_pnl,
                    realized_pnl=0.0
                )
                
                position_list.append(position)
        
        return position_list
    
    def get_quote(self, symbol: str) -> Optional[Quote]:
        """Get simulated quote"""
        try:
            last_price = self._get_mock_price(symbol)
            
            # Simulate bid-ask spread
            spread = last_price * 0.001  # 0.1% spread
            bid_price = last_price - spread / 2
            ask_price = last_price + spread / 2
            
            return Quote(
                symbol=symbol,
                last_price=last_price,
                bid_price=round(bid_price, 2),
                ask_price=round(ask_price, 2),
                volume=random.randint(1000, 10000),
                timestamp=datetime.now().isoformat()
            )
            
        except Exception:
            return None
    
    def get_ltp(self, symbol: str) -> Optional[float]:
        """Get simulated last traded price"""
        return self._get_mock_price(symbol)
    
    def get_margins(self) -> Dict[str, float]:
        """Get simulated margin information"""
        return {
            'available': 1000000.0,  # ₹10 lakh
            'used': 200000.0,        # ₹2 lakh
            'total': 1200000.0       # ₹12 lakh
        }
    
    def get_holdings(self) -> List[Dict[str, Any]]:
        """Get simulated holdings"""
        return []  # Empty holdings for options trading
    
    def _get_mock_price(self, symbol: str) -> float:
        """
        Generate mock price for a symbol
        
        Args:
            symbol: Trading symbol
            
        Returns:
            float: Mock price
        """
        # Base prices for different instrument types
        if 'BANKNIFTY' in symbol.upper():
            if 'FUT' in symbol.upper():
                base_price = 45000.0
            elif 'CE' in symbol.upper() or 'PE' in symbol.upper():
                # Extract strike from symbol and calculate option price
                base_price = self._calculate_option_price(symbol)
            else:
                base_price = 45000.0
        elif 'NIFTY' in symbol.upper():
            if 'FUT' in symbol.upper():
                base_price = 19500.0
            elif 'CE' in symbol.upper() or 'PE' in symbol.upper():
                base_price = self._calculate_option_price(symbol)
            else:
                base_price = 19500.0
        else:
            base_price = 100.0
        
        # Add some random variation
        variation = random.uniform(-0.01, 0.01)  # ±1%
        return round(base_price * (1 + variation), 2)
    
    def _calculate_option_price(self, symbol: str) -> float:
        """
        Calculate mock option price based on symbol
        
        Args:
            symbol: Option symbol
            
        Returns:
            float: Mock option price
        """
        try:
            # Simple mock option pricing
            # In reality, this would use Black-Scholes or similar model
            
            # Extract strike price from symbol (rough extraction)
            import re
            strike_match = re.search(r'(\d{5,6})', symbol)
            if strike_match:
                strike = float(strike_match.group(1))
            else:
                strike = 45000.0
            
            # Simple intrinsic + time value calculation
            underlying_price = 45000.0  # Mock underlying price
            
            if 'CE' in symbol.upper():  # Call option
                intrinsic = max(0, underlying_price - strike)
            else:  # Put option
                intrinsic = max(0, strike - underlying_price)
            
            time_value = random.uniform(10, 200)  # Random time value
            
            return round(intrinsic + time_value, 2)
            
        except Exception:
            return random.uniform(50, 300)
    
    def _update_position(self, symbol: str, action: str, quantity: int, price: float) -> None:
        """
        Update position tracking
        
        Args:
            symbol: Trading symbol
            action: BUY or SELL
            quantity: Quantity traded
            price: Trade price
        """
        if symbol not in self.positions:
            self.positions[symbol] = {
                'quantity': 0,
                'avg_price': 0.0,
                'total_cost': 0.0
            }
        
        pos = self.positions[symbol]
        
        # Calculate new position
        if action.upper() == 'BUY':
            new_quantity = pos['quantity'] + quantity
            new_cost = pos['total_cost'] + (quantity * price)
        else:  # SELL
            new_quantity = pos['quantity'] - quantity
            new_cost = pos['total_cost'] - (quantity * price)
        
        # Update position
        if new_quantity != 0:
            pos['avg_price'] = abs(new_cost / new_quantity)
        else:
            pos['avg_price'] = 0.0
        
        pos['quantity'] = new_quantity
        pos['total_cost'] = new_cost
