"""
MT5 Trading Tools — Account info, positions, orders, dan trade execution.

Digunakan oleh MCP server untuk interaksi trading via MetaTrader 5 broker.
Semua fungsi trade execution (order_send) butuh konfirmasi (privileged).
Fungsi read-only (account, positions, history) aman tanpa approval.
"""

from datetime import datetime, timezone

import MetaTrader5 as mt5

from core import success_response, error_response


# ---------------------------------------------------------------------------
# INIT / SHUTDOWN
# ---------------------------------------------------------------------------

def _init():
    """Initialize MT5 connection. Raises RuntimeError on failure."""
    if not mt5.initialize():
        raise RuntimeError(f"MT5 initialize failed: {mt5.last_error()}")

    acct = mt5.account_info()
    if acct is None:
        raise RuntimeError("MT5 belum login atau account_info tidak tersedia.")
    return acct


def _shutdown():
    try:
        mt5.shutdown()
    except Exception:
        pass


# ---------------------------------------------------------------------------
# SYMBOL RESOLUTION
# ---------------------------------------------------------------------------

SYMBOL_ALIASES = {
    "XAUUSD": ["XAUUSD", "XAUUSDm", "GOLD", "Gold", "XAUUSD."],
    "EURUSD": ["EURUSD", "EURUSDm", "EURUSD."],
    "GBPUSD": ["GBPUSD", "GBPUSDm", "GBPUSD."],
}


def resolve_symbol(symbol: str) -> str:
    symbol = symbol.upper().strip()
    candidates = SYMBOL_ALIASES.get(symbol, [symbol])

    all_symbols = mt5.symbols_get()
    if not all_symbols:
        raise RuntimeError("Tidak bisa membaca daftar symbol dari MT5.")

    available = {s.name: s for s in all_symbols}
    for c in candidates:
        if c in available:
            mt5.symbol_select(c, True)
            return c

    # fallback: substring match
    for s in available:
        if symbol in s.upper():
            mt5.symbol_select(s, True)
            return s

    raise RuntimeError(f"Symbol {symbol} tidak ditemukan di MT5 broker.")


# ---------------------------------------------------------------------------
# TRADE ACTION HELPERS
# ---------------------------------------------------------------------------

TRADE_ACTIONS = {
    "buy": mt5.ORDER_TYPE_BUY,
    "sell": mt5.ORDER_TYPE_SELL,
    "buy_limit": mt5.ORDER_TYPE_BUY_LIMIT,
    "sell_limit": mt5.ORDER_TYPE_SELL_LIMIT,
    "buy_stop": mt5.ORDER_TYPE_BUY_STOP,
    "sell_stop": mt5.ORDER_TYPE_SELL_STOP,
}

TRADE_ACTIONS_REVERSE = {
    mt5.ORDER_TYPE_BUY: "buy",
    mt5.ORDER_TYPE_SELL: "sell",
    mt5.ORDER_TYPE_BUY_LIMIT: "buy_limit",
    mt5.ORDER_TYPE_SELL_LIMIT: "sell_limit",
    mt5.ORDER_TYPE_BUY_STOP: "buy_stop",
    mt5.ORDER_TYPE_SELL_STOP: "sell_stop",
}


def _parse_action(action: str):
    """Convert string action to MT5 constant."""
    a = action.lower().strip()
    if a not in TRADE_ACTIONS:
        raise ValueError(
            f"Action tidak valid: {action}. Pilihan: {', '.join(TRADE_ACTIONS.keys())}"
        )
    return TRADE_ACTIONS[a]


# ---------------------------------------------------------------------------
# ACCOUNT INFO (read-only)
# ---------------------------------------------------------------------------

def mt5_account_info() -> dict:
    """
    Dapatkan informasi akun trading — balance, equity, margin, leverage.
    Aman tanpa konfirmasi (read-only).
    """
    _TOOL = "mt5_account_info"
    try:
        acct = _init()
        return success_response(
            _TOOL,
            "Akun MT5 berhasil dibaca",
            extra={
                "login": acct.login,
                "server": acct.server,
                "name": acct.name,
                "balance": acct.balance,
                "equity": acct.equity,
                "margin": acct.margin,
                "margin_free": acct.margin_free,
                "margin_level": acct.margin_level,
                "leverage": acct.leverage,
                "currency": acct.currency,
                "profit": acct.profit,
                "checked_at_utc": datetime.now(timezone.utc).isoformat(),
            },
        )
    except Exception as e:
        return error_response(_TOOL, e)
    finally:
        _shutdown()


