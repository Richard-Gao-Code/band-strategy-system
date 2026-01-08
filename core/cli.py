from __future__ import annotations

import argparse
import json
import random
import statistics
from concurrent.futures import ProcessPoolExecutor, as_completed
from datetime import datetime
from itertools import product
from pathlib import Path

from .data import (
    fetch_daily_bars_eastmoney,
    load_bars_from_csv,
    load_bars_from_csv_dir,
    write_bars_to_csv,
)
from .engine import BacktestEngine
from .event_engine import EventBacktestEngine
from .fundamentals import FundamentalsStore
from .platform_breakout import PlatformBreakoutConfig, PlatformBreakoutStrategy
from .strategy import (
    BreakoutStrategy,
    MovingAverageCrossStrategy,
    RiskParams,
)
from .types import BacktestConfig, BrokerConfig
from .universe import Universe
from .channel_hf import ChannelHFConfig, ChannelHFStrategy


def _build_parser() -> argparse.ArgumentParser:
    """构建命令行参数解析器"""
    parser = argparse.ArgumentParser(
        prog="quantbt",
        description="量化交易回测框架 - 命令行工具",
        epilog="使用示例: quantbt run --strategy ma_cross --data data.csv --initial-cash 1000000"
    )

    subparsers = parser.add_subparsers(
        dest="command",
        required=True,
        title="命令",
        description="可用命令"
    )

    # ==================== run 命令 ====================
    run_parser = subparsers.add_parser(
        "run",
        help="运行回测"
    )

    # 数据相关参数
    data_group = run_parser.add_argument_group("数据设置")
    data_group.add_argument(
        "--data",
        help="单个股票的CSV文件路径"
    )
    data_group.add_argument(
        "--data-dir",
        help="包含多个CSV文件的目录路径（*.csv）"
    )
    data_group.add_argument(
        "--index-data",
        help="指数数据CSV路径，例如沪深300"
    )
    data_group.add_argument(
        "--symbol",
        default="SAMPLE",
        help="股票代码标签（用于报告）"
    )
    data_group.add_argument(
        "--beg",
        help="开始日期 (YYYYMMDD 或 YYYY-MM-DD)"
    )
    data_group.add_argument(
        "--end",
        help="结束日期 (YYYYMMDD 或 YYYY-MM-DD)"
    )

    # 策略选择参数
    strategy_group = run_parser.add_argument_group("策略设置")
    strategy_group.add_argument(
        "--strategy",
        default="ma_cross",
        choices=["ma_cross", "platform_breakout", "breakout"],
        help="选择回测策略"
    )
    strategy_group.add_argument(
        "--strategy-name",
        default="",
        help="策略名称（用于报告）"
    )

    # 通用策略参数
    strategy_group.add_argument("--fast", type=int, default=5, help="快线周期（MA策略）")
    strategy_group.add_argument("--slow", type=int, default=20, help="慢线周期（MA策略）")
    strategy_group.add_argument("--lookback", type=int, default=20, help="回顾周期（突破策略）")
    strategy_group.add_argument("--breakout-multiplier", type=float, default=1.0, help="突破倍数")
    strategy_group.add_argument("--use-atr", action="store_true", help="使用ATR过滤")
    strategy_group.add_argument("--atr-period", type=int, default=14, help="ATR周期")

    # 平台突破策略参数
    platform_group = run_parser.add_argument_group("平台突破策略参数")
    platform_group.add_argument("--platform-min", type=int, default=20, help="平台最小天数")
    platform_group.add_argument("--platform-max", type=int, default=60, help="平台最大天数")
    platform_group.add_argument("--platform-amp", type=float, default=0.10, help="平台最大振幅")
    platform_group.add_argument("--vol-mult", type=float, default=1.5, help="成交量倍数")
    platform_group.add_argument("--risk-pct", type=float, default=0.01, help="每笔交易风险百分比")
    platform_group.add_argument("--max-symbol", type=float, default=0.20, help="单个股票最大暴露")
    platform_group.add_argument("--max-total", type=float, default=0.80, help="总暴露上限")
    platform_group.add_argument("--dd-pause", type=float, default=0.15, help="账户回撤暂停阈值")
    platform_group.add_argument("--enable-trend-exit", action="store_true", help="启用趋势出场")
    platform_group.add_argument("--enable-pe-filter", action="store_true", help="启用PE过滤")
    platform_group.add_argument("--require-index-confirm", action="store_true", help="需要指数确认")
    platform_group.add_argument("--index-symbol", default="000300.SH", help="指数代码")
    platform_group.add_argument("--max-symbols-per-day", type=int, default=5, help="每日最大关注股票数")

    # 资金和费用参数
    finance_group = run_parser.add_argument_group("资金和费用设置")
    finance_group.add_argument("--initial-cash", type=float, default=1_000_000.0, help="初始资金")
    finance_group.add_argument("--commission-rate", type=float, default=0.0003, help="佣金费率")
    finance_group.add_argument("--slippage-bps", type=float, default=2.0, help="滑点（基点）")
    finance_group.add_argument("--min-commission", type=float, default=5.0, help="最低佣金")
    finance_group.add_argument("--stamp-duty-rate", type=float, default=0.001, help="印花税率")
    finance_group.add_argument("--slippage-rate", type=float, default=0.001, help="滑点率")

    # 过滤参数
    filter_group = run_parser.add_argument_group("过滤设置")
    filter_group.add_argument("--universe", help="股票池CSV文件（用于ST/上市日期过滤）")
    filter_group.add_argument("--fundamentals", help="基本面数据CSV文件")
    filter_group.add_argument("--min-market-cap", type=float, default=50_000_000_000.0, help="最小市值")
    filter_group.add_argument("--min-avg-amount", type=float, default=100_000_000.0, help="最小平均成交额")
    filter_group.add_argument("--max-pe", type=float, default=60.0, help="最大PE TTM")

    # 输出参数
    output_group = run_parser.add_argument_group("输出设置")
    output_group.add_argument("--print-trades", action="store_true", help="打印交易明细")
    output_group.add_argument("--report-dir", help="报告输出目录")
    output_group.add_argument("--save-json", action="store_true", help="保存JSON格式报告")
    output_group.add_argument("--save-csv", action="store_true", help="保存CSV格式数据")
    output_group.add_argument("--save-signals", action="store_true", help="保存信号分析日志 (CSV)")
    output_group.add_argument("--save-decisions", action="store_true", help="保存详细决策日志 (TXT)")
    output_group.add_argument("--verbose", "-v", action="count", default=0, help="详细输出级别")

    # ==================== optimize 命令 ====================
    optimize_parser = subparsers.add_parser(
        "optimize",
        help="参数优化"
    )

    optimize_parser.add_argument("--data", required=True, help="数据CSV文件路径")
    optimize_parser.add_argument("--strategy", required=True, choices=["ma_cross", "breakout"], help="策略类型")
    optimize_parser.add_argument("--param-file", help="参数配置文件（JSON格式）")
    optimize_parser.add_argument("--out", required=True, help="优化结果输出文件")
    optimize_parser.add_argument("--initial-cash", type=float, default=1_000_000.0, help="初始资金")
    optimize_parser.add_argument("--max-combinations", type=int, default=100, help="最大参数组合数")

    chhf_opt_parser = subparsers.add_parser(
        "chhf_optimize",
        help="ChannelHF 参数压力测试/搜索"
    )

    chhf_opt_parser.add_argument("--data-dir", required=True, help="包含多个CSV文件的目录路径（*.csv）")
    chhf_opt_parser.add_argument("--index-data", help="指数数据CSV路径，例如沪深300")
    chhf_opt_parser.add_argument("--index-symbol", default="000300.SH", help="指数代码")
    chhf_opt_parser.add_argument("--beg", default="2018-01-01", help="开始日期 (YYYY-MM-DD)")
    chhf_opt_parser.add_argument("--end", default="2022-12-31", help="结束日期 (YYYY-MM-DD)")
    chhf_opt_parser.add_argument("--sample-size", type=int, default=500, help="抽样股票数量")
    chhf_opt_parser.add_argument("--seed", type=int, default=20251226, help="随机种子")
    chhf_opt_parser.add_argument("--combinations", type=int, default=300, help="抽样参数组合数量")
    chhf_opt_parser.add_argument("--param-space-file", help="参数空间配置文件（JSON），覆盖默认 param_space")
    chhf_opt_parser.add_argument("--params-file", help="参数组合列表文件（JSON list[dict]），指定则忽略 --combinations/--param-space-file")
    chhf_opt_parser.add_argument("--out", required=True, help="结果输出文件（JSON）")

    chhf_opt_parser.add_argument("--min-trades", type=int, default=5, help="硬约束：最少交易次数")
    chhf_opt_parser.add_argument("--max-dd", type=float, default=0.25, help="硬约束：最大回撤（0~1）")
    chhf_opt_parser.add_argument("--max-anomalies", type=int, default=0, help="硬约束：最大异常数量")
    chhf_opt_parser.add_argument("--min-valid-ratio", type=float, default=0.30, help="筛选：最小有效占比")

    chhf_opt_parser.add_argument("--robust-segments", type=int, default=0, help="稳健分段（0/2/4/6...）")
    chhf_opt_parser.add_argument("--jobs", type=int, default=0, help="并行进程数（0=自动）")

    # ==================== fetch 命令 ====================
    fetch_parser = subparsers.add_parser(
        "fetch",
        help="从东方财富API下载数据"
    )

    fetch_parser.add_argument("--symbol", required=True, help="股票代码")
    fetch_parser.add_argument("--out", required=True, help="输出文件路径")
    fetch_parser.add_argument("--beg", default="0", help="开始日期（格式：YYYYMMDD）")
    fetch_parser.add_argument("--end", default="20500101", help="结束日期（格式：YYYYMMDD）")
    fetch_parser.add_argument("--adjust", default="qfq", choices=["none", "qfq", "hfq"], help="复权类型")
    fetch_parser.add_argument("--market", choices=["sh", "sz", "bj"], help="市场代码")

    # ==================== analyze 命令 ====================
    analyze_parser = subparsers.add_parser(
        "analyze",
        help="分析回测结果"
    )

    analyze_parser.add_argument("--result-file", required=True, help="回测结果JSON文件")
    analyze_parser.add_argument("--plot", action="store_true", help="绘制净值曲线")
    analyze_parser.add_argument("--out", help="分析结果输出文件")

    return parser


