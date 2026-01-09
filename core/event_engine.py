from __future__ import annotations

import warnings
from dataclasses import dataclass, field, replace
from datetime import date
from typing import ClassVar

from .broker import PortfolioBroker
from .metrics import Metrics
from .types import BacktestConfig, Bar, EquityPoint, Order, Trade


def _format_table(headers: list[str], rows: list[list[str]]) -> str:
    """格式化表格输出"""
    if not headers or not rows:
        return ""

    widths = [len(h) for h in headers]
    for row in rows:
        for i, cell in enumerate(row):
            widths[i] = max(widths[i], len(str(cell)))

    def fmt(row: list[str]) -> str:
        return "  ".join(str(cell).ljust(widths[i]) for i, cell in enumerate(row))

    lines = [fmt(headers), fmt(["-" * w for w in widths])]
    lines.extend(fmt(r) for r in rows)
    return "\n".join(lines)


@dataclass(frozen=True, slots=True)
class MarketFrame:
    """市场数据帧（某一天的所有标的行情）"""
    dt: date
    bars: dict[str, Bar]

    @property
    def symbols(self) -> list[str]:
        """获取所有标的代码"""
        return list(self.bars.keys())


class EventStrategy:
    """事件驱动策略基类"""

    def on_open(self, i: int, frame: MarketFrame, broker: PortfolioBroker) -> None:
        """开盘事件处理"""
        pass

    def on_close(self, i: int, frame: MarketFrame, broker: PortfolioBroker) -> list[Order]:
        """收盘事件处理"""
        raise NotImplementedError("EventStrategy must implement on_close method")


