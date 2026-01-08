from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import ClassVar

from .types import Bar, BrokerConfig, Fill, Order, Position, PositionState, Side, Trade


@dataclass
class Broker:
    """简单经纪人（用于单一标的基础回测）"""
    config: BrokerConfig
    cash: float
    position: Position
    equity: float
    trade_count: int
    fills: list[Fill]
    trades: list[Trade]
    _entry_dt: date | None = None

    def __init__(self, config: BrokerConfig, initial_cash: float) -> None:
        self.config = config
        self.cash = float(initial_cash)
        self.position = Position(qty=0, avg_price=0.0, symbol=None)
        self.equity = float(initial_cash)
        self.trade_count = 0
        self.fills = []
        self.trades = []
        self._entry_dt = None

    def get_trade_history(self) -> list[Trade]:
        """获取交易历史"""
        return self.trades

    def mark_to_market(self, bar: Bar) -> None:
        """按市价重估"""
        if self.position.qty == 0 or self.position.symbol != bar.symbol:
            self.equity = self.cash
            return
        self.equity = self.cash + self.position.qty * bar.close

    def _execution_price(self, bar: Bar, side: Side) -> float:
        """计算执行价格（考虑滑点）"""
        # 策略文档：滑点0.1%
        if side == Side.BUY:
            return bar.open * (1.0 + self.config.slippage_rate)
        return bar.open * (1.0 - self.config.slippage_rate)

    def _commission(self, notional: float) -> float:
        """计算佣金：0.03%，最低5元"""
        commission = abs(notional) * self.config.commission_rate
        return max(commission, self.config.min_commission)

    def _stamp_duty(self, notional: float, side: Side) -> float:
        """计算印花税：0.1%，仅卖出时收取"""
        if side != Side.SELL:
            return 0.0
        return abs(notional) * self.config.stamp_duty_rate

    def rebalance_to_target(self, bar: Bar, target_qty: int) -> Fill | None:
        """调整到目标仓位"""
        if bar.symbol is None:
            return None
        if self.position.symbol is None and target_qty != 0:
            self.position.symbol = bar.symbol
        if self.position.symbol != bar.symbol:
            return None

        delta = int(target_qty) - int(self.position.qty)
        if delta == 0:
            return None

        side = Side.BUY if delta > 0 else Side.SELL
        qty = abs(delta)
        px = self._execution_price(bar, side=side)
        notional = qty * px
        commission = self._commission(notional)
        stamp = self._stamp_duty(notional, side=side)
        fee = commission + stamp

        if side == Side.BUY:
            if self.position.qty == 0:
                self._entry_dt = bar.dt

            total_cost = notional + fee
            if total_cost > self.cash:
                # 资金不足，放弃交易
                return None
            self.cash -= total_cost
            new_qty = self.position.qty + qty
            if new_qty == 0:
                self.position.avg_price = 0.0
            else:
                self.position.avg_price = (
                    (self.position.avg_price * self.position.qty) + (px * qty)
                ) / new_qty
            self.position.qty = new_qty
        else:
            if qty > self.position.qty:
                qty = self.position.qty
                notional = qty * px
                commission = self._commission(notional)
                stamp = self._stamp_duty(notional, side=side)
                fee = commission + stamp

            # 记录交易
            # 按照用户要求公式: (卖出价 - 买入价) × 股数
            gross_pnl = (px - self.position.avg_price) * qty
            # 内部计算仍需考虑费用以更新现金
            net_pnl = gross_pnl - fee
            
            entry_dt = self._entry_dt if self._entry_dt else bar.dt
            holding_days = (bar.dt - entry_dt).days

            self.trades.append(Trade(
                symbol=bar.symbol,
                entry_dt=entry_dt,
                exit_dt=bar.dt,
                qty=qty,
                entry_price=self.position.avg_price,
                exit_price=px,
                pnl=float(gross_pnl),
                r_multiple=None,
                holding_days=holding_days
            ))

            self.cash += notional - fee
            self.position.qty -= qty
            if self.position.qty == 0:
                self.position.avg_price = 0.0
                self._entry_dt = None

        self.trade_count += 1
        self.mark_to_market(bar)
        fill = Fill(
            side=side,
            qty=qty,
            price=px,
            fee=fee,
            dt=bar.dt,
            symbol=bar.symbol
        )
        self.fills.append(fill)
        return fill

    def close_out_last_price(self, bar: Bar | None) -> None:
        """最后一天按市价平仓"""
        if bar is None:
            return
        self.mark_to_market(bar)

    @property
    def positions(self) -> dict[str, Position]:
        """兼容接口：返回持仓映射"""
        if self.position.symbol is None or self.position.qty == 0:
            return {}
        return {self.position.symbol: self.position}


