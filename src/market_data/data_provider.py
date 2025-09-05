"""
Market Data Provider

Handles market data from various sources including broker APIs and external providers.
"""

import logging
from typing import Dict, Any, Optional, List
from datetime import datetime


class MarketDataProvider:
    """Market data provider with multiple source support"""
    
    def __init__(self, config: Dict[str, Any]):
        """
        Initialize market data provider
        
        Args:
            config: Market data configuration
        """
        self.config = config
        self.logger = logging.getLogger(__name__)
        
        self.primary_source = config.get('primary_source', 'broker')
        self.backup_source = config.get('backup_source', 'yahoo')
        
        # Cache for market data
        self.price_cache = {}
        self.cache_timeout = 5  # 5 seconds cache
    
    def get_ltp(self, symbol: str) -> Optional[float]:
        """
        Get last traded price for a symbol
        
        Args:
            symbol: Trading symbol
            
        Returns:
            float: Last traded price or None if not available
        """
        try:
            # Check cache first
            cached_data = self.price_cache.get(symbol)
            if cached_data:
                timestamp, price = cached_data
                if (datetime.now() - timestamp).seconds < self.cache_timeout:
                    return price
            
            # Try primary source
            price = self._get_ltp_from_source(symbol, self.primary_source)
            
            if price is None and self.backup_source:
                # Try backup source
                price = self._get_ltp_from_source(symbol, self.backup_source)
            
            # Cache the result
            if price is not None:
                self.price_cache[symbol] = (datetime.now(), price)
            
            return price
            
        except Exception as e:
            self.logger.error(f"Failed to get LTP for {symbol}: {str(e)}")
            return None
    
    def get_historical_data(self, symbol: str, from_date: str, to_date: str, 
                          interval: str = 'day') -> List[Dict[str, Any]]:
        """
        Get historical data for a symbol
        
        Args:
            symbol: Trading symbol
            from_date: Start date (YYYY-MM-DD)
            to_date: End date (YYYY-MM-DD)
            interval: Data interval (minute, day, etc.)
            
        Returns:
            List: Historical data records
        """
        try:
            # Implementation would depend on the data source
            # This is a placeholder
            self.logger.info(f"Getting historical data for {symbol} from {from_date} to {to_date}")
            
            # Return empty list for now
            return []
            
        except Exception as e:
            self.logger.error(f"Failed to get historical data for {symbol}: {str(e)}")
            return []
    
    def get_option_chain(self, underlying: str, expiry_date: str) -> Dict[str, Any]:
        """
        Get option chain data
        
        Args:
            underlying: Underlying symbol (e.g., BANKNIFTY)
            expiry_date: Expiry date (YYYY-MM-DD)
            
        Returns:
            Dict: Option chain data
        """
        try:
            # Implementation would depend on the data source
            # This is a placeholder
            self.logger.info(f"Getting option chain for {underlying} expiry {expiry_date}")
            
            return {
                'underlying': underlying,
                'expiry_date': expiry_date,
                'calls': [],
                'puts': []
            }
            
        except Exception as e:
            self.logger.error(f"Failed to get option chain for {underlying}: {str(e)}")
            return {}
    
    def _get_ltp_from_source(self, symbol: str, source: str) -> Optional[float]:
        """
        Get LTP from specific source
        
        Args:
            symbol: Trading symbol
            source: Data source name
            
        Returns:
            float: Last traded price or None
        """
        try:
            if source == 'broker':
                return self._get_ltp_from_broker(symbol)
            elif source == 'yahoo':
                return self._get_ltp_from_yahoo(symbol)
            elif source == 'mock':
                return self._get_mock_ltp(symbol)
            else:
                self.logger.warning(f"Unknown data source: {source}")
                return None
                
        except Exception as e:
            self.logger.error(f"Failed to get LTP from {source} for {symbol}: {str(e)}")
            return None
    
    def _get_ltp_from_broker(self, symbol: str) -> Optional[float]:
        """
        Get LTP from broker (placeholder)
        
        Args:
            symbol: Trading symbol
            
        Returns:
            float: Last traded price or None
        """
        # This would be implemented with actual broker integration
        # For now, return None to indicate not available
        return None
    
    def _get_ltp_from_yahoo(self, symbol: str) -> Optional[float]:
        """
        Get LTP from Yahoo Finance
        
        Args:
            symbol: Trading symbol
            
        Returns:
            float: Last traded price or None
        """
        try:
            # Convert NSE symbol to Yahoo format if needed
            yahoo_symbol = self._convert_to_yahoo_symbol(symbol)
            
            if not yahoo_symbol:
                return None
            
            # This would require yfinance library
            # For now, return None
            return None
            
        except Exception as e:
            self.logger.error(f"Failed to get LTP from Yahoo for {symbol}: {str(e)}")
            return None
    
    def _get_mock_ltp(self, symbol: str) -> Optional[float]:
        """
        Get mock LTP for testing
        
        Args:
            symbol: Trading symbol
            
        Returns:
            float: Mock price
        """
        import random
        
        # Generate mock prices based on symbol type
        if 'BANKNIFTY' in symbol.upper():
            if 'FUT' in symbol.upper():
                base_price = 45000.0
            else:  # Options
                base_price = random.uniform(50, 500)
        elif 'NIFTY' in symbol.upper():
            if 'FUT' in symbol.upper():
                base_price = 19500.0
            else:  # Options
                base_price = random.uniform(20, 300)
        else:
            base_price = 100.0
        
        # Add random variation
        variation = random.uniform(-0.02, 0.02)  # ±2%
        return round(base_price * (1 + variation), 2)
    
    def _convert_to_yahoo_symbol(self, symbol: str) -> Optional[str]:
        """
        Convert NSE symbol to Yahoo Finance symbol
        
        Args:
            symbol: NSE trading symbol
            
        Returns:
            str: Yahoo symbol or None if not convertible
        """
        # Basic conversion logic
        if 'NIFTY' in symbol.upper() and 'BANKNIFTY' not in symbol.upper():
            return '^NSEI'
        elif 'BANKNIFTY' in symbol.upper():
            # Bank Nifty is not directly available on Yahoo
            return None
        else:
            # For individual stocks, add .NS suffix
            return f"{symbol}.NS"
    
    def set_broker_instance(self, broker):
        """
        Set broker instance for market data
        
        Args:
            broker: Broker instance
        """
        self.broker = broker
        if hasattr(broker, 'get_ltp'):
            self._get_ltp_from_broker = broker.get_ltp