@dataclass(frozen=True, slots=True)
class EventBacktestResult:
    """事件驱动回测结果"""
    equity_curve: list[EquityPoint]
    metrics: Metrics
    trades: list[Trade]
    signal_logs: list[dict] = field(default_factory=list)
    decision_logs: list[str] = field(default_factory=list)
    validation_data: dict = field(default_factory=dict)
    benchmark_equity_curve: list[EquityPoint] = field(default_factory=list)
    data_anomalies: list[dict] = field(default_factory=list)
    data_anomalies: list[dict] = field(default_factory=list) # 数据异常记录

    # 统计字段
    _cached_summary: str = field(default="", init=False, repr=False)
    _cached_trades_text: str = field(default="", init=False, repr=False)
    _cached_performance_text: str = field(default="", init=False, repr=False)

    def summary_text(self) -> str:
        """生成策略概要文本"""
        if not self._cached_summary:
            m = self.metrics
            dd_dur = m.max_drawdown_detail.drawdown_duration if m.max_drawdown_detail is not None else None
            lines = [
                f"期初资金={self.equity_curve[0].equity if self.equity_curve else 0:.2f}",
                f"期末权益={m.final_equity:.2f}",
                f"总收益率={m.total_return:.4f}",
                f"年化收益率={m.cagr:.4f}",
                f"最大回撤={m.max_drawdown:.4f}",
                f"最大回撤持续={(str(dd_dur) + '天') if dd_dur is not None else '-'}",
                f"夏普比率={m.sharpe:.4f}",
                f"索提诺比率={m.sortino:.4f}",
                f"卡玛比率={m.calmar:.4f}",
                f"尾部比率={m.tail_ratio:.4f}",
                f"总交易次数={m.trade_count}",
                f"胜率={m.win_rate:.4f}",
                f"盈亏因子={m.profit_factor:.4f}",
                f"期望值={m.expectancy:.4f}",
                f"最大单笔亏损={m.largest_loss:+.2f}",
                f"平均R倍数={m.avg_r_multiple:.4f}",
            ]
            object.__setattr__(self, "_cached_summary", "\n".join(lines))
        return self._cached_summary

    def trades_text(self) -> str:
        """生成交易明细文本"""
        if not self._cached_trades_text:
            if not self.trades:
                object.__setattr__(self, "_cached_trades_text", "无交易记录")
                return self._cached_trades_text

            headers = [
                "股票", "入场日期", "出场日期", "数量", "入场价", "出场价",
                "入场原因", "出场原因", "初始止损", "移动止损", "本次盈亏",
                "累计盈亏", "收益率", "R倍数", "持有天数", "指数确认"
            ]

            rows: list[list[str]] = []
            cumulative_pnl = 0.0

            for trade in self.trades:
                # 计算收益率
                return_rate = 0.0 if trade.entry_price == 0 else (
                    (trade.exit_price / trade.entry_price) - 1.0
                )

                # 使用用户要求的简单盈亏公式：(卖出价 - 买入价) * 股数
                simple_pnl = (trade.exit_price - trade.entry_price) * trade.qty

                # R倍数文本
                r_text = "" if trade.r_multiple is None else f"{trade.r_multiple:.2f}"

                # 累计盈亏 (使用简单盈亏累计)
                cumulative_pnl += simple_pnl

                rows.append([
                    trade.symbol,
                    trade.entry_dt.isoformat(),
                    trade.exit_dt.isoformat(),
                    f"{int(trade.qty):,}",
                    f"{trade.entry_price:.2f}",
                    f"{trade.exit_price:.2f}",
                    trade.entry_reason[:10] if trade.entry_reason else "",
                    trade.exit_reason[:10] if trade.exit_reason else "",
                    "" if trade.initial_stop is None else f"{trade.initial_stop:.2f}",
                    "" if trade.trailing_stop is None else f"{trade.trailing_stop:.2f}",
                    f"{simple_pnl:+.2f}",
                    f"{cumulative_pnl:+.2f}",
                    f"{return_rate * 100.0:+.2f}%",
                    r_text,
                    str(int(trade.holding_days)),
                    "✓" if trade.entry_index_confirmed else "✗"
                ])

            object.__setattr__(self, "_cached_trades_text", _format_table(headers, rows))

        return self._cached_trades_text

    def performance_text(self) -> str:
        """生成绩效分析文本"""
        if not self._cached_performance_text:
            m = self.metrics

            # 关键绩效指标
            kpi_lines = [
                "【关键绩效指标】",
                f"期初资金={self.equity_curve[0].equity if self.equity_curve else 0:.2f}",
                f"期末权益={m.final_equity:.2f}",
                f"总收益率={m.total_return:.4f} ({m.total_return * 100:.2f}%)",
                f"年化收益率={m.cagr:.4f} ({m.cagr * 100:.2f}%)",
                f"夏普比率={m.sharpe:.4f}",
                f"最大回撤={m.max_drawdown:.4f} ({m.max_drawdown * 100:.2f}%)",
                f"胜率={m.win_rate:.4f} ({m.win_rate * 100:.1f}%)",
                f"盈亏比={m.profit_factor:.4f}",
                f"总交易次数={m.trade_count}",
                f"平均R倍数={m.avg_r_multiple:.4f}",
            ]

            # 出场原因分析
            if self.trades:
                reasons: dict[str, dict[str, float]] = {}
                for trade in self.trades:
                    reason = trade.exit_reason or "未知"
                    if reason not in reasons:
                        reasons[reason] = {"count": 0, "total_pnl": 0.0, "winning": 0}

                    reasons[reason]["count"] += 1
                    reasons[reason]["total_pnl"] += trade.pnl
                    if trade.pnl > 0:
                        reasons[reason]["winning"] += 1

                reason_lines = ["", "【出场原因分析】"]
                for reason, stats in reasons.items():
                    count = stats["count"]
                    win_rate = stats["winning"] / count if count > 0 else 0.0
                    avg_pnl = stats["total_pnl"] / count if count > 0 else 0.0
                    reason_lines.append(
                        f"{reason}: {count}次, 胜率={win_rate:.2f}, 平均盈亏={avg_pnl:+.2f}"
                    )
            else:
                reason_lines = ["", "【出场原因分析】", "无交易记录"]
            
            # 过滤器统计
            filter_lines = []
            if self.signal_logs:
                filter_stats = {}
                for log in self.signal_logs:
                    trace = log.get("trace", [])
                    if not trace:
                        continue
                    # Find the first failed step
                    for step in trace:
                        if not step.get("passed", True):
                            name = step.get("step", "Unknown")
                            filter_stats[name] = filter_stats.get(name, 0) + 1
                            break
                
                if filter_stats:
                    filter_lines = ["", "【过滤器拒绝统计】"]
                    sorted_stats = sorted(filter_stats.items(), key=lambda x: x[1], reverse=True)
                    for name, count in sorted_stats:
                        filter_lines.append(f"{name}: {count}次")

            object.__setattr__(self, "_cached_performance_text", "\n".join(kpi_lines + reason_lines + filter_lines))

        return self._cached_performance_text

    def to_dict(self) -> dict:
        """
        转换为字典（用于API返回）
        """
        # --- 新增：生成 rejections 列表的逻辑 ---
        rejections = []
        for log in self.signal_logs:
            # 筛选出被拒绝的信号（final_signal == 0）
            if log.get('final_signal') == 0:
                date = log.get('date')
                symbol = log.get('symbol')
                # 从 trace 中提取所有未通过的检查
                for trace_item in log.get('trace', []):
                    if trace_item.get('passed') is False:
                        rejections.append({
                            'date': date,
                            'symbol': symbol,
                            'step': trace_item.get('step', 'Unknown'),
                            'check': trace_item.get('check', ''),
                            'actual': trace_item.get('actual', ''),
                            'threshold': trace_item.get('threshold', ''),
                            'reason': trace_item.get('reason', 'Filter not passed')
                        })
        # --- 新增逻辑结束 ---

        return {
            "metrics": self.metrics.to_dict() if self.metrics else {},
            "trades": [t.to_dict() for t in self.trades],
            "signal_logs": self.signal_logs,
            "decision_logs": self.decision_logs,
            "validation_data": self.validation_data,
            "data_anomalies": self.data_anomalies,
            # --- 将生成的rejections列表加入到返回字典中 ---
            "rejections": rejections
        }


