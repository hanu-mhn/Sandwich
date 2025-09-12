import logging
from datetime import datetime, timedelta, date, time
from src.strategy.sandwich_strategy import SandwichStrategy
from src.utils.expiry_calculator import ExpiryCalculator
from src.market_data.data_provider import MarketDataProvider

"""Simple Sandwich strategy backtester using daily CSV spot approximation.

Assumptions:
 - Uses daily close as reference for monitoring steps.
 - Entry on each monthly expiry (force=True to allow arbitrary historical test windows).
 - PnL evolution still relies on internal mock option decay (CSV option pricing integration is pending full chain schema).
"""

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')

CONFIG = {
    'broker': {'name': 'mock'},
    'market_data': {
        'primary_source': 'csv',
        'backup_source': 'mock'
    },
    'strategy': {
        'capital': 1_000_000
    },
    'sandwich': {
        'profit_target_pct': 0.12,
    }
}

def iterate_months(start: date, end: date):
    cur = start
    while cur <= end:
        yield cur
        # jump to next month 1st
        if cur.month == 12:
            cur = date(cur.year+1, 1, 1)
        else:
            cur = date(cur.year, cur.month+1, 1)


def main():
    md = MarketDataProvider(CONFIG['market_data'])
    exp_calc = ExpiryCalculator()

    start_date = date.today().replace(year=date.today().year-1, day=1, month=1)
    end_date = date.today()

    results = []
    for month_start in iterate_months(start_date, end_date):
        cur_exp = exp_calc.get_monthly_expiry_date(month_start.year, month_start.month)
        if cur_exp < start_date or cur_exp > end_date:
            continue
        # Determine next expiry for context
        nm = cur_exp.month + 1
        ny = cur_exp.year
        if nm > 12:
            nm = 1
            ny += 1
        next_exp = exp_calc.get_monthly_expiry_date(ny, nm)

        strat = SandwichStrategy(CONFIG, dry_run=True, market_data=md)
        # Approx spot from CSV (if available)
        spot = md.get_spot(datetime.combine(cur_exp, time(15,0))) or 45000.0
        fut = spot * 1.002
        entered = strat.execute_entry(force=True, spot_override=spot, future_override=fut, current_expiry=cur_exp, next_expiry=next_exp)
        if not entered:
            continue
        # Simulate daily monitoring until next_exp
        d = cur_exp + timedelta(days=1)
        while d <= next_exp:
            # Simulate end-of-day monitor call
            strat.monitor()
            if strat.state == 'CLOSED':
                break
            d += timedelta(days=1)
        metrics = strat.get_metrics()
        results.append({
            'entry_expiry': cur_exp,
            'next_expiry': next_exp,
            'final_state': metrics['state'],
            'total_pnl': metrics['total_pnl'],
            'pnl_pct_capital': metrics['pnl_pct_capital']
        })

    wins = sum(1 for r in results if r['total_pnl'] > 0)
    total = len(results)
    avg_pnl = sum(r['total_pnl'] for r in results)/total if total else 0
    print('Backtest Completed: months=', total)
    print('Win Rate:', f"{wins/total*100:.1f}%" if total else 'N/A')
    print('Avg PnL:', round(avg_pnl,2))

if __name__ == '__main__':
    main()
