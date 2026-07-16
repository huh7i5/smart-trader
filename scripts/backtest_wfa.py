# -*- coding: utf-8 -*-
"""
Backtest Script: Walk-Forward Analysis (WFA) of Sentiment & Momentum Integrated Models
======================================================================================
Out-of-Sample Period: 2022-12-25 to 2026-07-16
Training Window: 365 days (rolling)
Testing Window: 90 days (rolling)
Data Source: Binance Daily BTC/USDT OHLCV + Alternative.me Fear & Greed Index
"""

import sys
import io
import os
import json
import datetime
from pathlib import Path
import pandas as pd
import numpy as np
import requests
import ccxt

# Ensure stdout handles UTF-8 correctly
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

# Configuration paths
SCRATCH_DIR = Path("d:/money/scratch")
SCRATCH_DIR.mkdir(parents=True, exist_ok=True)
BTC_CACHE_FILE = SCRATCH_DIR / "btc_daily_candles_wfa.json"
FNG_CACHE_FILE = SCRATCH_DIR / "fng_daily_data_wfa.json"
CONFIG_PATH = Path("d:/money/new222/config.json")

def create_exchange():
    if CONFIG_PATH.exists():
        try:
            cfg = json.load(open(CONFIG_PATH))
            ex = ccxt.binance({
                "apiKey": cfg.get("api_key", ""),
                "secret": cfg.get("api_secret", ""),
                "enableRateLimit": True,
                "timeout": 30000,
                "options": {
                    "defaultType": "spot",
                    "adjustForTimeDifference": True,
                    "recvWindow": 60000,
                },
            })
            if cfg.get("proxy"):
                ex.proxies = {"http": cfg["proxy"], "https": cfg["proxy"]}
            return ex
        except Exception as e:
            print(f"Warning: Failed to initialize CCXT with config.json: {e}. Using default.")
    return ccxt.binance({"enableRateLimit": True})

def load_btc_data():
    """Load daily BTC/USDT data, using cache if available, otherwise fetch from Binance."""
    if BTC_CACHE_FILE.exists():
        print(f"Loading BTC data from cache: {BTC_CACHE_FILE}")
        with open(BTC_CACHE_FILE, "r", encoding="utf-8") as f:
            candles = json.load(f)
        return candles

    print("Fetching BTC data from Binance...")
    ex = create_exchange()
    symbol = "BTC/USDT"
    # Fetch since 2021-01-01 to allow warm-up for indicators (MA200, RSI, Bollinger Bands)
    start_dt = datetime.datetime(2021, 1, 1, tzinfo=datetime.timezone.utc)
    since = int(start_dt.timestamp() * 1000)
    
    all_candles = []
    while True:
        try:
            candles = ex.fetch_ohlcv(symbol, timeframe="1d", since=since, limit=1000)
            if not candles:
                break
            all_candles.extend(candles)
            since = candles[-1][0] + 1
            if len(candles) < 1000:
                break
        except Exception as e:
            print(f"Error fetching candles: {e}")
            break
            
    print(f"Total candles fetched: {len(all_candles)}")
    # Cache the data
    with open(BTC_CACHE_FILE, "w", encoding="utf-8") as f:
        json.dump(all_candles, f)
    print(f"Saved BTC candles to cache.")
    return all_candles

