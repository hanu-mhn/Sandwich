"""
Test for Mock Broker

Tests the mock broker functionality.
"""

import unittest
import sys
from pathlib import Path

# Add src to path
sys.path.append(str(Path(__file__).parent.parent / 'src'))

from brokers.mock_broker import MockBroker


class TestMockBroker(unittest.TestCase):
    """Test cases for MockBroker"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.config = {
            'name': 'mock',
            'api_key': 'test_key',
            'api_secret': 'test_secret'
        }
        self.broker = MockBroker(self.config)
    
    def test_connection(self):
        """Test broker connection"""
        # Test connect
        result = self.broker.connect()
        self.assertTrue(result)
        self.assertTrue(self.broker.is_connected)
        
        # Test disconnect
        self.broker.disconnect()
        self.assertFalse(self.broker.is_connected)
    
    def test_place_order(self):
        """Test order placement"""
        self.broker.connect()
        
        # Test market order
        result = self.broker.place_order(
            symbol='BANKNIFTY25SEP45000CE',
            action='BUY',
            quantity=1,
            order_type='MARKET'
        )
        
        self.assertEqual(result.status, 'SUCCESS')
        self.assertIsNotNone(result.order_id)
        self.assertIsNotNone(result.price)
        self.assertGreater(result.price, 0)
    
    def test_position_tracking(self):
        """Test position tracking"""
        self.broker.connect()
        
        # Place a buy order
        result1 = self.broker.place_order('BANKNIFTY25SEP45000CE', 'BUY', 2, 'MARKET')
        self.assertEqual(result1.status, 'SUCCESS')
        
        # Place a sell order
        result2 = self.broker.place_order('BANKNIFTY25SEP45000CE', 'SELL', 1, 'MARKET')
        self.assertEqual(result2.status, 'SUCCESS')
        
        # Check positions
        positions = self.broker.get_positions()
        self.assertEqual(len(positions), 1)
        
        position = positions[0]
        self.assertEqual(position.symbol, 'BANKNIFTY25SEP45000CE')
        self.assertEqual(position.quantity, 1)  # 2 - 1 = 1
    
    def test_get_ltp(self):
        """Test getting last traded price"""
        self.broker.connect()
        
        # Test futures
        price = self.broker.get_ltp('BANKNIFTY25SEP45000FUT')
        self.assertIsNotNone(price)
        self.assertGreater(price, 0)
        
        # Test options
        price = self.broker.get_ltp('BANKNIFTY25SEP45000CE')
        self.assertIsNotNone(price)
        self.assertGreater(price, 0)
    
    def test_get_quote(self):
        """Test getting market quote"""
        self.broker.connect()
        
        quote = self.broker.get_quote('BANKNIFTY25SEP45000CE')
        self.assertIsNotNone(quote)
        self.assertEqual(quote.symbol, 'BANKNIFTY25SEP45000CE')
        self.assertGreater(quote.last_price, 0)
        self.assertGreater(quote.ask_price, quote.bid_price)
    
    def test_margins(self):
        """Test margin information"""
        self.broker.connect()
        
        margins = self.broker.get_margins()
        self.assertIn('available', margins)
        self.assertIn('used', margins)
        self.assertIn('total', margins)
        
        self.assertGreater(margins['available'], 0)
        self.assertGreaterEqual(margins['used'], 0)
        self.assertGreater(margins['total'], 0)


if __name__ == '__main__':
    unittest.main()
