"""
Test for Expiry Calculator

Tests the calculation of NSE monthly expiry dates.
"""

import unittest
from datetime import date
import sys
from pathlib import Path

# Add src to path
sys.path.append(str(Path(__file__).parent.parent / 'src'))

from utils.expiry_calculator import ExpiryCalculator


class TestExpiryCalculator(unittest.TestCase):
    """Test cases for ExpiryCalculator"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.calc = ExpiryCalculator()
    
    def test_thursday_rule_before_september_2025(self):
        """Test expiry calculation for Thursday rule (before September 2025)"""
        # Test August 2025 - should be last Thursday
        expiry = self.calc.get_monthly_expiry_date(2025, 8)
        # August 2025: Last Thursday is 28th
        expected = date(2025, 8, 28)
        self.assertEqual(expiry, expected)
        
        # Test January 2025 - should be last Thursday
        expiry = self.calc.get_monthly_expiry_date(2025, 1)
        # January 2025: Last Thursday is 30th
        expected = date(2025, 1, 30)
        self.assertEqual(expiry, expected)
    
    def test_tuesday_rule_from_september_2025(self):
        """Test expiry calculation for Tuesday rule (from September 2025)"""
        # Test September 2025 - should be last Tuesday
        expiry = self.calc.get_monthly_expiry_date(2025, 9)
        # September 2025: Last Tuesday is 30th
        expected = date(2025, 9, 30)
        self.assertEqual(expiry, expected)
        
        # Test December 2025 - should be last Tuesday
        expiry = self.calc.get_monthly_expiry_date(2025, 12)
        # December 2025: Last Tuesday is 30th
        expected = date(2025, 12, 30)
        self.assertEqual(expiry, expected)
    
    def test_is_expiry_day(self):
        """Test expiry day detection"""
        # Test a known expiry day
        expiry_date = self.calc.get_monthly_expiry_date(2025, 8)
        self.assertTrue(self.calc.is_expiry_day(expiry_date))
        
        # Test a non-expiry day
        non_expiry = date(2025, 8, 15)
        self.assertFalse(self.calc.is_expiry_day(non_expiry))
    
    def test_get_expiry_dates_for_year(self):
        """Test getting all expiry dates for a year"""
        expiry_dates = self.calc.get_expiry_dates_for_year(2025)
        
        # Should have 12 expiry dates
        self.assertEqual(len(expiry_dates), 12)
        
        # All should be date objects
        for expiry_date in expiry_dates:
            self.assertIsInstance(expiry_date, date)
        
        # Should be in chronological order
        for i in range(1, len(expiry_dates)):
            self.assertGreater(expiry_dates[i], expiry_dates[i-1])
    
    def test_days_to_expiry(self):
        """Test days to expiry calculation"""
        # Test with a known date
        test_date = date(2025, 8, 20)
        expiry_date = self.calc.get_monthly_expiry_date(2025, 8)
        expected_days = (expiry_date - test_date).days
        
        actual_days = self.calc.days_to_expiry(test_date)
        self.assertEqual(actual_days, expected_days)


if __name__ == '__main__':
    unittest.main()
