"""
Zerodha Broker Implementation

Implements Zerodha Kite Connect API integration for live trading.
"""

import logging
from typing import Dict, Any, Optional, List
from src.brokers.base_broker import BaseBroker, OrderResult, Position, Quote

try:
    from kiteconnect import KiteConnect
    KITE_AVAILABLE = True
except ImportError:
    KITE_AVAILABLE = False
    KiteConnect = None


class ZerodhaBroker(BaseBroker):
    """Zerodha Kite Connect broker implementation"""
    
    def __init__(self, config: Dict[str, Any]):
        """
        Initialize Zerodha broker
        
        Args:
            config: Broker configuration containing API credentials
        """
        super().__init__(config)
        self.logger = logging.getLogger(__name__)
        
        if not KITE_AVAILABLE:
            raise ImportError("kiteconnect library not installed. Run: pip install kiteconnect")
        
        self.api_key = config.get('api_key')
        self.api_secret = config.get('api_secret')
        self.access_token = config.get('access_token')
        
        if not all([self.api_key, self.api_secret]):
            raise ValueError("Missing required Zerodha API credentials")
        
        self.kite = None
    
    def connect(self) -> bool:
        """
        Connect to Zerodha Kite Connect API
        
        Returns:
            bool: True if connection successful
        """
        try:
            self.kite = KiteConnect(api_key=self.api_key)
            
            if self.access_token:
                # Use existing access token
                self.kite.set_access_token(self.access_token)
            else:
                # Note: In production, you need to implement OAuth flow
                # This is just a placeholder
                self.logger.error("Access token required for Zerodha connection")
                return False
            
            # Test connection by getting user profile
            profile = self.kite.profile()
            self.logger.info(f"Connected to Zerodha. User: {profile.get('user_name', 'Unknown')}")
            
            self.is_connected = True
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to connect to Zerodha: {str(e)}")
            self.is_connected = False
            return False
    
    def disconnect(self) -> None:
        """Disconnect from Zerodha API"""
        self.kite = None
        self.is_connected = False
        self.logger.info("Disconnected from Zerodha")
    
    def place_order(self, symbol: str, action: str, quantity: int, 
                   order_type: str, price: float = None) -> OrderResult:
        """
        Place order through Zerodha Kite
        
        Args:
            symbol: Trading symbol (NSE format)
            action: BUY or SELL
            quantity: Number of shares/lots
            order_type: MARKET, LIMIT, SL, SL-M
            price: Limit price (for limit orders)
            
        Returns:
            OrderResult: Result of order placement
        """
        if not self.is_connected or not self.kite:
            return OrderResult(status="FAILED", message="Not connected to broker")
        
        try:
            # Map order types
            kite_order_type = self._map_order_type(order_type)
            kite_transaction_type = self._map_action(action)
            
            # Determine exchange and product type
            exchange, product = self._get_exchange_and_product(symbol)
            
            # Prepare order parameters
            order_params = {
                'tradingsymbol': symbol,
                'exchange': exchange,
                'transaction_type': kite_transaction_type,
                'quantity': quantity,
                'order_type': kite_order_type,
                'product': product,
                'validity': 'DAY'
            }
            
            # Add price for limit orders
            if kite_order_type in ['LIMIT', 'SL']:
                if price is None:
                    return OrderResult(status="FAILED", message="Price required for limit orders")
                order_params['price'] = price
            
            # Place order
            response = self.kite.place_order(**order_params)
            order_id = response.get('order_id')
            
            self.logger.info(f"Order placed: {action} {quantity} {symbol} (Order ID: {order_id})")
            
            return OrderResult(
                status="SUCCESS",
                order_id=order_id,
                message="Order placed successfully"
            )
            
        except Exception as e:
            error_msg = f"Order placement failed: {str(e)}"
            self.logger.error(error_msg)
            return OrderResult(status="FAILED", message=error_msg)
    
    def cancel_order(self, order_id: str) -> bool:
        """
        Cancel order
        
        Args:
            order_id: Order ID to cancel
            
        Returns:
            bool: True if cancellation successful
        """
        if not self.is_connected or not self.kite:
            return False
        
        try:
            self.kite.cancel_order(order_id=order_id)
            self.logger.info(f"Order cancelled: {order_id}")
            return True
            
        except Exception as e:
            self.logger.error(f"Order cancellation failed: {str(e)}")
            return False
    
    def get_order_status(self, order_id: str) -> Dict[str, Any]:
        """
        Get order status
        
        Args:
            order_id: Order ID
            
        Returns:
            Dict: Order status information
        """
        if not self.is_connected or not self.kite:
            return {'status': 'ERROR', 'message': 'Not connected'}
        
        try:
            orders = self.kite.orders()
            for order in orders:
                if order.get('order_id') == order_id:
                    return order
            
            return {'status': 'NOT_FOUND', 'message': 'Order not found'}
            
        except Exception as e:
            self.logger.error(f"Failed to get order status: {str(e)}")
            return {'status': 'ERROR', 'message': str(e)}
    
    def get_positions(self) -> List[Position]:
        """
        Get current positions
        
        Returns:
            List[Position]: List of current positions
        """
        if not self.is_connected or not self.kite:
            return []
        
        try:
            positions_data = self.kite.positions()
            positions = []
            
            for pos_type in ['net', 'day']:
                for pos in positions_data.get(pos_type, []):
                    if pos.get('quantity', 0) != 0:
                        position = Position(
                            symbol=pos.get('tradingsymbol', ''),
                            quantity=pos.get('quantity', 0),
                            average_price=pos.get('average_price', 0.0),
                            last_price=pos.get('last_price', 0.0),
                            unrealized_pnl=pos.get('unrealised', 0.0),
                            realized_pnl=pos.get('realised', 0.0)
                        )
                        positions.append(position)
            
            return positions
            
        except Exception as e:
            self.logger.error(f"Failed to get positions: {str(e)}")
            return []
    
    def get_quote(self, symbol: str) -> Optional[Quote]:
        """
        Get market quote
        
        Args:
            symbol: Trading symbol
            
        Returns:
            Quote: Market quote or None
        """
        if not self.is_connected or not self.kite:
            return None
        
        try:
            # Determine exchange
            exchange, _ = self._get_exchange_and_product(symbol)
            instrument_key = f"{exchange}:{symbol}"
            
            quotes = self.kite.quote([instrument_key])
            quote_data = quotes.get(instrument_key, {})
            
            if not quote_data:
                return None
            
            return Quote(
                symbol=symbol,
                last_price=quote_data.get('last_price', 0.0),
                bid_price=quote_data.get('depth', {}).get('buy', [{}])[0].get('price', 0.0),
                ask_price=quote_data.get('depth', {}).get('sell', [{}])[0].get('price', 0.0),
                volume=quote_data.get('volume', 0),
                timestamp=quote_data.get('timestamp', '')
            )
            
        except Exception as e:
            self.logger.error(f"Failed to get quote for {symbol}: {str(e)}")
            return None
    
    def get_ltp(self, symbol: str) -> Optional[float]:
        """
        Get last traded price
        
        Args:
            symbol: Trading symbol
            
        Returns:
            float: Last traded price or None
        """
        if not self.is_connected or not self.kite:
            return None
        
        try:
            exchange, _ = self._get_exchange_and_product(symbol)
            instrument_key = f"{exchange}:{symbol}"
            
            ltp_data = self.kite.ltp([instrument_key])
            return ltp_data.get(instrument_key, {}).get('last_price')
            
        except Exception as e:
            self.logger.error(f"Failed to get LTP for {symbol}: {str(e)}")
            return None
    
    def get_margins(self) -> Dict[str, float]:
        """
        Get margin information
        
        Returns:
            Dict: Margin information
        """
        if not self.is_connected or not self.kite:
            return {}
        
        try:
            margins = self.kite.margins()
            equity_margins = margins.get('equity', {})
            
            return {
                'available': equity_margins.get('available', {}).get('cash', 0.0),
                'used': equity_margins.get('utilised', {}).get('debits', 0.0),
                'total': equity_margins.get('net', 0.0)
            }
            
        except Exception as e:
            self.logger.error(f"Failed to get margins: {str(e)}")
            return {}
    
    def get_holdings(self) -> List[Dict[str, Any]]:
        """
        Get holdings information
        
        Returns:
            List: Holdings information
        """
        if not self.is_connected or not self.kite:
            return []
        
        try:
            return self.kite.holdings()
            
        except Exception as e:
            self.logger.error(f"Failed to get holdings: {str(e)}")
            return []
    
    def _map_order_type(self, order_type: str) -> str:
        """Map generic order type to Kite order type"""
        mapping = {
            'MARKET': 'MARKET',
            'LIMIT': 'LIMIT',
            'SL': 'SL',
            'SL-M': 'SL-M'
        }
        return mapping.get(order_type.upper(), 'MARKET')
    
    def _map_action(self, action: str) -> str:
        """Map generic action to Kite transaction type"""
        return 'BUY' if action.upper() == 'BUY' else 'SELL'
    
    def _get_exchange_and_product(self, symbol: str) -> tuple:
        """
        Determine exchange and product type from symbol
        
        Args:
            symbol: Trading symbol
            
        Returns:
            tuple: (exchange, product)
        """
        symbol_upper = symbol.upper()
        
        if 'NIFTY' in symbol_upper or 'BANKNIFTY' in symbol_upper:
            if 'FUT' in symbol_upper:
                return 'NFO', 'NRML'  # Futures
            elif 'CE' in symbol_upper or 'PE' in symbol_upper:
                return 'NFO', 'NRML'  # Options
            else:
                return 'NSE', 'CNC'  # Cash
        else:
            return 'NSE', 'CNC'  # Default to cash market
