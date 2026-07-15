"""
Conviction Score — 把"感觉"量化成 0-10 分

分数决定仓位大小：
  0-3 分：不买
  4-5 分：小买（$30-50）
  6-7 分：标准买（$80-100）
  8-10分：加码（$120-150）

六个因子，每个 0-10 分，加权平均：
  ① 回撤深度（从近期高点跌了多少）  权重 25%
  ② 支撑位距离（离关键均线多远）    权重 20%
  ③ 趋势方向（周线级别）            权重 15%
  ④ 资金流信号（买卖量比）          权重 20%
  ⑤ 波动率环境（是不是极端波动）    权重 10%
  ⑥ 恐慌程度（连续下跌天数）        权重 10%
"""
import csv, sys, io, math, argparse, datetime
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

DATA_DIR = Path(r"d:\money\spot_gems\data")


import ccxt
import json

CONFIG_PATH = Path(__file__).resolve().parent.parent / "new222" / "config.json"

def create_exchange():
    cfg = json.load(open(CONFIG_PATH))
    ex = ccxt.binance({
        "apiKey": cfg["api_key"],
        "secret": cfg["api_secret"],
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
    """① 回撤深度：从近期高点跌了多少？跌得多 = 分高（机会大）"""
    if len(data) < lookback:
        return 5.0, "data insufficient"
    recent_high = max(d["h"] for d in data[-lookback:])
    current = data[-1]["c"]
    dd_pct = (recent_high - current) / recent_high * 100

    # 没跌 → 0分, 跌5% → 4分, 跌10% → 7分, 跌20%+ → 10分
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
    """② 支撑位：当前价格相对于 50 日均线的位置。在均线下方 = 分高"""
    ma50 = sma(data, 50)
    ma20 = sma(data, 20)
    if ma50 is None:
        return 5.0, "no MA50"
    current = data[-1]["c"]
    dist_pct = (current - ma50) / ma50 * 100

    # 在 MA50 上方很远 → 低分, 刚好在 MA50 附近 → 中分, 在下方 → 高分
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
    """③ 周线趋势：7 天涨跌幅。微涨最好（上升趋势），暴涨则过热"""
    if len(data) < 7:
        return 5.0, "insufficient"
    week_change = (data[-1]["c"] - data[-7]["c"]) / data[-7]["c"] * 100

    if week_change < -10:
        score = 6.0  # 暴跌，可能有机会但有风险
    elif week_change < -5:
        score = 7.0  # 大跌，机会开始出现
    elif week_change < -2:
        score = 8.0  # 温和下跌，好的买入区
    elif week_change < 0:
        score = 7.0  # 小跌
    elif week_change < 3:
        score = 6.0  # 微涨，健康趋势
    elif week_change < 5:
        score = 4.0  # 涨不少了
    elif week_change < 8:
        score = 2.0  # 涨太多，小心追高
    else:
        score = 0.0  # 暴涨，绝对不追

    return score, f"7d change {week_change:+.1f}%"


def score_volume(data):
    """④ 资金流信号：最近 3 天的买卖压力（用 K 线估算）"""
    if len(data) < 14:
        return 5.0, "insufficient"

    # 最近 3 天的平均买方力量
    recent_buy_pressure = 0
    for d in data[-3:]:
        rng = d["h"] - d["l"]
        if rng > 0:
            recent_buy_pressure += (d["c"] - d["l"]) / rng
    recent_buy_pressure /= 3  # 0-1, >0.5 = 买方主导

    # 最近 3 天 vs 14 天平均成交量
    recent_vol = sum(d["v"] for d in data[-3:]) / 3
    avg_vol = sum(d["v"] for d in data[-14:]) / 14
    vol_ratio = recent_vol / avg_vol if avg_vol > 0 else 1.0

    # 买方主导 + 放量 = 高分
    # 卖方主导 + 缩量 = 中分（卖方耗尽）
    # 卖方主导 + 放量 = 低分（恐慌抛售中）
    if recent_buy_pressure > 0.6 and vol_ratio > 1.2:
        score = 9.0  # 放量上攻
    elif recent_buy_pressure > 0.5:
        score = 7.0  # 买方主导
    elif recent_buy_pressure < 0.4 and vol_ratio < 0.8:
        score = 6.0  # 缩量下跌 = 卖盘耗尽（反转信号）
    elif recent_buy_pressure < 0.4 and vol_ratio > 1.5:
        score = 3.0  # 放量暴跌，还没企稳
    else:
        score = 5.0  # 中性

    return score, f"buy_pressure={recent_buy_pressure:.2f}, vol_ratio={vol_ratio:.1f}x"


def score_volatility(data):
    """⑤ 波动率环境：极端波动时不宜开仓"""
    if len(data) < 14:
        return 5.0, "insufficient"

    atr_14 = sum(d["h"] - d["l"] for d in data[-14:]) / 14
    today_range = data[-1]["h"] - data[-1]["l"]
    ratio = today_range / atr_14 if atr_14 > 0 else 1.0

    if ratio > 3.0:
        score = 1.0  # 极端波动，别碰
    elif ratio > 2.0:
        score = 3.0  # 高波动
    elif ratio > 1.5:
        score = 5.0  # 偏高
    elif ratio > 0.5:
        score = 8.0  # 正常
    else:
        score = 6.0  # 极低波动（盘整）

    return score, f"today_range/ATR14={ratio:.1f}x"


def score_fear(data):
    """⑥ 恐慌程度：连续下跌天数越多，恐慌越深，机会越大"""
    if len(data) < 10:
        return 5.0, "insufficient"

    # 数最近连续下跌天数
    consecutive_down = 0
    for i in range(len(data) - 1, 0, -1):
        if data[i]["c"] < data[i - 1]["c"]:
            consecutive_down += 1
        else:
            break

    # 连跌 0 天 → 4分, 3天 → 6分, 5天 → 8分, 7天+ → 10分
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
    """计算综合信心评分"""
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