class EventBacktestEngine:
    """事件驱动回测引擎
    
    严格按照策略文档的时序：
    1. T日收盘后识别信号
    2. T+1日开盘价执行
    """

    # 配置常量
    MIN_TRADING_DAYS: ClassVar[int] = 20
    MAX_DATE_GAP_DAYS: ClassVar[int] = 7

    def __init__(self, config: BacktestConfig) -> None:
        self._config = config
        self._calendar_cache: dict[str, list[date]] = {}
        self._bars_by_date_cache: dict[str, dict[date, dict[str, Bar]]] = {}
        self._data_anomalies: list[dict] = [] # 存储当前运行的异常

    @staticmethod
    def _build_calendar(bars: list[Bar]) -> list[date]:
        """构建交易日历（去重排序）"""
        dates = sorted({b.dt for b in bars})

        # 检查日期连续性
        for i in range(1, len(dates)):
            gap = (dates[i] - dates[i-1]).days
            if gap > 7:  # 超过7天间隔
                warnings.warn(f"交易日期间隔过大: {dates[i-1]} 到 {dates[i]}, 间隔 {gap} 天")

        return dates

    @staticmethod
    def _index_bars_by_date(bars: list[Bar]) -> dict[date, dict[str, Bar]]:
        """按日期索引行情数据"""
        by_date: dict[date, dict[str, Bar]] = {}

        for bar in bars:
            date_dict = by_date.setdefault(bar.dt, {})
            if bar.symbol in date_dict:
                warnings.warn(f"重复数据: {bar.symbol} 在 {bar.dt} 有多个Bar")
                # 保留最新的（根据index判断）
                if bar.index > date_dict[bar.symbol].index:
                    date_dict[bar.symbol] = bar
            else:
                date_dict[bar.symbol] = bar

        return by_date

    def _validate_input_data(self, bars: list[Bar]) -> None:
        """验证输入数据"""
        if not bars:
            raise ValueError("输入数据为空")

        # 检查数据连续性
        symbol_groups: dict[str, list[Bar]] = {}
        for bar in bars:
            symbol_groups.setdefault(bar.symbol, []).append(bar)

        for symbol, symbol_bars in symbol_groups.items():
            symbol_bars.sort(key=lambda x: x.dt)

            if len(symbol_bars) < self.MIN_TRADING_DAYS:
                msg = f"标的 {symbol} 数据量不足: {len(symbol_bars)} 天"
                warnings.warn(msg)
                self._data_anomalies.append({
                    "symbol": symbol,
                    "type": "数据量不足",
                    "detail": msg
                })

            # 检查日期连续性和异常跳空
            for i in range(1, len(symbol_bars)):
                prev = symbol_bars[i-1]
                curr = symbol_bars[i]
                
                # 1. 检查日期连续性
                gap = (curr.dt - prev.dt).days
                if gap > self.MAX_DATE_GAP_DAYS:
                    msg = f"标的 {symbol} 数据间隔过大: {prev.dt} 到 {curr.dt}, 间隔 {gap} 天"
                    warnings.warn(msg)
                    # 只有非常大的间隔才记录为异常（排除正常的节假日）
                    if gap > 15:
                        self._data_anomalies.append({
                            "symbol": symbol,
                            "date": curr.dt.isoformat(),
                            "type": "长期停牌",
                            "detail": msg
                        })

                # 2. 检查异常跳空 (比如 20% 以上的跳空，排除新股)
                if prev.close > 0:
                    gap_pct = (curr.open - prev.close) / prev.close
                    if abs(gap_pct) > 0.2: # 超过20%的跳空
                        msg = f"标的 {symbol} 在 {curr.dt} 出现大幅跳空 ({gap_pct:.2%}), 请检查复权"
                        warnings.warn(msg)
                        self._data_anomalies.append({
                            "symbol": symbol,
                            "date": curr.dt.isoformat(),
                            "type": "异常跳空",
                            "detail": msg
                        })

    def run(
        self,
        bars: list[Bar],
        strategy: EventStrategy,
        benchmark_bars: list[Bar] | None = None,
        start_date: date | None = None,
    ) -> EventBacktestResult:
        """执行回测
        
        时序说明：
        对于每个交易日 T:
          1. 处理前一日(T-1)收盘后生成的订单（在T日开盘执行）
          2. 调用策略的on_open方法（处理T日开盘时的操作）
          3. 按T日收盘价重估权益
          4. 调用策略的on_close方法（T日收盘后生成新的订单，将在T+1日开盘执行）
        """
        # 验证输入数据
        self._validate_input_data(bars)

        # 构建交易日历和索引
        calendar = self._build_calendar(bars)
        by_date = self._index_bars_by_date(bars)
        
        # 构建基准数据索引
        benchmark_by_date = {}
        if benchmark_bars:
            for b in benchmark_bars:
                benchmark_by_date[b.dt] = b

        # 初始化经纪人
        broker = PortfolioBroker(
            config=self._config.broker,
            initial_cash=self._config.initial_cash
        )

        # 待执行订单（key: 执行日期，value: 订单列表）
        # 这些订单是在前一日收盘后生成，计划在当日开盘执行的
        pending_orders: dict[date, list[Order]] = {}

        # 权益曲线
        equity_curve: list[EquityPoint] = []
        benchmark_curve: list[EquityPoint] = []

        util_series: list[dict] = []

        initial_benchmark_price = None

        start_idx = 0
        if start_date is not None:
            for j, dt_val in enumerate(calendar):
                if dt_val >= start_date:
                    start_idx = j
                    break
            else:
                start_idx = len(calendar)

        # 主回测循环
        for day_idx in range(start_idx, len(calendar)):
            current_dt = calendar[day_idx]
            # 创建市场数据帧
            frame = MarketFrame(
                dt=current_dt,
                bars=by_date.get(current_dt, {})
            )
            
            # 记录基准权益
            benchmark_equity = self._config.initial_cash
            if benchmark_by_date:
                b_bar = benchmark_by_date.get(current_dt)
                if b_bar:
                    if initial_benchmark_price is None:
                        initial_benchmark_price = b_bar.close
                    if initial_benchmark_price > 0:
                        benchmark_equity = self._config.initial_cash * (b_bar.close / initial_benchmark_price)
                elif benchmark_curve:
                    # 如果当天没有基准数据，沿用上一天的权益
                    benchmark_equity = benchmark_curve[-1].equity
            
            benchmark_curve.append(EquityPoint(dt=current_dt, equity=benchmark_equity))

            # ==== 开盘阶段 ====
            # 1. 先执行前一日收盘后生成的订单（这些订单计划在今天开盘执行）
            todays_orders = pending_orders.pop(current_dt, [])
            for order in todays_orders:
                bar = frame.bars.get(order.symbol)
                if bar is None:
                    # 如果标的今天没有数据，跳过该订单
                    warnings.warn(f"订单无法执行: 标的 {order.symbol} 在 {current_dt} 无行情数据")
                    continue

                # 执行订单
                broker.execute_order_open(
                    order=order,
                    bar=bar,
                    day_index=day_idx
                )

            # 2. 调用策略的开盘处理
            strategy.on_open(i=day_idx, frame=frame, broker=broker)

            # ==== 收盘阶段 ====
            # 3. 按收盘价重估权益
            close_prices = {sym: bar.close for sym, bar in frame.bars.items()}
            broker.mark_to_market(close_prices)

            # 记录权益曲线点
            equity_curve.append(EquityPoint(
                dt=current_dt,
                equity=broker.equity
            ))

            exposure = broker.exposure(close_prices)
            util = (exposure / broker.equity) if broker.equity > 0 else 0.0
            util_series.append({
                "dt": current_dt.isoformat(),
                "equity": float(broker.equity),
                "cash": float(broker.cash),
                "exposure": float(exposure),
                "utilization": float(util),
                "positions": int(len([p for p in broker.positions.values() if p.qty > 0]))
            })

            # 4. 调用策略的收盘处理（生成新的订单）
            new_orders = strategy.on_close(i=day_idx, frame=frame, broker=broker)

            # 将新生成的订单安排到下一个交易日开盘执行
            if new_orders and day_idx + 1 < len(calendar):
                next_trading_day = calendar[day_idx + 1]

                # 更新订单日期为执行日期
                orders_for_next_day = [
                    replace(order, dt=next_trading_day)
                    for order in new_orders
                    if order.qty > 0  # 过滤无效订单
                ]

                if orders_for_next_day:
                    pending_orders.setdefault(next_trading_day, []).extend(orders_for_next_day)

        # 回测结束，计算绩效指标
        metrics = Metrics.from_equity_curve(equity_curve, trades=broker.trades)

        # 提取策略日志和验证数据（如果存在）
        signal_logs = getattr(strategy, "signal_logs", [])
        decision_logs = getattr(strategy, "decision_logs", [])
        strategy_validation_data = getattr(strategy, "validation_data", {})

        avg_util = 0.0
        max_util = 0.0
        if util_series:
            uvals = [float(p.get("utilization", 0.0)) for p in util_series]
            avg_util = float(sum(uvals) / len(uvals))
            max_util = float(max(uvals))

        validation_data = strategy_validation_data if isinstance(strategy_validation_data, dict) else {}
        validation_data = dict(validation_data)
        validation_data["engine"] = {
            "utilization": {
                "avg": avg_util,
                "max": max_util,
                "series": util_series,
            }
        }

        return EventBacktestResult(
            equity_curve=equity_curve,
            metrics=metrics,
            trades=broker.trades,
            signal_logs=signal_logs,
            decision_logs=decision_logs,
            validation_data=validation_data,
            benchmark_equity_curve=benchmark_curve,
            data_anomalies=list(self._data_anomalies) # 复制当前收集到的异常
        )

    def run_with_validation(self, bars: list[Bar], strategy: EventStrategy) -> EventBacktestResult:
        """带详细验证的回测运行"""
        print("开始回测验证...")

        # 统计信息
        total_bars = len(bars)
        unique_symbols = len({b.symbol for b in bars})
        date_range = f"{min(b.dt for b in bars)} 到 {max(b.dt for b in bars)}"

        print("数据统计:")
        print(f"  - 总K线数: {total_bars}")
        print(f"  - 标的数量: {unique_symbols}")
        print(f"  - 时间范围: {date_range}")
        print(f"  - 期初资金: {self._config.initial_cash:,.2f}")

        # 执行回测
        result = self.run(bars, strategy)

        # 输出回测结果
        print("\n回测完成:")
        print(f"  - 交易天数: {len(result.equity_curve)}")
        print(f"  - 交易次数: {len(result.trades)}")
        print(f"  - 期末权益: {result.metrics.final_equity:,.2f}")
        print(f"  - 总收益率: {result.metrics.total_return:.2%}")

        return result
