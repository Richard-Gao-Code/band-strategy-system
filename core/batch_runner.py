from __future__ import annotations

import time
import traceback
from functools import lru_cache
from pathlib import Path
from typing import Any

from .data import load_bars_from_csv
from .event_engine import EventBacktestEngine
from .fundamentals import FundamentalsStore
from .platform_breakout import PlatformBreakoutConfig, PlatformBreakoutStrategy
from .types import BacktestConfig
from .universe import Universe


def resolve_any_path(path_str: str) -> Path | None:
    """Resolve a path (file or directory), checking common locations."""
    if not path_str:
        return None
    
    p = Path(path_str)
    
    # Handle leading slash on Windows (treat as relative to project root)
    if str(p).startswith('\\') or str(p).startswith('/'):
        p = Path(*p.parts[1:])
    
    # 1. Check absolute or direct relative path
    if p.exists():
        return p.resolve()
    
    # 2. Check relative to project root (ths_backtest)
    # If we are in webui, project root is ..
    cwd = Path.cwd()
    root_candidates = [cwd, cwd.parent]
    
    for root in root_candidates:
        # Try root/data
        try_p = root / "data" / p if p.name != "data" else root / p
        if try_p.exists():
            return try_p.resolve()
        
        # Try root/ths_backtest/data
        try_p = root / "ths_backtest" / "data" / p if p.name != "data" else root / "ths_backtest" / p
        if try_p.exists():
            return try_p.resolve()

    # 3. Check other common subdirectories
    for sub in ["", "ths_backtest", "webui", "ths_backtest/data", "data"]:
        try_p = Path(sub) / p if sub else p
        if try_p.exists():
            return try_p.resolve()
            
    # 4. Look up parent levels
    for i in range(min(5, len(cwd.parents) + 1)):
        parent = cwd.parents[i] if i < len(cwd.parents) else cwd
        try_p = parent / p
        if try_p.exists():
            return try_p.resolve()
            
    return None

def resolve_file_path(path_str: str) -> Path | None:
    """Resolve a file path, checking common locations."""
    res = resolve_any_path(path_str)
    if res and res.is_file():
        return res
    return None


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

import sys

def resolve_data_paths(
    symbols: list[str], data: str | None, data_dir: str | None
) -> dict[str, Path]:
    """Helper to resolve file paths for multiple symbols without loading data"""
    paths = {}
    
    print(f"DEBUG: resolve_data_paths(symbols={symbols}, data={data}, data_dir={data_dir})", file=sys.stderr)
    
    # 1. Determine base directory or file
    base_dir = None
    single_file = None
    
    if data_dir:
        base_dir = resolve_any_path(data_dir)
        print(f"DEBUG: Resolved data_dir {data_dir} -> {base_dir}", file=sys.stderr)
                 
    elif data:
        # Check if data is a pattern like "data/{symbol}.csv"
        if "{symbol}" in data:
            # Use the directory containing the pattern as base_dir
            p = Path(data)
            parent_str = str(p.parent)
            # Special case: if parent is just "/" or "\", it means project root data
            if parent_str in ["\\", "/"]:
                parent_str = "data"
            
            resolved_parent = resolve_any_path(parent_str)
            print(f"DEBUG: Pattern {data} parent {parent_str} -> {resolved_parent}", file=sys.stderr)
            if resolved_parent:
                base_dir = resolved_parent
            else:
                base_dir = p.parent
        else:
            resolved_data = resolve_file_path(data)
            print(f"DEBUG: Single data {data} -> {resolved_data}", file=sys.stderr)
            if resolved_data:
                 p = resolved_data
                 if p.is_dir():
                     base_dir = p
                 elif p.is_file():
                     if len(symbols) > 1:
                         base_dir = p.parent
                     else:
                         single_file = p
            else:
                 p = Path(data)
                 if p.is_dir():
                    base_dir = p

    print(f"DEBUG: Final base_dir={base_dir}, single_file={single_file}", file=sys.stderr)

    # 2. Resolve paths
    if single_file and len(symbols) == 1:
        paths[symbols[0]] = single_file
    elif base_dir:
        if not base_dir.exists():
            print(f"WARNING: base_dir {base_dir} does not exist", file=sys.stderr)
        
        for s in symbols:
            # Try exact match first
            s_path = base_dir / f"{s}.csv"
            if s_path.exists():
                paths[s] = s_path
                continue
            
            # Try with prefix if common (e.g. sh, sz)
            for prefix in ["sh", "sz", "bj"]:
                s_path = base_dir / f"{prefix}{s}.csv"
                if s_path.exists():
                    paths[s] = s_path
                    break
            if s in paths: continue

            # Try loose match (e.g. sh600975.csv for 600975)
            matches = list(base_dir.glob(f"*{s}*.csv"))
            if matches:
                best_match = min(matches, key=lambda x: len(str(x.name)))
                paths[s] = best_match
            else:
                print(f"Warning: No data found for symbol {s} in {base_dir}", file=sys.stderr)
    
    print(f"DEBUG: Found paths for symbols: {list(paths.keys())}", file=sys.stderr)
    return paths

