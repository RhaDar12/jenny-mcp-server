from datetime import datetime, timezone
import pandas as pd
import yfinance as yf

from core import success_response, error_response


SYMBOL_MAP = {
    "XAUUSD": "GC=F",
    "EURUSD": "EURUSD=X",
    "GBPUSD": "GBPUSD=X"
}


PIP_SIZE = {
    "XAUUSD": 0.1,      # 1 pip gold kira-kira 0.10 untuk scanner
    "EURUSD": 0.0001,
    "GBPUSD": 0.0001
}


def normalize_symbol(symbol):
    symbol = symbol.upper().strip()

    if symbol not in SYMBOL_MAP:
        raise ValueError(f"Symbol tidak didukung: {symbol}. Gunakan XAUUSD, EURUSD, atau GBPUSD.")

    return symbol, SYMBOL_MAP[symbol]


def get_pip_size(symbol):
    symbol = symbol.upper().strip()
    return PIP_SIZE.get(symbol, 0.0001)


def fetch_ohlc(symbol, interval="1h", period="7d"):
    """
    Mengambil data OHLC dari Yahoo Finance via yfinance.
    interval contoh: 15m, 1h
    period contoh: 5d, 7d, 30d
    """

    tool_name = "fetch_ohlc"

    try:
        clean_symbol, yf_symbol = normalize_symbol(symbol)

        df = yf.download(
            tickers=yf_symbol,
            interval=interval,
            period=period,
            progress=False,
            auto_adjust=False
        )

        if df is None or df.empty:
            raise RuntimeError(f"Data kosong dari yfinance untuk {clean_symbol} / {yf_symbol}")

        # Kalau multiindex, flatten
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = [col[0] for col in df.columns]

        df = df.reset_index()

        # Normalize datetime column
        datetime_col = None
        for col in ["Datetime", "Date"]:
            if col in df.columns:
                datetime_col = col
                break

        if datetime_col is None:
            raise RuntimeError("Kolom datetime tidak ditemukan dari hasil yfinance.")

        df = df.rename(columns={
            datetime_col: "time",
            "Open": "open",
            "High": "high",
            "Low": "low",
            "Close": "close",
            "Volume": "volume"
        })

        needed = ["time", "open", "high", "low", "close"]
        for col in needed:
            if col not in df.columns:
                raise RuntimeError(f"Kolom {col} tidak ditemukan pada data OHLC.")

        df = df[["time", "open", "high", "low", "close", "volume"] if "volume" in df.columns else needed]

        # Drop NaN
        df = df.dropna(subset=["open", "high", "low", "close"])

        # Convert time to string for JSON safety if needed later
        df["time"] = df["time"].astype(str)

        return success_response(
            tool=tool_name,
            message="Data OHLC berhasil diambil",
            extra={
                "symbol": clean_symbol,
                "yf_symbol": yf_symbol,
                "interval": interval,
                "period": period,
                "rows": len(df),
                "data": df.to_dict(orient="records")
            }
        )

    except Exception as e:
        return error_response(tool_name, e)


def fetch_market_bundle(symbol, primary_interval="5m"):
    """
    Mengambil bundle data M5 (primary) dan H1 (referensi level) untuk strategi.
    """
    tool_name = "fetch_market_bundle"

    try:
        primary = fetch_ohlc(symbol, interval=primary_interval, period="2d")
        h1 = fetch_ohlc(symbol, interval="1h", period="7d")

        if not primary.get("success"):
            raise RuntimeError(primary.get("error", f"Gagal mengambil {primary_interval}"))

        if not h1.get("success"):
            raise RuntimeError(h1.get("error", "Gagal mengambil H1"))

        return success_response(
            tool=tool_name,
            message=f"Bundle market berhasil diambil ({primary_interval})",
            extra={
                "symbol": symbol.upper().strip(),
                "fetched_at_utc": datetime.now(timezone.utc).isoformat(),
                "primary_interval": primary_interval,
                "primary": primary.get("data"),
                "h1": h1.get("data")
            }
        )

    except Exception as e:
        return error_response(tool_name, e)