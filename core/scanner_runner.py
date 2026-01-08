import time
import traceback
import statistics
from datetime import datetime, date
from functools import lru_cache
from pathlib import Path
from typing import Any

from .batch_runner import resolve_file_path
from .data import load_bars_from_csv, load_bars_with_realtime
from .event_engine import EventBacktestEngine
from .fundamentals import FundamentalsStore
from .platform_breakout import PlatformBreakoutConfig, PlatformBreakoutStrategy
from .channel_hf import ChannelHFConfig, ChannelHFStrategy
from .types import BacktestConfig, Bar
from .universe import Universe


@lru_cache(maxsize=8)
def _load_universe_cached(path_str: str) -> Universe | None:
    p = Path(path_str)
    if not p.exists():
        return None
    return Universe.load_csv(p)


@lru_cache(maxsize=8)
def _load_fundamentals_cached(path_str: str) -> FundamentalsStore | None:
    p = Path(path_str)
    if not p.exists():
        return None
    return FundamentalsStore.load_csv(p)


@lru_cache(maxsize=32)
def _load_bars_from_csv_cached(path_str: str, symbol: str, beg: str | None, end: str | None) -> tuple[Bar, ...]:
    p = Path(path_str)
    if not p.exists():
        return tuple()
    bars = load_bars_from_csv(p, symbol=symbol, beg=beg, end=end, validate=False)
    return tuple(bars or [])

def scan_strategy_for_symbol_path(
    symbol: str,
    data_path: Path,
    index_path: Path | None,
    config: dict[str, Any],
) -> dict[str, Any]:
    """
    Run strategy for a single symbol and return pending entry signals on the last day.
    """
    try:
        use_realtime = config.get('use_realtime', False)
        if use_realtime:
            symbol_bars = load_bars_with_realtime(data_path, symbol=symbol, validate=False)
        else:
            symbol_bars = load_bars_from_csv(data_path, symbol=symbol, validate=False)
            
        if not symbol_bars:
             return {"symbol": symbol, "error": "No data loaded"}

        last_date = symbol_bars[-1].dt

        # Load index bars if needed
        benchmark_bars = []
        if index_path:
            index_symbol = config.get('index_symbol', '000300.SH')
            benchmark_bars = list(_load_bars_from_csv_cached(str(index_path), str(index_symbol), None, None))
            # Align dates if possible, or just pass them all

        bars = symbol_bars + benchmark_bars if benchmark_bars else symbol_bars
            
        # Create config
        cfg = BacktestConfig(
            initial_cash=config.get('initial_cash', 1000000.0),
        )
        
        universe_obj = None
        fundamentals_obj = None
        if config.get("universe"):
            u_path = resolve_file_path(str(config.get("universe")))
            if u_path is not None:
                universe_obj = _load_universe_cached(str(u_path))

        if config.get("fundamentals"):
            f_path = resolve_file_path(str(config.get("fundamentals")))
            if f_path is not None:
                fundamentals_obj = _load_fundamentals_cached(str(f_path))

        # Strategy Config
        pcfg = PlatformBreakoutConfig(
            platform_min_days=config.get('platform_min', 7),
            platform_max_days=config.get('platform_max', 360),
            platform_max_amplitude=config.get('platform_amp', 0.45),
            volume_multiple=config.get('vol_mult', 1.5),
            initial_stop_atr_mult=config.get('atr_stop_mult', 1.5),
            trailing_activate_profit=config.get('trailing_profit', 0.15),
            trailing_atr_mult=config.get('trailing_atr_mult', 2.0),
            breakout_min_pct=config.get('breakout_min_pct', 0.03),
            gap_open_max_pct=config.get('gap_open_max_pct', 0.01),
            initial_stop_pct=config.get('initial_stop_pct', 0.0),
            risk_per_trade=config.get('risk_pct', 0.01),
            max_symbol_exposure=config.get('max_symbol', 0.20),
            max_total_exposure=config.get('max_total', 0.80),
            account_drawdown_pause=config.get('dd_pause', 0.15),
            loss_streak_pause_count=config.get('loss_streak_count', 3),
            loss_streak_pause_pct=config.get('loss_streak_pct', 0.05),
            platform_max_single_day_pct=config.get('platform_max_single_day_pct', 0.30),
            platform_min_slope=config.get('platform_min_slope', -0.01),
            platform_max_slope=config.get('platform_max_slope', 0.01),
            max_symbols_per_day=config.get('max_symbols_per_day', 5),
            enable_trend_exit=config.get('enable_trend_exit', False),
            enable_pe_filter=config.get('enable_pe_filter', False),
            require_index_confirm=config.get('require_index_confirm', False),
            index_symbol=config.get('index_symbol', '000300.SH'),
            stop_atr_days=config.get('atr_days', 14),
            max_holding_days=config.get('max_holding_days', 250),
            pe_ttm_max=config.get('pe_ttm_max', 60.0),
            min_avg_amount_20d=config.get('min_avg_amount_20d', 0.0),
            min_market_cap=config.get('min_market_cap', 0.0),
            auto_profile_enable=config.get('auto_profile_enable', False),
            auto_profile_mcap_threshold=config.get('auto_profile_mcap_threshold', 200.0),
        )
        
        strategy = PlatformBreakoutStrategy(
            bars=bars,
            config=pcfg,
            universe=universe_obj,
            fundamentals=fundamentals_obj,
        )
        engine = EventBacktestEngine(config=cfg)
        result = engine.run(bars=bars, strategy=strategy, benchmark_bars=benchmark_bars)
        
        # Check for signals in the last N trading days
        signals = []
        scan_recent_days = config.get('scan_recent_days', 30)
        
        # Get threshold date using trading bars
        if len(symbol_bars) >= scan_recent_days:
            threshold_dt = symbol_bars[-scan_recent_days].dt
        else:
            threshold_dt = symbol_bars[0].dt if symbol_bars else last_date
        
        # Filter from all_entry_intents
        latest_signal = None
        for intent in strategy.all_entry_intents:
            if intent.breakout_dt >= threshold_dt:
                # Calculate Risk/Reward Ratio
                risk = intent.breakout_price - intent.initial_stop
                rr_ratio = 0.0
                if risk > 0:
                    rr_ratio = (intent.platform_high - intent.platform_low) / risk
                
                signal = {
                    "symbol": intent.symbol,
                    "date": intent.breakout_dt.isoformat(),
                    "price": intent.breakout_price,
                    "stop": intent.initial_stop,
                    "risk": intent.risk_per_share,
                    "platform_high": intent.platform_high,
                    "platform_low": intent.platform_low,
                    "risk_reward_ratio": round(rr_ratio, 2)
                }
                # Update to keep the most recent signal
                if not latest_signal or intent.breakout_dt > datetime.fromisoformat(latest_signal["date"]).date():
                    latest_signal = signal
        
        if latest_signal:
            signals.append(latest_signal)

        # Get last few decision logs for context
        recent_logs = strategy.decision_logs[-5:] if strategy.decision_logs else []
        
        return {
            "symbol": symbol,
            "last_date": last_date.isoformat(),
            "signals": signals,
            "logs": recent_logs,
            "data_anomalies": result.data_anomalies
        }
        
    except Exception as e:
        traceback.print_exc()
        return {"symbol": symbol, "error": str(e)}