# ---------------------------------------------------------------------------
# POSITIONS (read-only)
# ---------------------------------------------------------------------------

def mt5_positions() -> dict:
    """
    Daftar semua posisi yang sedang terbuka.
    Aman tanpa konfirmasi (read-only).
    """
    _TOOL = "mt5_positions"
    try:
        _init()
        positions = mt5.positions_get()
        pos_list = []

        if positions is not None:
            for p in positions:
                pos_list.append(
                    {
                        "ticket": p.ticket,
                        "symbol": p.symbol,
                        "type": TRADE_ACTIONS_REVERSE.get(p.type, str(p.type)),
                        "volume": p.volume,
                        "price_open": p.price_open,
                        "sl": p.sl,
                        "tp": p.tp,
                        "profit": p.profit,
                        "swap": p.swap,
                        "price_current": p.price_current,
                        "comment": p.comment,
                        "magic": p.magic,
                        "time": datetime.fromtimestamp(p.time, tz=timezone.utc).isoformat(),
                    }
                )

        return success_response(
            _TOOL,
            f"Posisi terbuka: {len(pos_list)}",
            extra={
                "positions": pos_list,
                "total": len(pos_list),
            },
        )
    except Exception as e:
        return error_response(_TOOL, e)
    finally:
        _shutdown()


# ---------------------------------------------------------------------------
# PENDING ORDERS (read-only)
# ---------------------------------------------------------------------------

def mt5_pending_orders() -> dict:
    """
    Daftar semua pending order.
    Aman tanpa konfirmasi (read-only).
    """
    _TOOL = "mt5_pending_orders"
    try:
        _init()
        orders = mt5.orders_get()
        ord_list = []

        if orders is not None:
            for o in orders:
                ord_list.append(
                    {
                        "ticket": o.ticket,
                        "symbol": o.symbol,
                        "type": TRADE_ACTIONS_REVERSE.get(o.type, str(o.type)),
                        "volume": o.volume,
                        "price": o.price_open,
                        "sl": o.sl,
                        "tp": o.tp,
                        "comment": o.comment,
                        "magic": o.magic,
                        "time": datetime.fromtimestamp(o.time_setup, tz=timezone.utc).isoformat(),
                        "expiration": (
                            datetime.fromtimestamp(o.time_expiration, tz=timezone.utc).isoformat()
                            if o.time_expiration else None
                        ),
                    }
                )

        return success_response(
            _TOOL,
            f"Pending orders: {len(ord_list)}",
            extra={
                "pending_orders": ord_list,
                "total": len(ord_list),
            },
        )
    except Exception as e:
        return error_response(_TOOL, e)
    finally:
        _shutdown()


# ---------------------------------------------------------------------------
# TRADE HISTORY (read-only)
# ---------------------------------------------------------------------------

def mt5_trade_history(days: int = 7):
    """
    Riwayat transaksi N hari terakhir.
    Aman tanpa konfirmasi (read-only).
    """
    _TOOL = "mt5_trade_history"
    try:
        _init()
        now = datetime.now(timezone.utc)
        from_dt = datetime(
            now.year, now.month, now.day, tzinfo=timezone.utc
        ) - __import__("datetime").timedelta(days=int(days))

        history = mt5.history_deals_get(from_dt, now)
        h_list = []

        if history is not None:
            for h in history:
                h_list.append(
                    {
                        "ticket": h.ticket,
                        "order": h.order,
                        "symbol": h.symbol,
                        "type": TRADE_ACTIONS_REVERSE.get(h.type, str(h.type)),
                        "volume": h.volume,
                        "price": h.price,
                        "profit": h.profit,
                        "commission": h.commission,
                        "swap": h.swap,
                        "comment": h.comment,
                        "time": datetime.fromtimestamp(h.time, tz=timezone.utc).isoformat(),
                    }
                )

        # total profit
        total_profit = sum(h.get("profit", 0) for h in h_list)

        return success_response(
            _TOOL,
            f"Riwayat {len(h_list)} transaksi dalam {days} hari terakhir. Total profit: {total_profit:.2f}",
            extra={
                "trades": h_list,
                "total_trades": len(h_list),
                "total_profit": total_profit,
                "days": days,
            },
        )
    except Exception as e:
        return error_response(_TOOL, e)
    finally:
        _shutdown()


