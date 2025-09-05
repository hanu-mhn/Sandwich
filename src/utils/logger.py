"""
Logging configuration and setup

Provides centralized logging setup with rotation and formatting.
"""

import logging
import logging.handlers
import os
from pathlib import Path
from typing import Dict, Any


def setup_logging(config: Dict[str, Any]) -> None:
    """
    Setup logging configuration
    
    Args:
        config: Configuration dictionary containing logging settings
    """
    logging_config = config.get('logging', {})
    
    # Default values
    log_level = logging_config.get('level', 'INFO').upper()
    log_file = logging_config.get('file', 'logs/trading.log')
    max_size_mb = logging_config.get('max_size_mb', 10)
    backup_count = logging_config.get('backup_count', 5)
    
    # Create logs directory if it doesn't exist
    log_path = Path(log_file)
    log_path.parent.mkdir(parents=True, exist_ok=True)
    
    # Create formatter
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    # Setup root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, log_level))
    
    # Clear existing handlers
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)
    
    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(getattr(logging, log_level))
    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)
    
    # File handler with rotation
    file_handler = logging.handlers.RotatingFileHandler(
        log_file,
        maxBytes=max_size_mb * 1024 * 1024,
        backupCount=backup_count
    )
    file_handler.setLevel(getattr(logging, log_level))
    file_handler.setFormatter(formatter)
    root_logger.addHandler(file_handler)
    
    # Set specific logger levels
    logging.getLogger('urllib3').setLevel(logging.WARNING)
    logging.getLogger('requests').setLevel(logging.WARNING)
    
    logging.info("Logging configured successfully")


class TradeLogger:
    """Specialized logger for trade-related events"""
    
    def __init__(self, name: str = "trade_logger"):
        self.logger = logging.getLogger(name)
        
        # Create trade-specific log file
        trade_log_path = Path("logs/trades.log")
        trade_log_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Create trade file handler
        trade_handler = logging.handlers.RotatingFileHandler(
            trade_log_path,
            maxBytes=50 * 1024 * 1024,  # 50MB
            backupCount=10
        )
        
        # Trade log format includes more details
        trade_formatter = logging.Formatter(
            '%(asctime)s - TRADE - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        trade_handler.setFormatter(trade_formatter)
        trade_handler.setLevel(logging.INFO)
        
        self.logger.addHandler(trade_handler)
        self.logger.setLevel(logging.INFO)
    
    def log_order_placed(self, symbol: str, action: str, quantity: int, price: float, order_id: str):
        """Log order placement"""
        self.logger.info(f"ORDER_PLACED | {symbol} | {action} | Qty: {quantity} | Price: ₹{price} | ID: {order_id}")
    
    def log_order_filled(self, symbol: str, action: str, quantity: int, fill_price: float, order_id: str):
        """Log order fill"""
        self.logger.info(f"ORDER_FILLED | {symbol} | {action} | Qty: {quantity} | Fill: ₹{fill_price} | ID: {order_id}")
    
    def log_order_rejected(self, symbol: str, action: str, quantity: int, reason: str, order_id: str):
        """Log order rejection"""
        self.logger.error(f"ORDER_REJECTED | {symbol} | {action} | Qty: {quantity} | Reason: {reason} | ID: {order_id}")
    
    def log_position_update(self, symbol: str, net_quantity: int, avg_price: float, unrealized_pnl: float):
        """Log position update"""
        self.logger.info(f"POSITION_UPDATE | {symbol} | Net: {net_quantity} | Avg: ₹{avg_price} | PnL: ₹{unrealized_pnl}")
    
    def log_strategy_entry(self, capital_deployed: float, positions_count: int):
        """Log strategy entry"""
        self.logger.info(f"STRATEGY_ENTRY | Capital: ₹{capital_deployed:,.2f} | Positions: {positions_count}")
    
    def log_strategy_exit(self, total_pnl: float, percentage_return: float, positions_closed: int):
        """Log strategy exit"""
        self.logger.info(f"STRATEGY_EXIT | PnL: ₹{total_pnl:,.2f} | Return: {percentage_return:.2f}% | Closed: {positions_closed}")
    
    def log_risk_event(self, event_type: str, details: str):
        """Log risk management events"""
        self.logger.warning(f"RISK_EVENT | {event_type} | {details}")


def get_logger(name: str) -> logging.Logger:
    """
    Get a logger instance
    
    Args:
        name: Logger name
        
    Returns:
        logging.Logger: Logger instance
    """
    return logging.getLogger(name)
