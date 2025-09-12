"""
Market Data Provider

Handles market data from various sources including broker APIs and external providers.
"""

import logging
import os
from typing import Dict, Any, Optional, List, Tuple
from datetime import datetime, date

import pandas as pd


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
        # CSV data caches
        self._csv_cache: Dict[str, pd.DataFrame] = {}
        self._data_dir = self._resolve_data_dir()

    # ---------------- CSV Loading ---------------- #
    def _resolve_data_dir(self) -> str:
        """Resolve path to embedded CSV data directory."""
        # Allow override via config
        cfg_dir = self.config.get('csv_data_dir')
        if cfg_dir and os.path.isdir(cfg_dir):
            return cfg_dir
        # Default relative path
        base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # src/market_data
        data_dir = os.path.join(base, 'market_data', 'Data')
        # Fallback: sibling Data directory already inside market_data
        if not os.path.isdir(data_dir):
            data_dir = os.path.join(base, 'Data')
        return data_dir

    def _lazy_load_csv(self, trading_date: date) -> Optional[pd.DataFrame]:
        """Load a single day BANKNIFTY back-adjusted CSV.

        Expects filename pattern contains yyyymmdd (DDMMYYYY in provided samples like 02062025 -> ddmmyyyy).
        We'll attempt both DDMMYYYY and YYYYMMDD patterns.
        """
        # Already cached by date string
        key = trading_date.strftime('%Y-%m-%d')
        if key in self._csv_cache:
            return self._csv_cache[key]

        # Build candidate filenames (observed pattern: GFDLNFO_BACKADJUSTED_DDMMYYYY.csv)
        ddmmyyyy = trading_date.strftime('%d%m%Y')
        yyyymmdd = trading_date.strftime('%Y%m%d')
        candidates = [
            f'GFDLNFO_BACKADJUSTED_{ddmmyyyy}.csv',
            f'GFDLNFO_BACKADJUSTED_{yyyymmdd}.csv'
        ]
        for fname in candidates:
            fpath = os.path.join(self._data_dir, fname)
            if os.path.isfile(fpath):
                try:
                    df = pd.read_csv(fpath)
                    # Basic normalization
                    cols = {c.lower(): c for c in df.columns}
                    # Standardize expected columns
                    rename_map = {}
                    for target in ['symbol', 'close', 'open', 'high', 'low', 'expiry', 'instrument', 'optiontype', 'strike', 'date', 'timestamp']:
                        for col in df.columns:
                            if col.lower() == target:
                                rename_map[col] = target
                    if rename_map:
                        df = df.rename(columns=rename_map)
                    # Attempt date column parse
                    if 'timestamp' in df.columns:
                        try:
                            df['timestamp'] = pd.to_datetime(df['timestamp'])
                        except Exception:
                            pass
                    elif 'date' in df.columns:
                        try:
                            df['timestamp'] = pd.to_datetime(df['date'])
                        except Exception:
                            df['timestamp'] = trading_date
                    else:
                        df['timestamp'] = trading_date
                    self._csv_cache[key] = df
                    self.logger.info(f"Loaded CSV data {fname} rows={len(df)}")
                    return df
                except Exception as e:
                    self.logger.error(f"Failed parsing {fpath}: {e}")
        self.logger.warning(f"No CSV data found for {trading_date}")
        return None

    # ---------------- Public CSV Access ---------------- #
    def get_spot(self, dt: datetime) -> Optional[float]:
        """Return spot (approx) using FUT or nearest underlying record.

        Strategy: prefer nearest at-the-money future/underlying midpoint.
        """
        df = self._lazy_load_csv(dt.date())
        if df is None:
            return None
        # Heuristic: if there is a BANKNIFTY FUT row use its close; else average of option synthetic.
        fut_rows = df[df['symbol'].str.contains('BANKNIFTY', na=False) & df['symbol'].str.contains('FUT', na=False)] if 'symbol' in df.columns else pd.DataFrame()
        if not fut_rows.empty:
            return float(fut_rows.iloc[0].get('close', float('nan')))
        # Fallback: derive from CE/PE around median strike
        if 'strike' in df.columns and 'close' in df.columns and 'optiontype' in df.columns:
            ce = df[df['optiontype'].str.upper()=='CE']
            pe = df[df['optiontype'].str.upper()=='PE']
            if not ce.empty and not pe.empty:
                # Find ATM by minimal |CE_close - PE_close|
                merged = ce[['strike','close']].merge(pe[['strike','close']], on='strike', suffixes=('_ce','_pe'))
                merged['diff'] = (merged['close_ce'] - merged['close_pe']).abs()
                atm = merged.sort_values('diff').head(1)
                if not atm.empty:
                    # Spot approximation = strike + (CE - PE)
                    row = atm.iloc[0]
                    spot = row['strike'] + (row['close_ce'] - row['close_pe'])
                    return float(spot)
        return None

    def get_future(self, dt: datetime, expiry: date) -> Optional[float]:
        df = self._lazy_load_csv(dt.date())
        if df is None:
            return None
        if 'symbol' in df.columns:
            mask = df['symbol'].str.contains('FUT', na=False) & df['symbol'].str.contains(expiry.strftime('%y%m%d')[-5:], na=False)
            fut_rows = df[mask]
            if not fut_rows.empty:
                return float(fut_rows.iloc[0].get('close', float('nan')))
        return None

    def get_option_price(self, dt: datetime, expiry: date, strike: int, opt_type: str) -> Optional[float]:
        df = self._lazy_load_csv(dt.date())
        if df is None:
            return None
        opt_type_u = opt_type.upper()
        # Try symbol-based first
        if 'symbol' in df.columns:
            # Typical symbol might contain yymmdd strike and CE/PE
            yymmdd = expiry.strftime('%y%m%d')
            sym_part = f"{yymmdd}{strike}{opt_type_u}"
            subset = df[df['symbol'].str.contains(sym_part, na=False)]
            if not subset.empty:
                return float(subset.iloc[0].get('close', float('nan')))
        # Column-based fallback
        if {'strike','optiontype','close'}.issubset(set(c.lower() for c in df.columns)):
            # We normalized to lowercase earlier optionally
            col_map = {c.lower(): c for c in df.columns}
            sdf = df[(df[col_map['strike']] == strike) & (df[col_map['optiontype']].str.upper()==opt_type_u)]
            if not sdf.empty:
                return float(sdf.iloc[0][col_map['close']])
        return None
    
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
            self.logger.info(f"Getting historical data for {symbol} from {from_date} to {to_date} via CSV if possible")
            start = datetime.strptime(from_date, '%Y-%m-%d').date()
            end = datetime.strptime(to_date, '%Y-%m-%d').date()
            out: List[Dict[str, Any]] = []
            cur = start
            while cur <= end:
                df = self._lazy_load_csv(cur)
                if df is not None:
                    # Filter rows referencing symbol substring
                    if 'symbol' in df.columns:
                        rows = df[df['symbol'].str.contains(symbol, na=False)]
                        for _, r in rows.iterrows():
                            out.append({k: r[k] for k in r.index if k != '_index'})
                cur = cur + pd.Timedelta(days=1)
            return out
            
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
            import yfinance as yf

            # Build candidate symbols list (indices and ETF fallbacks)
            candidates = self._yahoo_candidates(symbol)
            if not candidates:
                self.logger.debug(f"Yahoo conversion returned no candidates for {symbol}")
                return None

            # Try each candidate with intraday then daily fallback
            for ysym in candidates:
                price = None
                try:
                    df = yf.download(tickers=ysym, period='1d', interval='1m', progress=False, threads=False)
                    if df is not None and not df.empty and 'Close' in df.columns:
                        price = float(df['Close'].iloc[-1])
                except Exception as e:
                    self.logger.debug(f"Minute data fetch failed for {ysym}: {e}")

                if price is None:
                    try:
                        df = yf.download(tickers=ysym, period='5d', interval='1d', progress=False, threads=False)
                        if df is not None and not df.empty and 'Close' in df.columns:
                            price = float(df['Close'].iloc[-1])
                    except Exception as e:
                        self.logger.debug(f"Daily data fetch failed for {ysym}: {e}")

                if price is not None:
                    return price

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
        symu = symbol.upper()

        # If it's a raw request for underlying indices
        if symu == 'NIFTY' or symu == '^NSEI':
            return '^NSEI'
        if symu == 'BANKNIFTY' or symu == '^NSEBANK':
            return '^NSEBANK'

        # Derivative patterns: map BANKNIFTY...FUT/CE/PE to index spot symbol
        if 'BANKNIFTY' in symu:
            return '^NSEBANK'
        if 'NIFTY' in symu and 'BANKNIFTY' not in symu:
            return '^NSEI'

        # For stocks: append .NS for NSE listings
        # Strip common suffixes if accidentally passed
        clean = symu.replace('.NS', '')
        return f"{clean}.NS"

    def _yahoo_candidates(self, symbol: str) -> List[str]:
        """Return Yahoo tickers for a given symbol, restricted to BankNifty only."""
        symu = symbol.upper()
        # Allow only BankNifty index and its derivatives via ETF fallback
        if symu in ('BANKNIFTY', '^NSEBANK'):
            return ['^NSEBANK', 'BANKBEES.NS']
        if 'BANKNIFTY' in symu:
            return ['^NSEBANK', 'BANKBEES.NS']
        # For any non-BankNifty symbol, don't provide candidates (force fallback/None)
        return []
    
    def set_broker_instance(self, broker):
        """
        Set broker instance for market data
        
        Args:
            broker: Broker instance
        """
        self.broker = broker
        if hasattr(broker, 'get_ltp'):
            self._get_ltp_from_broker = broker.get_ltp