def load_all_data_for_symbols(
    symbols: list[str],
    data: str | None,
    data_dir: str | None,
    beg: str | None = None,
    end: str | None = None,
) -> list:
    """Load data for all symbols into a single list"""
    paths = resolve_data_paths(symbols, data, data_dir)
    all_bars = []
    for symbol, path in paths.items():
        bars = load_bars_from_csv(path, symbol=symbol, beg=beg, end=end)
        all_bars.extend(bars)
    return all_bars

def run_strategy_for_symbol_path(
    symbol: str,
    data_path: Path,
    index_path: Path | None,
    config: dict[str, Any],
) -> dict[str, Any]:
    """Run strategy for a single symbol loading data in-process.
    
    Args:
        symbol: Stock symbol
        data_path: Path to stock CSV data
        index_path: Path to index CSV data (optional)
        config: Configuration dictionary (from RunReq)
    """
    try:
        t0 = time.time()
        beg = config.get("beg") or None
        end = config.get("end") or None

        # Load bars
        bars = load_bars_from_csv(data_path, symbol=symbol, beg=beg, end=end)

        # Load index bars if needed
        benchmark_bars = []
        if index_path:
            # config['index_symbol'] should be present
            index_symbol = config.get('index_symbol', '000300.SH')
            benchmark_bars = load_bars_from_csv(index_path, symbol=index_symbol, beg=beg, end=end)
            bars.extend(benchmark_bars)
            
        t1 = time.time()
        
        # Create config
        cfg = BacktestConfig(
            initial_cash=config.get('initial_cash', 1000000.0),
            broker=type(BacktestConfig(initial_cash=config.get('initial_cash', 1000000.0)).broker)(
                commission_rate=config.get('commission_rate', 0.0003),
                slippage_bps=config.get('slippage_bps', 2.0),
                min_commission=config.get('min_commission', 5.0),
                stamp_duty_rate=config.get('stamp_duty_rate', 0.0005),
                slippage_rate=config.get('slippage_rate', 0.0001),
            ),
        )
        
        # Create Strategy Config
        strategy_name = config.get('strategy', 'platform_breakout')
        if strategy_name == "platform_breakout":
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

            pcfg = PlatformBreakoutConfig(
                platform_min_days=config.get('platform_min', 20),
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
                platform_min_slope=config.get('platform_min_slope', -0.005),
                platform_max_slope=config.get('platform_max_slope', 0.005),
                max_symbols_per_day=config.get('max_symbols_per_day', 5),
                enable_trend_exit=config.get('enable_trend_exit', False),
                enable_pe_filter=config.get('enable_pe_filter', False),
                require_index_confirm=config.get('require_index_confirm', True),
                index_symbol=config.get('index_symbol', '000300.SH'),
                stop_atr_days=config.get('atr_days', 14),
                max_holding_days=config.get('max_holding_days', 20),
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
        else:
            return {"symbol": symbol, "error": f"Unsupported strategy: {strategy_name}"}

        # Run Engine
        engine = EventBacktestEngine(config=cfg)
        result = engine.run(bars=bars, strategy=strategy, benchmark_bars=benchmark_bars)
        m = result.metrics
        
        t2 = time.time()
        print(f"[Worker] {symbol}: Load {t1-t0:.2f}s, Run {t2-t1:.2f}s")
        
        detail = result.to_dict()
        return {
            "symbol": symbol,
            "total_return": m.total_return,
            "annualized_return": m.cagr,
            "max_drawdown": m.max_drawdown,
            "sharpe_ratio": m.sharpe,
            "win_rate": m.win_rate,
            "trades": m.trade_count,
            "final_equity": m.final_equity,
            "detail": detail,
        }
    except Exception as e:
        traceback.print_exc()
        return {"symbol": symbol, "error": str(e)}