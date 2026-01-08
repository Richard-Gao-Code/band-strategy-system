import sys
import os
import random
from pathlib import Path
from datetime import date
import logging

import json

# Add current directory to path
sys.path.append(str(Path(__file__).parent))

from dataclasses import fields, replace

from core.data import load_bars_from_csv
from core.channel_hf import ChannelHFStrategy, ChannelHFConfig
from core.event_engine import EventBacktestEngine
from core.types import BacktestConfig, BrokerConfig

def load_config():
    """Load configuration from config.json if it exists"""
    config_path = Path(__file__).parent / "config.json"
    if config_path.exists():
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print(f"Warning: Failed to load config.json: {e}")
    return {}

def main():
    # Setup logging
    logging.basicConfig(level=logging.INFO, format='%(message)s')
    
    # Load UI Config
    ui_config = load_config()
    print(f"Loaded UI Config: {ui_config}")
    
    # 1. List all CSV files
    data_dir = Path(__file__).parent / "data"
    if not data_dir.exists():
        print(f"Error: Data directory {data_dir.resolve()} not found.")
        return

    all_files = list(data_dir.glob("*.csv"))
    # Filter out index and non-stock files (assuming stock codes start with digit and not 000300)
    stock_files = [f for f in all_files if f.name[0].isdigit() and "000300.SH" not in f.name]
    
    if len(stock_files) < 3:
        print(f"Error: Not enough stock files found (found {len(stock_files)}).")
        return

    desired_n = 10
    random.seed(42)
    random.shuffle(stock_files)

    selected_files: list[Path] = []
    selected_symbols: list[str] = []

    print(f"Selecting {desired_n} stocks (seed=42)...")

    # 3. Load Index Data (000300.SH)
    index_path = data_dir / "000300.SH.csv"
    if not index_path.exists():
        print("Error: Index file 000300.SH.csv not found.")
        return
        
    beg_date = "2023-10-01"
    end_date = "2024-01-31"
    
    print(f"Loading index data for {beg_date} to {end_date}...")
    index_bars = load_bars_from_csv(index_path, symbol="000300.SH", beg=beg_date, end=end_date)
    if not index_bars:
        print("Error: Index bars are empty.")
        return
    print(f"Loaded {len(index_bars)} index bars.")

    index_calendar = [b.dt for b in index_bars]
    index_calendar_set = set(index_calendar)

    bars_by_symbol_by_dt: dict[str, dict] = {}

    for f in stock_files:
        if len(selected_files) >= desired_n:
            break
        symbol = f.name.replace(".csv", "")
        bars = load_bars_from_csv(f, symbol=symbol, beg=beg_date, end=end_date)
        if not bars:
            continue
            
        # Relaxed check: Just ensure we have data for the first day (to avoid IPO mid-test issues for now)
        # and reasonable coverage (>80%)
        bars_by_dt = {b.dt: b for b in bars}
        
        if index_calendar[0] not in bars_by_dt:
            # Skip if no data on start date (simplification)
            continue
            
        if len(bars) < len(index_calendar) * 0.8:
            continue

        # Forward Fill for Alignment
        aligned_bars_dict = {}
        last_bar = None
        valid = True
        
        for dt_val in index_calendar:
            if dt_val in bars_by_dt:
                last_bar = bars_by_dt[dt_val]
                aligned_bars_dict[dt_val] = last_bar
            elif last_bar:
                # Suspension: Forward fill with vol=0
                filled_bar = replace(last_bar, dt=dt_val, volume=0, open=last_bar.close, high=last_bar.close, low=last_bar.close)
                aligned_bars_dict[dt_val] = filled_bar
            else:
                # Missing at start even though we checked? Should not happen given check above
                valid = False
                break
        
        if valid:
            selected_files.append(f)
            selected_symbols.append(symbol)
            bars_by_symbol_by_dt[symbol] = aligned_bars_dict

    if len(selected_symbols) < desired_n:
        print(f"Warning: Only found {len(selected_symbols)} stocks (wanted {desired_n}). Continuing...")

    print(f"Selected stocks: {selected_symbols}")

    all_bars = []
    for dt_val in index_calendar:
        for sym in selected_symbols:
            all_bars.append(bars_by_symbol_by_dt[sym][dt_val])

    allowed = {f.name for f in fields(ChannelHFConfig)}
    clean_ui_config = {k: v for k, v in ui_config.items() if k in allowed}

    strat_config_dict = clean_ui_config.copy()
    
    # Defaults (only if not present in UI config)
    defaults = {
        "capture_logs": False,
        "max_positions": 5,
        "max_position_pct": 0.10,
        "cooling_period": 5,
        "max_holding_days": 20,
        "sell_target_mode": "mid_up",
        "sell_trigger_eps": 0.005,
        "stop_loss_mul": 0.96,
        "stop_loss_on_close": False,
        "channel_break_eps": 0.02,
    }
    
    for k, v in defaults.items():
        if k not in strat_config_dict:
            strat_config_dict[k] = v

    print(f"DEBUG: sell_target_mode = {strat_config_dict.get('sell_target_mode')}")


    # Ensure critical overrides if needed (optional, but let's trust UI config mostly)
    # strat_config_dict["capture_logs"] = False # Force logs off for performance if desired

    strat_config = ChannelHFConfig(**strat_config_dict)

    strategy = ChannelHFStrategy(bars=all_bars, config=strat_config, index_bars=index_bars)

    engine_config = BacktestConfig(
        initial_cash=1_000_000.0,
        broker=BrokerConfig(commission_rate=0.0003)
    )

    engine = EventBacktestEngine(config=engine_config)
    result = engine.run(bars=all_bars, strategy=strategy, benchmark_bars=index_bars)

    trades = list(result.trades or [])
    trades.sort(key=lambda t: (t.exit_dt or t.entry_dt))

    trade_count = len(trades)
    win_trades = [t for t in trades if float(t.pnl) > 0]
    win_count = len(win_trades)
    win_rate = (win_count / trade_count) if trade_count else 0.0

    avg_holding_days = (sum(float(t.holding_days) for t in trades) / trade_count) if trade_count else 0.0

    best_ret = 0.0
    worst_ret = 0.0
    if trades:
        rets = [((float(t.exit_price) / float(t.entry_price)) - 1.0) for t in trades if float(t.entry_price) > 0]
        if rets:
            best_ret = max(rets)
            worst_ret = min(rets)

    max_consec_win = 0
    max_consec_loss = 0
    cur_w = 0
    cur_l = 0
    for t in trades:
        if float(t.pnl) > 0:
            cur_w += 1
            cur_l = 0
        elif float(t.pnl) < 0:
            cur_l += 1
            cur_w = 0
        else:
            cur_w = 0
            cur_l = 0
        if cur_w > max_consec_win:
            max_consec_win = cur_w
        if cur_l > max_consec_loss:
            max_consec_loss = cur_l

    util_avg = None
    try:
        util_avg = float(result.validation_data.get("engine", {}).get("utilization", {}).get("avg"))
    except Exception:
        util_avg = None

    print("\n=== 平衡型参数小规模回测结果 ===")
    print(f"测试期间：{beg_date} 至 {end_date}")
    print(f"测试股票：{len(selected_symbols)}只")
    print("初始资金：1,000,000")

    print("\n[1] 交易统计：")
    print(f"- 总交易次数：{trade_count}次")
    print(f"- 盈利交易：{win_count}次（胜率：{win_rate*100:.2f}%）")
    print(f"- 平均持仓天数：{avg_holding_days:.1f}天")
    print(f"- 盈亏比：{result.metrics.win_loss_ratio:.2f}（平均盈/平均亏）")

    print("\n[2] 绩效指标：")
    print(f"- 期末资金：{result.metrics.final_equity:,.2f}")
    print(f"- 总收益率：{result.metrics.total_return*100:.2f}%")
    print(f"- 年化收益率：{result.metrics.cagr*100:.2f}%")
    print(f"- 最大回撤：{result.metrics.max_drawdown*100:.2f}%")
    if util_avg is not None:
        print(f"- 资金使用率（均值）：{util_avg*100:.2f}%")

    print("\n[3] 关键观察：")
    print(f"- 最佳单笔收益：{best_ret*100:+.2f}%")
    print(f"- 最差单笔收益：{worst_ret*100:+.2f}%")
    print(f"- 最大连续盈利：{max_consec_win}次")
    print(f"- 最大连续亏损：{max_consec_loss}次")

    print("\n[4] 交易明细：")
    print(f"{'代码':<10} {'入场日期':<12} {'出场日期':<12} {'方向':<6} {'数量':<8} {'入场价':<10} {'出场价':<10} {'盈亏':<12} {'收益率':<10} {'持仓天数':<8} {'入场原因':<15} {'出场原因':<15}")
    print("-" * 130)
    for t in trades:
        pnl_pct = (t.exit_price - t.entry_price) / t.entry_price if t.entry_price else 0
        print(f"{t.symbol:<10} {str(t.entry_dt):<12} {str(t.exit_dt):<12} {'做多':<6} {str(t.qty):<8} {t.entry_price:<10.2f} {t.exit_price:<10.2f} {t.pnl:<12.2f} {pnl_pct*100:<9.2f}% {t.holding_days:<8} {t.entry_reason:<15} {t.exit_reason:<15}")

    return


if __name__ == "__main__":
    main()