def _create_broker_config(args) -> BrokerConfig:
    """创建经纪商配置"""
    return BrokerConfig(
        commission_rate=args.commission_rate,
        slippage_bps=args.slippage_bps,
        min_commission=args.min_commission,
        stamp_duty_rate=args.stamp_duty_rate,
        slippage_rate=args.slippage_rate,
        lot_size=100  # 默认100股一手
    )


def _create_backtest_config(args) -> BacktestConfig:
    """创建回测配置"""
    broker_config = _create_broker_config(args)
    return BacktestConfig(
        initial_cash=args.initial_cash,
        broker=broker_config
    )


def _create_risk_params(args) -> RiskParams:
    """创建风险参数"""
    return RiskParams(
        max_position_size=args.max_symbol if hasattr(args, 'max_symbol') else 0.1,
        max_portfolio_risk=args.risk_pct if hasattr(args, 'risk_pct') else 0.02,
        stop_loss_pct=0.10,
        take_profit_pct=0.20,
        trailing_stop_pct=0.05
    )


def _run_ma_cross_strategy(args) -> int:
    """运行移动平均线交叉策略"""
    if not args.data:
        raise ValueError("移动平均策略需要 --data 参数")

    # 加载数据
    bars = load_bars_from_csv(Path(args.data), symbol=args.symbol, beg=args.beg, end=args.end)

    # 创建策略
    strategy = MovingAverageCrossStrategy(
        fast=args.fast,
        slow=args.slow,
        name=args.strategy_name or f"MA交叉_{args.fast}_{args.slow}"
    )

    # 创建配置和引擎
    config = _create_backtest_config(args)
    engine = BacktestEngine(config=config)

    # 运行回测
    result = engine.run(bars=bars, strategy=strategy)

    # 输出结果
    print(result.summary_text())

    if args.print_trades:
        print("\n" + "="*80)
        print("交易明细")
        print("="*80)
        print(result.fills_text())

    # 保存报告
    if args.report_dir:
        _save_reports(result, args)

    return 0


