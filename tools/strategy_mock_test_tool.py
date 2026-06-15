from datetime import datetime, timedelta, timezone
import pandas as pd

from core import success_response, error_response

from mt5_liquidity_sweep_strategy import (
    _detect_sweep,
    _check_institutional_sr,
    _calculate_trade_levels,
    _check_consolidation,
    _spread_value
)


SYMBOL = "XAUUSD"


def _make_h1_base(
    base_price=100.0,
    candles=200,
    prior_low=100.0,
    prior_high=150.0
):
    """
    Membuat candle H1 mock yang stabil.
    24 candle sebelum candle terakhir berisi prior high/low.
    """
    now = datetime.now(timezone.utc).replace(minute=0, second=0, microsecond=0)
    rows = []

    start = now - timedelta(hours=candles)

    for i in range(candles):
        t = start + timedelta(hours=i)

        # default candle aman
        open_ = base_price + 10
        high = base_price + 12
        low = base_price + 8
        close = base_price + 10.5

        rows.append({
            "time": t,
            "open": open_,
            "high": high,
            "low": low,
            "close": close
        })

    df = pd.DataFrame(rows)

    # Buat prior 24H range jelas.
    # Fungsi _find_prior_24h_high_low membaca h1.iloc[-25:-1]
    for idx in range(candles - 25, candles - 1):
        df.loc[idx, "high"] = prior_high
        df.loc[idx, "low"] = prior_low
        df.loc[idx, "open"] = (prior_low + prior_high) / 2
        df.loc[idx, "close"] = (prior_low + prior_high) / 2

    for col in ["open", "high", "low", "close"]:
        df[col] = df[col].astype(float)

    return df


def _build_bullish_entry_df():
    """
    Bullish valid:
    - prior low = 100
    - candle terakhir sweep low ke 99.3
    - XAUUSD pip size 0.10 => sweep 7 pips
    - close balik di atas 100
    - long lower wick
    - round number 100 = valid institutional S&R
    """
    df = _make_h1_base(
        base_price=100,
        prior_low=100,
        prior_high=150
    )

    last = len(df) - 1

    df.loc[last, "open"] = 100.2
    df.loc[last, "high"] = 101.0
    df.loc[last, "low"] = 99.3
    df.loc[last, "close"] = 100.8

    return df


def _build_bearish_entry_df():
    """
    Bearish valid:
    - prior high = 150
    - candle terakhir sweep high ke 150.7
    - XAUUSD pip size 0.10 => sweep 7 pips
    - close balik di bawah 150
    - long upper wick
    - round number 150 = valid institutional S&R
    """
    df = _make_h1_base(
        base_price=100,
        prior_low=100,
        prior_high=150
    )

    last = len(df) - 1

    df.loc[last, "open"] = 149.8
    df.loc[last, "high"] = 150.7
    df.loc[last, "low"] = 149.0
    df.loc[last, "close"] = 149.2

    return df


def _build_no_sweep_df():
    df = _make_h1_base(
        base_price=100,
        prior_low=100,
        prior_high=150
    )

    last = len(df) - 1

    df.loc[last, "open"] = 120.0
    df.loc[last, "high"] = 121.0
    df.loc[last, "low"] = 119.0
    df.loc[last, "close"] = 120.5

    return df


def _build_invalid_rejection_df():
    """
    Ada sweep, tapi body candle terlalu besar / bukan rejection wick.
    """
    df = _make_h1_base(
        base_price=100,
        prior_low=100,
        prior_high=150
    )

    last = len(df) - 1

    df.loc[last, "open"] = 99.4
    df.loc[last, "high"] = 102.0
    df.loc[last, "low"] = 99.3
    df.loc[last, "close"] = 101.9

    return df


def _run_entry_pipeline(df):
    sweep = _detect_sweep(SYMBOL, df)

    if not sweep.get("has_sweep"):
        return {
            "verdict": "NO TRADE",
            "failed_at": "sweep",
            "sweep": sweep,
            "sr": None,
            "rr": None
        }

    sr = _check_institutional_sr(
        symbol=SYMBOL,
        h1=df,
        sweep_level=sweep.get("swept_level")
    )

    if not sr.get("valid"):
        return {
            "verdict": "NO TRADE",
            "failed_at": "sr",
            "sweep": sweep,
            "sr": sr,
            "rr": None
        }

    current_price = float(df["close"].iloc[-1])

    rr = _calculate_trade_levels(
        symbol=SYMBOL,
        direction=sweep.get("direction"),
        swept_level=sweep.get("swept_level"),
        current_price=current_price
    )

    if not rr.get("valid"):
        return {
            "verdict": "NO TRADE",
            "failed_at": "rr",
            "sweep": sweep,
            "sr": sr,
            "rr": rr
        }

    return {
        "verdict": "ENTRY",
        "failed_at": None,
        "sweep": sweep,
        "sr": sr,
        "rr": rr
    }


def _assert_equal(name, actual, expected, details=None):
    passed = actual == expected

    return {
        "name": name,
        "passed": passed,
        "expected": expected,
        "actual": actual,
        "details": details or {}
    }


