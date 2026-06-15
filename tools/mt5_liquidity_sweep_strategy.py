from datetime import datetime, timezone
import math
import pandas as pd

from core import success_response, error_response
from mt5_data_tool import get_mt5_market_bundle, get_mt5_tick
from news_filter_tool import check_high_impact_news


ALLOWED_SYMBOLS = ["XAUUSD", "EURUSD", "GBPUSD"]

PIP_SIZE = {
    "XAUUSD": 0.10,      # Gold pip/cents logic: 0.10 = 10 cents
    "EURUSD": 0.0001,
    "GBPUSD": 0.0001
}

MAX_SPREAD = {
    "XAUUSD": 0.30,      # 30 cents
    "EURUSD": 2.0,       # 2 pips
    "GBPUSD": 2.0        # 2 pips
}


def _get_pip_size(symbol):
    return PIP_SIZE.get(symbol.upper(), 0.0001)


def _to_df(records):
    df = pd.DataFrame(records)

    if df.empty:
        raise ValueError("Data candle kosong.")

    for col in ["open", "high", "low", "close"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    df = df.dropna(subset=["open", "high", "low", "close"])
    df["time"] = pd.to_datetime(df["time"], errors="coerce", utc=True)
    df = df.dropna(subset=["time"])
    df = df.sort_values("time").reset_index(drop=True)

    return df


def _ema(series, period=200):
    return series.ewm(span=period, adjust=False).mean()


def _pip_distance(symbol, price_a, price_b):
    pip = _get_pip_size(symbol)
    return abs(float(price_a) - float(price_b)) / pip


def _current_gmt_hour():
    return datetime.now(timezone.utc).hour


def _is_allowed_session():
    hour = _current_gmt_hour()

    london_open = 8 <= hour < 17       # GMT 8-16
    ny_open = 13 <= hour < 22          # GMT 13-21
    london_ny_overlap = 12 <= hour < 16 # GMT 12-15
    asian_forbidden = hour >= 22 or hour < 6  # GMT 22-5

    return {
        "allowed": (london_open or ny_open) and not asian_forbidden,
        "hour_gmt": hour,
        "london_open": london_open,
        "ny_open": ny_open,
        "london_ny_overlap": london_ny_overlap,
        "asian_forbidden": asian_forbidden
    }


def _spread_value(symbol, tick_data):
    """
    Untuk XAUUSD:
    - pakai spread_price langsung, contoh 0.28 = 28 cents.

    Untuk EURUSD/GBPUSD:
    - ubah spread_price ke pips.
    """
    symbol = symbol.upper()

    spread_price = float(tick_data.get("spread_price", 0))

    if symbol == "XAUUSD":
        return {
            "spread_value": spread_price,
            "spread_unit": "price/cents",
            "max_allowed": MAX_SPREAD["XAUUSD"],
            "valid": spread_price <= MAX_SPREAD["XAUUSD"]
        }

    pip = _get_pip_size(symbol)
    spread_pips = spread_price / pip if pip else 999

    return {
        "spread_value": round(spread_pips, 2),
        "spread_unit": "pips",
        "max_allowed": MAX_SPREAD.get(symbol, 2.0),
        "valid": spread_pips <= MAX_SPREAD.get(symbol, 2.0)
    }


def _find_prior_24h_high_low(h1):
    if len(h1) < 25:
        raise ValueError("Data H1 kurang dari 25 candle untuk prior 24H high/low.")

    prior = h1.iloc[-25:-1]

    return {
        "prior_24h_high": float(prior["high"].max()),
        "prior_24h_low": float(prior["low"].min())
    }


def _is_rejection_candle(row, direction):
    high = float(row["high"])
    low = float(row["low"])
    open_ = float(row["open"])
    close = float(row["close"])

    candle_range = high - low

    if candle_range <= 0:
        return False, {
            "body_pct": None,
            "wick_ratio": None
        }

    body = abs(close - open_)
    body_pct = body / candle_range

    upper_wick = high - max(open_, close)
    lower_wick = min(open_, close) - low

    if direction == "bullish":
        wick_ratio = lower_wick / candle_range
        valid = lower_wick > body and body_pct <= 0.5
    else:
        wick_ratio = upper_wick / candle_range
        valid = upper_wick > body and body_pct <= 0.5

    return valid, {
        "body_pct": round(body_pct, 3),
        "wick_ratio": round(wick_ratio, 3)
    }


def _detect_sweep(symbol, h1):
    """
    Cek sweep pada 4 candle H1 terakhir.

    Bullish:
    - low candle melewati prior 24H low 5–10 pips
    - close balik di atas prior 24H low

    Bearish:
    - high candle melewati prior 24H high 5–10 pips
    - close balik di bawah prior 24H high
    """
    levels = _find_prior_24h_high_low(h1)
    prior_high = levels["prior_24h_high"]
    prior_low = levels["prior_24h_low"]

    last_candles = h1.iloc[-4:].copy()

    for _, row in last_candles.iterrows():
        low = float(row["low"])
        high = float(row["high"])
        close = float(row["close"])

        # Bullish sweep
        sweep_pips_low = _pip_distance(symbol, low, prior_low)

        if low < prior_low and 5 <= sweep_pips_low <= 10 and close > prior_low:
            rejection_valid, wick_info = _is_rejection_candle(row, "bullish")

            return {
                "has_sweep": bool(rejection_valid),
                "direction": "Long",
                "swept_level": prior_low,
                "sweep_price": low,
                "sweep_pips": round(sweep_pips_low, 2),
                "location": "prior 24H low",
                "candle_time": str(row["time"]),
                "rejection_valid": rejection_valid,
                "wick_info": wick_info,
                "reason_if_failed": None if rejection_valid else "Sweep candle is not a valid bullish rejection candle."
            }

        # Bearish sweep
        sweep_pips_high = _pip_distance(symbol, high, prior_high)

        if high > prior_high and 5 <= sweep_pips_high <= 10 and close < prior_high:
            rejection_valid, wick_info = _is_rejection_candle(row, "bearish")

            return {
                "has_sweep": bool(rejection_valid),
                "direction": "Short",
                "swept_level": prior_high,
                "sweep_price": high,
                "sweep_pips": round(sweep_pips_high, 2),
                "location": "prior 24H high",
                "candle_time": str(row["time"]),
                "rejection_valid": rejection_valid,
                "wick_info": wick_info,
                "reason_if_failed": None if rejection_valid else "Sweep candle is not a valid bearish rejection candle."
            }

    return {
        "has_sweep": False,
        "direction": None,
        "swept_level": None,
        "sweep_price": None,
        "sweep_pips": None,
        "location": None,
        "candle_time": None,
        "rejection_valid": False,
        "wick_info": None,
        "reason_if_failed": "No valid liquidity sweep in last 4 hours on H1."
    }


def _near_round_number(symbol, price, max_pips=15):
    symbol = symbol.upper()

    if symbol == "XAUUSD":
        candidates = [
            round(price / 50) * 50,
            round(price / 100) * 100,
            math.floor(price / 50) * 50,
            math.ceil(price / 50) * 50
        ]
    else:
        step = 0.005
        candidates = [
            round(price / step) * step,
            math.floor(price / step) * step,
            math.ceil(price / step) * step
        ]

    distances = [(_pip_distance(symbol, price, c), c) for c in candidates]
    distances.sort(key=lambda x: x[0])

    best_dist, best_level = distances[0]

    return best_dist <= max_pips, {
        "nearest_round": float(best_level),
        "distance_pips": round(best_dist, 2)
    }


def _horizontal_level_tested(h1, level, symbol, tolerance_pips=15, min_tests=3):
    tolerance = _get_pip_size(symbol) * tolerance_pips
    last_5_days = h1.iloc[-120:] if len(h1) >= 120 else h1

    tests = 0

    for _, row in last_5_days.iterrows():
        touched = (
            abs(float(row["high"]) - level) <= tolerance or
            abs(float(row["low"]) - level) <= tolerance
        )

        if touched:
            tests += 1

    return tests >= min_tests, tests


def _check_institutional_sr(symbol, h1, sweep_level):
    h1 = h1.copy()
    h1["ema200"] = _ema(h1["close"], 200)
    latest_ema200 = float(h1["ema200"].iloc[-1])

    ema_distance = _pip_distance(symbol, sweep_level, latest_ema200)
    near_ema = ema_distance <= 15

    horizontal_ok, horizontal_tests = _horizontal_level_tested(
        h1=h1,
        level=sweep_level,
        symbol=symbol,
        tolerance_pips=15,
        min_tests=3
    )

    round_ok, round_info = _near_round_number(symbol, sweep_level, max_pips=15)

    sr_types = []

    if near_ema:
        sr_types.append("200 EMA")

    if horizontal_ok:
        sr_types.append("horizontal level")

    if round_ok:
        sr_types.append("round number")

    return {
        "valid": len(sr_types) > 0,
        "sr_types": sr_types,
        "ema200": latest_ema200,
        "ema_distance_pips": round(ema_distance, 2),
        "horizontal_tests": horizontal_tests,
        "round_info": round_info
    }


def _check_consolidation(symbol, h1):
    last_8 = h1.iloc[-8:]

    if len(last_8) < 8:
        return {
            "is_tight": False,
            "range_pips": None
        }

    high = float(last_8["high"].max())
    low = float(last_8["low"].min())
    range_pips = _pip_distance(symbol, high, low)

    return {
        "is_tight": range_pips < 20,
        "range_pips": round(range_pips, 2)
    }


def _calculate_trade_levels(symbol, direction, swept_level, current_price):
    pip = _get_pip_size(symbol)

    # SL default 10 pips beyond swept level
    sl_pips = 10

    if direction == "Long":
        stop_loss = swept_level - (sl_pips * pip)
        entry = current_price
        risk = entry - stop_loss
        take_profit = entry + (risk * 3)
    else:
        stop_loss = swept_level + (sl_pips * pip)
        entry = current_price
        risk = stop_loss - entry
        take_profit = entry - (risk * 3)

    if risk <= 0:
        return {
            "valid": False,
            "reason": "Invalid risk calculation.",
            "entry": entry,
            "stop_loss": stop_loss,
            "take_profit": take_profit,
            "sl_pips": None,
            "tp_pips": None,
            "rr": None
        }

    sl_distance_pips = risk / pip
    tp_distance_pips = abs(take_profit - entry) / pip
    rr = tp_distance_pips / sl_distance_pips if sl_distance_pips else 0

    return {
        "valid": rr >= 3,
        "reason": None if rr >= 3 else "R:R < 1:3",
        "entry": float(entry),
        "stop_loss": float(stop_loss),
        "take_profit": float(take_profit),
        "sl_pips": round(sl_distance_pips, 2),
        "tp_pips": round(tp_distance_pips, 2),
        "rr": round(rr, 2)
    }


def _format_output(symbol, verdict, sweep, sr, rr, session, news_status, spread_check, reason=None):
    direction = sweep.get("direction") if sweep else None

    lines = []
    lines.append(f"VERDICT: {verdict}")
    lines.append("")
    lines.append(f"ASSET: {symbol}")
    lines.append("TIMEFRAME: H1")
    lines.append("")

    if sweep and sweep.get("has_sweep"):
        lines.append(f"SWEEP CHECK: Yes, {sweep.get('location')} swept by {sweep.get('sweep_pips')} pips")
    else:
        lines.append("SWEEP CHECK: No")

    if sr and sr.get("valid"):
        lines.append(f"S&R LEVEL: {', '.join(sr.get('sr_types', []))}")
    else:
        lines.append("S&R LEVEL: No valid institutional S&R")

    if rr and rr.get("rr"):
        lines.append(f"R:R CALCULATION: SL={rr.get('sl_pips')} pips, TP={rr.get('tp_pips')} pips → 1:{rr.get('rr')}")
    else:
        lines.append("R:R CALCULATION: Not valid")

    lines.append(f"NEWS CHECK: {news_status}")

    if spread_check:
        lines.append(
            f"SPREAD CHECK: {spread_check.get('spread_value')} {spread_check.get('spread_unit')} "
            f"/ max {spread_check.get('max_allowed')} "
            f"/ {'Valid' if spread_check.get('valid') else 'Too high'}"
        )
    else:
        lines.append("SPREAD CHECK: Not available")

    lines.append(f"SESSION CHECK: GMT hour {session.get('hour_gmt')} / {'Allowed' if session.get('allowed') else 'Not allowed'}")
    lines.append("")

    if verdict == "ENTRY":
        lines.append("TRADE SCENARIO:")
        lines.append(f"- Direction: {direction}")
        lines.append(f"- Entry zone: {rr.get('entry')}")
        lines.append(f"- Stop loss: {rr.get('stop_loss')}")
        lines.append(f"- Take profit: {rr.get('take_profit')}")
        lines.append("- Rationale: Liquidity sweep confirmed at valid institutional S&R with minimum 1:3 R:R.")
        lines.append("")
        lines.append(f"ALERT: Watch retest near swept level {sweep.get('swept_level')}")
    elif verdict == "EXIT":
        lines.append("EXIT REASON:")
        lines.append(f"- {reason or 'Exit rule triggered.'}")
    else:
        lines.append(f"REASON: {reason or 'One or more rules failed.'}")

    lines.append("")
    lines.append("I do not execute trades. User is responsible for order placement, position sizing, and brokerage conditions. Verify spreads and liquidity before entering.")

    return "\n".join(lines)


def analyze_liquidity_sweep_mt5(symbol):
    """
    MT5 Broker Mode:
    - Candle H1/M15 dari MT5 broker
    - Spread real broker dari bid/ask
    - News dari local economic calendar
    - Output strict ENTRY / NO TRADE / EXIT
    """
    tool_name = "analyze_liquidity_sweep_mt5"

    try:
        symbol = symbol.upper().strip()

        if symbol not in ALLOWED_SYMBOLS:
            raise ValueError(f"Symbol tidak didukung: {symbol}")

        bundle = get_mt5_market_bundle(symbol)

        if not bundle.get("success"):
            raise RuntimeError(bundle.get("error", "Gagal mengambil market bundle MT5."))

        tick_result = bundle.get("tick")

        if not tick_result or not tick_result.get("success"):
            raise RuntimeError("Tick MT5 tidak tersedia di bundle.")

        tick_data = tick_result
        h1 = _to_df(bundle.get("h1"))
        m15 = _to_df(bundle.get("m15"))

        session = _is_allowed_session()

        news = check_high_impact_news(symbol, window_minutes=30)

        if not news.get("success"):
            news_status = "News unavailable"
        else:
            news_status = news.get("news_status", "News unavailable")

        spread_check = _spread_value(symbol, tick_data)

        # Session filter
        if not session["allowed"]:
            output = _format_output(
                symbol=symbol,
                verdict="NO TRADE",
                sweep=None,
                sr=None,
                rr=None,
                session=session,
                news_status=news_status,
                spread_check=spread_check,
                reason="Current GMT time is outside allowed London/London-NY trading windows or inside forbidden Asian session."
            )

            return success_response(
                tool=tool_name,
                message="Analisis MT5 selesai",
                extra={
                    "verdict": "NO TRADE",
                    "symbol": symbol,
                    "output": output,
                    "session": session,
                    "spread_check": spread_check,
                    "news": news,
                    "data_source": "MT5"
                }
            )

        # News filter
        if news_status != "Clear":
            output = _format_output(
                symbol=symbol,
                verdict="NO TRADE",
                sweep=None,
                sr=None,
                rr=None,
                session=session,
                news_status=news_status,
                spread_check=spread_check,
                reason="High-impact news filter is not clear."
            )

            return success_response(
                tool=tool_name,
                message="Analisis MT5 selesai",
                extra={
                    "verdict": "NO TRADE",
                    "symbol": symbol,
                    "output": output,
                    "session": session,
                    "spread_check": spread_check,
                    "news": news,
                    "data_source": "MT5"
                }
            )

        # Spread filter
        if not spread_check["valid"]:
            output = _format_output(
                symbol=symbol,
                verdict="NO TRADE",
                sweep=None,
                sr=None,
                rr=None,
                session=session,
                news_status=news_status,
                spread_check=spread_check,
                reason="Spread is above strategy limit."
            )

            return success_response(
                tool=tool_name,
                message="Analisis MT5 selesai",
                extra={
                    "verdict": "NO TRADE",
                    "symbol": symbol,
                    "output": output,
                    "session": session,
                    "spread_check": spread_check,
                    "news": news,
                    "data_source": "MT5"
                }
            )

        consolidation = _check_consolidation(symbol, h1)

        if consolidation["is_tight"]:
            output = _format_output(
                symbol=symbol,
                verdict="NO TRADE",
                sweep=None,
                sr=None,
                rr=None,
                session=session,
                news_status=news_status,
                spread_check=spread_check,
                reason=f"Price is inside tight consolidation: H1 8-hour range is {consolidation['range_pips']} pips."
            )

            return success_response(
                tool=tool_name,
                message="Analisis MT5 selesai",
                extra={
                    "verdict": "NO TRADE",
                    "symbol": symbol,
                    "output": output,
                    "consolidation": consolidation,
                    "spread_check": spread_check,
                    "news": news,
                    "data_source": "MT5"
                }
            )

        sweep = _detect_sweep(symbol, h1)

        if not sweep["has_sweep"]:
            output = _format_output(
                symbol=symbol,
                verdict="NO TRADE",
                sweep=sweep,
                sr=None,
                rr=None,
                session=session,
                news_status=news_status,
                spread_check=spread_check,
                reason=sweep.get("reason_if_failed")
            )

            return success_response(
                tool=tool_name,
                message="Analisis MT5 selesai",
                extra={
                    "verdict": "NO TRADE",
                    "symbol": symbol,
                    "output": output,
                    "sweep": sweep,
                    "spread_check": spread_check,
                    "news": news,
                    "data_source": "MT5"
                }
            )

        sr = _check_institutional_sr(
            symbol=symbol,
            h1=h1,
            sweep_level=sweep["swept_level"]
        )

        if not sr["valid"]:
            output = _format_output(
                symbol=symbol,
                verdict="NO TRADE",
                sweep=sweep,
                sr=sr,
                rr=None,
                session=session,
                news_status=news_status,
                spread_check=spread_check,
                reason="Sweep did not occur within 15 pips of valid institutional S&R."
            )

            return success_response(
                tool=tool_name,
                message="Analisis MT5 selesai",
                extra={
                    "verdict": "NO TRADE",
                    "symbol": symbol,
                    "output": output,
                    "sweep": sweep,
                    "sr": sr,
                    "spread_check": spread_check,
                    "news": news,
                    "data_source": "MT5"
                }
            )

        current_price = float(h1["close"].iloc[-1])

        rr = _calculate_trade_levels(
            symbol=symbol,
            direction=sweep["direction"],
            swept_level=sweep["swept_level"],
            current_price=current_price
        )

        if not rr["valid"]:
            output = _format_output(
                symbol=symbol,
                verdict="NO TRADE",
                sweep=sweep,
                sr=sr,
                rr=rr,
                session=session,
                news_status=news_status,
                spread_check=spread_check,
                reason=rr.get("reason")
            )

            return success_response(
                tool=tool_name,
                message="Analisis MT5 selesai",
                extra={
                    "verdict": "NO TRADE",
                    "symbol": symbol,
                    "output": output,
                    "sweep": sweep,
                    "sr": sr,
                    "rr": rr,
                    "spread_check": spread_check,
                    "news": news,
                    "data_source": "MT5"
                }
            )

        output = _format_output(
            symbol=symbol,
            verdict="ENTRY",
            sweep=sweep,
            sr=sr,
            rr=rr,
            session=session,
            news_status=news_status,
            spread_check=spread_check,
            reason=None
        )

        return success_response(
            tool=tool_name,
            message="Analisis MT5 selesai",
            extra={
                "verdict": "ENTRY",
                "symbol": symbol,
                "output": output,
                "sweep": sweep,
                "sr": sr,
                "rr": rr,
                "session": session,
                "consolidation": consolidation,
                "spread_check": spread_check,
                "news": news,
                "data_source": "MT5",
                "mode": "MT5 Broker Scanner Mode"
            }
        )

    except Exception as e:
        return error_response(tool_name, e)