def backtest_channel_hf_for_symbol_path(
    symbol: str,
    data_path: Path,
    index_path: Path | None,
    config: dict[str, Any],
) -> dict[str, Any]:
    """Run Channel HF backtest for a single symbol and return metrics (plus optional detail)."""
    try:
        beg = config.get("beg") or None
        end = config.get("end") or None
        detail = bool(config.get("detail"))

        use_realtime = bool(config.get("use_realtime", False))
        if use_realtime and not beg and not end:
            bars = load_bars_with_realtime(data_path, symbol=symbol, validate=False)
        else:
            bars = load_bars_from_csv(data_path, symbol=symbol, beg=beg, end=end, validate=False)

        if not bars:
            return {"symbol": symbol, "error": "No data loaded"}

        benchmark_bars: list = []
        if index_path:
            index_symbol = config.get("index_symbol", "000300.SH")
            benchmark_bars = list(_load_bars_from_csv_cached(str(index_path), str(index_symbol), beg, end))

        stop_mul = config.get("stop_loss_mul", None)
        if stop_mul is None:
            stop_mul = config.get("stop_loss_pct", 0.97)

        hcfg = ChannelHFConfig(
            channel_period=config.get("channel_period", 20),
            buy_touch_eps=config.get("buy_touch_eps", 0.005),
            sell_trigger_eps=config.get("sell_trigger_eps", 0.005),
            sell_target_mode=config.get("sell_target_mode", "mid_up"),
            channel_break_eps=config.get("channel_break_eps", 0.02),
            entry_fill_eps=config.get("entry_fill_eps", 0.002),
            exit_fill_eps=config.get("exit_fill_eps", 0.002),
            stop_loss_mul=stop_mul,
            stop_loss_on_close=config.get("stop_loss_on_close", True),
            stop_loss_panic_eps=config.get("stop_loss_panic_eps", 0.02),
            max_holding_days=config.get("max_holding_days", 20),
            cooling_period=config.get("cooling_period", 5),
            slope_abs_max=config.get("slope_abs_max", 0.01),
            min_slope_norm=config.get("min_slope_norm", -1.0),
            vol_shrink_threshold=config.get("vol_shrink_threshold", 0.9),
            vol_shrink_min=config.get("vol_shrink_min", None),
            vol_shrink_max=config.get("vol_shrink_max", None),
            min_channel_height=config.get("min_channel_height", 0.05),
            min_mid_room=config.get("min_mid_room", 0.015),
            min_mid_profit_pct=config.get("min_mid_profit_pct", 0.0),
            min_rr_to_mid=config.get("min_rr_to_mid", 0.0),
            require_index_condition=config.get("require_index_condition", True),
            index_bear_exit=config.get("index_bear_exit", True),
            fill_at_close=config.get("fill_at_close", True),
            trend_ma_period=config.get("trend_ma_period", 0),
            index_trend_ma_period=config.get("index_trend_ma_period", 0),
            require_rebound=config.get("require_rebound", False),
            require_green=config.get("require_green", False),
            index_symbol=config.get("index_symbol", "000300.SH"),
            capture_logs=detail,
        )

        initial_cash = config.get("initial_cash", 1_000_000.0)
        try:
            initial_cash = float(initial_cash)
        except Exception:
            initial_cash = 1_000_000.0

        engine = EventBacktestEngine(config=BacktestConfig(initial_cash=initial_cash))
        strategy = ChannelHFStrategy(bars=bars, config=hcfg, index_bars=benchmark_bars)
        result = engine.run(bars=bars, strategy=strategy, benchmark_bars=benchmark_bars)

        if detail:
            d = result.to_dict()
            d["symbol"] = symbol
            d["beg"] = beg
            d["end"] = end
            return d

        m = result.metrics

        dd_dur = None
        if m.max_drawdown_detail is not None:
            dd_dur = m.max_drawdown_detail.drawdown_duration

        calc_score = config.get("calc_score", False)
        if isinstance(calc_score, str):
            calc_score = calc_score.strip().lower() in ("1", "true", "yes", "y", "on")
        calc_score = bool(calc_score)

        calc_robust = config.get("calc_robust", False)
        if isinstance(calc_robust, str):
            calc_robust = calc_robust.strip().lower() in ("1", "true", "yes", "y", "on")
        calc_robust = bool(calc_robust)

        score = None
        score_mean = None
        score_std = None
        score_robust = None

        robust_segments = 0

        if calc_score:
            score = (m.sharpe * 20.0) + (m.cagr * 100.0) + (m.win_rate * 50.0) - (m.max_drawdown * 50.0)

            if calc_robust:
                robust_segments = config.get("robust_segments", 0)
                try:
                    robust_segments = int(robust_segments)
                except Exception:
                    robust_segments = 0

                seg_scores: list[float] = []
                if robust_segments >= 2 and len(bars) >= 2:
                    n = len(bars)
                    for k in range(robust_segments):
                        a = (k * n) // robust_segments
                        b = ((k + 1) * n) // robust_segments - 1
                        if a < 0:
                            a = 0
                        if b >= n:
                            b = n - 1
                        if a > b:
                            continue

                        seg_beg_dt = bars[a].dt
                        seg_end_dt = bars[b].dt

                        seg_bars = [x for x in bars if seg_beg_dt <= x.dt <= seg_end_dt]
                        if not seg_bars:
                            continue

                        seg_benchmark = [x for x in benchmark_bars if seg_beg_dt <= x.dt <= seg_end_dt] if benchmark_bars else []

                        seg_engine = EventBacktestEngine(config=BacktestConfig(initial_cash=initial_cash))
                        seg_strategy = ChannelHFStrategy(bars=seg_bars, config=hcfg, index_bars=seg_benchmark)
                        seg_res = seg_engine.run(bars=seg_bars, strategy=seg_strategy, benchmark_bars=seg_benchmark)
                        sm = seg_res.metrics
                        seg_scores.append((sm.sharpe * 20.0) + (sm.cagr * 100.0) + (sm.win_rate * 50.0) - (sm.max_drawdown * 50.0))

                score_mean = statistics.mean(seg_scores) if seg_scores else None
                score_std = statistics.pstdev(seg_scores) if len(seg_scores) > 1 else (0.0 if seg_scores else None)
                score_robust = (score_mean - score_std) if (score_mean is not None and score_std is not None) else None

        return {
            "symbol": symbol,
            "beg": beg,
            "end": end,
            "total_return": m.total_return,
            "annualized_return": m.cagr,
            "max_drawdown": m.max_drawdown,
            "drawdown_duration": dd_dur,
            "sharpe_ratio": m.sharpe,
            "sortino_ratio": m.sortino,
            "calmar_ratio": m.calmar,
            "tail_ratio": m.tail_ratio,
            "expectancy": m.expectancy,
            "profit_factor": m.profit_factor,
            "largest_loss": m.largest_loss,
            "win_rate": m.win_rate,
            "trades": m.trade_count,
            "final_equity": m.final_equity,
            "anomalies": len(result.data_anomalies or []),
            "score": score,
            "robust_segments": robust_segments if robust_segments >= 2 else 0,
            "score_mean": score_mean,
            "score_std": score_std,
            "score_robust": score_robust,
            "sell_target_mode": hcfg.sell_target_mode,
        }

    except Exception as e:
        traceback.print_exc()
        return {"symbol": symbol, "error": str(e)}

