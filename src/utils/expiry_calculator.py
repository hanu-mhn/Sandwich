"""
Expiry Date Calculator for Indian Markets

Handles the calculation of NSE monthly expiry dates, including the rule change
from last Thursday to last Tuesday starting September 2025.
"""

from datetime import datetime, date, timedelta
from typing import List
import calendar


class ExpiryCalculator:
    """Calculator for NSE monthly expiry dates"""
    
    # Rule change date - September 2025 onwards, expiry is last Tuesday
    RULE_CHANGE_DATE = date(2025, 9, 1)
    
    def __init__(self):
        self.cache = {}
    
    def get_monthly_expiry_date(self, year: int, month: int) -> date:
        """
        Get the monthly expiry date for a given year and month
        
        Args:
            year: Year (e.g., 2025)
            month: Month (1-12)
            
        Returns:
            date: The expiry date for that month
        """
        cache_key = (year, month)
        if cache_key in self.cache:
            return self.cache[cache_key]
        
        # Determine if we use Thursday or Tuesday rule
        check_date = date(year, month, 1)
        
        if check_date >= self.RULE_CHANGE_DATE:
            # Use Tuesday rule (September 2025 onwards)
            expiry_date = self._get_last_weekday(year, month, calendar.TUESDAY)
        else:
            # Use Thursday rule (until August 2025)
            expiry_date = self._get_last_weekday(year, month, calendar.THURSDAY)
        
        self.cache[cache_key] = expiry_date
        return expiry_date
    
    def _get_last_weekday(self, year: int, month: int, weekday: int) -> date:
        """
        Get the last occurrence of a specific weekday in a month
        
        Args:
            year: Year
            month: Month
            weekday: Weekday (0=Monday, 1=Tuesday, ..., 6=Sunday)
            
        Returns:
            date: The last occurrence of the weekday in that month
        """
        # Get the last day of the month
        last_day = calendar.monthrange(year, month)[1]
        last_date = date(year, month, last_day)
        
        # Find the last occurrence of the specified weekday
        days_back = (last_date.weekday() - weekday) % 7
        return last_date - timedelta(days=days_back)
    
    def get_current_expiry_date(self, reference_date: date = None) -> date:
        """
        Get the current month's expiry date
        
        Args:
            reference_date: Reference date (defaults to today)
            
        Returns:
            date: Current month's expiry date
        """
        if reference_date is None:
            reference_date = date.today()
        
        return self.get_monthly_expiry_date(reference_date.year, reference_date.month)
    
    def get_next_expiry_date(self, reference_date: date = None) -> date:
        """
        Get the next month's expiry date
        
        Args:
            reference_date: Reference date (defaults to today)
            
        Returns:
            date: Next month's expiry date
        """
        if reference_date is None:
            reference_date = date.today()
        
        # Calculate next month
        if reference_date.month == 12:
            next_year = reference_date.year + 1
            next_month = 1
        else:
            next_year = reference_date.year
            next_month = reference_date.month + 1
        
        return self.get_monthly_expiry_date(next_year, next_month)
    
    def get_previous_expiry_date(self, reference_date: date = None) -> date:
        """
        Get the previous month's expiry date
        
        Args:
            reference_date: Reference date (defaults to today)
            
        Returns:
            date: Previous month's expiry date
        """
        if reference_date is None:
            reference_date = date.today()
        
        # Calculate previous month
        if reference_date.month == 1:
            prev_year = reference_date.year - 1
            prev_month = 12
        else:
            prev_year = reference_date.year
            prev_month = reference_date.month - 1
        
        return self.get_monthly_expiry_date(prev_year, prev_month)
    
    def is_expiry_day(self, check_date: date = None) -> bool:
        """
        Check if a given date is an expiry day
        
        Args:
            check_date: Date to check (defaults to today)
            
        Returns:
            bool: True if it's an expiry day
        """
        if check_date is None:
            check_date = date.today()
        
        current_expiry = self.get_current_expiry_date(check_date)
        return check_date == current_expiry
    
    def get_expiry_dates_for_year(self, year: int) -> List[date]:
        """
        Get all expiry dates for a given year
        
        Args:
            year: Year to get expiry dates for
            
        Returns:
            List[date]: List of all expiry dates in the year
        """
        expiry_dates = []
        for month in range(1, 13):
            expiry_date = self.get_monthly_expiry_date(year, month)
            expiry_dates.append(expiry_date)
        
        return expiry_dates
    
    def days_to_expiry(self, reference_date: date = None) -> int:
        """
        Calculate days remaining to current month's expiry
        
        Args:
            reference_date: Reference date (defaults to today)
            
        Returns:
            int: Number of days to expiry
        """
        if reference_date is None:
            reference_date = date.today()
        
        expiry_date = self.get_current_expiry_date(reference_date)
        return (expiry_date - reference_date).days
    
    def is_strategy_execution_day(self, check_date: date = None) -> bool:
        """
        Check if a given date is a strategy execution day
        (previous month's expiry day)
        
        Args:
            check_date: Date to check (defaults to today)
            
        Returns:
            bool: True if it's a strategy execution day
        """
        if check_date is None:
            check_date = date.today()
        
        prev_expiry = self.get_previous_expiry_date(check_date)
        return check_date == prev_expiry
