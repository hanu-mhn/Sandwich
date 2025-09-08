"""
Configuration loader utility

Handles loading and validation of YAML configuration files.
"""

import yaml
import os
from typing import Dict, Any
from pathlib import Path


class ConfigLoader:
    """Configuration loader and validator"""
    
    @staticmethod
    def load(config_path: str) -> Dict[str, Any]:
        """
        Load configuration from YAML file
        
        Args:
            config_path: Path to the configuration file
            
        Returns:
            Dict: Configuration dictionary
            
        Raises:
            FileNotFoundError: If config file doesn't exist
            ValueError: If config is invalid
        """
        config_file = Path(config_path)
        
        if not config_file.exists():
            raise FileNotFoundError(f"Configuration file not found: {config_path}")
        
        try:
            with open(config_file, 'r') as f:
                config = yaml.safe_load(f)
            
            # Validate configuration
            ConfigLoader._validate_config(config)
            
            # Process environment variables
            config = ConfigLoader._process_env_vars(config)
            
            return config
            
        except yaml.YAMLError as e:
            raise ValueError(f"Invalid YAML in configuration file: {str(e)}")
        except Exception as e:
            raise ValueError(f"Error loading configuration: {str(e)}")
    
    @staticmethod
    def _validate_config(config: Dict[str, Any]) -> None:
        """
        Validate configuration structure
        
        Args:
            config: Configuration dictionary
            
        Raises:
            ValueError: If configuration is invalid
        """
        required_sections = ['broker', 'strategy', 'market_data', 'risk', 'logging']
        
        for section in required_sections:
            if section not in config:
                raise ValueError(f"Missing required configuration section: {section}")
        
        # Validate broker config
        broker_config = config['broker']
        required_broker_fields = ['name', 'api_key', 'api_secret']
        for field in required_broker_fields:
            if field not in broker_config:
                raise ValueError(f"Missing required broker field: {field}")
        
        # Validate strategy config
        strategy_config = config['strategy']
        required_strategy_fields = ['capital', 'profit_target', 'strike_percentages', 'execution_time']
        for field in required_strategy_fields:
            if field not in strategy_config:
                raise ValueError(f"Missing required strategy field: {field}")
        
        # Validate strike percentages
        if not isinstance(strategy_config['strike_percentages'], list):
            raise ValueError("strike_percentages must be a list")
        
        if len(strategy_config['strike_percentages']) < 2:
            raise ValueError("strike_percentages must contain at least 2 values")
        
        if len(strategy_config['strike_percentages']) > 6:
            raise ValueError("strike_percentages must contain at most 6 values for risk management")
        
        # Validate profit target
        if not 0 < strategy_config['profit_target'] <= 1:
            raise ValueError("profit_target must be between 0 and 1")
        
        # Validate capital
        if strategy_config['capital'] <= 0:
            raise ValueError("capital must be positive")
    
    @staticmethod
    def _process_env_vars(config: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process environment variables in configuration
        
        Args:
            config: Configuration dictionary
            
        Returns:
            Dict: Processed configuration
        """
        def replace_env_vars(obj):
            if isinstance(obj, dict):
                return {k: replace_env_vars(v) for k, v in obj.items()}
            elif isinstance(obj, list):
                return [replace_env_vars(item) for item in obj]
            elif isinstance(obj, str) and obj.startswith('${') and obj.endswith('}'):
                # Extract environment variable name
                env_var = obj[2:-1]
                default_value = None
                
                # Check for default value
                if ':' in env_var:
                    env_var, default_value = env_var.split(':', 1)
                
                # Get environment variable value
                value = os.getenv(env_var, default_value)
                
                if value is None:
                    raise ValueError(f"Environment variable not found: {env_var}")
                
                # Try to convert to appropriate type
                try:
                    # Try integer
                    return int(value)
                except ValueError:
                    try:
                        # Try float
                        return float(value)
                    except ValueError:
                        # Try boolean
                        if value.lower() in ('true', 'false'):
                            return value.lower() == 'true'
                        # Return as string
                        return value
            else:
                return obj
        
        return replace_env_vars(config)
    
    @staticmethod
    def save_example_config(output_path: str) -> None:
        """
        Save an example configuration file
        
        Args:
            output_path: Path where to save the example config
        """
        example_config = {
            'broker': {
                'name': 'zerodha',
                'api_key': '${BROKER_API_KEY}',
                'api_secret': '${BROKER_API_SECRET}',
                'access_token': '${BROKER_ACCESS_TOKEN}',
                'user_id': '${BROKER_USER_ID}'
            },
            'strategy': {
                'capital': 500000,
                'max_risk_per_trade': 0.05,
                'profit_target': 0.10,
                'strike_percentages': [0.5, 1.0, 1.5, 2.0],
                'execution_time': '15:00',
                'timezone': 'Asia/Kolkata'
            },
            'market_data': {
                'primary_source': 'broker',
                'backup_source': 'yahoo'
            },
            'risk': {
                'max_positions': 10,
                'margin_buffer': 1.2,
                'max_drawdown': 0.15
            },
            'logging': {
                'level': 'INFO',
                'file': 'logs/trading.log',
                'max_size_mb': 10,
                'backup_count': 5
            }
        }
        
        with open(output_path, 'w') as f:
            yaml.dump(example_config, f, default_flow_style=False, indent=2)
