from core import success_response, error_response
from mt5_data_tool import get_mt5_market_bundle
from news_filter_tool import check_high_impact_news

from mt5_liquidity_sweep_strategy import (
    ALLOWED_SYMBOLS,
    _to_df,
    _is_allowed_session,
    _spread_value,
    _check_consolidation,
    _detect_sweep,
    _check_institutional_sr,
    _calculate_trade_levels,
    _find_prior_24h_high_low,
    _pip_distance
)


def _pass_fail(value):
    return "PASS" if value else "FAIL"


def _safe(value, default="-"):
    return value if value is not None else default


def build_mt5_debug_report(symbol):
    """
    Debug report untuk memastikan strategi Liquidity Sweep berjalan benar.
    Tidak mengirim alert dan tidak eksekusi trade.
    """

    tool_name = "build_mt5_debug_report"

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
        news_status = news.get("news_status", "News unavailable") if news.get("success") else "News unavailable"
        spread_check = _spread_value(symbol, tick_data)
        consolidation = _check_consolidation(symbol, h1)

        prior_levels = None
        sweep = None
        sr = None
        rr = None

        try:
            prior_levels = _find_prior_24h_high_low(h1)
        except Exception as e:
            prior_levels = {
                "error": str(e)
            }

        try:
            sweep = _detect_sweep(symbol, h1)
        except Exception as e:
            sweep = {
                "has_sweep": False,
                "reason_if_failed": f"Sweep detection error: {e}"
            }

        if sweep and sweep.get("has_sweep"):
            try:
                sr = _check_institutional_sr(
                    symbol=symbol,
                    h1=h1,
                    sweep_level=sweep.get("swept_level")
                )
            except Exception as e:
                sr = {
                    "valid": False,
                    "error": str(e)
                }

            try:
                current_price = float(h1["close"].iloc[-1])
                rr = _calculate_trade_levels(
                    symbol=symbol,
                    direction=sweep.get("direction"),
                    swept_level=sweep.get("swept_level"),
                    current_price=current_price
                )
            except Exception as e:
                rr = {
                    "valid": False,
                    "reason": f"RR calculation error: {e}"
                }

        checks = {
            "session": bool(session.get("allowed")),
            "news": news_status == "Clear",
            "spread": bool(spread_check.get("valid")),
            "consolidation": not bool(consolidation.get("is_tight")),
            "sweep": bool(sweep and sweep.get("has_sweep")),
            "sr": bool(sr and sr.get("valid")),
            "rr": bool(rr and rr.get("valid"))
        }

        # Final verdict debug
        if not checks["session"]:
            verdict = "NO TRADE"
            final_reason = "Session filter failed."
        elif not checks["news"]:
            verdict = "NO TRADE"
            final_reason = "News filter failed."
        elif not checks["spread"]:
            verdict = "NO TRADE"
            final_reason = "Spread filter failed."
        elif not checks["consolidation"]:
            verdict = "NO TRADE"
            final_reason = "Tight consolidation filter failed."
        elif not checks["sweep"]:
            verdict = "NO TRADE"
            final_reason = sweep.get("reason_if_failed") if sweep else "No valid sweep."
        elif not checks["sr"]:
            verdict = "NO TRADE"
            final_reason = "Institutional S&R filter failed."
        elif not checks["rr"]:
            verdict = "NO TRADE"
            final_reason = rr.get("reason") if rr else "R:R filter failed."
        else:
            verdict = "ENTRY"
            final_reason = "All strategy rules passed."

        latest = h1.iloc[-1]
        last_4 = h1.iloc[-4:]

        # Tambahan info sweep distance untuk debug
        sweep_debug_lines = []

        if prior_levels and "error" not in prior_levels:
            prior_high = prior_levels.get("prior_24h_high")
            prior_low = prior_levels.get("prior_24h_low")

            lowest_4h = float(last_4["low"].min())
            highest_4h = float(last_4["high"].max())

            low_sweep_distance = _pip_distance(symbol, lowest_4h, prior_low)
            high_sweep_distance = _pip_distance(symbol, highest_4h, prior_high)

            sweep_debug_lines.append(f"- Prior 24H High: {prior_high}")
            sweep_debug_lines.append(f"- Prior 24H Low: {prior_low}")
            sweep_debug_lines.append(f"- Lowest last 4H: {lowest_4h}")
            sweep_debug_lines.append(f"- Highest last 4H: {highest_4h}")
            sweep_debug_lines.append(f"- Distance lowest 4H to prior low: {round(low_sweep_distance, 2)} pips")
            sweep_debug_lines.append(f"- Distance highest 4H to prior high: {round(high_sweep_distance, 2)} pips")
            sweep_debug_lines.append("- Required sweep distance: 5–10 pips")
        else:
            sweep_debug_lines.append(f"- Prior level error: {prior_levels.get('error') if prior_levels else 'Unknown'}")

        report_lines = []
        report_lines.append("*MT5 STRATEGY DEBUG REPORT*")
        report_lines.append("")
        report_lines.append(f"ASSET: {symbol}")
        report_lines.append("STRATEGY: Liquidity Sweep + 1:3 R:R")
        report_lines.append("DATA SOURCE: MetaTrader 5 broker data")
        report_lines.append("")
        report_lines.append("━━━━━━━━━━━━━━")
        report_lines.append("[1] SESSION CHECK")
        report_lines.append(f"Status: {_pass_fail(checks['session'])}")
        report_lines.append(f"- GMT hour: {session.get('hour_gmt')}")
        report_lines.append(f"- London Open: {session.get('london_open')}")
        report_lines.append(f"- NY Open: {session.get('ny_open')}")
        report_lines.append(f"- London-NY Overlap: {session.get('london_ny_overlap')}")
        report_lines.append(f"- Asian Forbidden: {session.get('asian_forbidden')}")
        report_lines.append("")
        report_lines.append("[2] NEWS CHECK")
        report_lines.append(f"Status: {_pass_fail(checks['news'])}")
        report_lines.append(f"- News status: {news_status}")
        report_lines.append(f"- Matched news: {news.get('matched_news', []) if news.get('success') else news.get('error')}")
        report_lines.append("")
        report_lines.append("[3] SPREAD CHECK")
        report_lines.append(f"Status: {_pass_fail(checks['spread'])}")
        report_lines.append(f"- MT5 Symbol: {tick_data.get('mt5_symbol')}")
        report_lines.append(f"- Bid: {tick_data.get('bid')}")
        report_lines.append(f"- Ask: {tick_data.get('ask')}")
        report_lines.append(f"- Spread: {spread_check.get('spread_value')} {spread_check.get('spread_unit')}")
        report_lines.append(f"- Max allowed: {spread_check.get('max_allowed')}")
        report_lines.append("")
        report_lines.append("[4] CONSOLIDATION CHECK")
        report_lines.append(f"Status: {_pass_fail(checks['consolidation'])}")
        report_lines.append(f"- Last 8H range: {consolidation.get('range_pips')} pips")
        report_lines.append("- Rule: NO TRADE if H1 range < 20 pips over 8 hours")
        report_lines.append("")
        report_lines.append("[5] SWEEP CHECK")
        report_lines.append(f"Status: {_pass_fail(checks['sweep'])}")
        report_lines.extend(sweep_debug_lines)
        report_lines.append(f"- Detected direction: {_safe(sweep.get('direction') if sweep else None)}")
        report_lines.append(f"- Swept level: {_safe(sweep.get('swept_level') if sweep else None)}")
        report_lines.append(f"- Sweep price: {_safe(sweep.get('sweep_price') if sweep else None)}")
        report_lines.append(f"- Sweep pips: {_safe(sweep.get('sweep_pips') if sweep else None)}")
        report_lines.append(f"- Rejection valid: {_safe(sweep.get('rejection_valid') if sweep else None)}")
        report_lines.append(f"- Wick info: {_safe(sweep.get('wick_info') if sweep else None)}")
        report_lines.append(f"- Reason: {_safe(sweep.get('reason_if_failed') if sweep else None)}")
        report_lines.append("")
        report_lines.append("[6] INSTITUTIONAL S&R CHECK")
        report_lines.append(f"Status: {_pass_fail(checks['sr'])}")

        if sr:
            report_lines.append(f"- Valid S&R types: {sr.get('sr_types', [])}")
            report_lines.append(f"- EMA200: {sr.get('ema200')}")
            report_lines.append(f"- EMA distance: {sr.get('ema_distance_pips')} pips")
            report_lines.append(f"- Horizontal tests: {sr.get('horizontal_tests')}")
            report_lines.append(f"- Round number info: {sr.get('round_info')}")
            if sr.get("error"):
                report_lines.append(f"- Error: {sr.get('error')}")
        else:
            report_lines.append("- Skipped because no valid sweep.")
        report_lines.append("")
        report_lines.append("[7] RISK:REWARD CHECK")
        report_lines.append(f"Status: {_pass_fail(checks['rr'])}")

        if rr:
            report_lines.append(f"- Entry: {rr.get('entry')}")
            report_lines.append(f"- Stop loss: {rr.get('stop_loss')}")
            report_lines.append(f"- Take profit: {rr.get('take_profit')}")
            report_lines.append(f"- SL distance: {rr.get('sl_pips')} pips")
            report_lines.append(f"- TP distance: {rr.get('tp_pips')} pips")
            report_lines.append(f"- R:R: 1:{rr.get('rr')}")
            report_lines.append(f"- Reason: {_safe(rr.get('reason'))}")
        else:
            report_lines.append("- Skipped because no valid sweep.")
        report_lines.append("")
        report_lines.append("━━━━━━━━━━━━━━")
        report_lines.append(f"FINAL VERDICT: {verdict}")
        report_lines.append(f"FINAL REASON: {final_reason}")
        report_lines.append("")
        report_lines.append("I do not execute trades. This is a debug report only.")

        report = "\n".join(report_lines)

        return success_response(
            tool=tool_name,
            message="Debug MT5 strategy selesai",
            extra={
                "symbol": symbol,
                "verdict": verdict,
                "final_reason": final_reason,
                "report": report,
                "checks": checks,
                "session": session,
                "news": news,
                "spread_check": spread_check,
                "consolidation": consolidation,
                "sweep": sweep,
                "sr": sr,
                "rr": rr,
                "latest_h1_candle": {
                    "time": str(latest["time"]),
                    "open": float(latest["open"]),
                    "high": float(latest["high"]),
                    "low": float(latest["low"]),
                    "close": float(latest["close"])
                }
            }
        )

    except Exception as e:
        return error_response(tool_name, e)