def load_fng_data():
    """Load historical Fear & Greed index data, using cache if available, otherwise fetch from alternative.me."""
    if FNG_CACHE_FILE.exists():
        print(f"Loading F&G data from cache: {FNG_CACHE_FILE}")
        with open(FNG_CACHE_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data

    print("Fetching Fear & Greed Index history...")
    url = "https://api.alternative.me/fng/?limit=3000"
    try:
        r = requests.get(url, timeout=15)
        data = r.json()["data"]
        # Cache the data
        with open(FNG_CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f)
        print(f"Saved F&G data to cache.")
        return data
    except Exception as e:
        print(f"Error fetching F&G data: {e}")
        return []

def calc_rsi(df, period=14):
    delta = df['close'].diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    
    # Wilder's smoothing
    avg_gain = gain.ewm(alpha=1/period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1/period, adjust=False).mean()
    
    rs = avg_gain / avg_loss
    rsi = 100 - (100 / (1 + rs))
    return rsi

def prepare_dataframe(candles, fng_raw):
    df = pd.DataFrame(candles, columns=["timestamp", "open", "high", "low", "close", "volume"])
    df['open'] = df['open'].astype(float)
    df['high'] = df['high'].astype(float)
    df['low'] = df['low'].astype(float)
    df['close'] = df['close'].astype(float)
    df['volume'] = df['volume'].astype(float)
    
    # Convert timestamp to date
    df['date'] = pd.to_datetime(df['timestamp'], unit='ms', utc=True).dt.date
    
    # Process F&G data
    fng_records = []
    for item in fng_raw:
        ts = int(item["timestamp"])
        val = int(item["value"])
        dt = datetime.datetime.fromtimestamp(ts, tz=datetime.timezone.utc).date()
        fng_records.append({"date": dt, "fng": val})
    fng_df = pd.DataFrame(fng_records)
    
    # Merge BTC and F&G
    df = pd.merge(df, fng_df, on="date", how="left")
    df['fng'] = df['fng'].fillna(50)  # Default neutral
    
    # ---- 3-Point Checklist: Smart Money Proxy ----
    df['trend_7d'] = df['close'].pct_change(7) * 100
    df['close_diff'] = df['close'].diff()
    df['up_vol'] = df.apply(lambda r: r['volume'] if r['close_diff'] > 0 else 0.0, axis=1)
    df['down_vol'] = df.apply(lambda r: r['volume'] if r['close_diff'] <= 0 else 0.0, axis=1)
    df['sum_up_vol_5d'] = df['up_vol'].rolling(window=5).sum()
    df['sum_down_vol_5d'] = df['down_vol'].rolling(window=5).sum()
    df['obv_ratio'] = df.apply(lambda r: r['sum_up_vol_5d'] / r['sum_down_vol_5d'] if r['sum_down_vol_5d'] > 0 else 999.0, axis=1)
    df['sm_passed'] = (df['trend_7d'] > 0) & (df['obv_ratio'] > 1.0)
    
    # ---- 3-Point Checklist: Retail Flow Proxy ----
    df['net_flow'] = df.apply(lambda r: r['volume'] * (2 * r['close'] - r['high'] - r['low']) / (r['high'] - r['low'] if r['high'] > r['low'] else 1.0) if r['high'] > r['low'] else 0.0, axis=1)
    df['change'] = (df['close'] - df['open']) / df['open'] * 100
    df['rt_passed'] = (df['net_flow'] > 0) | ((df['net_flow'] <= 0) & (df['change'] > -1.0))
    
    # ---- 3-Point Checklist: Macro Events Filter ----
    fomc_dates = [
        # 2022
        datetime.date(2022, 1, 26), datetime.date(2022, 3, 16), datetime.date(2022, 5, 4), datetime.date(2022, 6, 15),
        datetime.date(2022, 7, 27), datetime.date(2022, 9, 21), datetime.date(2022, 11, 2), datetime.date(2022, 12, 14),
        # 2023
        datetime.date(2023, 2, 1), datetime.date(2023, 3, 22), datetime.date(2023, 5, 3), datetime.date(2023, 6, 14),
        datetime.date(2023, 7, 26), datetime.date(2023, 9, 20), datetime.date(2023, 11, 1), datetime.date(2023, 12, 13),
        # 2024
        datetime.date(2024, 1, 31), datetime.date(2024, 3, 20), datetime.date(2024, 5, 1), datetime.date(2024, 6, 12),
        datetime.date(2024, 7, 31), datetime.date(2024, 9, 18), datetime.date(2024, 11, 7), datetime.date(2024, 12, 18),
        # 2025
        datetime.date(2025, 1, 29), datetime.date(2025, 3, 19), datetime.date(2025, 4, 30), datetime.date(2025, 6, 18),
        datetime.date(2025, 7, 30), datetime.date(2025, 9, 17), datetime.date(2025, 11, 5), datetime.date(2025, 12, 17),
        # 2026
        datetime.date(2026, 1, 28), datetime.date(2026, 3, 18), datetime.date(2026, 5, 6), datetime.date(2026, 6, 17),
        datetime.date(2026, 7, 29), datetime.date(2026, 9, 16), datetime.date(2026, 11, 5), datetime.date(2026, 12, 16)
    ]
    
    blocked_dates = set()
    for d in fomc_dates:
        for offset in [0, 1, 2]:
            blocked_dates.add(d - datetime.timedelta(days=offset))
            
    for year in [2021, 2022, 2023, 2024, 2025, 2026]:
        for month in range(1, 13):
            cpi_d = datetime.date(year, month, 12)
            for offset in [0, 1, 2]:
                blocked_dates.add(cpi_d - datetime.timedelta(days=offset))
                
    df['macro_passed'] = df['date'].apply(lambda d: d not in blocked_dates)
    
    # Combined Checklist Verdict
    df['checklist_passed'] = df['sm_passed'] & df['rt_passed'] & df['macro_passed']
    
    # ---- Indicators for Model 1 & 2 ----
    df['rsi_14'] = calc_rsi(df, 14)
    
    # ---- Indicators for Model 3 ----
    df['ma20'] = df['close'].rolling(window=20).mean()
    df['std20'] = df['close'].rolling(window=20).std()
    df['bb_lower'] = df['ma20'] - 2.0 * df['std20']
    df['bb_upper'] = df['ma20'] + 2.0 * df['std20']
    df['bbw'] = (df['bb_upper'] - df['bb_lower']) / df['ma20']
    
    df['bbw_prev'] = df['bbw'].shift(1)
    df['bbw_max_10d'] = df['bbw'].shift(1).rolling(window=10).max()
    df['vol_decline'] = (df['bbw'] < df['bbw_prev']) & (df['bbw'] <= 0.95 * df['bbw_max_10d'])
    
    df['prev_close'] = df['close'].shift(1)
    df['tr'] = df.apply(lambda r: max(r['high'] - r['low'], abs(r['high'] - r['prev_close']), abs(r['low'] - r['prev_close'])) if not pd.isna(r['prev_close']) else r['high'] - r['low'], axis=1)
    df['atr_14'] = df['tr'].ewm(alpha=1/14, adjust=False).mean()
    
    df['sigma_rel'] = df['atr_14'] / df['close']
    df['bar_sigma_rel'] = df['sigma_rel'].rolling(window=30).mean()
    
    return df

# -------------------------------------------------------------------------
# 3. Model Mathematical Modifiers and Helpers
# -------------------------------------------------------------------------

def f_fng(x, fng_low):
    if x <= fng_low:
        return 1.5 + (fng_low - x) * 0.025
    elif fng_low < x <= 35:
        return 1.0 + (35 - x) * (0.5 / (35 - fng_low)) if (35 - fng_low) > 0 else 1.0
    elif 35 < x <= 65:
        return 1.0
    elif 65 < x <= 80:
        return 0.5 + (80 - x) * (0.5 / 15)
    else:
        return 0.5

def f_rsi(y, rsi_low):
    if y <= rsi_low:
        return 1.5 + (rsi_low - y) * 0.025
    elif rsi_low < y <= 45:
        return 1.0 + (45 - y) * (0.5 / (45 - rsi_low)) if (45 - rsi_low) > 0 else 1.0
    elif 45 < y <= 60:
        return 1.0
    elif 60 < y <= 75:
        return 0.5 + (75 - y) * (0.5 / 15)
    else:
        return 0.5

def check_rsi_crossback(idx, df, rsi_cross_th):
    rsi = df['rsi_14'].values
    if idx < 11:
        return False
    crossback = (rsi[idx - 1] <= rsi_cross_th) and (rsi[idx] > rsi_cross_th)
    recent_oversold = any(rsi[j] < rsi_cross_th for j in range(idx - 10, idx))
    return crossback and recent_oversold

def check_bullish_divergence(idx, df):
    prices = df['close'].values
    rsi = df['rsi_14'].values
    if idx < 65:
        return False
        
    swing_lows = []
    # Search for local swing lows in range [idx-60, idx-5]
    for i in range(max(5, idx - 60), idx - 4):
        # A day i is a local swing low if it is the minimum in window [i-5, i+5]
        is_low = True
        for k in range(i - 5, i + 6):
            if prices[k] < prices[i]:
                is_low = False
                break
        if is_low:
            # Filter: corresponding RSI was oversold (RSI < 40)
            if rsi[i] < 40:
                swing_lows.append(i)
                
    if len(swing_lows) < 2:
        return False
        
    t1 = swing_lows[-2]
    t2 = swing_lows[-1]
    
    # Divergence checks
    cond_price = prices[t2] < prices[t1]
    cond_rsi = rsi[t2] > rsi[t1]
    cond_dist = 5 <= (t2 - t1) <= 35
    cond_recency = 0 <= (idx - t2) <= 5
    cond_confirm = (prices[idx] > prices[t2]) and (rsi[idx] > rsi[t2])
    
    return cond_price and cond_rsi and cond_dist and cond_recency and cond_confirm

# -------------------------------------------------------------------------
# 4. Simulation Engine
# -------------------------------------------------------------------------

def run_integrated_simulation(df, indices, fng_low, rsi_low, rsi_cross_th, initial_capital, base_amount, require_fng_m3=35, use_vol_decline=False, state=None):
    if state is None:
        cash = initial_capital
        btc = 0.0
        spent = 0.0
        buys = 0
        equity = []
    else:
        cash, btc, spent, buys, equity_old = state
        # Create a copy so we don't modify the old state's list in place if we are testing different parameters
        equity = list(equity_old)
        
    for idx in indices:
        close_t = df.loc[idx, 'close']
        low_t = df.loc[idx, 'low']
        fng_t = df.loc[idx, 'fng']
        rsi_t = df.loc[idx, 'rsi_14']
        checklist_passed = df.loc[idx, 'checklist_passed']
        
        m1_buy = 0.0
        m2_buy = 0.0
        m3_buy = 0.0
        
        if checklist_passed:
            # Model 1
            mult = max(0.5, min(3.0, f_fng(fng_t, fng_low) * f_rsi(rsi_t, rsi_low)))
            m1_buy = mult * base_amount
            
            # Model 2
            cond_a = check_rsi_crossback(idx, df, rsi_cross_th)
            cond_b = check_bullish_divergence(idx, df)
            if cond_a or cond_b:
                m2_buy = base_amount
                
            # Model 3
            pass_m3_fng = (fng_t <= require_fng_m3)
            pass_m3_bb = (low_t <= df.loc[idx, 'bb_lower'])
            pass_m3_vol = True
            if use_vol_decline:
                pass_m3_vol = df.loc[idx, 'vol_decline']
                
            if pass_m3_fng and pass_m3_bb and pass_m3_vol:
                vol_mult = df.loc[idx, 'bar_sigma_rel'] / df.loc[idx, 'sigma_rel'] if df.loc[idx, 'sigma_rel'] > 0 else 1.0
                vol_mult_final = max(0.5, min(3.0, vol_mult))
                m3_buy = vol_mult_final * base_amount
                
        buy_amount = m1_buy + m2_buy + m3_buy
        if buy_amount > 0:
            qty = buy_amount / close_t
            btc += qty
            spent += buy_amount
            cash -= buy_amount
            buys += 1
            
        equity.append(cash + btc * close_t)
        
    return cash, btc, spent, buys, equity

def grid_search_params(df, train_start_idx, train_end_idx):
    best_params = (20, 30, 30) # default fallback
    best_roi = -999999.0
    
    train_indices = list(range(train_start_idx, train_end_idx))
    
    for fng_low in [15, 20, 25]:
        for rsi_low in [25, 30, 35]:
            for rsi_cross_th in [25, 30, 35]:
                # In training, we simulate with fresh capital of 500,000
                cash, btc, spent, buys, equity = run_integrated_simulation(
                    df,
                    train_indices,
                    fng_low,
                    rsi_low,
                    rsi_cross_th,
                    initial_capital=500000.0,
                    base_amount=100.0,
                    require_fng_m3=35,
                    use_vol_decline=False
                )
                final_close = df.loc[train_end_idx - 1, 'close']
                final_value = btc * final_close
                net_pnl = final_value - spent
                roi = net_pnl / spent if spent > 0 else 0.0
                
                if roi > best_roi:
                    best_roi = roi
                    best_params = (fng_low, rsi_low, rsi_cross_th)
                    
    return best_params, best_roi

def calculate_metrics_dict(spent, btc, equity, final_close):
    avg_cost = spent / btc if btc > 0 else 0.0
    final_value = btc * final_close
    net_pnl = final_value - spent
    deployed_roi = (net_pnl / spent) * 100 if spent > 0 else 0.0
    
    eq = np.array(equity)
    peaks = np.maximum.accumulate(eq)
    drawdowns = (peaks - eq) / peaks
    max_dd = np.max(drawdowns) * 100 if len(drawdowns) > 0 else 0.0
    
    returns = np.diff(eq) / eq[:-1]
    if len(returns) == 0 or np.std(returns) == 0:
        sharpe = 0.0
    else:
        sharpe = np.mean(returns) / np.std(returns) * np.sqrt(365)
        
    return {
        "Total Invested": spent,
        "BTC Accumulated": btc,
        "Avg Cost": avg_cost,
        "Final Value": final_value,
        "Net P&L": net_pnl,
        "Deployed ROI": deployed_roi,
        "Max Drawdown": max_dd,
        "Sharpe Ratio": sharpe
    }

def main():
    print("=========================================================================")
    print("  WALK-FORWARD ANALYSIS (WFA) BACKTEST - INTEGRATED STRATEGY")
    print("=========================================================================")
    
    # 1. Load Data
    candles = load_btc_data()
    fng_raw = load_fng_data()
    
    # 2. Prepare DataFrame
    df = prepare_dataframe(candles, fng_raw)
    
    # Define backtest dates
    start_date = datetime.date(2022, 12, 25)
    end_date = datetime.date(2026, 7, 16)
    
    # Get index of start and end dates
    start_indices = df[df['date'] == start_date].index.tolist()
    end_indices = df[df['date'] == end_date].index.tolist()
    
    if not start_indices:
        print(f"Error: Start date {start_date} not found in dataset.")
        return
    if not end_indices:
        print(f"Error: End date {end_date} not found in dataset.")
        return
        
    start_idx = start_indices[0]
    end_idx = end_indices[0]
    
    print(f"Start index: {start_idx} | Date: {df.loc[start_idx, 'date']}")
    print(f"End index: {end_idx} | Date: {df.loc[end_idx, 'date']}")
    
    bt_indices = list(range(start_idx, end_idx + 1))
    print(f"Out-of-sample backtest period length: {len(bt_indices)} days.")
    
    # 3. Create WFA Windows (90-day testing size)
    test_windows = []
    i = 0
    while i < len(bt_indices):
        test_windows.append(bt_indices[i : i + 90])
        i += 90
        
    print(f"Created {len(test_windows)} rolling test windows.")
    
    # 4. WFA Simulation
    wfa_cash = 500000.0
    wfa_btc = 0.0
    wfa_spent = 0.0
    wfa_buys = 0
    wfa_equity = []
    wfa_state = (wfa_cash, wfa_btc, wfa_spent, wfa_buys, wfa_equity)
    
    print("\nStarting WFA optimization and execution loop...")
    for idx_w, W in enumerate(test_windows):
        t_start = W[0]
        t_end = W[-1]
        t_start_date = df.loc[t_start, 'date']
        t_end_date = df.loc[t_end, 'date']
        
        # Training Window: preceding 365 days
        train_start_idx = t_start - 365
        train_end_idx = t_start
        
        # Grid Search
        best_params, train_roi = grid_search_params(df, train_start_idx, train_end_idx)
        best_fng_low, best_rsi_low, best_rsi_cross_th = best_params
        
        print(f"Window {idx_w+1:02d}: Test {t_start_date} to {t_end_date} | Optimal Params: fng_low={best_fng_low}, rsi_low={best_rsi_low}, rsi_cross_th={best_rsi_cross_th} | Train ROI: {train_roi*100:.2f}%")
        
        # Run test window with optimal parameters
        wfa_state = run_integrated_simulation(
            df,
            W,
            best_fng_low,
            best_rsi_low,
            best_rsi_cross_th,
            initial_capital=500000.0,
            base_amount=100.0,
            require_fng_m3=35,
            use_vol_decline=False,
            state=wfa_state
        )
        
    wfa_cash, wfa_btc, wfa_spent, wfa_buys, wfa_equity = wfa_state
    
    # 5. Fixed In-Sample Optimized Strategy (Fixed parameters)
    print("\nRunning Fixed In-Sample Optimized Strategy...")
    fixed_cash, fixed_btc, fixed_spent, fixed_buys, fixed_equity = run_integrated_simulation(
        df,
        bt_indices,
        fng_low=15,
        rsi_low=25,
        rsi_cross_th=30,
        initial_capital=500000.0,
        base_amount=100.0,
        require_fng_m3=35,
        use_vol_decline=False
    )
    
    # 6. Naive Daily DCA (buy $100 every day)
    print("Running Naive Daily DCA...")
    daily_cash = 500000.0
    daily_btc = 0.0
    daily_spent = 0.0
    daily_equity = []
    for idx in bt_indices:
        close_t = df.loc[idx, 'close']
        buy_amt = 100.0
        daily_btc += buy_amt / close_t
        daily_spent += buy_amt
        daily_cash -= buy_amt
        daily_equity.append(daily_cash + daily_btc * close_t)
        
    # 7. Naive Weekly DCA (buy $700 every 7 days)
    print("Running Naive Weekly DCA...")
    weekly_cash = 500000.0
    weekly_btc = 0.0
    weekly_spent = 0.0
    weekly_equity = []
    for i, idx in enumerate(bt_indices):
        close_t = df.loc[idx, 'close']
        if i % 7 == 0:
            buy_amt = 700.0
            weekly_btc += buy_amt / close_t
            weekly_spent += buy_amt
            weekly_cash -= buy_amt
        weekly_equity.append(weekly_cash + weekly_btc * close_t)
        
    # 8. Metrics Calculations
    final_close = df.loc[end_idx, 'close']
    wfa_metrics = calculate_metrics_dict(wfa_spent, wfa_btc, wfa_equity, final_close)
    fixed_metrics = calculate_metrics_dict(fixed_spent, fixed_btc, fixed_equity, final_close)
    daily_metrics = calculate_metrics_dict(daily_spent, daily_btc, daily_equity, final_close)
    weekly_metrics = calculate_metrics_dict(weekly_spent, weekly_btc, weekly_equity, final_close)
    
    # 9. Print Results
    results = [
        ("WFA Integrated Strategy", wfa_metrics),
        ("Fixed In-Sample Optimized", fixed_metrics),
        ("Naive Daily DCA", daily_metrics),
        ("Naive Weekly DCA", weekly_metrics)
    ]
    
    print("\n" + "="*90)
    print(f"{'Strategy Name':<28} | {'Invested':<12} | {'BTC Accum':<10} | {'Avg Cost':<10} | {'Final Value':<12} | {'ROI':>8} | {'Max DD':>7} | {'Sharpe':>6}")
    print("-"*99)
    for name, m in results:
        print(f"{name:<28} | ${m['Total Invested']:>10,.2f} | {m['BTC Accumulated']:>9.4f} | ${m['Avg Cost']:>8,.2f} | ${m['Final Value']:>10,.2f} | {m['Deployed ROI']:>7.2f}% | {m['Max Drawdown']:>6.2f}% | {m['Sharpe Ratio']:>6.2f}")
    print("="*90)
    
    # Save output to file
    out_file = Path("C:/Users/menger/.gemini/antigravity/brain/2c2583a9-b347-4628-9fe2-3c2451151d84/scratch/wfa_results.txt")
    out_file.parent.mkdir(parents=True, exist_ok=True)
    
    with open(out_file, "w", encoding="utf-8") as f:
        f.write("=========================================================================\n")
        f.write("  WALK-FORWARD ANALYSIS (WFA) BACKTEST RESULTS\n")
        f.write("=========================================================================\n")
        f.write(f"Backtest Period: {start_date} to {end_date}\n\n")
        
        f.write("WFA Window Optimizations:\n")
        for idx_w, W in enumerate(test_windows):
            t_start = W[0]
            t_start_date = df.loc[t_start, 'date']
            t_end_date = df.loc[W[-1], 'date']
            train_start_idx = t_start - 365
            best_params, train_roi = grid_search_params(df, train_start_idx, t_start)
            f.write(f"Window {idx_w+1:02d}: Test {t_start_date} to {t_end_date} | Optimal Params: fng_low={best_params[0]}, rsi_low={best_params[1]}, rsi_cross_th={best_params[2]} | Train ROI: {train_roi*100:.2f}%\n")
            
        f.write("\n" + "="*90 + "\n")
        f.write(f"{'Strategy Name':<28} | {'Invested':<12} | {'BTC Accum':<10} | {'Avg Cost':<10} | {'Final Value':<12} | {'ROI':>8} | {'Max DD':>7} | {'Sharpe':>6}\n")
        f.write("-"*99 + "\n")
        for name, m in results:
            f.write(f"{name:<28} | ${m['Total Invested']:>10,.2f} | {m['BTC Accumulated']:>9.4f} | ${m['Avg Cost']:>8,.2f} | ${m['Final Value']:>10,.2f} | {m['Deployed ROI']:>7.2f}% | {m['Max Drawdown']:>6.2f}% | {m['Sharpe Ratio']:>6.2f}\n")
        f.write("="*90 + "\n")
        
    print(f"\nResults successfully written to {out_file}")

if __name__ == "__main__":
    main()
