from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import datetime
from typing import Any, Optional

import pandas as pd

from .broker import Broker
from .metrics import Metrics
from .strategy import BaseStrategy, Signal, SignalType
from .types import BacktestConfig, Bar, EquityPoint, Fill, Order, Position


@dataclass(frozen=True)
class BacktestResult:
    """回测结果"""
    equity_curve: list[EquityPoint]
    metrics: Metrics
    fills: list[Fill]
    orders: list[Order]
    positions_history: list[dict[str, Position]]

    # 策略相关
    strategy_name: str
    symbol: str
    config: dict[str, Any]

    # 性能数据
    returns: list[float]
    benchmark_returns: Optional[list[float]] = None
    benchmark_metrics: Optional[Metrics] = None

    # 日志数据 (可选)
    signal_logs: Optional[list[dict[str, Any]]] = None
    decision_logs: Optional[list[str]] = None
    validation_data: Optional[dict[str, Any]] = None

    def summary_text(self) -> str:
        """生成文本摘要"""
        m = self.metrics
        lines = [
            "=== 回测结果摘要 ===",
            f"策略名称: {self.strategy_name}",
            f"标的: {self.symbol}",
            f"回测期间: {self.equity_curve[0].dt if self.equity_curve else 'N/A'} 至 {self.equity_curve[-1].dt if self.equity_curve else 'N/A'}",
            f"总天数: {len(self.equity_curve)}",
            "",
            "【绩效指标】",
            f"初始净值: {m.initial_equity:.2f}",
            f"最终净值: {m.final_equity:.2f}",
            f"总收益率: {m.total_return:.2%}",
            f"年化收益率: {m.cagr:.2%}",
            f"最大回撤: {m.max_drawdown:.2%}",
            f"夏普比率: {m.sharpe:.3f}",
            f"索提诺比率: {m.sortino:.3f}",
            f"Calmar比率: {m.calmar:.3f}",
            "",
            "【交易统计】",
            f"总交易次数: {m.trade_count}",
            f"胜率: {m.win_rate:.2%}",
            f"盈利因子: {m.profit_factor:.3f}",
            f"平均盈利: {m.avg_win:.2f}",
            f"平均亏损: {m.avg_loss:.2f}",
            f"盈亏比: {m.win_loss_ratio:.3f}",
            f"期望值: {m.expectancy:.3f}",
            "",
            "【风险指标】",
            f"年化波动率: {m.volatility:.2%}",
            f"下行波动率: {m.downside_volatility:.2%}",
            f"K比率: {m.k_ratio:.3f}",
            f"尾部比率: {m.tail_ratio:.3f}",
            f"盈利天数比例: {m.profitable_days:.2%}",
            f"亏损天数比例: {m.losing_days:.2%}",
            f"最佳单日收益: {m.best_day:.2%}",
            f"最差单日收益: {m.worst_day:.2%}"
        ]

        if m.max_drawdown_detail:
            dd = m.max_drawdown_detail
            lines.append("")
            lines.append("【最大回撤详情】")
            lines.append(f"回撤开始: {dd.drawdown_start_date}")
            lines.append(f"回撤结束: {dd.drawdown_end_date}")
            lines.append(f"回撤持续时间: {dd.drawdown_duration}天")
            if dd.recovery_date:
                lines.append(f"回撤恢复: {dd.recovery_date}")

        if self.benchmark_metrics:
            bm = self.benchmark_metrics
            lines.append("")
            lines.append("【基准对比】")
            lines.append(f"策略总收益: {m.total_return:.2%} | 基准总收益: {bm.total_return:.2%}")
            lines.append(f"策略夏普: {m.sharpe:.3f} | 基准夏普: {bm.sharpe:.3f}")
            lines.append(f"策略最大回撤: {m.max_drawdown:.2%} | 基准最大回撤: {bm.max_drawdown:.2%}")

        return "\n".join(lines)

    def fills_text(self) -> str:
        """生成成交记录文本"""
        if not self.fills:
            return "无成交记录"

        headers = ["日期", "方向", "股票", "数量", "价格", "手续费", "名义金额", "盈亏"]
        rows: list[list[str]] = []

        for f in self.fills:
            sym = "" if f.symbol is None else f.symbol
            notional = abs(f.qty * f.price)
            pnl_str = f"{f.pnl:.2f}" if f.pnl is not None else "N/A"

            rows.append(
                [
                    f.dt.isoformat(),
                    f.side,
                    sym,
                    str(int(f.qty)),
                    f"{f.price:.3f}",
                    f"{f.fee:.2f}",
                    f"{notional:.2f}",
                    pnl_str
                ]
            )

        # 计算列宽
        widths = [len(h) for h in headers]
        for row in rows:
            for i, cell in enumerate(row):
                widths[i] = max(widths[i], len(cell))

        def fmt(row: list[str]) -> str:
            return "  ".join(cell.ljust(widths[i]) for i, cell in enumerate(row))

        lines = [fmt(headers), fmt(["-" * w for w in widths])]
        lines.extend(fmt(r) for r in rows)

        # 添加汇总
        total_trades = len(self.fills)
        total_pnl = sum(f.pnl or 0 for f in self.fills)
        win_trades = sum(1 for f in self.fills if f.pnl and f.pnl > 0)
        loss_trades = sum(1 for f in self.fills if f.pnl and f.pnl < 0)

        lines.append("")
        lines.append("=== 成交汇总 ===")
        lines.append(f"总成交次数: {total_trades}")
        lines.append(f"盈利次数: {win_trades}")
        lines.append(f"亏损次数: {loss_trades}")
        lines.append(f"总盈亏: {total_pnl:.2f}")
        lines.append(f"平均每笔盈亏: {total_pnl/total_trades if total_trades > 0 else 0:.2f}")

        return "\n".join(lines)

    def to_dataframe(self) -> pd.DataFrame:
        """将回测结果转换为DataFrame"""
        data = []
        for point in self.equity_curve:
            data.append({
                'date': point.dt,
                'equity': point.equity,
                'returns': point.returns if hasattr(point, 'returns') else None
            })

        return pd.DataFrame(data)

    def to_dict(self) -> dict[str, Any]:
        """将回测结果转换为字典，用于前端展示和API返回"""
        m = self.metrics
        
        # 构建基准数据
        benchmark_curve = []
        if self.benchmark_returns and len(self.benchmark_returns) == len(self.equity_curve):
            # 假设基准初始值为初始净值
            current_bench = m.initial_equity
            for i, r in enumerate(self.benchmark_returns):
                dt = self.equity_curve[i].dt
                current_bench *= (1 + r)
                benchmark_curve.append({
                    "dt": dt.isoformat(),
                    "equity": round(current_bench, 2)
                })

        return {
            "summary": self.summary_text(),
            "performance_text": self.summary_text(),  # 使用 summary_text 作为基础
            "fills_text": self.fills_text(),
            "strategy_name": self.strategy_name,
            "symbol": self.symbol,
            "equity_curve": [
                {"dt": p.dt.isoformat(), "equity": round(p.equity, 2)} 
                for p in self.equity_curve
            ],
            "benchmark_curve": benchmark_curve,
            "metrics": {
                "initial_equity": round(m.initial_equity, 2),
                "final_equity": round(m.final_equity, 2),
                "total_return": round(m.total_return, 4),
                "cagr": round(m.cagr, 4),
                "max_drawdown": round(m.max_drawdown, 4),
                "sharpe": round(m.sharpe, 4),
                "sortino": round(m.sortino, 4),
                "calmar": round(m.calmar, 4),
                "volatility": round(m.volatility, 4),
                "trade_count": m.trade_count,
                "win_rate": round(m.win_rate, 4),
                "profit_factor": round(m.profit_factor, 4),
                "avg_r_multiple": round(m.avg_r_multiple, 4),
                "monthly_returns": m.monthly_returns,
                "all_trade_pnls": m.all_trade_pnls,
                "max_drawdown_detail": asdict(m.max_drawdown_detail) if m.max_drawdown_detail else None
            },
            "signal_logs": self.signal_logs,
            "decision_logs": self.decision_logs,
            "validation_data": self.validation_data,
            "trades": [
                {
                    "symbol": f.symbol,
                    "dt": f.dt.isoformat(),
                    "side": f.side,
                    "qty": f.qty,
                    "price": round(f.price, 3),
                    "fee": round(f.fee, 2),
                    "pnl": round(f.pnl or 0, 2)
                }
                for f in self.fills
            ]
        }

    def save_report(self, filepath: str) -> None:
        """保存回测报告"""
        report = {
            'summary': self.to_dict(),
            'equity_curve': [
                {'date': p.dt.isoformat(), 'equity': p.equity}
                for p in self.equity_curve
            ],
            'trades': [
                {
                    'date': f.dt.isoformat(),
                    'symbol': f.symbol,
                    'side': f.side,
                    'quantity': f.qty,
                    'price': f.price,
                    'fee': f.fee,
                    'pnl': f.pnl
                }
                for f in self.fills
            ]
        }

        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(report, f, indent=2, ensure_ascii=False)


