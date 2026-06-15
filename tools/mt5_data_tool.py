from datetime import datetime, timezone
from pathlib import Path

import MetaTrader5 as mt5
import pandas as pd

from core import success_response, error_response


SYMBOL_ALIASES = {
    "XAUUSD": ["XAUUSD", "XAUUSDm", "GOLD", "Gold", "XAUUSD."],
    "EURUSD": ["EURUSD", "EURUSDm", "EURUSD."],
    "GBPUSD": ["GBPUSD", "GBPUSDm", "GBPUSD."]
}


TIMEFRAME_MAP = {
    "M1": mt5.TIMEFRAME_M1,
    "M5": mt5.TIMEFRAME_M5,
    "M15": mt5.TIMEFRAME_M15,
    "M30": mt5.TIMEFRAME_M30,
    "H1": mt5.TIMEFRAME_H1,
    "H4": mt5.TIMEFRAME_H4,
    "D1": mt5.TIMEFRAME_D1
}


def initialize_mt5():
    if not mt5.initialize():
        raise RuntimeError(f"MT5 initialize failed: {mt5.last_error()}")

    account = mt5.account_info()

    if account is None:
        raise RuntimeError("MT5 belum login atau account_info tidak tersedia.")

    return account


def shutdown_mt5():
    try:
        mt5.shutdown()
    except Exception:
        pass


def resolve_symbol(symbol):
    symbol = symbol.upper().strip()

    candidates = SYMBOL_ALIASES.get(symbol, [symbol])

    all_symbols = mt5.symbols_get()

    if not all_symbols:
        raise RuntimeError("Tidak bisa membaca daftar symbol dari MT5.")

    available = {s.name: s for s in all_symbols}

    for candidate in candidates:
        if candidate in available:
            if not mt5.symbol_select(candidate, True):
                raise RuntimeError(f"Gagal select symbol MT5: {candidate}")

            return candidate

    # fallback: cari yang mengandung symbol utama
    for s in available.keys():
        if symbol in s.upper():
            if mt5.symbol_select(s, True):
                return s

    raise RuntimeError(f"Symbol {symbol} tidak ditemukan di MT5 broker.")


def get_mt5_tick(symbol):
    tool_name = "get_mt5_tick"

    try:
        account = initialize_mt5()
        mt5_symbol = resolve_symbol(symbol)

        tick = mt5.symbol_info_tick(mt5_symbol)
        info = mt5.symbol_info(mt5_symbol)

        if tick is None:
            raise RuntimeError(f"Tick tidak tersedia untuk {mt5_symbol}")

        if info is None:
            raise RuntimeError(f"Symbol info tidak tersedia untuk {mt5_symbol}")

        point = info.point
        spread_points = info.spread
        spread_price = spread_points * point

        result = success_response(
            tool=tool_name,
            message="Tick MT5 berhasil dibaca",
            extra={
                "requested_symbol": symbol.upper().strip(),
                "mt5_symbol": mt5_symbol,
                "bid": tick.bid,
                "ask": tick.ask,
                "last": tick.last,
                "point": point,
                "digits": info.digits,
                "spread_points": spread_points,
                "spread_price": spread_price,
                "account_login": account.login,
                "server": account.server,
                "checked_at_utc": datetime.now(timezone.utc).isoformat()
            }
        )

        return result

    except Exception as e:
        return error_response(tool_name, e)

    finally:
        shutdown_mt5()


def get_mt5_ohlc(symbol, timeframe="H1", bars=200):
    tool_name = "get_mt5_ohlc"

    try:
        initialize_mt5()

        mt5_symbol = resolve_symbol(symbol)
        timeframe = timeframe.upper().strip()

        if timeframe not in TIMEFRAME_MAP:
            raise ValueError(f"Timeframe tidak didukung: {timeframe}")

        rates = mt5.copy_rates_from_pos(
            mt5_symbol,
            TIMEFRAME_MAP[timeframe],
            0,
            int(bars)
        )

        if rates is None or len(rates) == 0:
            raise RuntimeError(f"Data candle kosong untuk {mt5_symbol} {timeframe}")

        df = pd.DataFrame(rates)
        df["time"] = pd.to_datetime(df["time"], unit="s", utc=True)

        data = []

        for _, row in df.iterrows():
            data.append({
                "time": str(row["time"]),
                "open": float(row["open"]),
                "high": float(row["high"]),
                "low": float(row["low"]),
                "close": float(row["close"]),
                "tick_volume": int(row["tick_volume"]),
                "spread": int(row["spread"]),
                "real_volume": int(row["real_volume"])
            })

        return success_response(
            tool=tool_name,
            message="Data OHLC MT5 berhasil dibaca",
            extra={
                "requested_symbol": symbol.upper().strip(),
                "mt5_symbol": mt5_symbol,
                "timeframe": timeframe,
                "bars": len(data),
                "data": data
            }
        )

    except Exception as e:
        return error_response(tool_name, e)

    finally:
        shutdown_mt5()


def get_mt5_market_bundle(symbol):
    tool_name = "get_mt5_market_bundle"

    try:
        tick = get_mt5_tick(symbol)

        if not tick.get("success"):
            raise RuntimeError(tick.get("error", "Gagal membaca tick MT5."))

        h1 = get_mt5_ohlc(symbol, "H1", 200)

        if not h1.get("success"):
            raise RuntimeError(h1.get("error", "Gagal membaca H1 MT5."))

        m15 = get_mt5_ohlc(symbol, "M15", 300)

        if not m15.get("success"):
            raise RuntimeError(m15.get("error", "Gagal membaca M15 MT5."))

        return success_response(
            tool=tool_name,
            message="Bundle market MT5 berhasil dibaca",
            extra={
                "symbol": symbol.upper().strip(),
                "tick": tick,
                "h1": h1.get("data"),
                "m15": m15.get("data"),
                "fetched_at_utc": datetime.now(timezone.utc).isoformat()
            }
        )

    except Exception as e:
        return error_response(tool_name, e)