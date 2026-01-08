from __future__ import annotations
import traceback
import math
import json
import hashlib
from pathlib import Path
from typing import Any, List, Dict
from datetime import date, datetime, timedelta

from .data import load_bars_from_csv
from .event_engine import EventBacktestEngine
from .channel_hf import ChannelHFConfig, ChannelHFStrategy, calculate_volatility_ratio
from .types import BacktestConfig, BrokerConfig, Bar
from .batch_runner import resolve_file_path
 
def _round_finite(x: Any, ndigits: int) -> float | None:
    try:
        v = float(x)
    except Exception:
        return None
    if not math.isfinite(v):
        return None
    return round(v, int(ndigits))

def _round_bool(x: Any) -> bool | None:
    return bool(x) if isinstance(x, bool) else None

def _filter_type_by_step(step: str) -> str:
    s = str(step or "").strip()
    if s in {"VolumeShrinkFilter"}:
        return "量能过滤"
    if s in {"Volatility"}:
        return "波动率过滤"
    if s in {"TrendMA"}:
        return "趋势过滤"
    if s in {"SlopeMin", "SlopeMax", "ChanHeight", "MidRoom"}:
        return "通道过滤"
    if s in {"TouchLowerFilter"}:
        return "触底过滤"
    if s in {"Cooling"}:
        return "冷却期"
    if s in {"IndexFilter", "IndexMA", "IndexConfirm"}:
        return "指数过滤"
    if s in {"PivotSig", "PivotDays", "NoNewLow", "ReboundAmp"}:
        return "企稳过滤"
    if s in {"MinProfit"}:
        return "盈利过滤"
    if s in {"MinRR"}:
        return "风报比过滤"
    if s in {"MaxPos"}:
        return "仓位过滤"
    if s in {"Rebound"}:
        return "反弹过滤"
    if s in {"CandleColor"}:
        return "K线过滤"
    return "其他过滤"

def _generate_rejection_details_from_daily(daily_data: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], dict[str, Any], dict[str, int]]:
    details: list[dict[str, Any]] = []
    by_step: dict[str, dict[str, Any]] = {}
    flat_stats: dict[str, int] = {}

    for item in daily_data:
        try:
            if bool(item.get("has_position")):
                continue
            if int(item.get("final_signal") or 0) == 1:
                continue
        except Exception:
            continue

        dt_str = str(item.get("date") or "").strip()
        trace = item.get("trace")
        if not dt_str or not isinstance(trace, list) or not trace:
            continue

        failed = None
        for step in reversed(trace):
            if not isinstance(step, dict):
                continue
            if step.get("passed") is False:
                failed = step
                break
        if not failed:
            continue

        step_name = str(failed.get("step") or "Unknown").strip() or "Unknown"
        check = str(failed.get("check") or "").strip()
        threshold = str(failed.get("threshold") or "").strip()
        actual = str(failed.get("actual") or "").strip()
        reason = str(failed.get("reason") or "").strip()
        if not reason:
            reason = check or step_name

        filter_type = _filter_type_by_step(step_name)

        details.append({
            "date": dt_str,
            "step": step_name,
            "filter_type": filter_type,
            "check": check,
            "actual": actual,
            "threshold": threshold,
            "reason": reason,
        })

        rec = by_step.get(step_name)
        if rec is None:
            rec = {"step": step_name, "filter_type": filter_type, "total": 0, "reasons": {}}
            by_step[step_name] = rec
        rec["total"] = int(rec.get("total") or 0) + 1
        reasons = rec.get("reasons")
        if not isinstance(reasons, dict):
            reasons = {}
            rec["reasons"] = reasons
        
        # Enhanced reason stats with range tracking
        if reason not in reasons:
            reasons[reason] = {"count": 0, "min_val": float('inf'), "max_val": float('-inf'), "has_val": False}
        
        r_stat = reasons[reason]
        r_stat["count"] += 1
        
        # Try to parse actual value for range stats
        try:
            # Clean actual string (handle % or other suffixes if present, though usually it's a number string from channel_hf)
            val_str = actual.split('/')[0].split('=')[-1].strip().rstrip('%')
            val = float(val_str)
            r_stat["has_val"] = True
            if val < r_stat["min_val"]:
                r_stat["min_val"] = val
            if val > r_stat["max_val"]:
                r_stat["max_val"] = val
        except Exception:
            pass

        flat_key = f"{filter_type}/{reason}"
        flat_stats[flat_key] = int(flat_stats.get(flat_key) or 0) + 1

    summary = list(by_step.values())
    summary.sort(key=lambda x: int(x.get("total") or 0), reverse=True)
    
    # Finalize reasons structure for JSON serialization
    for s in summary:
        rs = s.get("reasons")
        if isinstance(rs, dict):
            # Sort reasons by count
            sorted_rs = sorted(rs.items(), key=lambda kv: kv[1]["count"], reverse=True)
            # Convert to list or keep as dict? The frontend expects a dict currently but I'm changing the schema.
            # Let's keep it as a dict but with objects as values.
            # To make it easy for frontend, let's normalize the min/max
            final_rs = {}
            for k, v in sorted_rs:
                if v["has_val"] and v["min_val"] != float('inf'):
                    v["range_text"] = f"{v['min_val']:.2f}-{v['max_val']:.2f}"
                else:
                    v["range_text"] = ""
                # Remove infinity for JSON safety
                if v["min_val"] == float('inf'): v["min_val"] = None
                if v["max_val"] == float('-inf'): v["max_val"] = None
                final_rs[k] = v
            s["reasons"] = final_rs

    return details, {"summary": summary, "by_step": by_step}, flat_stats

