import requests
import pandas as pd
import numpy as np
import datetime
import sys
import io

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

def fetch_yahoo_data(ticker: str, range_str: str = "5y") -> pd.DataFrame:
    """Fetches historical daily chart data from Yahoo Finance API"""
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.3'
    }
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{ticker}?interval=1d&range={range_str}"
    
    # Use proxy if configured in our config.json
    try:
        import json
        cfg = json.load(open(r"d:\money\new222\config.json"))
        proxies = {"http": cfg.get("proxy", ""), "https": cfg.get("proxy", "")} if cfg.get("proxy") else None
    except Exception:
        proxies = None

    response = requests.get(url, headers=headers, proxies=proxies, timeout=15)
    data = response.json()
    
    chart = data['chart']['result'][0]
    timestamps = chart['timestamp']
    indicators = chart['indicators']['quote'][0]
    close_prices = indicators['close']
    
    df = pd.DataFrame({
        'timestamp': pd.to_datetime(timestamps, unit='s'),
        'close': close_prices
    })
    # Drop rows with missing close price
    df = df.dropna(subset=['close']).reset_index(drop=True)
    return df

def run_dca_simulation(df: pd.DataFrame, dca_amount: float, years: float) -> dict:
    """Simulates a weekly DCA of dca_amount over the last X years"""
    # Filter data for the last X years
    end_date = df['timestamp'].max()
    start_date = end_date - datetime.timedelta(days=int(years * 365.25))
    
    sub_df = df[df['timestamp'] >= start_date].copy().sort_values('timestamp').reset_index(drop=True)
    
    if sub_df.empty:
        return {}
        
    # Group by week and take the first trading day of the week
    sub_df['week_id'] = sub_df['timestamp'].dt.to_period('W')
    dca_days = sub_df.groupby('week_id').first().reset_index()
    
    total_invested = 0.0
    accumulated_assets = 0.0
    portfolio_values = []
    dates = []
    
    # Maintain a mapping of daily prices to calculate daily portfolio values (for drawdown)
    # Reindex daily prices
    sub_df.set_index('timestamp', inplace=True)
    
    # We will iterate day by day to simulate DCA and track portfolio value
    current_asset = 0.0
    current_invested = 0.0
    
    # Find DCA timestamps
    dca_dates = set(dca_days['timestamp'])
    
    for date, row in sub_df.iterrows():
        price = row['close']
        if date in dca_dates:
            current_invested += dca_amount
            current_asset += dca_amount / price
            
        current_value = current_asset * price
        portfolio_values.append(current_value)
        dates.append(date)
        
    p_series = pd.Series(portfolio_values, index=dates)
    
    # Calculate Max Drawdown of the portfolio value relative to cumulative investment
    cum_invested = []
    inv_val = 0.0
    for date in dates:
        if date in dca_dates:
            inv_val += dca_amount
        cum_invested.append(inv_val)
    cum_invested = np.array(cum_invested)
    
    # Peak value minus current value, normalized by peak value
    peak = p_series.cummax()
    # Drawdown of portfolio value relative to peak portfolio value
    drawdowns = (p_series - peak) / peak
    max_dd = abs(drawdowns.min()) if len(drawdowns) > 0 else 0.0
    
    final_price = sub_df.iloc[-1]['close']
    final_value = current_asset * final_price
    net_profit = final_value - current_invested
    roi = (net_profit / current_invested) * 100 if current_invested > 0 else 0.0
    avg_cost = current_invested / current_asset if current_asset > 0 else 0.0
    
    return {
        'total_invested': current_invested,
        'accumulated': current_asset,
        'final_value': final_value,
        'avg_cost': avg_cost,
        'final_price': final_price,
        'roi': roi,
        'max_dd': max_dd,
        'buys_count': len(dca_dates)
    }

def main():
    tickers = {
        'BTC-USD': 'Bitcoin (BTC)',
        'QQQ': 'Nasdaq 100 (QQQ)',
        'TSM': 'TSMC (TSM)'
    }
    
    print("Fetching historical data from Yahoo Finance...")
    dfs = {}
    for ticker, name in tickers.items():
        try:
            dfs[ticker] = fetch_yahoo_data(ticker, "5y")
            print(f"  Successfully fetched {name} ({len(dfs[ticker])} data points)")
        except Exception as e:
            print(f"  Error fetching {ticker}: {e}")
            return
            
    dca_amount = 100.0 # $100 per week
    
    for period in [3.0, 5.0]:
        print(f"\n=========================================================================")
        print(f"  DCA BACKTEST SIMULATION: LAST {int(period)} YEARS | Weekly Buy: ${dca_amount:.2f}")
        print(f"=========================================================================")
        print(f"{'Asset':<15} | {'Invested':<11} | {'Avg Cost':<10} | {'Final Price':<11} | {'Final Value':<11} | {'ROI (%)':<8} | {'Max DD':<7} | {'Buys'}")
        print("-" * 95)
        for ticker, name in tickers.items():
            res = run_dca_simulation(dfs[ticker], dca_amount, period)
            if not res:
                print(f"{name:<15} | No data")
                continue
            print(f"{name:<15} | ${res['total_invested']:10.2f} | ${res['avg_cost']:9.2f} | ${res['final_price']:10.2f} | ${res['final_value']:10.2f} | {res['roi']:+7.2f}% | {res['max_dd']*100:5.2f}% | {res['buys_count']}")
            
if __name__ == "__main__":
    main()
