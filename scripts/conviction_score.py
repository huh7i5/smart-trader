# -*- coding: utf-8 -*-
# -*- coding: utf-8 -*-

"""

Conviction Score 鈥?鎶?鎰熻"閲忓寲鎴?0-10 鍒?


鍒嗘暟鍐冲畾浠撲綅澶у皬锛?
  0-3 鍒嗭細涓嶄拱

  4-5 鍒嗭細灏忎拱锛?30-50锛?
  6-7 鍒嗭細鏍囧噯涔帮紙$80-100锛?
  8-10鍒嗭細鍔犵爜锛?120-150锛?


鍏釜鍥犲瓙锛屾瘡涓?0-10 鍒嗭紝鍔犳潈骞冲潎锛?
    # Cleaned comment
    # Cleaned comment
    # Cleaned comment
    # Cleaned comment
    # Cleaned comment
    # Cleaned comment
"""

import csv, sys, io, math, argparse, datetime

from pathlib import Path



sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")



ROOT_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT_DIR / "data"





from trader_runtime import create_exchange as create_public_exchange, load_config
from order_safety import SafetyError, validate_checklist



def create_exchange():
    return create_public_exchange(private=False)



def load_ohlcv(symbol="BTCUSDT"):

    """Fetch live daily OHLCV data from Binance API."""

    sym = symbol.upper()

    if "/" not in sym:

        # e.g. BTCUSDT -> BTC/USDT

        if sym.endswith("USDT"):

            sym = sym[:-4] + "/USDT"

        else:

            sym = sym + "/USDT"

            

    ex = create_exchange()

    try:

        # Fetch last 100 daily candles

        klines = ex.fetch_ohlcv(sym, timeframe="1d", limit=100)

        rows = []

        for k in klines:

            # timestamp is ms

            dt = datetime.datetime.fromtimestamp(k[0]/1000, datetime.timezone.utc).strftime("%Y-%m-%d")

            rows.append({

                "date": dt,

                "o": float(k[1]),

                "h": float(k[2]),

                "l": float(k[3]),

                "c": float(k[4]),

                "v": float(k[5]),

            })

        return rows

    except Exception as e:

        print(f"Error fetching live data for {sym}: {e}")

        return []





def sma(data, period, key="c"):

    """Simple moving average of last N periods."""

    if len(data) < period:

        return None

    return sum(d[key] for d in data[-period:]) / period





def score_drawdown(data, lookback=30):

    # Cleaned comment
    if len(data) < lookback:

        return 5.0, "data insufficient"

    recent_high = max(d["h"] for d in data[-lookback:])

    current = data[-1]["c"]

    dd_pct = (recent_high - current) / recent_high * 100



    # 娌¤穼 鈫?0鍒? 璺?% 鈫?4鍒? 璺?0% 鈫?7鍒? 璺?0%+ 鈫?10鍒?
    if dd_pct <= 1:

        score = 1.0

    elif dd_pct <= 3:

        score = 3.0

    elif dd_pct <= 5:

        score = 4.0

    elif dd_pct <= 10:

        score = 5.0 + (dd_pct - 5) * 0.4  # 5-7

    elif dd_pct <= 20:

        score = 7.0 + (dd_pct - 10) * 0.3  # 7-10

    else:

        score = 10.0



    return min(score, 10), f"drawdown {dd_pct:.1f}% from {lookback}d high"





def score_support(data):

    """Support score: distance from MA50"""
    ma50 = sma(data, 50)

    ma20 = sma(data, 20)

    if ma50 is None:

        return 5.0, "no MA50"

    current = data[-1]["c"]

    dist_pct = (current - ma50) / ma50 * 100



    # Distance from MA50
    if dist_pct > 10:

        score = 1.0

    elif dist_pct > 5:

        score = 3.0

    elif dist_pct > 0:

        score = 5.0

    elif dist_pct > -5:

        score = 7.0

    elif dist_pct > -10:

        score = 8.5

    else:

        score = 10.0



    pos = "above" if dist_pct > 0 else "below"

    return score, f"{abs(dist_pct):.1f}% {pos} MA50"