def _run_breakout_strategy(args) -> int:
    """运行突破策略"""
    if not args.data:
        raise ValueError("突破策略需要 --data 参数")

    # 加载数据
    bars = load_bars_from_csv(Path(args.data), symbol=args.symbol, beg=args.beg, end=args.end)

    # 创建风险参数
    risk_params = _create_risk_params(args)

    # 创建策略
    strategy = BreakoutStrategy(
        lookback_period=args.lookback,
        breakout_multiplier=args.breakout_multiplier,
        use_atr=args.use_atr,
        atr_period=args.atr_period,
        name=args.strategy_name or f"突破_{args.lookback}",
        risk_params=risk_params
    )

    # 创建配置和引擎
    config = _create_backtest_config(args)
    engine = BacktestEngine(config=config)

    # 运行回测
    result = engine.run(bars=bars, strategy=strategy)

    # 输出结果
    print(result.summary_text())

    if args.print_trades:
        print("\n" + "="*80)
        print("交易明细")
        print("="*80)
        print(result.fills_text())

    # 保存报告
    if args.report_dir:
        _save_reports(result, args)

    return 0


def _run_platform_breakout_strategy(args) -> int:
    """运行平台突破策略"""
    if bool(args.data) == bool(args.data_dir):
        raise ValueError("请提供 --data 或 --data-dir 参数中的一个")

    # 加载数据
    if args.data:
        bars = load_bars_from_csv(Path(args.data), symbol=args.symbol, beg=args.beg, end=args.end)
    else:
        bars = load_bars_from_csv_dir(Path(args.data_dir), beg=args.beg, end=args.end)

    # 加载指数数据
    if args.index_data:
        index_bars = load_bars_from_csv(Path(args.index_data), symbol=args.index_symbol, beg=args.beg, end=args.end)
        bars.extend(index_bars)

    # 加载股票池和基本面数据
    universe = None
    fundamentals = None

    if args.universe:
        universe = Universe.load_csv(Path(args.universe))

    if args.fundamentals:
        fundamentals = FundamentalsStore.load_csv(Path(args.fundamentals))

    # 创建配置
    pb_cfg = PlatformBreakoutConfig(
        platform_min_days=args.platform_min,
        platform_max_days=args.platform_max,
        platform_max_amplitude=args.platform_amp,
        volume_multiple=args.vol_mult,
        risk_per_trade=args.risk_pct,
        max_symbol_exposure=args.max_symbol,
        max_total_exposure=args.max_total,
        account_drawdown_pause=args.dd_pause,
        enable_trend_exit=args.enable_trend_exit,
        enable_pe_filter=args.enable_pe_filter,
        require_index_confirm=bool(args.index_data) or args.require_index_confirm,
        index_symbol=args.index_symbol,
        max_symbols_per_day=args.max_symbols_per_day,
        min_avg_amount_20d=args.min_avg_amount,
        min_market_cap=args.min_market_cap,
        pe_ttm_max=args.max_pe,
    )

    # 创建策略
    pb_strategy = PlatformBreakoutStrategy(
        bars=bars,
        config=pb_cfg,
        universe=universe,
        fundamentals=fundamentals,
        strategy_name=args.strategy_name or "平台突破"
    )

    # 创建配置和引擎
    pb_config = _create_backtest_config(args)
    pb_engine = EventBacktestEngine(config=pb_config)

    # 运行回测
    pb_result = pb_engine.run(bars=bars, strategy=pb_strategy)

    # 输出结果
    print(pb_result.summary_text())

    if args.print_trades:
        print("\n" + "="*80)
        print("交易明细")
        print("="*80)
        print(pb_result.trades_text())
        print("\n" + "="*80)
        print("绩效指标")
        print("="*80)
        print(pb_result.performance_text())

    # 保存报告
    if args.report_dir:
        _save_reports(pb_result, args, strategy=pb_strategy)

    return 0