# ---------------------------------------------------------------------------
# MARKET ORDER (privileged — needs confirmation)
# ---------------------------------------------------------------------------

def mt5_market_order(
    symbol: str,
    action: str,
    volume: float,
    sl: float | None = None,
    tp: float | None = None,
    comment: str = "Jenny MCP",
):
    """
    Eksekusi market order (buy/sell) via MT5.
    PRIVILEGED — butuh konfirmasi pengguna.
    """
    _TOOL = "mt5_market_order"
    try:
        acct = _init()
        mt5_symbol = resolve_symbol(symbol)
        order_type = _parse_action(action)

        if order_type not in (mt5.ORDER_TYPE_BUY, mt5.ORDER_TYPE_SELL):
            raise ValueError("market_order hanya support 'buy' atau 'sell'.")

        tick = mt5.symbol_info_tick(mt5_symbol)
        if tick is None:
            raise RuntimeError(f"Tick tidak tersedia untuk {mt5_symbol}")

        info = mt5.symbol_info(mt5_symbol)
        if info is None:
            raise RuntimeError(f"Symbol info tidak tersedia untuk {mt5_symbol}")

        # hitung volume berdasarkan lot step
        volume = round(volume / info.volume_step) * info.volume_step
        volume = max(info.volume_min, min(info.volume_max, volume))

        # hitung price
        price = tick.ask if order_type == mt5.ORDER_TYPE_BUY else tick.bid

        # hitung SL/TP dalam price mutlak
        sl_price = sl
        tp_price = tp

        request = {
            "action": mt5.TRADE_ACTION_DEAL,
            "symbol": mt5_symbol,
            "volume": float(volume),
            "type": order_type,
            "price": float(price),
            "sl": float(sl_price) if sl_price else 0.0,
            "tp": float(tp_price) if tp_price else 0.0,
            "deviation": 50,
            "magic": 123456,
            "comment": comment,
            "type_time": mt5.ORDER_TIME_GTC,
            "type_filling": mt5.ORDER_FILLING_IOC,
        }

        result = mt5.order_send(request)

        if result is None:
            raise RuntimeError("order_send mengembalikan None (gagal).")

        resp = {
            "retcode": result.retcode,
            "comment": result.comment,
            "ticket": result.order if result.retcode == mt5.TRADE_RETCODE_DONE else None,
            "request": {
                "symbol": mt5_symbol,
                "action": action,
                "volume": float(volume),
                "price": float(price),
                "sl": float(sl_price) if sl_price else None,
                "tp": float(tp_price) if tp_price else None,
            },
            "account_login": acct.login,
            "server": acct.server,
        }

        if result.retcode != mt5.TRADE_RETCODE_DONE:
            resp["error_detail"] = f"retcode={result.retcode}: {result.comment}"
            return error_response(
                _TOOL,
                RuntimeError(f"Order gagal: {result.comment} (retcode {result.retcode})"),
                extra=resp,
            )

        return success_response(
            _TOOL,
            f"Market {action} {volume} lot {mt5_symbol} sukses! Ticket #{result.order}",
            extra=resp,
        )

    except Exception as e:
        return error_response(_TOOL, e)
    finally:
        _shutdown()


# ---------------------------------------------------------------------------
# MODIFY TRADE (privileged — needs confirmation)
# ---------------------------------------------------------------------------

