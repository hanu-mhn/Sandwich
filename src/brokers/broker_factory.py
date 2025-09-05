"""
Broker Factory

Creates broker instances based on configuration.
"""

from typing import Dict, Any
from src.brokers.base_broker import BaseBroker
from src.brokers.zerodha_broker import ZerodhaBroker
from src.brokers.upstox_broker import UpstoxBroker
from src.brokers.mock_broker import MockBroker


class BrokerFactory:
    """Factory class for creating broker instances"""
    
    BROKER_CLASSES = {
        'zerodha': ZerodhaBroker,
        'upstox': UpstoxBroker,
        'mock': MockBroker
    }
    
    @classmethod
    def create(cls, broker_config: Dict[str, Any], dry_run: bool = False) -> BaseBroker:
        """
        Create a broker instance
        
        Args:
            broker_config: Broker configuration
            dry_run: If True, return mock broker
            
        Returns:
            BaseBroker: Broker instance
            
        Raises:
            ValueError: If broker type is not supported
        """
        if dry_run:
            return MockBroker(broker_config)
        
        broker_name = broker_config.get('name', '').lower()
        
        if broker_name not in cls.BROKER_CLASSES:
            raise ValueError(f"Unsupported broker: {broker_name}")
        
        broker_class = cls.BROKER_CLASSES[broker_name]
        return broker_class(broker_config)
    
    @classmethod
    def get_supported_brokers(cls) -> list:
        """Get list of supported brokers"""
        return list(cls.BROKER_CLASSES.keys())
