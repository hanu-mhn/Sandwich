"""
Position Manager

Handles position tracking, risk management, and portfolio monitoring.
"""

import logging
from typing import Dict, Any, List, Optional
from datetime import datetime
from dataclasses import dataclass


@dataclass
class RiskLimits:
    """Risk limit configuration"""
    max_positions: int
    max_position_size: float
    max_daily_loss: float
    max_drawdown: float
    margin_buffer: float


@dataclass
class PortfolioMetrics:
    """Portfolio performance metrics"""
    total_pnl: float
    unrealized_pnl: float
    realized_pnl: float
    total_capital: float
    used_margin: float
    available_margin: float
    number_of_positions: int
    max_drawdown: float
    win_rate: float


class PositionManager:
    """Manages positions and risk controls"""
    
    def __init__(self, config: Dict[str, Any]):
        """
        Initialize position manager
        
        Args:
            config: Risk management configuration
        """
        self.config = config
        self.logger = logging.getLogger(__name__)
        
        # Setup risk limits
        self.risk_limits = RiskLimits(
            max_positions=config.get('max_positions', 10),
            max_position_size=config.get('max_position_size', 100000),
            max_daily_loss=config.get('max_daily_loss', 50000),
            max_drawdown=config.get('max_drawdown', 0.15),
            margin_buffer=config.get('margin_buffer', 1.2)
        )
        
        # Position tracking
        self.positions = {}
        self.daily_pnl = 0.0
        self.peak_portfolio_value = 0.0
        self.current_drawdown = 0.0
        
        # Trade history
        self.trade_history = []
        self.daily_stats = {}
    
    def add_position(self, symbol: str, quantity: int, entry_price: float, 
                    position_type: str = 'LONG') -> bool:
        """
        Add a new position
        
        Args:
            symbol: Trading symbol
            quantity: Position quantity
            entry_price: Entry price
            position_type: LONG or SHORT
            
        Returns:
            bool: True if position added successfully
        """
        try:
            # Check risk limits
            if not self._check_position_limits(symbol, quantity, entry_price):
                return False
            
            # Create position record
            position = {
                'symbol': symbol,
                'quantity': quantity,
                'entry_price': entry_price,
                'position_type': position_type,
                'entry_time': datetime.now(),
                'current_price': entry_price,
                'unrealized_pnl': 0.0,
                'margin_used': self._calculate_margin_requirement(symbol, quantity, entry_price)
            }
            
            self.positions[symbol] = position
            self.logger.info(f"Position added: {symbol} {quantity} @ {entry_price}")
            
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to add position {symbol}: {str(e)}")
            return False
    
    def update_position(self, symbol: str, current_price: float) -> None:
        """
        Update position with current market price
        
        Args:
            symbol: Trading symbol
            current_price: Current market price
        """
        try:
            if symbol not in self.positions:
                return
            
            position = self.positions[symbol]
            position['current_price'] = current_price
            
            # Calculate unrealized P&L
            if position['position_type'] == 'LONG':
                position['unrealized_pnl'] = (current_price - position['entry_price']) * position['quantity']
            else:  # SHORT
                position['unrealized_pnl'] = (position['entry_price'] - current_price) * position['quantity']
            
            # Update portfolio metrics
            self._update_portfolio_metrics()
            
        except Exception as e:
            self.logger.error(f"Failed to update position {symbol}: {str(e)}")
    
    def close_position(self, symbol: str, exit_price: float) -> bool:
        """
        Close a position
        
        Args:
            symbol: Trading symbol
            exit_price: Exit price
            
        Returns:
            bool: True if position closed successfully
        """
        try:
            if symbol not in self.positions:
                self.logger.warning(f"Position not found for closing: {symbol}")
                return False
            
            position = self.positions[symbol]
            
            # Calculate realized P&L
            if position['position_type'] == 'LONG':
                realized_pnl = (exit_price - position['entry_price']) * position['quantity']
            else:  # SHORT
                realized_pnl = (position['entry_price'] - exit_price) * position['quantity']
            
            # Record trade
            trade_record = {
                'symbol': symbol,
                'entry_price': position['entry_price'],
                'exit_price': exit_price,
                'quantity': position['quantity'],
                'position_type': position['position_type'],
                'entry_time': position['entry_time'],
                'exit_time': datetime.now(),
                'realized_pnl': realized_pnl,
                'holding_period': datetime.now() - position['entry_time']
            }
            
            self.trade_history.append(trade_record)
            
            # Remove position
            del self.positions[symbol]
            
            # Update daily P&L
            self.daily_pnl += realized_pnl
            
            self.logger.info(f"Position closed: {symbol} P&L: ₹{realized_pnl:,.2f}")
            
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to close position {symbol}: {str(e)}")
            return False
    
    def get_portfolio_metrics(self) -> PortfolioMetrics:
        """
        Get current portfolio metrics
        
        Returns:
            PortfolioMetrics: Current portfolio metrics
        """
        try:
            total_unrealized_pnl = sum(pos['unrealized_pnl'] for pos in self.positions.values())
            total_realized_pnl = sum(trade['realized_pnl'] for trade in self.trade_history)
            total_pnl = total_unrealized_pnl + total_realized_pnl
            
            used_margin = sum(pos['margin_used'] for pos in self.positions.values())
            
            # Calculate win rate
            winning_trades = len([t for t in self.trade_history if t['realized_pnl'] > 0])
            total_trades = len(self.trade_history)
            win_rate = (winning_trades / total_trades * 100) if total_trades > 0 else 0
            
            return PortfolioMetrics(
                total_pnl=total_pnl,
                unrealized_pnl=total_unrealized_pnl,
                realized_pnl=total_realized_pnl,
                total_capital=500000,  # From config
                used_margin=used_margin,
                available_margin=500000 - used_margin,
                number_of_positions=len(self.positions),
                max_drawdown=self.current_drawdown,
                win_rate=win_rate
            )
            
        except Exception as e:
            self.logger.error(f"Failed to calculate portfolio metrics: {str(e)}")
            return PortfolioMetrics(0, 0, 0, 0, 0, 0, 0, 0, 0)
    
    def check_risk_limits(self) -> List[str]:
        """
        Check if any risk limits are violated
        
        Returns:
            List[str]: List of risk violations
        """
        violations = []
        
        try:
            metrics = self.get_portfolio_metrics()
            
            # Check number of positions
            if metrics.number_of_positions > self.risk_limits.max_positions:
                violations.append(f"Too many positions: {metrics.number_of_positions} > {self.risk_limits.max_positions}")
            
            # Check daily loss
            if self.daily_pnl < -self.risk_limits.max_daily_loss:
                violations.append(f"Daily loss limit exceeded: ₹{self.daily_pnl:,.2f}")
            
            # Check drawdown
            if self.current_drawdown > self.risk_limits.max_drawdown:
                violations.append(f"Max drawdown exceeded: {self.current_drawdown:.2%}")
            
            # Check margin utilization
            margin_ratio = metrics.used_margin / metrics.total_capital
            if margin_ratio > (1 / self.risk_limits.margin_buffer):
                violations.append(f"Margin utilization too high: {margin_ratio:.2%}")
            
        except Exception as e:
            self.logger.error(f"Failed to check risk limits: {str(e)}")
            violations.append("Error checking risk limits")
        
        return violations
    
    def _check_position_limits(self, symbol: str, quantity: int, price: float) -> bool:
        """
        Check if new position violates limits
        
        Args:
            symbol: Trading symbol
            quantity: Position quantity
            price: Position price
            
        Returns:
            bool: True if position is within limits
        """
        # Check max positions
        if len(self.positions) >= self.risk_limits.max_positions:
            self.logger.warning("Maximum positions limit reached")
            return False
        
        # Check position size
        position_value = quantity * price
        if position_value > self.risk_limits.max_position_size:
            self.logger.warning(f"Position size too large: ₹{position_value:,.2f}")
            return False
        
        # Check margin requirement
        margin_required = self._calculate_margin_requirement(symbol, quantity, price)
        current_used_margin = sum(pos['margin_used'] for pos in self.positions.values())
        total_margin_needed = current_used_margin + margin_required
        
        available_capital = 500000  # From config
        if total_margin_needed > (available_capital / self.risk_limits.margin_buffer):
            self.logger.warning("Insufficient margin for new position")
            return False
        
        return True
    
    def _calculate_margin_requirement(self, symbol: str, quantity: int, price: float) -> float:
        """
        Calculate margin requirement for a position
        
        Args:
            symbol: Trading symbol
            quantity: Position quantity
            price: Position price
            
        Returns:
            float: Margin requirement
        """
        # Simplified margin calculation
        # In reality, this would be more complex based on instrument type
        
        if 'FUT' in symbol.upper():
            # Futures margin (approximately 10-15% of contract value)
            lot_size = 25  # Bank Nifty lot size
            contract_value = price * lot_size * quantity
            margin_rate = 0.12  # 12%
            return contract_value * margin_rate
        
        elif 'CE' in symbol.upper() or 'PE' in symbol.upper():
            # Options margin (premium + additional margin for short positions)
            lot_size = 25
            premium = price * lot_size * quantity
            # For long options, margin is just the premium
            return premium
        
        else:
            # Cash market (100% margin)
            return price * quantity
    
    def _update_portfolio_metrics(self) -> None:
        """Update portfolio-level metrics"""
        try:
            metrics = self.get_portfolio_metrics()
            current_portfolio_value = metrics.total_capital + metrics.total_pnl
            
            # Update peak value
            if current_portfolio_value > self.peak_portfolio_value:
                self.peak_portfolio_value = current_portfolio_value
            
            # Calculate current drawdown
            if self.peak_portfolio_value > 0:
                self.current_drawdown = (self.peak_portfolio_value - current_portfolio_value) / self.peak_portfolio_value
            
        except Exception as e:
            self.logger.error(f"Failed to update portfolio metrics: {str(e)}")
    
    def get_position_summary(self) -> Dict[str, Any]:
        """
        Get summary of all positions
        
        Returns:
            Dict: Position summary
        """
        try:
            summary = {
                'total_positions': len(self.positions),
                'positions': [],
                'total_unrealized_pnl': 0.0
            }
            
            for symbol, position in self.positions.items():
                pos_summary = {
                    'symbol': symbol,
                    'quantity': position['quantity'],
                    'entry_price': position['entry_price'],
                    'current_price': position['current_price'],
                    'unrealized_pnl': position['unrealized_pnl'],
                    'position_type': position['position_type']
                }
                summary['positions'].append(pos_summary)
                summary['total_unrealized_pnl'] += position['unrealized_pnl']
            
            return summary
            
        except Exception as e:
            self.logger.error(f"Failed to get position summary: {str(e)}")
            return {'total_positions': 0, 'positions': [], 'total_unrealized_pnl': 0.0}