def _save_reports(result, args, strategy=None) -> None:
    """保存回测报告"""
    out_dir = Path(args.report_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    strategy_name = args.strategy_name or args.strategy

    # 保存交易报告
    trades_text = result.trades_text() if hasattr(result, 'trades_text') else result.fills_text()
    trades_file = out_dir / f"{strategy_name}_{timestamp}_trades.txt"
    trades_file.write_text(trades_text, encoding="utf-8")

    # 保存绩效报告
    perf_text = result.summary_text()
    perf_file = out_dir / f"{strategy_name}_{timestamp}_performance.txt"
    perf_file.write_text(perf_text, encoding="utf-8")

    # 保存JSON报告
    if args.save_json and hasattr(result, 'to_dict'):
        json_data = result.to_dict()
        json_file = out_dir / f"{strategy_name}_{timestamp}_report.json"
        with open(json_file, 'w', encoding='utf-8') as f:
            json.dump(json_data, f, indent=2, ensure_ascii=False)

    # 保存CSV数据
    if args.save_csv and hasattr(result, 'to_dataframe'):
        df = result.to_dataframe()
        csv_file = out_dir / f"{strategy_name}_{timestamp}_equity.csv"
        df.to_csv(csv_file, index=False, encoding='utf-8-sig')

    # 保存信号分析日志
    if args.save_signals and strategy and hasattr(strategy, 'signal_logs'):
        import pandas as pd
        signals_df = pd.DataFrame(strategy.signal_logs)
        signals_file = out_dir / f"{strategy_name}_{timestamp}_signals.csv"
        signals_df.to_csv(signals_file, index=False, encoding='utf-8-sig')
        print(f"- 信号分析日志: {signals_file.name}")

    # 保存决策日志
    if args.save_decisions and strategy and hasattr(strategy, 'decision_logs'):
        decisions_file = out_dir / f"{strategy_name}_{timestamp}_decisions.txt"
        decisions_file.write_text("\n".join(strategy.decision_logs), encoding="utf-8")
        print(f"- 详细决策日志: {decisions_file.name}")

    print(f"\n报告已保存到: {out_dir}")
    print(f"- 交易明细: {trades_file.name}")
    print(f"- 绩效报告: {perf_file.name}")
    if args.save_json:
        print(f"- JSON报告: {json_file.name}")
    if args.save_csv:
        print(f"- CSV数据: {csv_file.name}")


def _optimize_parameters(args) -> int:
    """运行参数优化"""

    from .engine import AdvancedBacktestEngine
    from .strategy import BreakoutStrategy, MovingAverageCrossStrategy

    # 加载数据
    bars = load_bars_from_csv(Path(args.data), symbol="OPTIMIZE")

    # 创建引擎
    config = _create_backtest_config(args)
    engine = AdvancedBacktestEngine(config)

    # 定义参数网格
    if args.strategy == "ma_cross":
        param_grid = {
            'fast': range(3, 20, 2),
            'slow': range(20, 60, 5)
        }
        strategy_class = MovingAverageCrossStrategy
    elif args.strategy == "breakout":
        param_grid = {
            'lookback_period': range(10, 50, 5),
            'breakout_multiplier': [0.5, 1.0, 1.5, 2.0]
        }
        strategy_class = BreakoutStrategy
    else:
        raise ValueError(f"不支持的优化策略: {args.strategy}")

    # 如果提供了参数文件，则从文件加载参数网格
    if args.param_file:
        with open(args.param_file, 'r', encoding='utf-8') as f:
            param_grid = json.load(f)

    # 运行优化
    results = engine.run_optimization(
        strategy_class=strategy_class,
        param_grid=param_grid,
        symbols=["OPTIMIZE"]
    )

    # 限制结果数量
    if len(results) > args.max_combinations:
        results = results[:args.max_combinations]

    # 生成报告
    report = engine.generate_optimization_report(results)

    # 输出报告
    print(report)

    # 保存优化结果
    out_file = Path(args.out)
    with open(out_file, 'w', encoding='utf-8') as f:
        json.dump(results, f, indent=2, ensure_ascii=False)

    print(f"\n优化结果已保存到: {out_file}")

    return 0


_CHHF_PARAMS_LIST: list[dict[str, float | int | bool]] = []
_CHHF_INDEX_BARS: list = []
_CHHF_INDEX_SYMBOL: str = "000300.SH"
_CHHF_BEG: str | None = None
_CHHF_END: str | None = None
_CHHF_INITIAL_CASH: float = 1_000_000.0
_CHHF_ROBUST_SEGMENTS: int = 0


def _chhf_worker_init(
    params_list: list[dict[str, float | int | bool]],
    index_path_str: str | None,
    index_symbol: str,
    beg: str | None,
    end: str | None,
    initial_cash: float,
    robust_segments: int,
) -> None:
    global _CHHF_PARAMS_LIST, _CHHF_INDEX_BARS, _CHHF_INDEX_SYMBOL, _CHHF_BEG, _CHHF_END, _CHHF_INITIAL_CASH, _CHHF_ROBUST_SEGMENTS

    _CHHF_PARAMS_LIST = params_list
    _CHHF_INDEX_SYMBOL = str(index_symbol)
    _CHHF_BEG = beg
    _CHHF_END = end
    _CHHF_INITIAL_CASH = float(initial_cash)

    _CHHF_ROBUST_SEGMENTS = int(robust_segments) if robust_segments is not None else 0
    _CHHF_ROBUST_SEGMENTS = _CHHF_ROBUST_SEGMENTS if _CHHF_ROBUST_SEGMENTS >= 2 else 0

    _CHHF_INDEX_BARS = []
    if index_path_str:
        p = Path(index_path_str)
        if p.exists():
            _CHHF_INDEX_BARS = load_bars_from_csv(p, symbol=_CHHF_INDEX_SYMBOL, beg=_CHHF_BEG, end=_CHHF_END)


def _chhf_score_from_metrics(m) -> float:
    return (m.sharpe * 20.0) + (m.cagr * 100.0) + (m.win_rate * 50.0) - (m.max_drawdown * 50.0)


def _chhf_worker_eval_symbol(symbol: str, data_path_str: str) -> tuple[str, list[tuple[float | None, float | None, int, int, bool]]]:
    bars = load_bars_from_csv(Path(data_path_str), symbol=symbol, beg=_CHHF_BEG, end=_CHHF_END)
    if not bars:
        return symbol, [(None, None, 0, 0, False) for _ in _CHHF_PARAMS_LIST]

    benchmark_bars = _CHHF_INDEX_BARS

    out: list[tuple[float | None, float | None, int, int, bool]] = []

    for params in _CHHF_PARAMS_LIST:
        try:
            hcfg = ChannelHFConfig(
                channel_period=int(params.get("channel_period", 20)),
                buy_touch_eps=float(params.get("buy_touch_eps", 0.005)),
                sell_trigger_eps=float(params.get("sell_trigger_eps", 0.005)),
                channel_break_eps=float(params.get("channel_break_eps", 0.02)),
                stop_loss_mul=float(params.get("stop_loss_mul", 0.97)),
                stop_loss_on_close=bool(params.get("stop_loss_on_close", True)),
                stop_loss_panic_eps=float(params.get("stop_loss_panic_eps", 0.02)),
                max_holding_days=int(params.get("max_holding_days", 20)),
                cooling_period=int(params.get("cooling_period", 5)),
                slope_abs_max=float(params.get("slope_abs_max", 0.01)),
                min_slope_norm=float(params.get("min_slope_norm", -1.0)),
                vol_shrink_threshold=float(params.get("vol_shrink_threshold", 0.9)),
                min_channel_height=float(params.get("min_channel_height", 0.05)),
                min_mid_room=float(params.get("min_mid_room", 0.015)),
                min_mid_profit_pct=float(params.get("min_mid_profit_pct", 0.0)),
                min_rr_to_mid=float(params.get("min_rr_to_mid", 0.0)),
                require_index_confirm=True,
                index_symbol=_CHHF_INDEX_SYMBOL,
            )

            engine = EventBacktestEngine(config=BacktestConfig(initial_cash=_CHHF_INITIAL_CASH))
            strategy = ChannelHFStrategy(bars=bars, config=hcfg, index_bars=benchmark_bars)
            result = engine.run(bars=bars, strategy=strategy, benchmark_bars=benchmark_bars)

            m = result.metrics
            anomalies = len(result.data_anomalies or [])
            score = _chhf_score_from_metrics(m)

            eval_score = score
            if _CHHF_ROBUST_SEGMENTS >= 2 and len(bars) >= 2:
                seg_scores: list[float] = []
                n = len(bars)
                for k in range(_CHHF_ROBUST_SEGMENTS):
                    a = (k * n) // _CHHF_ROBUST_SEGMENTS
                    b = ((k + 1) * n) // _CHHF_ROBUST_SEGMENTS - 1
                    a = max(0, min(n - 1, a))
                    b = max(0, min(n - 1, b))
                    if a > b:
                        continue

                    seg_bars = bars[a : b + 1]
                    if not seg_bars:
                        continue

                    seg_beg_dt = seg_bars[0].dt
                    seg_end_dt = seg_bars[-1].dt
                    seg_bench = [x for x in benchmark_bars if seg_beg_dt <= x.dt <= seg_end_dt] if benchmark_bars else []

                    seg_engine = EventBacktestEngine(config=BacktestConfig(initial_cash=_CHHF_INITIAL_CASH))
                    seg_strategy = ChannelHFStrategy(bars=seg_bars, config=hcfg, index_bars=seg_bench)
                    seg_res = seg_engine.run(bars=seg_bars, strategy=seg_strategy, benchmark_bars=seg_bench)
                    seg_scores.append(_chhf_score_from_metrics(seg_res.metrics))

                if seg_scores:
                    score_mean = statistics.mean(seg_scores)
                    score_std = statistics.pstdev(seg_scores) if len(seg_scores) > 1 else 0.0
                    eval_score = score_mean - score_std

            out.append((float(eval_score), float(m.max_drawdown), int(m.trade_count), int(anomalies), True))

        except Exception:
            out.append((None, None, 0, 0, False))

    return symbol, out


def _chhf_quantile(xs: list[float], q: float) -> float | None:
    if not xs:
        return None
    if q <= 0:
        return min(xs)
    if q >= 1:
        return max(xs)
    s = sorted(xs)
    idx = int(round(q * (len(s) - 1)))
    idx = max(0, min(len(s) - 1, idx))
    return s[idx]


def _chhf_build_param_space() -> dict[str, list]:
    return {
        "channel_period": [15, 20, 25, 30, 40],
        "buy_touch_eps": [0.002, 0.005, 0.008, 0.01],
        "sell_trigger_eps": [0.002, 0.005, 0.008, 0.01],
        "channel_break_eps": [0.01, 0.02, 0.03, 0.04],
        "stop_loss_mul": [0.95, 0.96, 0.97, 0.98],
        "stop_loss_on_close": [True, False],
        "stop_loss_panic_eps": [0.0, 0.01, 0.02, 0.03],
        "max_holding_days": [10, 15, 20, 30, 45],
        "cooling_period": [0, 3, 5, 8],
        "slope_abs_max": [0.005, 0.01, 0.015],
        "min_slope_norm": [-1.0],
        "vol_shrink_threshold": [0.8, 0.9, 1.0],
        "min_channel_height": [0.03, 0.05, 0.08],
        "min_mid_room": [0.01, 0.015, 0.02],
        "min_mid_profit_pct": [0.0],
        "min_rr_to_mid": [0.0],
    }


def _chhf_sample_param_combos(
    space: dict[str, list],
    k: int,
    rng: random.Random,
) -> list[dict[str, float | int | bool]]:
    keys = list(space.keys())
    if not keys:
        return []

    sizes = [len(space[key]) for key in keys]
    total = 1
    for n in sizes:
        total *= max(1, int(n))

    if k <= 0 or k >= total:
        out: list[dict[str, float | int]] = []
        for values in product(*(space[key] for key in keys)):
            out.append({k2: v2 for k2, v2 in zip(keys, values)})
        return out

    seen: set[tuple] = set()
    out2: list[dict[str, float | int]] = []
    max_iter = k * 50
    it = 0
    while len(out2) < k and it < max_iter:
        it += 1
        values = tuple(rng.choice(space[key]) for key in keys)
        if values in seen:
            continue
        seen.add(values)
        out2.append({k2: v2 for k2, v2 in zip(keys, values)})

    if len(out2) < k:
        out = []
        for values in product(*(space[key] for key in keys)):
            out.append({k2: v2 for k2, v2 in zip(keys, values)})
        rng.shuffle(out)
        return out[:k]

    return out2


def _chhf_eval_symbol_combos(
    symbol: str,
    data_path_str: str,
    index_path_str: str | None,
    index_symbol: str,
    beg: str | None,
    end: str | None,
    initial_cash: float,
    robust_segments: int,
    params_list: list[dict[str, float | int | bool]],
) -> tuple[str, list[tuple[float | None, float | None, int, int, bool]]]:
    from datetime import date

    data_path = Path(data_path_str)
    index_path = Path(index_path_str) if index_path_str else None

    bars = load_bars_from_csv(data_path, symbol=symbol, beg=beg, end=end)
    if not bars:
        return symbol, [(None, None, 0, 0, False) for _ in params_list]

    benchmark_bars: list = []
    if index_path is not None:
        benchmark_bars = load_bars_from_csv(index_path, symbol=index_symbol, beg=beg, end=end)

    robust_segments = int(robust_segments) if robust_segments is not None else 0
    robust_segments = robust_segments if robust_segments >= 2 else 0

    out: list[tuple[float | None, float | None, int, int, bool]] = []

    for params in params_list:
        try:
            hcfg = ChannelHFConfig(
                channel_period=int(params.get("channel_period", 20)),
                buy_touch_eps=float(params.get("buy_touch_eps", 0.005)),
                sell_trigger_eps=float(params.get("sell_trigger_eps", 0.005)),
                channel_break_eps=float(params.get("channel_break_eps", 0.02)),
                stop_loss_mul=float(params.get("stop_loss_mul", 0.97)),
                stop_loss_on_close=bool(params.get("stop_loss_on_close", True)),
                stop_loss_panic_eps=float(params.get("stop_loss_panic_eps", 0.02)),
                max_holding_days=int(params.get("max_holding_days", 20)),
                cooling_period=int(params.get("cooling_period", 5)),
                slope_abs_max=float(params.get("slope_abs_max", 0.01)),
                min_slope_norm=float(params.get("min_slope_norm", -1.0)),
                vol_shrink_threshold=float(params.get("vol_shrink_threshold", 0.9)),
                min_channel_height=float(params.get("min_channel_height", 0.05)),
                min_mid_room=float(params.get("min_mid_room", 0.015)),
                min_mid_profit_pct=float(params.get("min_mid_profit_pct", 0.0)),
                min_rr_to_mid=float(params.get("min_rr_to_mid", 0.0)),
                require_index_confirm=True,
                index_symbol=index_symbol,
            )

            engine = EventBacktestEngine(config=BacktestConfig(initial_cash=initial_cash))
            strategy = ChannelHFStrategy(bars=bars, config=hcfg, index_bars=benchmark_bars)
            result = engine.run(bars=bars, strategy=strategy, benchmark_bars=benchmark_bars)

            m = result.metrics
            anomalies = len(result.data_anomalies or [])
            score = _chhf_score_from_metrics(m)

            eval_score = score
            if robust_segments >= 2 and len(bars) >= 2:
                seg_scores: list[float] = []
                n = len(bars)
                for k in range(robust_segments):
                    a = (k * n) // robust_segments
                    b = ((k + 1) * n) // robust_segments - 1
                    a = max(0, min(n - 1, a))
                    b = max(0, min(n - 1, b))
                    if a > b:
                        continue

                    seg_bars = bars[a : b + 1]
                    if not seg_bars:
                        continue

                    seg_beg_dt: date = seg_bars[0].dt
                    seg_end_dt: date = seg_bars[-1].dt
                    seg_bench = [x for x in benchmark_bars if seg_beg_dt <= x.dt <= seg_end_dt] if benchmark_bars else []

                    seg_engine = EventBacktestEngine(config=BacktestConfig(initial_cash=initial_cash))
                    seg_strategy = ChannelHFStrategy(bars=seg_bars, config=hcfg, index_bars=seg_bench)
                    seg_res = seg_engine.run(bars=seg_bars, strategy=seg_strategy, benchmark_bars=seg_bench)
                    seg_scores.append(_chhf_score_from_metrics(seg_res.metrics))

                if seg_scores:
                    score_mean = statistics.mean(seg_scores)
                    score_std = statistics.pstdev(seg_scores) if len(seg_scores) > 1 else 0.0
                    eval_score = score_mean - score_std

            out.append((eval_score, m.max_drawdown, int(m.trade_count), int(anomalies), True))

        except Exception:
            out.append((None, None, 0, 0, False))

    return symbol, out


def _chhf_optimize(args) -> int:
    import os
    import time

    data_dir = Path(args.data_dir)
    if not data_dir.exists() or not data_dir.is_dir():
        raise ValueError(f"Not a directory: {data_dir}")

    out_file = Path(args.out)
    out_file.parent.mkdir(parents=True, exist_ok=True)

    index_path = Path(args.index_data) if args.index_data else None
    if index_path is not None and not index_path.exists():
        raise ValueError(f"Index data not found: {index_path}")

    all_csv = sorted([p for p in data_dir.glob("*.csv") if p.is_file()])
    if index_path is not None:
        try:
            all_csv = [p for p in all_csv if p.resolve() != index_path.resolve()]
        except Exception:
            all_csv = [p for p in all_csv if p != index_path]

    all_csv = [p for p in all_csv if p.name.lower() not in {"universe.csv", "fundamentals.csv"}]

    if not all_csv:
        raise ValueError(f"No csv files under: {data_dir}")

    rng = random.Random(int(args.seed))

    sample_size = int(args.sample_size)
    if sample_size <= 0 or sample_size >= len(all_csv):
        sample_csv = all_csv
    else:
        sample_csv = rng.sample(all_csv, sample_size)

    symbols = [p.stem for p in sample_csv]

    params_file = Path(args.params_file) if getattr(args, "params_file", None) else None
    if params_file is not None:
        if not params_file.exists():
            raise ValueError(f"Params file not found: {params_file}")
        with params_file.open("r", encoding="utf-8") as f:
            raw = json.load(f)
        if not isinstance(raw, list) or not raw:
            raise ValueError("params-file must be a non-empty JSON list[dict]")
        params_list: list[dict[str, float | int | bool]] = []
        for item in raw:
            if not isinstance(item, dict):
                raise ValueError("params-file must be a JSON list of objects")
            params_list.append(item)
        space: dict[str, list] = {}
    else:
        space = _chhf_build_param_space()
        param_space_file = Path(args.param_space_file) if getattr(args, "param_space_file", None) else None
        if param_space_file is not None:
            if not param_space_file.exists():
                raise ValueError(f"Param space file not found: {param_space_file}")
            with param_space_file.open("r", encoding="utf-8") as f:
                raw = json.load(f)
            if not isinstance(raw, dict) or not raw:
                raise ValueError("param-space-file must be a non-empty JSON object mapping param->list")
            space = {str(k): (v if isinstance(v, list) else [v]) for k, v in raw.items()}

        params_list = _chhf_sample_param_combos(space, int(args.combinations), rng)
        if not params_list:
            raise ValueError("No parameter combinations generated")

    n_symbols = len(sample_csv)
    n_combos = len(params_list)

    min_trades = int(args.min_trades)
    max_dd = float(args.max_dd)
    max_anomalies = int(args.max_anomalies)
    min_valid_ratio = float(args.min_valid_ratio)

    robust_segments = int(args.robust_segments)
    jobs = int(args.jobs)
    if jobs <= 0:
        cpu = os.cpu_count() or 1
        jobs = max(1, min(cpu - 1 if cpu > 1 else 1, 8))

    combo_scores: list[list[float]] = [[] for _ in range(n_combos)]
    combo_dds: list[list[float]] = [[] for _ in range(n_combos)]
    combo_trades: list[list[int]] = [[] for _ in range(n_combos)]
    combo_valid = [0 for _ in range(n_combos)]
    combo_errors = [0 for _ in range(n_combos)]

    started = time.time()

    print(f"Symbols={n_symbols}  Combos={n_combos}  Jobs={jobs}")

    with ProcessPoolExecutor(
        max_workers=jobs,
        initializer=_chhf_worker_init,
        initargs=(
            params_list,
            (str(index_path) if index_path is not None else None),
            str(args.index_symbol),
            (str(args.beg) if args.beg else None),
            (str(args.end) if args.end else None),
            1_000_000.0,
            robust_segments,
        ),
    ) as ex:
        futures = [ex.submit(_chhf_worker_eval_symbol, p.stem, str(p)) for p in sample_csv]

        done = 0
        for fut in as_completed(futures):
            symbol, rows = fut.result()
            done += 1

            for i, (score, dd, trades, anomalies, ok) in enumerate(rows):
                if not ok or score is None or dd is None:
                    combo_errors[i] += 1
                    continue
                if trades < min_trades:
                    continue
                if dd > max_dd:
                    continue
                if anomalies > max_anomalies:
                    continue

                combo_valid[i] += 1
                combo_scores[i].append(float(score))
                combo_dds[i].append(float(dd))
                combo_trades[i].append(int(trades))

            if done % 25 == 0 or done == n_symbols:
                elapsed = time.time() - started
                print(f"Progress {done}/{n_symbols}  Elapsed {elapsed:.1f}s")

    results = []
    for i, params in enumerate(params_list):
        valid_n = int(combo_valid[i])
        valid_ratio = valid_n / n_symbols if n_symbols > 0 else 0.0

        scores = combo_scores[i]
        dds = combo_dds[i]
        trades_list = combo_trades[i]

        score_median = statistics.median(scores) if scores else None
        score_p25 = _chhf_quantile(scores, 0.25)
        score_mean = statistics.mean(scores) if scores else None
        score_std = statistics.pstdev(scores) if len(scores) > 1 else (0.0 if scores else None)

        dd_median = statistics.median(dds) if dds else None
        dd_p25 = _chhf_quantile(dds, 0.25)

        trades_median = statistics.median(trades_list) if trades_list else None

        results.append(
            {
                "params": params,
                "valid_ratio": valid_ratio,
                "valid": valid_n,
                "symbols": n_symbols,
                "errors": int(combo_errors[i]),
                "score_median": score_median,
                "score_p25": score_p25,
                "score_mean": score_mean,
                "score_std": score_std,
                "dd_median": dd_median,
                "dd_p25": dd_p25,
                "trades_median": trades_median,
            }
        )

    def _sort_key(r: dict) -> tuple[float, float, float]:
        vr = float(r.get("valid_ratio") or 0.0)
        sm = r.get("score_median")
        dm = r.get("dd_median")
        score = float(sm) if sm is not None else float("-inf")
        dd_score = (-float(dm)) if dm is not None else float("-inf")
        return vr, score, dd_score

    results.sort(key=_sort_key, reverse=True)

    filtered = [r for r in results if float(r.get("valid_ratio") or 0.0) >= min_valid_ratio]

    payload = {
        "meta": {
            "created_at": datetime.now().isoformat(timespec="seconds"),
            "data_dir": str(data_dir),
            "index_data": (str(index_path) if index_path is not None else None),
            "index_symbol": str(args.index_symbol),
            "beg": (str(args.beg) if args.beg else None),
            "end": (str(args.end) if args.end else None),
            "seed": int(args.seed),
            "sample_size": int(args.sample_size),
            "symbols": symbols,
            "combinations": int(n_combos),
            "param_space_file": (str(getattr(args, "param_space_file", None)) if getattr(args, "param_space_file", None) else None),
            "params_file": (str(getattr(args, "params_file", None)) if getattr(args, "params_file", None) else None),
            "robust_segments": int(args.robust_segments),
            "min_trades": min_trades,
            "max_dd": max_dd,
            "max_anomalies": max_anomalies,
            "min_valid_ratio": min_valid_ratio,
            "jobs": jobs,
            "elapsed_sec": round(time.time() - started, 3),
        },
        "param_space": space,
        "results": results,
        "filtered": filtered,
        "top": results[:50],
    }

    with out_file.open("w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)

    print(f"\nSaved: {out_file}")
    if results:
        print("Top 10:")
        for r in results[:10]:
            p = r.get("params") or {}
            print(
                f"valid={r.get('valid_ratio', 0):.2%} score_med={r.get('score_median')} dd_med={r.get('dd_median')} "
                f"cp={p.get('channel_period')} buy={p.get('buy_touch_eps')} sell={p.get('sell_trigger_eps')}"
            )

    return 0


def _analyze_results(args) -> int:
    """分析回测结果"""
    result_file = Path(args.result_file)

    if not result_file.exists():
        print(f"错误: 文件不存在 {result_file}")
        return 1

    # 读取结果
    with open(result_file, 'r', encoding='utf-8') as f:
        result_data = json.load(f)

    print("="*80)
    print("回测结果分析")
    print("="*80)

    # 显示基本统计
    if 'summary' in result_data:
        summary = result_data['summary']
        print(f"策略名称: {summary.get('strategy_name', 'N/A')}")
        print(f"标的: {summary.get('symbol', 'N/A')}")
        print(f"初始资金: {summary.get('initial_equity', 0):.2f}")
        print(f"最终资金: {summary.get('final_equity', 0):.2f}")
        print(f"总收益率: {summary.get('total_return', 0):.2%}")
        print(f"最大回撤: {summary.get('max_drawdown', 0):.2%}")
        print(f"夏普比率: {summary.get('sharpe_ratio', 0):.3f}")
        print(f"胜率: {summary.get('win_rate', 0):.2%}")
        print(f"交易次数: {summary.get('total_trades', 0)}")

    # 显示详细指标
    if 'metrics' in result_data:
        metrics = result_data['metrics']
        print("\n详细指标:")
        for key, value in metrics.items():
            if isinstance(value, float):
                if 'rate' in key or 'return' in key or 'drawdown' in key:
                    print(f"  {key}: {value:.2%}")
                else:
                    print(f"  {key}: {value:.4f}")
            else:
                print(f"  {key}: {value}")

    # 绘制图表（如果启用）
    if args.plot:
        try:
            import matplotlib.pyplot as plt
            import pandas as pd

            if 'equity_curve' in result_data:
                equity_data = result_data['equity_curve']
                dates = [pd.to_datetime(item['date']) for item in equity_data]
                equities = [item['equity'] for item in equity_data]

                plt.figure(figsize=(12, 6))
                plt.plot(dates, equities, linewidth=2)
                plt.title('净值曲线')
                plt.xlabel('日期')
                plt.ylabel('净值')
                plt.grid(True, alpha=0.3)

                if args.out:
                    plot_file = Path(args.out).with_suffix('.png')
                    plt.savefig(plot_file, dpi=300, bbox_inches='tight')
                    print(f"\n图表已保存到: {plot_file}")
                else:
                    plt.show()

        except ImportError:
            print("\n警告: 需要安装matplotlib才能绘制图表")
            print("安装命令: pip install matplotlib")

    # 保存分析报告
    if args.out and not args.plot:
        out_file = Path(args.out)
        with open(out_file, 'w', encoding='utf-8') as f:
            json.dump(result_data, f, indent=2, ensure_ascii=False)
        print(f"\n分析报告已保存到: {out_file}")

    return 0


def main(argv: list[str] | None = None) -> int:
    """主函数"""
    parser = _build_parser()
    args = parser.parse_args(argv)

    try:
        if args.command == "run":
            if args.strategy == "ma_cross":
                return _run_ma_cross_strategy(args)
            elif args.strategy == "breakout":
                return _run_breakout_strategy(args)
            elif args.strategy == "platform_breakout":
                return _run_platform_breakout_strategy(args)
            else:
                raise ValueError(f"未知策略: {args.strategy}")

        elif args.command == "optimize":
            return _optimize_parameters(args)

        elif args.command == "chhf_optimize":
            return _chhf_optimize(args)

        elif args.command == "fetch":
            bars = fetch_daily_bars_eastmoney(
                symbol=args.symbol,
                beg=args.beg,
                end=args.end,
                adjust=args.adjust,
                market=args.market,
            )
            write_bars_to_csv(Path(args.out), bars)
            print(f"数据已保存: {args.out}")
            print(f"数据条数: {len(bars)}")
            return 0

        elif args.command == "analyze":
            return _analyze_results(args)

        else:
            parser.print_help()
            return 2

    except Exception as e:
        print(f"错误: {e}")
        if args.verbose > 0:
            import traceback
            traceback.print_exc()
        return 1


if __name__ == "__main__":
    import sys
    sys.exit(main())