@dataclass
class PortfolioBroker:
    """组合经纪人（用于多标的组合回测）"""
    config: BrokerConfig
    cash: float
    positions: dict[str, PositionState]
    equity: float
    trade_count: int
    trades: list[Trade]

    # 验证常量
    MIN_CASH_THRESHOLD: ClassVar[float] = 0.01  # 最小现金阈值

    def __init__(self, config: BrokerConfig, initial_cash: float) -> None:
        self.config = config
        self.cash = float(initial_cash)
        self.positions = {}
        self.equity = float(initial_cash)
        self.trade_count = 0
        self.trades = []

    def position_qty(self, symbol: str) -> int:
        """获取指定标的的持仓数量"""
        pos = self.positions.get(symbol)
        return 0 if pos is None else int(pos.qty)

    def exposure(self, close_by_symbol: dict[str, float]) -> float:
        """计算当前总持仓市值"""
        total = 0.0
        for sym, pos in self.positions.items():
            if pos.qty == 0:
                continue
            px = close_by_symbol.get(sym)
            if px is None:
                continue
            total += pos.qty * px
        return total

    def mark_to_market(self, close_by_symbol: dict[str, float]) -> None:
        """按市价重估整个组合"""
        equity = self.cash
        for sym, pos in self.positions.items():
            if pos.qty == 0:
                continue
            px = close_by_symbol.get(sym)
            if px is None:
                continue
            equity += pos.qty * px
        self.equity = float(equity)

    def _commission(self, notional: float) -> float:
        """计算佣金：0.03%，最低5元"""
        commission = abs(notional) * self.config.commission_rate
        if commission == 0:
            return 0.0
        return max(commission, self.config.min_commission)

    def _stamp_duty(self, notional: float, side: Side) -> float:
        """计算印花税：0.1%，仅卖出时收取"""
        if side != Side.SELL:
            return 0.0
        return abs(notional) * self.config.stamp_duty_rate

    def _execution_price(self, open_price: float, side: Side) -> float:
        """计算执行价格（考虑滑点）"""
        # 策略文档：滑点0.1%
        if side == Side.BUY:
            return open_price * (1.0 + self.config.slippage_rate)
        return open_price * (1.0 - self.config.slippage_rate)

    def execute_order_open(
        self,
        order: Order,
        bar: Bar,
        day_index: int,
    ) -> Fill | None:
        """执行开盘订单
        
        严格按照策略文档：
        - T+1日开盘价成交
        - 考虑滑点0.1%
        - 佣金0.03%（最低5元）
        - 印花税0.1%（仅卖出）
        """
        if order.qty <= 0:
            return None
        if order.symbol != bar.symbol:
            return None

        side = order.side

        forced_open = order.open_price is not None and order.open_price > 0
        limit_price = getattr(order, "limit_price", None)
        if limit_price is not None:
            try:
                limit_price = float(limit_price)
            except Exception:
                limit_price = None
        if limit_price is not None and limit_price <= 0:
            limit_price = None

        open_price = float(bar.open)
        if forced_open:
            open_price = float(order.open_price)

        if (not forced_open) and (limit_price is not None):
            lp = float(limit_price)
            if side == Side.BUY:
                if float(bar.open) > lp:
                    if float(bar.low) <= lp:
                        open_price = lp
                    else:
                        return None
            else:
                if float(bar.open) < lp:
                    if float(bar.high) >= lp:
                        open_price = lp
                    else:
                        return None

        px = self._execution_price(open_price, side=side)
        if (not forced_open) and (limit_price is not None):
            if side == Side.BUY:
                px = min(px, float(limit_price))
            else:
                px = max(px, float(limit_price))

        notional = order.qty * px

        # 计算费用
        commission = self._commission(notional)
        stamp = self._stamp_duty(notional, side)
        fee = commission + stamp

        if side == Side.BUY:
            total_cost = notional + fee

            # 资金不足，放弃交易
            if total_cost > self.cash:
                return None

            qty = order.qty
            self.cash -= total_cost

            # 获取或创建仓位
            pos = self.positions.get(order.symbol)
            if pos is None:
                pos = PositionState(
                    symbol=order.symbol,
                    qty=0,
                    avg_price=0.0,
                    entry_dt=order.dt,
                    entry_price=px,
                    entry_index=day_index,
                    entry_reason=order.reason,
                    initial_stop=order.initial_stop
                )
                self.positions[order.symbol] = pos

            # 更新仓位信息
            new_qty = pos.qty + qty
            pos.avg_price = ((pos.avg_price * pos.qty) + (px * qty)) / new_qty if new_qty > 0 else 0.0
            pos.qty = new_qty

            # 如果是首次入场（或之前已平仓重新入场），更新入场信息
            if pos.entry_dt is None:
                pos.entry_dt = order.dt
                pos.entry_price = px
                pos.entry_index = day_index
                pos.entry_reason = order.reason

            pos.entry_qty += qty
            pos.entry_notional += notional
            pos.entry_fee += fee
        else:
            # 卖出逻辑
            pos = self.positions.get(order.symbol)
            if pos is None or pos.qty <= 0:
                return None

            qty_before = pos.qty
            qty = min(order.qty, qty_before)

            # 重新计算卖出部分的名义金额和费用
            notional = qty * px
            commission = self._commission(notional)
            stamp = self._stamp_duty(notional, side)
            fee = commission + stamp

            self.cash += notional - fee
            pos.qty -= qty

            # 计算入场均价 (当前周期的平均买入成本)
            entry_avg_price = (
                pos.entry_notional / pos.entry_qty if pos.entry_qty > 0 else pos.entry_price
            )

            # 计算盈亏 (按照用户要求公式: (卖出价 - 买入价) × 股数)
            gross_pnl = (px - entry_avg_price) * qty
            
            # 计算持有天数
            holding_days = (
                (day_index - pos.entry_index + 1) if pos.entry_index is not None else 0
            )

            # 计算R倍数（盈亏/风险）
            r_multiple = None
            if pos.initial_stop is not None and entry_avg_price is not None:
                risk_per_share = entry_avg_price - pos.initial_stop
                if risk_per_share > 0:
                    profit_per_share = px - entry_avg_price
                    r_multiple = profit_per_share / risk_per_share

            # 创建交易记录 (每次卖出都记录)
            trade = Trade(
                symbol=order.symbol,
                entry_dt=pos.entry_dt,
                exit_dt=order.dt,
                qty=qty,  # 使用本次卖出数量
                entry_price=float(entry_avg_price),
                exit_price=px,
                pnl=float(gross_pnl),
                r_multiple=r_multiple,
                holding_days=holding_days,
                entry_reason=pos.entry_reason,
                exit_reason=order.reason,
                initial_stop=pos.initial_stop,
                trailing_stop=pos.trailing_stop,
                entry_index_confirmed=bool(pos.entry_index_confirmed),
            )
            self.trades.append(trade)

            # 如果完全平仓，清理仓位状态
            if pos.qty == 0:
                del self.positions[order.symbol]
            else:
                # 部分卖出，更新平均成本
                # 注意：avg_price 保持不变（因为是部分卖出，剩余部分的单位成本不变）
                pass

        self.trade_count += 1

        # 创建成交记录
        fill = Fill(
            side=side,
            qty=qty,
            price=px,
            fee=fee,
            dt=order.dt,
            symbol=order.symbol
        )
        return fill