def scan_channel_hf_for_symbol_path(
    symbol: str,
    data_path: Path,
    index_path: Path | None,
    config: dict[str, Any],
) -> dict[str, Any]:
    """
    Run Channel HF strategy for a single symbol and return context.
    """
    try:
        beg = config.get("beg") or None
        end = config.get("end") or None

        bars = load_bars_from_csv(data_path, symbol=symbol, beg=beg, end=end, validate=False)
        if not bars:
            return {"symbol": symbol, "error": "No data loaded"}

        last_date = bars[-1].dt

        # Load index bars if needed
        benchmark_bars = []
        if index_path:
            index_symbol = config.get("index_symbol", "000300.SH")
            benchmark_bars = list(_load_bars_from_csv_cached(str(index_path), str(index_symbol), beg, end))

        # Strategy Config
        stop_mul = config.get("stop_loss_mul", None)
        if stop_mul is None:
            stop_mul = config.get("stop_loss_pct", 0.97)

        hcfg = ChannelHFConfig(
            channel_period=config.get("channel_period", 20),
            buy_touch_eps=config.get("buy_touch_eps", 0.005),
            sell_trigger_eps=config.get("sell_trigger_eps", 0.005),
            sell_target_mode=config.get("sell_target_mode", "mid_up"),
            channel_break_eps=config.get("channel_break_eps", 0.02),
            entry_fill_eps=config.get("entry_fill_eps", 0.002),
            exit_fill_eps=config.get("exit_fill_eps", 0.002),
            stop_loss_mul=stop_mul,
            stop_loss_on_close=config.get("stop_loss_on_close", True),
            stop_loss_panic_eps=config.get("stop_loss_panic_eps", 0.02),
            max_holding_days=config.get("max_holding_days", 20),
            cooling_period=config.get("cooling_period", 5),
            slope_abs_max=config.get("slope_abs_max", 0.01),
            min_slope_norm=config.get("min_slope_norm", -1.0),
            vol_shrink_threshold=config.get("vol_shrink_threshold", 0.9),
            vol_shrink_min=config.get("vol_shrink_min", None),
            vol_shrink_max=config.get("vol_shrink_max", None),
            min_channel_height=config.get("min_channel_height", 0.05),
            min_mid_room=config.get("min_mid_room", 0.015),
            min_mid_profit_pct=config.get("min_mid_profit_pct", 0.0),
            min_rr_to_mid=config.get("min_rr_to_mid", 0.0),
            require_index_condition=config.get("require_index_condition", True),
            index_bear_exit=config.get("index_bear_exit", True),
            fill_at_close=config.get("fill_at_close", True),
            pivot_k=config.get("pivot_k", 2),
            pivot_drop_min=config.get("pivot_drop_min", 0.03),
            capture_logs=True,
        )

        strategy = ChannelHFStrategy(bars=bars, config=hcfg, index_bars=benchmark_bars)
        engine = EventBacktestEngine(config=BacktestConfig())
        engine.run(bars=bars, strategy=strategy, benchmark_bars=benchmark_bars)

        recent_n = config.get("scan_recent_days", 1)
        try:
            recent_n = int(recent_n)
        except Exception:
            recent_n = 1
        recent_n = max(1, recent_n)

        threshold_dt = bars[0].dt
        if len(bars) >= recent_n:
            threshold_dt = bars[-recent_n].dt

        latest_signal_log: dict[str, Any] | None = None
        if strategy.signal_logs:
            for log in reversed(strategy.signal_logs):
                if log.get("symbol") != symbol:
                    continue
                if log.get("final_signal") not in (1, -1):
                    continue
                dt_str = str(log.get("date") or "")
                try:
                    dt_val = datetime.fromisoformat(dt_str).date()
                except Exception:
                    continue
                if dt_val < threshold_dt:
                    continue
                latest_signal_log = log
                break

        return {
            "symbol": symbol,
            "last_date": last_date.isoformat(),
            "env": latest_signal_log or {},
            "signals": [latest_signal_log] if latest_signal_log else [],
        }

    except Exception as e:
        traceback.print_exc()
        return {"symbol": symbol, "error": str(e)}