def score_trend(data):

    # Cleaned comment
    if len(data) < 7:

        return 5.0, "insufficient"

    week_change = (data[-1]["c"] - data[-7]["c"]) / data[-7]["c"] * 100



    if week_change < -10:

        score = 6.0  # 鏆磋穼锛屽彲鑳芥湁鏈轰細浣嗘湁椋庨櫓

    elif week_change < -5:

        score = 7.0  # 澶ц穼锛屾満浼氬紑濮嬪嚭鐜?
    elif week_change < -2:

        score = 8.0  # 娓╁拰涓嬭穼锛屽ソ鐨勪拱鍏ュ尯

    elif week_change < 0:

        score = 7.0  # 灏忚穼

    elif week_change < 3:

        score = 6.0  # 寰定锛屽仴搴疯秼鍔?
    elif week_change < 5:

        score = 4.0  # 娑ㄤ笉灏戜簡

    elif week_change < 8:

        score = 2.0  # 娑ㄥお澶氾紝灏忓績杩介珮

    else:

        score = 0.0  # 鏆存定锛岀粷瀵逛笉杩?


    return score, f"7d change {week_change:+.1f}%"





def score_volume(data):

    # Cleaned comment
    if len(data) < 14:

        return 5.0, "insufficient"



    # 鏈€杩?3 澶╃殑骞冲潎涔版柟鍔涢噺

    recent_buy_pressure = 0

    for d in data[-3:]:

        rng = d["h"] - d["l"]

        if rng > 0:

            recent_buy_pressure += (d["c"] - d["l"]) / rng

    recent_buy_pressure /= 3  # 0-1, >0.5 = 涔版柟涓诲



    # 鏈€杩?3 澶?vs 14 澶╁钩鍧囨垚浜ら噺

    recent_vol = sum(d["v"] for d in data[-3:]) / 3

    avg_vol = sum(d["v"] for d in data[-14:]) / 14

    vol_ratio = recent_vol / avg_vol if avg_vol > 0 else 1.0



    # 涔版柟涓诲 + 鏀鹃噺 = 楂樺垎

    # 鍗栨柟涓诲 + 缂╅噺 = 涓垎锛堝崠鏂硅€楀敖锛?
    # 鍗栨柟涓诲 + 鏀鹃噺 = 浣庡垎锛堟亹鎱屾姏鍞腑锛?
    if recent_buy_pressure > 0.6 and vol_ratio > 1.2:

        score = 9.0  # 鏀鹃噺涓婃敾

    elif recent_buy_pressure > 0.5:

        score = 7.0  # 涔版柟涓诲

    elif recent_buy_pressure < 0.4 and vol_ratio < 0.8:

        score = 6.0  # 缂╅噺涓嬭穼 = 鍗栫洏鑰楀敖锛堝弽杞俊鍙凤級

    elif recent_buy_pressure < 0.4 and vol_ratio > 1.5:

        score = 3.0  # 鏀鹃噺鏆磋穼锛岃繕娌′紒绋?
    else:

        score = 5.0  # 涓€?


    return score, f"buy_pressure={recent_buy_pressure:.2f}, vol_ratio={vol_ratio:.1f}x"





def score_volatility(data):

    # Cleaned comment
    if len(data) < 14:

        return 5.0, "insufficient"



    atr_14 = sum(d["h"] - d["l"] for d in data[-14:]) / 14

    today_range = data[-1]["h"] - data[-1]["l"]

    ratio = today_range / atr_14 if atr_14 > 0 else 1.0



    if ratio > 3.0:

        score = 1.0  # 鏋佺娉㈠姩锛屽埆纰?
    elif ratio > 2.0:

        score = 3.0  # 楂樻尝鍔?
    elif ratio > 1.5:

        score = 5.0  # 鍋忛珮

    elif ratio > 0.5:

        score = 8.0  # 姝ｅ父

    else:

        score = 6.0  # 鏋佷綆娉㈠姩锛堢洏鏁达級



    return score, f"today_range/ATR14={ratio:.1f}x"