def mt5_modify_trade(ticket: int, sl: float | None = None, tp: float | None = None):
    """
    Ubah SL/TP dari posisi terbuka.
    PRIVILEGED — butuh konfirmasi pengguna.
    """
    _TOOL = "mt5_modify_trade"
    try:
        _init()

        # cari posisi by ticket
        position = mt5.positions_get(ticket=ticket)
        if not position or len(position) == 0:
            raise RuntimeError(f"Posisi dengan ticket #{ticket} tidak ditemukan.")
        pos = position[0]

        request = {
            "action": mt5.TRADE_ACTION_SLTP,
            "symbol": pos.symbol,
            "position": ticket,
            "sl": float(sl) if sl is not None else pos.sl,
            "tp": float(tp) if tp is not None else pos.tp,
        }

        result = mt5.order_send(request)

        if result is None:
            raise RuntimeError("order_send gagal (None).")

        resp = {
            "ticket": ticket,
            "new_sl": float(sl) if sl is not None else pos.sl,
            "new_tp": float(tp) if tp is not None else pos.tp,
            "retcode": result.retcode,
            "comment": result.comment,
        }

        if result.retcode != mt5.TRADE_RETCODE_DONE:
            return error_response(
                _TOOL,
                RuntimeError(f"Modify gagal: {result.comment} (retcode {result.retcode})"),
                extra=resp,
            )

        return success_response(
            _TOOL,
            f"SL/TP posisi #{ticket} berhasil diubah",
            extra=resp,
        )

    except Exception as e:
        return error_response(_TOOL, e)
    finally:
        _shutdown()


# ---------------------------------------------------------------------------
# CLOSE TRADE (privileged — needs confirmation)
# ---------------------------------------------------------------------------

def mt5_close_trade(ticket: int, volume: float | None = None):
    """
    Tutup posisi terbuka sebagian atau seluruhnya.
    PRIVILEGED — butuh konfirmasi pengguna.
    """
    _TOOL = "mt5_close_trade"
    try:
        _init()

        position = mt5.positions_get(ticket=ticket)
        if not position or len(position) == 0:
            raise RuntimeError(f"Posisi #{ticket} tidak ditemukan.")
        pos = position[0]

        close_volume = volume if volume else pos.volume

        tick = mt5.symbol_info_tick(pos.symbol)
        if tick is None:
            raise RuntimeError(f"Tick tidak tersedia untuk {pos.symbol}")

        close_type = (
            mt5.ORDER_TYPE_SELL if pos.type == mt5.ORDER_TYPE_BUY else mt5.ORDER_TYPE_BUY
        )
        close_price = tick.bid if close_type == mt5.ORDER_TYPE_SELL else tick.ask

        request = {
            "action": mt5.TRADE_ACTION_DEAL,
            "symbol": pos.symbol,
            "volume": float(close_volume),
            "type": close_type,
            "position": ticket,
            "price": float(close_price),
            "deviation": 50,
            "magic": 123456,
            "comment": "Jenny MCP Close",
            "type_time": mt5.ORDER_TIME_GTC,
            "type_filling": mt5.ORDER_FILLING_IOC,
        }

        result = mt5.order_send(request)

        if result is None:
            raise RuntimeError("order_send gagal (None).")

        resp = {
            "ticket": ticket,
            "close_volume": float(close_volume),
            "close_price": float(close_price),
            "retcode": result.retcode,
            "comment": result.comment,
        }

        if result.retcode != mt5.TRADE_RETCODE_DONE:
            return error_response(
                _TOOL,
                RuntimeError(
                    f"Close gagal: {result.comment} (retcode {result.retcode})"
                ),
                extra=resp,
            )

        return success_response(
            _TOOL,
            f"Posisi #{ticket} berhasil ditutup ({close_volume} lot @ {close_price:.2f})",
            extra=resp,
        )

    except Exception as e:
        return error_response(_TOOL, e)
    finally:
        _shutdown()


# ---------------------------------------------------------------------------
# PENDING ORDER (privileged — needs confirmation)
# ---------------------------------------------------------------------------