def _compute_feature_snapshot_for_trade(
    *,
    symbol: str,
    strat_conf: ChannelHFConfig,
    logs_by_date: dict[str, Any],
    bar_idx_by_date: dict[date, int],
    close_by_idx: list[float],
    entry_dt: date,
    exit_dt: date,
    qty: int,
    entry_price: float,
    exit_price: float,
    holding_days: int,
    exit_reason: str,
    return_rate: float,
) -> tuple[str, dict[str, Any]]:
    def _pick_entry_signal_date(entry_dt_local: date) -> date | None:
        last = None
        for dstr, log in logs_by_date.items():
            try:
                if int(log.get("final_signal") or 0) != 1:
                    continue
                d = datetime.fromisoformat(str(dstr)).date()
            except Exception:
                continue
            if d < entry_dt_local and (last is None or d > last):
                last = d
        return last

    def _step_pass(trace: Any, step_name: str) -> bool | None:
        if not isinstance(trace, list):
            return None
        for s in reversed(trace):
            if isinstance(s, dict) and s.get("step") == step_name:
                p = s.get("passed")
                if isinstance(p, bool):
                    return p
                return None
        return None

    def _step_any_fail(trace: Any, step_names: set[str]) -> bool | None:
        if not isinstance(trace, list):
            return None
        found = False
        for s in trace:
            if not isinstance(s, dict):
                continue
            nm = s.get("step")
            if nm in step_names:
                found = True
                if s.get("passed") is False:
                    return True
        return False if found else None

    base_payload = {
        "symbol": str(symbol),
        "signal_date": (_pick_entry_signal_date(entry_dt) or entry_dt).isoformat(),
        "entry_dt": entry_dt.isoformat(),
        "exit_dt": exit_dt.isoformat(),
        "qty": int(qty),
        "exit_reason": str(exit_reason or ""),
        "return_rate": float(return_rate),
    }
    raw = json.dumps(base_payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    transaction_id = hashlib.sha1(raw.encode("utf-8")).hexdigest()

    signal_dt = _pick_entry_signal_date(entry_dt) or entry_dt
    log_entry = logs_by_date.get(signal_dt.isoformat(), {})
    trace = log_entry.get("trace", []) if isinstance(log_entry, dict) else []

    idx = bar_idx_by_date.get(signal_dt)
    close0 = float(log_entry.get("close")) if isinstance(log_entry, dict) and log_entry.get("close") is not None else None
    if close0 is None and idx is not None:
        try:
            close0 = float(close_by_idx[idx])
        except Exception:
            close0 = None

    vol_short = None
    vol_long = None
    vol_ratio = None
    if idx is not None and idx >= 1:
        try:
            import numpy as np
            arr = np.asarray(close_by_idx[: idx + 1], dtype=float)
            v = calculate_volatility_ratio(arr, short_window=5, long_window=20)
            if v is not None:
                vol_short, vol_long, vol_ratio = v
        except Exception:
            vol_short = None
            vol_long = None
            vol_ratio = None

    ma20 = None
    if idx is not None and idx >= 19:
        try:
            ma20 = float(sum(close_by_idx[idx - 19 : idx + 1]) / 20.0)
        except Exception:
            ma20 = None

    vol_thr = float(getattr(strat_conf, "volatility_ratio_max", 1.0))
    vol_pass = _step_pass(trace, "Volatility")
    if vol_pass is None:
        if vol_ratio is None or vol_thr >= 1.0:
            vol_pass = True
        else:
            vol_pass = bool(float(vol_ratio) <= float(vol_thr))

    trend_pass = _step_pass(trace, "TrendMA")
    if trend_pass is None:
        trend_pass = True if int(getattr(strat_conf, "trend_ma_period", 0) or 0) <= 0 else None

    volume_ratio = None
    if isinstance(log_entry, dict) and log_entry.get("vol_ratio") is not None:
        try:
            volume_ratio = float(log_entry.get("vol_ratio"))
        except Exception:
            volume_ratio = None

    vol_shrink_threshold = float(getattr(strat_conf, "vol_shrink_threshold", 0.9))
    vol_shrink_min = getattr(strat_conf, "vol_shrink_min", None)
    vol_shrink_max = getattr(strat_conf, "vol_shrink_max", None)
    volume_pass = _step_pass(trace, "VolumeShrinkFilter")
    if volume_pass is None:
        if volume_ratio is None:
            volume_pass = True
        else:
            if vol_shrink_min is not None or vol_shrink_max is not None:
                mn = float(vol_shrink_min) if vol_shrink_min is not None else float("-inf")
                mx = float(vol_shrink_max) if vol_shrink_max is not None else float("inf")
                volume_pass = bool(float(volume_ratio) >= mn and float(volume_ratio) <= mx)
            else:
                if vol_shrink_threshold >= 1.0:
                    volume_pass = bool(volume_ratio >= vol_shrink_threshold)
                else:
                    volume_pass = bool(volume_ratio <= vol_shrink_threshold)

    slope_value = None
    if isinstance(log_entry, dict) and log_entry.get("slope_norm") is not None:
        try:
            slope_value = float(log_entry.get("slope_norm"))
        except Exception:
            slope_value = None
    slope_min = float(getattr(strat_conf, "min_slope_norm", -1.0))
    slope_pass = _step_pass(trace, "SlopeMin")
    if slope_pass is None:
        slope_pass = True if slope_min <= -1.0 else None

    height_value = None
    if isinstance(log_entry, dict) and log_entry.get("channel_height") is not None:
        try:
            height_value = float(log_entry.get("channel_height"))
        except Exception:
            height_value = None
    height_min = float(getattr(strat_conf, "min_channel_height", 0.0))
    height_pass = _step_pass(trace, "ChanHeight")

    room_value = None
    if isinstance(log_entry, dict) and log_entry.get("mid_room") is not None:
        try:
            room_value = float(log_entry.get("mid_room"))
        except Exception:
            room_value = None
    room_min = float(getattr(strat_conf, "min_mid_room", 0.0))
    room_pass = _step_pass(trace, "MidRoom")

    cooling_pass = _step_pass(trace, "Cooling")
    if cooling_pass is None:
        cooling_pass = True

    pivot_confirm_days = int(getattr(strat_conf, "pivot_confirm_days", 0) or 0)
    pivot_fail = _step_any_fail(trace, {"PivotSig", "PivotDays", "NoNewLow", "ReboundAmp"})
    pivot_pass = True if pivot_confirm_days <= 0 else (False if pivot_fail is True else (True if pivot_fail is False else None))

    entry_fill_eps = float(getattr(strat_conf, "entry_fill_eps", 0.0))
    sell_trigger_eps = float(getattr(strat_conf, "sell_trigger_eps", 0.0))
    sell_mode = str(getattr(strat_conf, "sell_target_mode", "mid_up") or "mid_up").strip().lower()
    mid = log_entry.get("mid") if isinstance(log_entry, dict) else None
    upper = log_entry.get("upper") if isinstance(log_entry, dict) else None

    entry_px = (float(close0) * (1.0 + max(0.0, entry_fill_eps))) if close0 is not None else None
    target_px = None
    try:
        midv = float(mid) if mid is not None else None
        upv = float(upper) if upper is not None else None
        if midv is not None and upv is not None:
            if sell_mode == "mid_up":
                target_px = midv * (1.0 + max(0.0, sell_trigger_eps))
            elif sell_mode == "upper_down":
                target_px = upv * (1.0 - max(0.0, sell_trigger_eps))
            else:
                target_px = midv * (1.0 - max(0.0, sell_trigger_eps))
    except Exception:
        target_px = None

    min_profit_threshold = float(getattr(strat_conf, "min_mid_profit_pct", 0.0))
    min_profit_value = None
    if entry_px is not None and entry_px > 0 and target_px is not None:
        min_profit_value = (float(target_px) / float(entry_px)) - 1.0
    profit_pass = _step_pass(trace, "MinProfit")
    if profit_pass is None:
        profit_pass = True if min_profit_threshold <= 0.0 else (bool(min_profit_value is not None and float(min_profit_value) >= float(min_profit_threshold)))

    min_rr_threshold = float(getattr(strat_conf, "min_rr_to_mid", 0.0))
    min_rr_value = None
    if entry_px is not None and entry_px > 0 and target_px is not None:
        stop_mul = float(getattr(strat_conf, "stop_loss_mul", 0.97))
        initial_stop = float(entry_px) * max(0.0, stop_mul)
        risk = float(entry_px) - initial_stop
        reward = float(target_px) - float(entry_px)
        if risk > 0:
            min_rr_value = reward / risk
    rr_pass = _step_pass(trace, "MinRR")
    if rr_pass is None:
        rr_pass = True if min_rr_threshold <= 0.0 else (bool(min_rr_value is not None and float(min_rr_value) >= float(min_rr_threshold)))

    feature_snapshot = {
        "transaction_id": transaction_id,
        "stock_code": str(symbol),
        "entry_date": entry_dt.isoformat(),
        "exit_date": exit_dt.isoformat(),
        "entry_price": _round_finite(entry_price, 2),
        "exit_price": _round_finite(exit_price, 2),
        "holding_days": int(holding_days),
        "exit_reason": str(exit_reason or ""),
        "return_rate": _round_finite(return_rate, 6),
        "vol_short": _round_finite(vol_short, 4),
        "vol_long": _round_finite(vol_long, 4),
        "vol_ratio": _round_finite(vol_ratio, 3),
        "vol_threshold": _round_finite(vol_thr, 3),
        "vol_pass": _round_bool(vol_pass),
        "price": _round_finite(close0, 2),
        "ma20": _round_finite(ma20, 2),
        "buy_touch_eps": _round_finite(getattr(strat_conf, "buy_touch_eps", 0.0), 3),
        "trend_pass": _round_bool(trend_pass),
        "volume_ratio": _round_finite(volume_ratio, 3),
        "vol_shrink_threshold": _round_finite(vol_shrink_threshold, 3),
        "vol_shrink_min": _round_finite(vol_shrink_min, 3),
        "vol_shrink_max": _round_finite(vol_shrink_max, 3),
        "volume_pass": _round_bool(volume_pass),
        "slope_value": _round_finite(slope_value, 4),
        "slope_min": _round_finite(slope_min, 4),
        "slope_pass": _round_bool(slope_pass),
        "height_value": _round_finite(height_value, 4),
        "height_min": _round_finite(height_min, 4),
        "height_pass": _round_bool(height_pass),
        "room_value": _round_finite(room_value, 4),
        "room_min": _round_finite(room_min, 4),
        "room_pass": _round_bool(room_pass),
        "cooling_pass": _round_bool(cooling_pass),
        "pivot_confirm_days": int(pivot_confirm_days),
        "pivot_pass": _round_bool(pivot_pass),
        "min_profit_value": _round_finite(min_profit_value, 4),
        "min_profit_threshold": _round_finite(min_profit_threshold, 4),
        "profit_pass": _round_bool(profit_pass),
        "min_rr_value": _round_finite(min_rr_value, 2),
        "min_rr_threshold": _round_finite(min_rr_threshold, 2),
        "rr_pass": _round_bool(rr_pass),
    }

    return transaction_id, feature_snapshot

def debug_analyze_channel_hf(
    symbol: str,
    data_path: Path,
    index_path: Path | None,
    config: dict[str, Any],
) -> dict[str, Any]:
    """
    Run a detailed backtest for a single symbol to support the Strategy Debug Analyzer.
    Returns a rich structure with:
    - Overview metrics
    - Trade list with entry/exit/reason details
    - Full decision trace logs (signal_logs)
    - Daily OHLCV data for charting
    """
    try:
        beg = config.get("beg")
        end = config.get("end")

        req_beg = None
        req_end = None
        try:
            if beg:
                req_beg = datetime.fromisoformat(str(beg)).date()
        except Exception:
            req_beg = None
        try:
            if end:
                req_end = datetime.fromisoformat(str(end)).date()
        except Exception:
            req_end = None

        load_beg = beg
        if req_beg is not None:
            load_beg = (req_beg - timedelta(days=400)).isoformat()

        # 1. Load Data
        symbol_bars = load_bars_from_csv(data_path, symbol=symbol, beg=load_beg, end=end, validate=False)
        if not symbol_bars:
            return {"status": "error", "message": f"No data loaded for {symbol}"}

        index_bars = []
        if index_path:
            index_symbol = config.get("index_symbol", "000300.SH")
            index_bars = load_bars_from_csv(index_path, symbol=index_symbol, beg=load_beg, end=end, validate=False)

        # 2. Setup Config
        # Filter supported fields for ChannelHFConfig
        from dataclasses import fields
        valid_fields = {f.name for f in fields(ChannelHFConfig)}
        strat_params = {k: v for k, v in config.items() if k in valid_fields}
        
        # Enforce capture_logs=True for debug mode
        strat_params["capture_logs"] = True
        
        # Ensure position constraints are reasonable for single stock debug
        # (Though max_positions doesn't matter much for single stock, we keep it consistent)
        if "max_positions" not in strat_params:
            strat_params["max_positions"] = 5
        
        strat_conf = ChannelHFConfig(**strat_params)

        broker_conf = BrokerConfig(
            commission_rate=float(config.get("commission_rate", 0.0003)),
            slippage_bps=float(config.get("slippage_bps", 2.0)),
            min_commission=float(config.get("min_commission", 5.0)),
            stamp_duty_rate=float(config.get("stamp_duty_rate", config.get("stamp_duty", 0.001))),
            slippage_rate=float(config.get("slippage_rate", config.get("slippage", 0.001))),
            lot_size=int(config.get("lot_size", 100)),
        )
        engine_conf = BacktestConfig(
            initial_cash=float(config.get("initial_cash", 1000000.0)),
            broker=broker_conf,
            benchmark_symbol=str(config.get("index_symbol", "000300.SH")) if config.get("index_symbol") else None,
        )

        # 3. Run Strategy
        strategy = ChannelHFStrategy(
            bars=symbol_bars,
            config=strat_conf,
            index_bars=index_bars
        )
        engine = EventBacktestEngine(config=engine_conf)
        
        # The engine.run returns a BacktestResult
        result = engine.run(bars=symbol_bars, strategy=strategy, benchmark_bars=index_bars, start_date=req_beg)

        # 4. Process Results
        m = result.metrics
        avg_holding_days = 0.0
        if result.trades:
            avg_holding_days = sum(t.holding_days for t in result.trades) / len(result.trades)
        overview = {
            "total_trades": m.trade_count,
            "win_rate": m.win_rate,
            "total_return": m.total_return,
            "annual_return": m.annual_return,
            "max_drawdown": m.max_drawdown,
            "avg_holding_days": avg_holding_days,
            "profit_factor": m.profit_factor,
            "sharpe_ratio": m.sharpe,
            "final_value": m.final_equity,
            "initial_cash": engine_conf.initial_cash,
        }

        # B. Trade List
        logs_by_date = {log["date"]: log for log in strategy.signal_logs}
        bar_idx_by_date: dict[date, int] = {}
        close_by_idx: list[float] = []
        date_by_idx: list[date] = []
        for i, b in enumerate(symbol_bars):
            bar_idx_by_date[b.dt] = i
            date_by_idx.append(b.dt)
            close_by_idx.append(float(b.close))

        trades_list = []
        for t in result.trades:
            dt_val = t.entry_dt
            if isinstance(dt_val, datetime):
                dt_val = dt_val.date()
            if req_beg is not None and dt_val < req_beg:
                continue
            if req_end is not None and dt_val > req_end:
                continue
            ret = (t.exit_price / t.entry_price - 1.0) if t.entry_price != 0 else 0.0
            transaction_id, feature_snapshot = _compute_feature_snapshot_for_trade(
                symbol=str(symbol),
                strat_conf=strat_conf,
                logs_by_date=logs_by_date,
                bar_idx_by_date=bar_idx_by_date,
                close_by_idx=close_by_idx,
                entry_dt=dt_val,
                exit_dt=t.exit_dt if not isinstance(t.exit_dt, datetime) else t.exit_dt.date(),
                qty=int(t.qty),
                entry_price=float(t.entry_price),
                exit_price=float(t.exit_price),
                holding_days=int(t.holding_days),
                exit_reason=str(t.exit_reason or ""),
                return_rate=float(ret),
            )
            trades_list.append({
                "entry_dt": t.entry_dt.isoformat(),
                "exit_dt": t.exit_dt.isoformat(),
                "entry_date": t.entry_dt.isoformat(),
                "exit_date": t.exit_dt.isoformat(),
                "entry_price": t.entry_price,
                "exit_price": t.exit_price,
                "qty": t.qty,
                "pnl": t.pnl,
                "return_rate": ret,
                "return_pct": ret,
                "holding_days": t.holding_days,
                "entry_reason": t.entry_reason,
                "exit_reason": t.exit_reason,
                "initial_stop": t.initial_stop,
                "trailing_stop": t.trailing_stop,
                "r_multiple": t.r_multiple,
                "entry_index_confirmed": t.entry_index_confirmed,
                "transaction_id": transaction_id,
                "feature_snapshot": feature_snapshot,
            })

        if trades_list:
            overview["avg_holding_days"] = sum(float(t.get("holding_days") or 0.0) for t in trades_list) / len(trades_list)
        else:
            overview["avg_holding_days"] = 0.0
        overview["total_trades"] = len(trades_list)

        # C. Daily Data for Charts
        # We need OHLCV + Indicators (Channel lines, etc.)
        # The strategy.signal_logs contains channel lines for every day processed.
        # But signal_logs might skip days if we filter them? 
        # Actually ChannelHFStrategy logs every day if capture_logs is True.
        
        daily_data = []
        
        for bar in symbol_bars:
            dt_str = bar.dt.isoformat()
            log_entry = logs_by_date.get(dt_str, {})
            
            item = {
                "date": dt_str,
                "open": bar.open,
                "high": bar.high,
                "low": bar.low,
                "close": bar.close,
                "volume": bar.volume,
                # Indicators from log
                "mid": log_entry.get("mid"),
                "upper": log_entry.get("upper"),
                "lower": log_entry.get("lower"),
                "slope_norm": log_entry.get("slope_norm"),
                "vol_ratio": log_entry.get("vol_ratio"),
                "channel_height": log_entry.get("channel_height"),
                "mid_room": log_entry.get("mid_room"),
                "has_position": log_entry.get("has_position", False),
                "final_signal": log_entry.get("final_signal", 0),
                "trace": log_entry.get("trace", []) # The detailed decision steps
            }
            daily_data.append(item)

        if req_beg is not None or req_end is not None:
            filtered = []
            for item in daily_data:
                try:
                    d = datetime.fromisoformat(str(item.get("date"))).date()
                except Exception:
                    continue
                if req_beg is not None and d < req_beg:
                    continue
                if req_end is not None and d > req_end:
                    continue
                filtered.append(item)
            daily_data = filtered

        rejection_details, rejection_stats, flat_stats = _generate_rejection_details_from_daily(daily_data)
        overview["filter_rejection_total"] = len(rejection_details)
        overview["filter_rejection_stats"] = flat_stats
        overview["filter_rejection_summary"] = rejection_stats.get("summary") if isinstance(rejection_stats, dict) else []
        
        # D. Equity Curve
        equity_curve = []
        for p in result.equity_curve:
            equity_curve.append({
                "date": p.dt.isoformat(),
                "value": p.equity
            })

        return {
            "status": "success",
            "overview": overview,
            "trades": trades_list,
            "rejection_details": rejection_details,
            "daily_data": daily_data,
            "equity_curve": equity_curve,
            "params": strat_params
        }

    except Exception as e:
        traceback.print_exc()
        return {"status": "error", "message": str(e)}


def reanalyze_channel_hf_trade_features(
    symbol: str,
    data_path: Path,
    index_path: Path | None,
    config: dict[str, Any],
    targets: list[dict[str, Any]],
) -> dict[str, Any]:
    try:
        beg = config.get("beg")
        end = config.get("end")

        req_beg = None
        req_end = None
        try:
            if beg:
                req_beg = datetime.fromisoformat(str(beg)).date()
        except Exception:
            req_beg = None
        try:
            if end:
                req_end = datetime.fromisoformat(str(end)).date()
        except Exception:
            req_end = None

        load_beg = beg
        if req_beg is not None:
            load_beg = (req_beg - timedelta(days=400)).isoformat()

        symbol_bars = load_bars_from_csv(data_path, symbol=symbol, beg=load_beg, end=end, validate=False)
        if not symbol_bars:
            return {"status": "error", "message": f"No data loaded for {symbol}"}

        index_bars = []
        if index_path:
            index_symbol = config.get("index_symbol", "000300.SH")
            index_bars = load_bars_from_csv(index_path, symbol=index_symbol, beg=load_beg, end=end, validate=False)

        from dataclasses import fields
        valid_fields = {f.name for f in fields(ChannelHFConfig)}
        strat_params = {k: v for k, v in config.items() if k in valid_fields}
        strat_params["capture_logs"] = True
        if "max_positions" not in strat_params:
            strat_params["max_positions"] = 5
        strat_conf = ChannelHFConfig(**strat_params)

        strategy = ChannelHFStrategy(bars=symbol_bars, config=strat_conf, index_bars=index_bars)
        engine = EventBacktestEngine(config=BacktestConfig(broker=BrokerConfig()))
        engine.run(bars=symbol_bars, strategy=strategy, benchmark_bars=index_bars, start_date=req_beg)

        logs_by_date = {log["date"]: log for log in strategy.signal_logs}
        bar_idx_by_date: dict[date, int] = {}
        close_by_idx: list[float] = []
        for i, b in enumerate(symbol_bars):
            bar_idx_by_date[b.dt] = i
            close_by_idx.append(float(b.close))

        out = []
        for it in (targets or []):
            try:
                entry_dt_raw = it.get("entry_dt") or it.get("entry_date")
                exit_dt_raw = it.get("exit_dt") or it.get("exit_date")
                if not entry_dt_raw or not exit_dt_raw:
                    continue
                entry_dt = datetime.fromisoformat(str(entry_dt_raw)).date()
                exit_dt = datetime.fromisoformat(str(exit_dt_raw)).date()
                if req_beg is not None and entry_dt < req_beg:
                    continue
                if req_end is not None and entry_dt > req_end:
                    continue

                qty = int(it.get("qty") or 0)
                entry_price = float(it.get("entry_price") or 0.0)
                exit_price = float(it.get("exit_price") or 0.0)
                holding_days = int(it.get("holding_days") or 0)
                exit_reason = str(it.get("exit_reason") or "")
                return_rate = float(it.get("return_rate") or 0.0)
            except Exception:
                continue

            transaction_id, feature_snapshot = _compute_feature_snapshot_for_trade(
                symbol=str(symbol),
                strat_conf=strat_conf,
                logs_by_date=logs_by_date,
                bar_idx_by_date=bar_idx_by_date,
                close_by_idx=close_by_idx,
                entry_dt=entry_dt,
                exit_dt=exit_dt,
                qty=qty,
                entry_price=entry_price,
                exit_price=exit_price,
                holding_days=holding_days,
                exit_reason=exit_reason,
                return_rate=return_rate,
            )
            out.append({"transaction_id": transaction_id, "feature_snapshot": feature_snapshot})

        return {"status": "success", "symbol": str(symbol), "count": len(out), "items": out}
    except Exception as e:
        traceback.print_exc()
        return {"status": "error", "message": str(e)}