def score_fear(data):

    # Cleaned comment
    if len(data) < 10:

        return 5.0, "insufficient"



    # 鏁版渶杩戣繛缁笅璺屽ぉ鏁?
    consecutive_down = 0

    for i in range(len(data) - 1, 0, -1):

        if data[i]["c"] < data[i - 1]["c"]:

            consecutive_down += 1

        else:

            break



    # 杩炶穼 0 澶?鈫?4鍒? 3澶?鈫?6鍒? 5澶?鈫?8鍒? 7澶? 鈫?10鍒?
    if consecutive_down <= 1:

        score = 4.0

    elif consecutive_down <= 3:

        score = 6.0

    elif consecutive_down <= 5:

        score = 8.0

    else:

        score = 10.0



    return score, f"{consecutive_down} consecutive down days"





def compute_conviction(symbol="BTCUSDT"):

    """璁＄畻缁煎悎淇″績璇勫垎"""

    data = load_ohlcv(symbol)

    if len(data) < 50:

        print(f"Not enough data for {symbol}")

        return None



    weights = {

        "drawdown":   0.10,

        "support":    0.05,

        "trend":      0.15,

        "volume":     0.00,

        "volatility": 0.70,

        "fear":       0.00,

    }



    factors = {}

    factors["drawdown"] = score_drawdown(data)

    factors["support"] = score_support(data)

    factors["trend"] = score_trend(data)

    factors["volume"] = score_volume(data)

    factors["volatility"] = score_volatility(data)

    factors["fear"] = score_fear(data)



    weighted_sum = 0

    for name, (score, _) in factors.items():

        weighted_sum += score * weights[name]



    total = weighted_sum



    # Position sizing

    if total >= 8.0:

        action = "STRONG BUY"

        size = "$120-150"

    elif total >= 6.0:

        action = "BUY"

        size = "$80-100"

    elif total >= 3.5:

        action = "SMALL BUY"

        size = "$30-50"

    else:

        action = "NO BUY"

        size = "$0"

    checklist_symbol = symbol[:-4] + "/USDT" if symbol.endswith("USDT") else symbol
    try:
        config = load_config()
        checklist = validate_checklist(
            checklist_symbol,
            max_age_minutes=float(config.get("checklist_ttl_minutes", 15)),
        )
        gate = f"PASS ({checklist['checked_at_utc']})"
    except (SafetyError, OSError, ValueError) as exc:
        gate = f"BLOCKED ({exc})"
        action = "BLOCKED - CHECKLIST REQUIRED"
        size = "$0"



    # Display

    labels = {

        "drawdown":   "Drawdown depth   ",

        "support":    "Support distance ",

        "trend":      "Weekly trend     ",

        "volume":     "Fund flow signal ",

        "volatility": "Volatility env   ",

        "fear":       "Fear level       ",

    }



    print(f"\n{'=' * 65}")

    print(f"  CONVICTION SCORE: {symbol}")

    print(f"  Date: {data[-1]['date']}  Price: ${data[-1]['c']:,.2f}")

    print(f"{'=' * 65}")



    for name in ["drawdown", "support", "trend", "volume", "volatility", "fear"]:

        score, detail = factors[name]

        w = weights[name]

        bar = "#" * int(score) + "." * (10 - int(score))

        print(f"  {labels[name]} [{bar}] {score:.1f}/10 (x{w:.0%})  {detail}")



    print(f"\n  {'=' * 50}")

    print(f"  TOTAL SCORE:  {total:.1f} / 10")

    print(f"  CHECKLIST:    {gate}")

    print(f"  ACTION:       {action}")

    print(f"  POSITION:     {size}")

    print(f"  {'=' * 50}")



    return total





if __name__ == "__main__":

    parser = argparse.ArgumentParser()

    parser.add_argument("symbols", nargs="*", default=["BTCUSDT"])

    args = parser.parse_args()



    for sym in args.symbols:

        sym = sym.upper()

        if not sym.endswith("USDT"):

            sym += "USDT"

        compute_conviction(sym)