def run_strategy_mock_tests():
    tool_name = "run_strategy_mock_tests"

    try:
        tests = []

        # 1. Bullish valid ENTRY
        bullish_df = _build_bullish_entry_df()
        bullish_result = _run_entry_pipeline(bullish_df)

        tests.append(
            _assert_equal(
                name="bullish_entry_should_pass",
                actual=bullish_result["verdict"],
                expected="ENTRY",
                details={
                    "direction": bullish_result["sweep"].get("direction"),
                    "sweep_pips": bullish_result["sweep"].get("sweep_pips"),
                    "sr_types": bullish_result["sr"].get("sr_types") if bullish_result["sr"] else None,
                    "rr": bullish_result["rr"].get("rr") if bullish_result["rr"] else None
                }
            )
        )

        # 2. Bearish valid ENTRY
        bearish_df = _build_bearish_entry_df()
        bearish_result = _run_entry_pipeline(bearish_df)

        tests.append(
            _assert_equal(
                name="bearish_entry_should_pass",
                actual=bearish_result["verdict"],
                expected="ENTRY",
                details={
                    "direction": bearish_result["sweep"].get("direction"),
                    "sweep_pips": bearish_result["sweep"].get("sweep_pips"),
                    "sr_types": bearish_result["sr"].get("sr_types") if bearish_result["sr"] else None,
                    "rr": bearish_result["rr"].get("rr") if bearish_result["rr"] else None
                }
            )
        )

        # 3. No sweep should fail
        no_sweep_df = _build_no_sweep_df()
        no_sweep_result = _run_entry_pipeline(no_sweep_df)

        tests.append(
            _assert_equal(
                name="no_sweep_should_fail",
                actual=no_sweep_result["verdict"],
                expected="NO TRADE",
                details={
                    "failed_at": no_sweep_result.get("failed_at"),
                    "reason": no_sweep_result["sweep"].get("reason_if_failed")
                }
            )
        )

        # 4. Invalid rejection candle should fail
        invalid_rejection_df = _build_invalid_rejection_df()
        invalid_rejection_result = _run_entry_pipeline(invalid_rejection_df)

        tests.append(
            _assert_equal(
                name="invalid_rejection_should_fail",
                actual=invalid_rejection_result["verdict"],
                expected="NO TRADE",
                details={
                    "failed_at": invalid_rejection_result.get("failed_at"),
                    "reason": invalid_rejection_result["sweep"].get("reason_if_failed"),
                    "wick_info": invalid_rejection_result["sweep"].get("wick_info")
                }
            )
        )

        # 5. Spread valid for XAUUSD
        tick_valid = {
            "spread_price": 0.28
        }

        spread_valid = _spread_value(SYMBOL, tick_valid)

        tests.append(
            _assert_equal(
                name="xauusd_spread_028_should_pass",
                actual=spread_valid["valid"],
                expected=True,
                details=spread_valid
            )
        )

        # 6. Spread too high for XAUUSD
        tick_high = {
            "spread_price": 0.35
        }

        spread_high = _spread_value(SYMBOL, tick_high)

        tests.append(
            _assert_equal(
                name="xauusd_spread_035_should_fail",
                actual=spread_high["valid"],
                expected=False,
                details=spread_high
            )
        )

        # 7. Consolidation check should fail if range < 20 pips
        consolidation_df = _make_h1_base(
            base_price=100,
            prior_low=100,
            prior_high=150
        )

        for idx in range(len(consolidation_df) - 8, len(consolidation_df)):
            consolidation_df.loc[idx, "high"] = 101.0
            consolidation_df.loc[idx, "low"] = 100.0
            consolidation_df.loc[idx, "open"] = 100.4
            consolidation_df.loc[idx, "close"] = 100.6

        consolidation = _check_consolidation(SYMBOL, consolidation_df)

        tests.append(
            _assert_equal(
                name="tight_consolidation_should_fail",
                actual=consolidation["is_tight"],
                expected=True,
                details=consolidation
            )
        )

        passed_count = sum(1 for t in tests if t["passed"])
        failed_count = len(tests) - passed_count

        lines = []
        lines.append("🧪 STRATEGY MOCK TEST REPORT")
        lines.append("")
        lines.append(f"Total tests: {len(tests)}")
        lines.append(f"Passed: {passed_count}")
        lines.append(f"Failed: {failed_count}")
        lines.append("")

        for test in tests:
            status = "PASS" if test["passed"] else "FAIL"
            lines.append(f"{status} - {test['name']}")
            lines.append(f"  expected: {test['expected']}")
            lines.append(f"  actual:   {test['actual']}")
            lines.append(f"  details:  {test['details']}")
            lines.append("")

        report = "\n".join(lines)

        return success_response(
            tool=tool_name,
            message="Strategy mock test selesai",
            extra={
                "total": len(tests),
                "passed": passed_count,
                "failed": failed_count,
                "tests": tests,
                "report": report
            }
        )

    except Exception as e:
        return error_response(tool_name, e)