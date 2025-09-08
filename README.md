# Bank Nifty Monthly Expiry Trading Strategy

A Python-based automated trading system for executing a sophisticated Bank Nifty options and futures strategy on monthly expiry days.

## Strategy Overview

This system automates a calendar spread trading strategy that:
- Executes on current month's expiry day at 3:00 PM IST (e.g., June expiry)
- Uses next month's Bank Nifty futures and options (e.g., July expiry)
- Targets 10% profit on deployed capital
- Handles the NSE expiry rule change (Thursday to Tuesday from Sept 2025)

## Features

- **Automated Execution**: Precise timing at 3:00 PM IST on expiry days
- **Dynamic Strike Calculation**: ±0.25%, 0.5%, 0.75% from current price
- **Multi-leg Position Management**: Complex options spreads with futures
- **Risk Management**: 10% profit target with automatic exit
- **Broker Integration**: Support for popular Indian brokers
- **Backtesting**: Historical strategy performance analysis

## Installation

```bash
pip install -r requirements.txt
```

## Configuration

1. Copy `config/config.example.yaml` to `config/config.yaml`
2. Add your broker credentials and API keys
3. Configure risk parameters and capital allocation

## Usage

### Manual Execution
```bash
python src/main.py --execute
```

### Backtesting
```bash
python src/backtest.py --start-date 2024-01-01 --end-date 2024-12-31
```

### Scheduler (Production)
```bash
python src/scheduler.py
```

## Project Structure

```
├── src/
│   ├── main.py              # Main execution script
│   ├── strategy/            # Strategy implementation
│   ├── brokers/             # Broker integrations
│   ├── market_data/         # Market data providers
│   ├── risk_management/     # Risk and position management
│   └── utils/               # Utility functions
├── config/                  # Configuration files
├── tests/                   # Unit and integration tests
└── logs/                    # Log files
```

## Strategy Details

### Position Structure
- **Futures**: 1 lot short next month Bank Nifty futures
- **Put Options**: 2 buy (0.75%), 1 sell (0.25%), 2 sell (0.5%) - next month expiry
- **Call Options**: 1 buy (0.25%), 2 sell (0.5%), 2 buy (0.75%) - next month expiry

### Entry Rules
- Execute at 3:00 PM IST on current month expiry day
- Use next month's expiry instruments for longer time to expiry
- Calculate strikes based on current futures price
- Round strikes to nearest 100

### Exit Rules
- Monitor combined P&L continuously
- Exit all positions at 10% profit target
- Auto-exit at 3:25 PM on current month expiry day at market price

## Risk Considerations

- Ensure adequate margin for multi-leg positions
- Factor in transaction costs and slippage
- Monitor market conditions and volatility
- Implement position sizing based on capital

## License

MIT License

## Disclaimer

This software is for educational purposes. Trading involves substantial risk of loss. Use at your own risk.
