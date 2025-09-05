"""
Base Broker Interface

Defines the common interface that all broker implementations must follow.
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, List
from dataclasses import dataclass


@dataclass
class OrderResult:
    """Result of an order placement"""
    status: str  # SUCCESS, FAILED, PENDING
    order_id: Optional[str] = None
    price: Optional[float] = None
    message: Optional[str] = None
    timestamp: Optional[str] = None


@dataclass
class Position:
    """Position information"""
    symbol: str
    quantity: int
    average_price: float
    last_price: float
    unrealized_pnl: float
    realized_pnl: float


@dataclass
class Quote:
    """Market quote information"""
    symbol: str
    last_price: float
    bid_price: float
    ask_price: float
    volume: int
    timestamp: str


class BaseBroker(ABC):
    """Abstract base class for all broker implementations"""
    
    def __init__(self, config: Dict[str, Any]):
        """
        Initialize broker with configuration
        
        Args:
            config: Broker configuration dictionary
        """
        self.config = config
        self.is_connected = False
    
    @abstractmethod
    def connect(self) -> bool:
        """
        Connect to broker API
        
        Returns:
            bool: True if connection successful
        """
        pass
    
    @abstractmethod
    def disconnect(self) -> None:
        """Disconnect from broker API"""
        pass
    
    @abstractmethod
    def place_order(self, symbol: str, action: str, quantity: int, 
                   order_type: str, price: float = None) -> OrderResult:
        """
        Place an order
        
        Args:
            symbol: Trading symbol
            action: BUY or SELL
            quantity: Number of shares/lots
            order_type: MARKET, LIMIT, SL, etc.
            price: Limit price (for limit orders)
            
        Returns:
            OrderResult: Result of order placement
        """
        pass
    
    @abstractmethod
    def cancel_order(self, order_id: str) -> bool:
        """
        Cancel an order
        
        Args:
            order_id: Order ID to cancel
            
        Returns:
            bool: True if cancellation successful
        """
        pass
    
    @abstractmethod
    def get_order_status(self, order_id: str) -> Dict[str, Any]:
        """
        Get order status
        
        Args:
            order_id: Order ID
            
        Returns:
            Dict: Order status information
        """
        pass
    
    @abstractmethod
    def get_positions(self) -> List[Position]:
        """
        Get current positions
        
        Returns:
            List[Position]: List of current positions
        """
        pass
    
    @abstractmethod
    def get_quote(self, symbol: str) -> Optional[Quote]:
        """
        Get market quote
        
        Args:
            symbol: Trading symbol
            
        Returns:
            Quote: Market quote or None if not available
        """
        pass
    
    @abstractmethod
    def get_ltp(self, symbol: str) -> Optional[float]:
        """
        Get last traded price
        
        Args:
            symbol: Trading symbol
            
        Returns:
            float: Last traded price or None if not available
        """
        pass
    
    @abstractmethod
    def get_margins(self) -> Dict[str, float]:
        """
        Get margin information
        
        Returns:
            Dict: Margin information (available, used, etc.)
        """
        pass
    
    @abstractmethod
    def get_holdings(self) -> List[Dict[str, Any]]:
        """
        Get holdings information
        
        Returns:
            List: Holdings information
        """
        pass
    
    def is_market_open(self) -> bool:
        """
        Check if market is open
        
        Returns:
            bool: True if market is open
        """
        # Default implementation - can be overridden by specific brokers
        from datetime import datetime, time
        import pytz
        
        ist = pytz.timezone('Asia/Kolkata')
        now = datetime.now(ist)
        current_time = now.time()
        
        # NSE trading hours: 9:15 AM to 3:30 PM on weekdays
        market_open = time(9, 15)
        market_close = time(15, 30)
        
        # Check if it's a weekday and within trading hours
        is_weekday = now.weekday() < 5  # Monday = 0, Sunday = 6
        is_trading_hours = market_open <= current_time <= market_close
        
        return is_weekday and is_trading_hours