class BacktestEngine:
    """增强版回测引擎"""

    def __init__(self, config: BacktestConfig) -> None:
        self.config = config
        self.broker = None
        self.strategy = None
        self.current_date = None

        # 数据缓存
        self.bars_by_symbol: dict[str, list[Bar]] = {}
        self.current_bars: dict[str, Bar] = {}

        # 结果存储
        self.equity_curve: list[EquityPoint] = []
        self.all_fills: list[Fill] = []
        self.all_orders: list[Order] = []
        self.positions_history: list[dict[str, Position]] = []

        # 基准数据
        self.benchmark_bars: Optional[list[Bar]] = None
        self.benchmark_returns: Optional[list[float]] = None

    def add_data(self, symbol: str, bars: list[Bar]) -> None:
        """添加行情数据"""
        if not bars:
            raise ValueError(f"标的 {symbol} 的数据为空")

        # 按日期排序
        bars.sort(key=lambda x: x.dt)
        self.bars_by_symbol[symbol] = bars

    def add_benchmark_data(self, bars: list[Bar]) -> None:
        """添加基准数据"""
        if not bars:
            return

        bars.sort(key=lambda x: x.dt)
        self.benchmark_bars = bars

        # 计算基准收益率
        self.benchmark_returns = []
        for i in range(1, len(bars)):
            if bars[i-1].close > 0:
                ret = (bars[i].close / bars[i-1].close) - 1
                self.benchmark_returns.append(ret)
            else:
                self.benchmark_returns.append(0.0)

    def run(self, bars: list[Bar], strategy: BaseStrategy) -> BacktestResult:
        """运行回测（接受原始K线数据）"""
        if not bars:
            raise ValueError("输入的K线数据为空")

        # 加载数据到引擎
        symbols_set = {b.symbol for b in bars}
        for symbol in symbols_set:
            sym_bars = [b for b in bars if b.symbol == symbol]
            self.add_data(symbol, sym_bars)

        # 初始化
        self.strategy = strategy
        self.broker = Broker(
            config=self.config.broker,
            initial_cash=self.config.initial_cash
        )

        # 策略初始化
        self.strategy.on_init(self.broker)

        # 获取所有日期
        symbols = list(symbols_set)
        all_dates = self._get_all_dates(symbols)
        if not all_dates:
            raise ValueError("没有可用的交易日数据")

        # 按日期循环
        for date_idx, current_date in enumerate(all_dates):
            self.current_date = current_date

            # 获取当前日期的K线数据
            self.current_bars = self._get_bars_for_date(current_date, symbols)
            if not self.current_bars:
                continue

            # 标记到市场
            for symbol, bar in self.current_bars.items():
                self.broker.mark_to_market(bar)

            # 更新持仓信息到策略
            self.strategy.on_position(self.broker.positions)

            # 执行策略逻辑
            signals = self.strategy.on_bar(self.current_bars)

            # 处理交易信号
            for signal in signals:
                self._process_signal(signal)

            # 记录每日数据
            self._record_daily_data()

        # 回测结束，平仓
        self._close_out_positions()

        # 计算绩效指标
        trades = self.broker.get_trade_history()
        metrics = Metrics.from_equity_curve(self.equity_curve, trades)

        # 计算基准绩效（如果提供了基准数据）
        benchmark_metrics = None
        if self.benchmark_bars and len(self.equity_curve) == len(self.benchmark_bars):
            benchmark_equity = [EquityPoint(dt=b.dt, equity=b.close) for b in self.benchmark_bars]
            benchmark_metrics = Metrics.from_equity_curve(benchmark_equity, [])

        # 创建回测结果
        result = BacktestResult(
            equity_curve=self.equity_curve,
            metrics=metrics,
            fills=self.all_fills,
            orders=self.all_orders,
            positions_history=self.positions_history,
            strategy_name=strategy.name,
            symbol=symbols[0] if symbols else "",
            config=asdict(self.config),
            returns=[p.returns for p in self.equity_curve] if hasattr(self.equity_curve[0], 'returns') else [],
            benchmark_returns=self.benchmark_returns,
            benchmark_metrics=benchmark_metrics
        )

        # 记录策略性能
        self.strategy.record_performance(metrics.to_dict())

        return result

    def _get_all_dates(self, symbols: list[str]) -> list[datetime]:
        """获取所有交易日日期"""
        all_dates = set()
        for symbol in symbols:
            if symbol in self.bars_by_symbol:
                dates = {bar.dt for bar in self.bars_by_symbol[symbol]}
                all_dates.update(dates)

        return sorted(list(all_dates))

    def _get_bars_for_date(self, date: datetime, symbols: list[str]) -> dict[str, Bar]:
        """获取指定日期的K线数据"""
        bars = {}
        for symbol in symbols:
            if symbol in self.bars_by_symbol:
                for bar in self.bars_by_symbol[symbol]:
                    if bar.dt == date:
                        bars[symbol] = bar
                        break

        return bars

    def _process_signal(self, signal: Signal) -> None:
        """处理交易信号"""
        if signal.symbol not in self.current_bars:
            return

        current_bar = self.current_bars[signal.symbol]
        current_price = current_bar.close

        # 根据信号类型创建订单
        if signal.type == SignalType.BUY:
            # 买入信号
            order = self.broker.create_order(
                symbol=signal.symbol,
                side="buy",
                quantity=signal.quantity,
                price=current_price,
                order_type="market"
            )

        elif signal.type == SignalType.SELL:
            # 卖出信号
            # 检查是否持有该标的
            position = self.broker.positions.get(signal.symbol)
            if position and position.quantity > 0:
                # 平仓或减仓
                qty_to_sell = min(signal.quantity, position.quantity)
                order = self.broker.create_order(
                    symbol=signal.symbol,
                    side="sell",
                    quantity=qty_to_sell,
                    price=current_price,
                    order_type="market"
                )
            else:
                # 无法卖出，跳过
                return

        elif signal.type == SignalType.CLOSE:
            # 平仓信号
            position = self.broker.positions.get(signal.symbol)
            if position and position.quantity != 0:
                side = "sell" if position.quantity > 0 else "buy"
                order = self.broker.create_order(
                    symbol=signal.symbol,
                    side=side,
                    quantity=abs(position.quantity),
                    price=current_price,
                    order_type="market"
                )
            else:
                return

        else:
            # HOLD信号，不操作
            return

        # 记录订单
        if order:
            self.all_orders.append(order)
            self.strategy.on_order(order)

            # 尝试执行订单
            fill = self.broker.execute_order(order, current_bar)
            if fill:
                self.all_fills.append(fill)
                self.strategy.on_trade({
                    'date': fill.dt,
                    'symbol': fill.symbol,
                    'side': fill.side,
                    'quantity': fill.qty,
                    'price': fill.price,
                    'pnl': fill.pnl
                })

    def _record_daily_data(self) -> None:
        """记录每日数据"""
        if self.broker is None:
            return

        # 计算日收益率
        daily_return = 0.0
        if self.equity_curve:
            prev_equity = self.equity_curve[-1].equity
            if prev_equity > 0:
                daily_return = (self.broker.equity / prev_equity) - 1

        # 记录净值点
        equity_point = EquityPoint(
            dt=self.current_date,
            equity=self.broker.equity,
            returns=daily_return
        )
        self.equity_curve.append(equity_point)

        # 记录持仓历史
        positions_copy = {
            symbol: Position(
                symbol=p.symbol,
                quantity=p.quantity,
                avg_price=p.avg_price,
                market_value=p.market_value
            )
            for symbol, p in self.broker.positions.items()
        }
        self.positions_history.append(positions_copy)

    def _close_out_positions(self) -> None:
        """回测结束时平仓"""
        if not self.broker or not self.current_bars:
            return

        # 获取最后一个交易日的数据
        last_date = max(self.current_bars.keys(), key=lambda x: self.current_bars[x].dt)
        last_bar = self.current_bars[last_date]

        # 平仓所有持仓
        self.broker.close_out_last_price(last_bar)

        # 记录平仓后的净值
        self._record_daily_data()

    def run_optimization(self, strategy_class, param_grid: dict[str, list[Any]],
                        symbols: list[str]) -> list[dict[str, Any]]:
        """运行参数优化"""
        results = []

        # 生成所有参数组合
        from itertools import product
        param_names = list(param_grid.keys())
        param_values = list(param_grid.values())

        for param_combo in product(*param_values):
            params = dict(zip(param_names, param_combo))

            try:
                # 创建策略实例
                strategy = strategy_class(**params)
                strategy.name = f"{strategy_class.__name__}_{len(results)+1}"

                # 运行回测
                result = self.run(strategy, symbols)

                # 记录结果
                result_dict = {
                    'params': params,
                    'total_return': result.metrics.total_return,
                    'sharpe_ratio': result.metrics.sharpe,
                    'max_drawdown': result.metrics.max_drawdown,
                    'win_rate': result.metrics.win_rate,
                    'profit_factor': result.metrics.profit_factor,
                    'trade_count': result.metrics.trade_count,
                    'final_equity': result.metrics.final_equity
                }

                results.append(result_dict)

            except Exception as e:
                print(f"参数组合 {params} 回测失败: {e}")
                continue

        # 按夏普比率排序
        results.sort(key=lambda x: x['sharpe_ratio'], reverse=True)

        return results

    def generate_optimization_report(self, optimization_results: list[dict[str, Any]]) -> str:
        """生成参数优化报告"""
        if not optimization_results:
            return "无优化结果"

        # 找到最佳参数组合
        best_by_sharpe = max(optimization_results, key=lambda x: x['sharpe_ratio'])
        best_by_return = max(optimization_results, key=lambda x: x['total_return'])
        best_by_drawdown = min(optimization_results, key=lambda x: x['max_drawdown'])

        lines = [
            "=== 参数优化报告 ===",
            f"总测试组合数: {len(optimization_results)}",
            "",
            "【最佳夏普比率组合】",
            f"参数: {best_by_sharpe['params']}",
            f"夏普比率: {best_by_sharpe['sharpe_ratio']:.3f}",
            f"总收益率: {best_by_sharpe['total_return']:.2%}",
            f"最大回撤: {best_by_sharpe['max_drawdown']:.2%}",
            f"胜率: {best_by_sharpe['win_rate']:.2%}",
            "",
            "【最佳总收益组合】",
            f"参数: {best_by_return['params']}",
            f"总收益率: {best_by_return['total_return']:.2%}",
            f"夏普比率: {best_by_return['sharpe_ratio']:.3f}",
            f"最大回撤: {best_by_return['max_drawdown']:.2%}",
            "",
            "【最佳回撤控制组合】",
            f"参数: {best_by_drawdown['params']}",
            f"最大回撤: {best_by_drawdown['max_drawdown']:.2%}",
            f"总收益率: {best_by_drawdown['total_return']:.2%}",
            f"夏普比率: {best_by_drawdown['sharpe_ratio']:.3f}"
        ]

        # 添加前10个组合的简要信息
        lines.append("")
        lines.append("【前10个最佳组合】")
        lines.append(f"{'排名':<5} {'夏普比率':<10} {'总收益率':<10} {'最大回撤':<10} {'胜率':<10}")

        for i, result in enumerate(optimization_results[:10], 1):
            lines.append(
                f"{i:<5} {result['sharpe_ratio']:<10.3f} {result['total_return']:<10.2%} "
                f"{result['max_drawdown']:<10.2%} {result['win_rate']:<10.2%}"
            )

        return "\n".join(lines)