def mt5_create_pending(
    symbol: str,
    action: str,
    volume: float,
    price: float,
    sl: float | None = None,
    tp: float | None = None,
    comment: str = "Jenny MCP",
    expiration: float | None = None,
):
    """
    Buat pending order (buy_limit/sell_limit/buy_stop/sell_stop).
    PRIVILEGED — butuh konfirmasi pengguna.
    """
    _TOOL = "mt5_create_pending"
    try:
        _init()
        mt5_symbol = resolve_symbol(symbol)
        order_type = _parse_action(action)

        if order_type not in (
            mt5.ORDER_TYPE_BUY_LIMIT,
            mt5.ORDER_TYPE_SELL_LIMIT,
            mt5.ORDER_TYPE_BUY_STOP,
            mt5.ORDER_TYPE_SELL_STOP,
        ):
            raise ValueError(
                "Pending order support: buy_limit, sell_limit, buy_stop, sell_stop"
            )

        info = mt5.symbol_info(mt5_symbol)
        if info is None:
            raise RuntimeError(f"Symbol info tidak tersedia untuk {mt5_symbol}")

        volume = round(volume / info.volume_step) * info.volume_step
        volume = max(info.volume_min, min(info.volume_max, volume))

        request = {
            "action": mt5.TRADE_ACTION_PENDING,
            "symbol": mt5_symbol,
            "volume": float(volume),
            "type": order_type,
            "price": float(price),
            "sl": float(sl) if sl is not None else 0.0,
            "tp": float(tp) if tp is not None else 0.0,
            "comment": comment,
            "type_time": (
                mt5.ORDER_TIME_SPECIFIED if expiration else mt5.ORDER_TIME_GTC
            ),
            "type_filling": mt5.ORDER_FILLING_IOC,
            "expiration": int(expiration) if expiration else 0,
        }

        result = mt5.order_send(request)

        if result is None:
            raise RuntimeError("order_send gagal (None).")

        resp = {
            "symbol": mt5_symbol,
            "action": action,
            "volume": float(volume),
            "price": float(price),
            "sl": float(sl) if sl else None,
            "tp": float(tp) if tp else None,
            "ticket": result.order if result.retcode == mt5.TRADE_RETCODE_DONE else None,
            "retcode": result.retcode,
            "comment": result.comment,
        }

        if result.retcode != mt5.TRADE_RETCODE_DONE:
            return error_response(
                _TOOL,
                RuntimeError(
                    f"Pending order gagal: {result.comment} (retcode {result.retcode})"
                ),
                extra=resp,
            )

        return success_response(
            _TOOL,
            f"Pending {action} {volume} lot {mt5_symbol} @ {price} sukses! Ticket #{result.order}",
            extra=resp,
        )

    except Exception as e:
        return error_response(_TOOL, e)
    finally:
        _shutdown()


# ---------------------------------------------------------------------------
# CANCEL PENDING ORDER (privileged)
# ---------------------------------------------------------------------------

def mt5_cancel_order(ticket: int):
    """
    Batalkan pending order berdasarkan ticket.
    PRIVILEGED — butuh konfirmasi pengguna.
    """
    _TOOL = "mt5_cancel_order"
    try:
        _init()

        order = mt5.orders_get(ticket=ticket)
        if not order or len(order) == 0:
            raise RuntimeError(f"Pending order #{ticket} tidak ditemukan atau sudah dieksekusi.")
        ord_info = order[0]

        request = {
            "action": mt5.TRADE_ACTION_REMOVE,
            "order": ticket,
            "symbol": ord_info.symbol,
        }

        result = mt5.order_send(request)

        if result is None:
            raise RuntimeError("order_send gagal (None).")

        resp = {
            "ticket": ticket,
            "symbol": ord_info.symbol,
            "retcode": result.retcode,
            "comment": result.comment,
        }

        if result.retcode != mt5.TRADE_RETCODE_DONE:
            return error_response(
                _TOOL,
                RuntimeError(
                    f"Cancel order gagal: {result.comment} (retcode {result.retcode})"
                ),
                extra=resp,
            )

        return success_response(
            _TOOL,
            f"Pending order #{ticket} berhasil dibatalkan",
            extra=resp,
        )

    except Exception as e:
        return error_response(_TOOL, e)
    finally:
        _shutdown()
