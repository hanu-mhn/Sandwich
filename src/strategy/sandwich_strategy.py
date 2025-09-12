"""Sandwich Strategy Implementation

Implements the rules provided:

Entry (Monthly Expiry Day 3:00 PM IST):
  - Get SPOT (S0) and next-month FUT (F1). If F1 < S0: abort.
  - Determine 4-week vs 5-week month (next_expiry - current_expiry > 28 days => 5-week).

Initial Position Construction ("Units"):
  Sausage Units (core):
    1. SELL next-month future (1 lot)
    2. BUY 1 Call +500 points ("5 OTM" assumed 500 points) from FUT price
    3. SELL 1 Put with premium ~= bought call premium (approx by choosing strike equidistant below FUT)
  Bread Units (outer): distances depend on month length
    4/5. CALL Bread: SELL 2 Calls at +D_sell (D_sell = 2000 or 2500) and BUY 2 Calls at +D_sell + hedge_offset (500)
    6/7. PUT Bread:  SELL 2 Puts  at -D_sell and BUY 2 Puts  at -D_sell - hedge_offset (500)

Lifecycle / Adjustments:
  - Passive hold: 2 weeks (4-week) or 3 weeks (5-week) unless profit >= 12% (close all early).
  - Firefighting trigger (after passive window): PnL < 0 AND rally >= 1500 (4-week) / 2000 (5-week) vs S0.
      * Adjustment 1: Roll single short put up by 400/500/600 (pick closest to align with initial FUT level). Shift bread puts up by +D_sell (i.e. +2000 or +2500).
  - After additional 3-4 trading days if still no downward movement (spot above new put sold strike + 250 points) shift puts another +1000 (Adjustment 2).
  - On expiry week Monday: if spot > upper sold call strike => transform to short straddle: move sold puts to that call strike (close old put structure) + adjust protective long puts 500 lower.
  - Final exit: monthly expiry 3:00 PM or early profit target.

Notes:
  - This implementation focuses on structural orchestration and state transitions with mock pricing.
  - Broker & real option chain integration can replace mock selection logic later.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, date, timedelta, time
from typing import List, Optional, Dict

from src.utils.expiry_calculator import ExpiryCalculator
from src.market_data.data_provider import MarketDataProvider
from src.brokers.broker_factory import BrokerFactory


@dataclass
class Leg:
    instrument: str
    side: str          # BUY / SELL
    type: str          # FUT / CE / PE
    strike: Optional[int]
    qty: int
    role: str          # SAUSAGE_CALL_LONG, SAUSAGE_PUT_SHORT, BREAD_CALL_SHORT, etc.
    entry_price: float
    current_price: float = 0.0
    open: bool = True

    def pnl(self) -> float:
        if not self.open:
            return 0.0
        multiplier = 1 if self.side == 'BUY' else -1
        return (self.current_price - self.entry_price) * multiplier * self.qty


class SandwichStrategy:
    """Stateful Sandwich Strategy"""

    STATES = [
        'IDLE', 'ACTIVE_PASSIVE', 'FIREFIGHT_STAGE1', 'FIREFIGHT_STAGE2', 'STRADDLE_FINAL', 'CLOSED'
    ]

    def __init__(self, config: Dict, dry_run: bool = True, market_data: MarketDataProvider | None = None):
        self.config = config
        self.logger = logging.getLogger(__name__)
        self.dry_run = dry_run
        self.expiry_calc = ExpiryCalculator()
        self.market_data = market_data or MarketDataProvider(config['market_data'])
        self.broker = BrokerFactory.create(config['broker'], dry_run)
        self.market_data.set_broker_instance(self.broker)

        # Strategy specific configuration
        strat_cfg = config.get('sandwich', {})
        self.profit_target_pct = strat_cfg.get('profit_target_pct', 0.12)
        self.call_offset = strat_cfg.get('call_offset_points', 500)
        self.base_sell_4 = strat_cfg.get('base_sell_distance_4w', 2000)
        self.base_sell_5 = strat_cfg.get('base_sell_distance_5w', 2500)
        self.hedge_offset = strat_cfg.get('hedge_offset', 500)
        self.rally_threshold_4 = strat_cfg.get('rally_threshold_4w', 1500)
        self.rally_threshold_5 = strat_cfg.get('rally_threshold_5w', 2000)
        self.passive_weeks_4 = strat_cfg.get('passive_weeks_4w', 2)
        self.passive_weeks_5 = strat_cfg.get('passive_weeks_5w', 3)
        self.core_put_roll_candidates = strat_cfg.get('core_put_roll_points', [400, 500, 600])
        self.secondary_put_shift = strat_cfg.get('secondary_put_shift', 1000)

        # State tracking
        self.state = 'IDLE'
        self.legs: List[Leg] = []
        self.entry_datetime: Optional[datetime] = None
        self.initial_spot: Optional[float] = None
        self.initial_future: Optional[float] = None
        self.month_type: Optional[str] = None  # '4W' or '5W'
        self.current_expiry: Optional[date] = None
        self.next_expiry: Optional[date] = None
        self.last_adjustment_date: Optional[date] = None

    # ---------------------------- Public API ---------------------------- #
    def execute_entry(self, force: bool = False, spot_override: float | None = None, future_override: float | None = None,
                      current_expiry: date | None = None, next_expiry: date | None = None) -> bool:
        """Attempt entry on monthly expiry day at ~15:00 IST.

        Args:
            force: bypass date/time gating (for backtests)
            spot_override: externally supplied spot price
            future_override: externally supplied future price
            current_expiry: override current expiry date
            next_expiry: override next month expiry date
        """
        now = datetime.now()
        today = now.date()
        self.current_expiry = current_expiry or self.expiry_calc.get_current_expiry_date(today)
        if not force:
            if today != self.current_expiry:
                self.logger.info("Not monthly expiry day; skipping Sandwich entry.")
                return False
            # Time gate (allow +/- 5 min)
            if not self._time_near(now.time(), time(15, 0), tolerance_min=5):
                self.logger.info("Time not within 3 PM entry window")
                return False

        # Determine next month expiry
        next_month = self.current_expiry.month + 1
        next_year = self.current_expiry.year
        if next_month > 12:
            next_month = 1
            next_year += 1
        self.next_expiry = next_expiry or self.expiry_calc.get_monthly_expiry_date(next_year, next_month)

        # Month classification (4-week vs 5-week)
        gap_days = (self.next_expiry - self.current_expiry).days
        self.month_type = '5W' if gap_days > 28 else '4W'

        # Spot & Future (mock retrieval via market_data; if future < spot abort)
        self.initial_spot = spot_override if spot_override is not None else self._get_mock_spot()
        self.initial_future = future_override if future_override is not None else self._get_mock_future(self.initial_spot)

        if self.initial_future < self.initial_spot:
            self.logger.info("Future below spot - aborting entry per rule.")
            return False

        # Build initial structure
        self._build_initial_positions()
        self.entry_datetime = now
        self.state = 'ACTIVE_PASSIVE'
        self.logger.info(f"Sandwich strategy entered. MonthType={self.month_type} Spot={self.initial_spot} Fut={self.initial_future}")
        return True

    def monitor(self):
        """Main monitoring function to be called periodically (e.g., daily)."""
        if self.state in ('IDLE', 'CLOSED'):
            return
        self._update_prices()
        pnl, pnl_pct = self._portfolio_pnl()
        self.logger.info(f"State={self.state} PnL={pnl:.2f} ({pnl_pct:.2f}%) Spot={self._get_mock_spot():.2f}")

        # Early profit exit
        if pnl_pct >= self.profit_target_pct * 100 and self.state != 'CLOSED':
            self.logger.info("Early profit target achieved -> closing all positions")
            self._close_all("PROFIT_TARGET")
            return

        # Forced expiry exit at 15:00 on next expiry? (Final day)
        now = datetime.now()
        if now.date() == self.next_expiry and self._time_near(now.time(), time(15, 0), tolerance_min=5):
            self.logger.info("Final expiry exit -> closing all positions")
            self._close_all("FINAL_EXPIRY")
            return

        # Determine rally & days since entry
        spot_now = self._get_mock_spot()
        rally_points = spot_now - (self.initial_spot or spot_now)
        days_since_entry = (now.date() - self.entry_datetime.date()).days if self.entry_datetime else 0
        passive_weeks = self.passive_weeks_5 if self.month_type == '5W' else self.passive_weeks_4
        passive_days = passive_weeks * 7

        # Adjustment logic
        if self.state == 'ACTIVE_PASSIVE':
            if days_since_entry >= passive_days:
                # Eligible to consider firefighting
                if pnl < 0:
                    rally_th = self.rally_threshold_5 if self.month_type == '5W' else self.rally_threshold_4
                    if rally_points >= rally_th:
                        self._firefight_stage1()
        elif self.state == 'FIREFIGHT_STAGE1':
            # After 3-4 trading days w/out downward move -> shift +1000
            if self.last_adjustment_date and (now.date() - self.last_adjustment_date).days >= 4:
                # Condition: spot above new sold put + 250 buffer
                sold_puts = [l for l in self.legs if l.role == 'BREAD_PUT_SHORT' and l.open]
                if sold_puts:
                    max_put_strike = max(sp.strike for sp in sold_puts if sp.strike)
                    if spot_now > (max_put_strike + 250):
                        self._firefight_stage2()
        elif self.state == 'FIREFIGHT_STAGE2':
            # Expiry week Monday straddle conversion
            if now.weekday() == 0 and (self.next_expiry - now.date()).days <= 4:  # Monday of expiry week
                upper_calls = [l for l in self.legs if l.role == 'BREAD_CALL_SHORT' and l.open]
                if upper_calls:
                    upper_strike = min(l.strike for l in upper_calls if l.strike)
                    if spot_now > upper_strike:
                        self._convert_to_straddle(upper_strike)

    # ---------------------------- Metrics API ---------------------------- #
    def get_metrics(self) -> Dict[str, any]:
        """Return current strategy metrics as a dictionary."""
        total_pnl, pnl_pct = self._portfolio_pnl()
        open_legs = [l for l in self.legs if l.open]
        closed_legs = [l for l in self.legs if not l.open]
        role_counts: Dict[str, int] = {}
        for leg in open_legs:
            role_counts[leg.role] = role_counts.get(leg.role, 0) + 1
        long_pnl = sum(l.pnl() for l in open_legs if l.side == 'BUY')
        short_pnl = sum(l.pnl() for l in open_legs if l.side == 'SELL')
        days_since_entry = (datetime.now().date() - self.entry_datetime.date()).days if self.entry_datetime else 0
        return {
            'state': self.state,
            'month_type': self.month_type,
            'open_legs': len(open_legs),
            'closed_legs': len(closed_legs),
            'role_breakdown': role_counts,
            'total_pnl': round(total_pnl, 2),
            'pnl_pct_capital': round(pnl_pct, 4),
            'long_pnl': round(long_pnl, 2),
            'short_pnl': round(short_pnl, 2),
            'net_pnl_consistency': round(long_pnl + short_pnl - total_pnl, 4),  # diagnostic
            'days_since_entry': days_since_entry,
            'future_vs_spot_diff': round((self.initial_future - self.initial_spot) if (self.initial_future and self.initial_spot) else 0, 2),
            'rally_points': round((self._get_mock_spot() - self.initial_spot) if self.initial_spot else 0, 2)
        }

    def log_metrics(self):
        """Convenience logger for current metrics."""
        m = self.get_metrics()
        self.logger.info(
            "METRICS state=%s legs(open=%d closed=%d) pnl=%.2f(%.3f%%) long=%.2f short=%.2f roles=%s",
            m['state'], m['open_legs'], m['closed_legs'], m['total_pnl'], m['pnl_pct_capital'], m['long_pnl'], m['short_pnl'], m['role_breakdown']
        )

    # ---------------------------- Internal Helpers ---------------------------- #
    def _build_initial_positions(self):
        fut_symbol = self._fut_symbol(self.next_expiry)
        # 1. Sell Future
        self._add_leg(fut_symbol, 'SELL', 'FUT', None, 1, 'SAUSAGE_FUT')

        # 2. Buy Call +500
        call_strike = self._round_strike(self.initial_future + self.call_offset)
        call_symbol = self._opt_symbol(call_strike, 'CE')
        call_price = self._mock_option_price(call_strike, is_call=True)
        self._add_leg(call_symbol, 'BUY', 'CE', call_strike, 1, 'SAUSAGE_CALL_LONG', call_price)

        # 3. Sell Put ~ matching premium -> choose strike symmetrical below future
        put_strike = self._round_strike(self.initial_future - self.call_offset)
        put_symbol = self._opt_symbol(put_strike, 'PE')
        put_price = self._mock_option_price(put_strike, is_call=False)
        self._add_leg(put_symbol, 'SELL', 'PE', put_strike, 1, 'SAUSAGE_PUT_SHORT', put_price)

        # Bread Units distances
        D_sell = self.base_sell_5 if self.month_type == '5W' else self.base_sell_4
        # Calls
        sell_call_strike = self._round_strike(self.initial_spot + D_sell)
        buy_call_strike = self._round_strike(sell_call_strike + self.hedge_offset)
        sell_call_symbol = self._opt_symbol(sell_call_strike, 'CE')
        buy_call_symbol = self._opt_symbol(buy_call_strike, 'CE')
        self._add_leg(sell_call_symbol, 'SELL', 'CE', sell_call_strike, 2, 'BREAD_CALL_SHORT')
        self._add_leg(buy_call_symbol, 'BUY', 'CE', buy_call_strike, 2, 'BREAD_CALL_LONG')

        # Puts
        sell_put_strike = self._round_strike(self.initial_spot - D_sell)
        buy_put_strike = self._round_strike(sell_put_strike - self.hedge_offset)
        sell_put_symbol = self._opt_symbol(sell_put_strike, 'PE')
        buy_put_symbol = self._opt_symbol(buy_put_strike, 'PE')
        self._add_leg(sell_put_symbol, 'SELL', 'PE', sell_put_strike, 2, 'BREAD_PUT_SHORT')
        self._add_leg(buy_put_symbol, 'BUY', 'PE', buy_put_strike, 2, 'BREAD_PUT_LONG')

    def _firefight_stage1(self):
        self.logger.info("Entering Firefight Stage 1: Rolling core put + shifting bread puts")
        # Roll core short put upward
        core_puts = [l for l in self.legs if l.role == 'SAUSAGE_PUT_SHORT' and l.open]
        if core_puts:
            core = core_puts[0]
            target_level = self._round_strike(self.initial_future)
            # Choose candidate shift getting closest to target
            best_shift = None
            best_diff = 1e9
            for shift in self.core_put_roll_candidates:
                new_strike = core.strike + shift if core.strike else None
                if new_strike:
                    diff = abs(new_strike - target_level)
                    if diff < best_diff:
                        best_diff = diff
                        best_shift = shift
            if best_shift:
                # Close existing core put (mark open False) and add new
                core.open = False
                new_strike = core.strike + best_shift
                new_symbol = self._opt_symbol(new_strike, 'PE')
                self._add_leg(new_symbol, 'SELL', 'PE', new_strike, 1, 'SAUSAGE_PUT_SHORT')

        # Shift bread puts upward by base distance
        D_sell = self.base_sell_5 if self.month_type == '5W' else self.base_sell_4
        for leg in self.legs:
            if leg.role in ('BREAD_PUT_SHORT', 'BREAD_PUT_LONG') and leg.open:
                leg.open = False
        # Recreate bread puts shifted
        new_sell_put_strike = self._round_strike(self.initial_spot - (D_sell - D_sell))  # effectively spot (for upward shift approximation)
        # Real logic would use previous strikes + D_sell; simplified: move closer to spot by D_sell
        shifted_sell = self._round_strike(new_sell_put_strike + 0)  # placeholder
        shifted_buy = self._round_strike(shifted_sell - self.hedge_offset)
        self._add_leg(self._opt_symbol(shifted_sell, 'PE'), 'SELL', 'PE', shifted_sell, 2, 'BREAD_PUT_SHORT')
        self._add_leg(self._opt_symbol(shifted_buy, 'PE'), 'BUY', 'PE', shifted_buy, 2, 'BREAD_PUT_LONG')

        self.state = 'FIREFIGHT_STAGE1'
        self.last_adjustment_date = datetime.now().date()

    def _firefight_stage2(self):
        self.logger.info("Entering Firefight Stage 2: Additional +1000 shift on puts")
        # Close current bread puts and recreate + secondary shift
        for leg in self.legs:
            if leg.role in ('BREAD_PUT_SHORT', 'BREAD_PUT_LONG') and leg.open:
                leg.open = False
        # Determine current highest put short strike to shift from
        put_shorts_old = [l for l in self.legs if l.role == 'BREAD_PUT_SHORT']
        base_strike = max((l.strike or 0) for l in put_shorts_old) + self.secondary_put_shift
        new_sell = self._round_strike(base_strike)
        new_buy = self._round_strike(new_sell - self.hedge_offset)
        self._add_leg(self._opt_symbol(new_sell, 'PE'), 'SELL', 'PE', new_sell, 2, 'BREAD_PUT_SHORT')
        self._add_leg(self._opt_symbol(new_buy, 'PE'), 'BUY', 'PE', new_buy, 2, 'BREAD_PUT_LONG')
        self.state = 'FIREFIGHT_STAGE2'
        self.last_adjustment_date = datetime.now().date()

    def _convert_to_straddle(self, strike: int):
        self.logger.info(f"Converting to short straddle at strike {strike}")
        # Close all open bread puts
        for leg in self.legs:
            if leg.role in ('BREAD_PUT_SHORT', 'BREAD_PUT_LONG') and leg.open:
                leg.open = False
        # Add new sold puts at strike to match call sold strike
        self._add_leg(self._opt_symbol(strike, 'PE'), 'SELL', 'PE', strike, 2, 'BREAD_PUT_SHORT')
        self._add_leg(self._opt_symbol(strike - self.hedge_offset, 'PE'), 'BUY', 'PE', strike - self.hedge_offset, 2, 'BREAD_PUT_LONG')
        self.state = 'STRADDLE_FINAL'

    def _close_all(self, reason: str):
        for leg in self.legs:
            leg.open = False
        self.state = 'CLOSED'
        self.logger.info(f"All legs closed. Reason={reason} FinalPnL={self._portfolio_pnl()[0]:.2f}")

    # ---------------------------- Utility Methods ---------------------------- #
    def _add_leg(self, instrument: str, side: str, opt_type: str, strike: Optional[int], qty: int, role: str, price: Optional[float] = None):
        if price is None:
            price = self._mock_option_price(strike, is_call=(opt_type == 'CE')) if opt_type != 'FUT' else self.initial_future
        leg = Leg(instrument, side, opt_type, strike, qty, role, price, current_price=price)
        self.legs.append(leg)
        self.logger.info(f"ADD {side} {qty} {instrument} role={role} price={price}")

    def _portfolio_pnl(self) -> tuple[float, float]:
        total = sum(l.pnl() for l in self.legs if l.open)
        capital_ref = self.config['strategy'].get('capital', 1) or 1
        return total, (total / capital_ref) * 100

    def _update_prices(self):
        # Mock: update each open leg with slight drift
        for leg in self.legs:
            if not leg.open:
                continue
            if leg.type == 'FUT':
                leg.current_price = self.initial_future * 1.0  # static for now
            else:
                # simplistic decay / movement
                leg.current_price *= 0.99

    # Mock data utilities (replace with real market data integrations)
    def _get_mock_spot(self) -> float:
        # Could integrate a real spot feed; for now static placeholder
        return 45000.0

    def _get_mock_future(self, spot: float) -> float:
        # Add small positive carry
        return spot * 1.002

    def _mock_option_price(self, strike: Optional[int], is_call: bool) -> float:
        if strike is None:
            return 0.0
        # Very rough synthetic price model
        intrinsic = max(0, (self.initial_future - strike) if is_call else (strike - self.initial_future))
        time_value = 80
        return round(intrinsic + time_value, 2)

    def _round_strike(self, value: float) -> int:
        return int(round(value / 100) * 100)

    def _fut_symbol(self, expiry: date) -> str:
        return f"BANKNIFTY{expiry.strftime('%y%m%d')}FUT"

    def _opt_symbol(self, strike: int, opt_type: str) -> str:
        return f"BANKNIFTY{self.next_expiry.strftime('%y%m%d')}{strike}{opt_type}"

    @staticmethod
    def _time_near(current: time, target: time, tolerance_min: int = 5) -> bool:
        cur_minutes = current.hour * 60 + current.minute
        tgt_minutes = target.hour * 60 + target.minute
        return abs(cur_minutes - tgt_minutes) <= tolerance_min
