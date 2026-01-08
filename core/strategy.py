from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional

import numpy as np

from .broker import Broker
from .types import Bar, Order, Position


class SignalType(Enum):
    """信号类型"""
    BUY = "buy"
    SELL = "sell"
    HOLD = "hold"
    CLOSE = "close"


class OrderType(Enum):
    """订单类型"""
    MARKET = "market"
    LIMIT = "limit"
    STOP = "stop"
    STOP_LIMIT = "stop_limit"


@dataclass
class Signal:
    """交易信号"""
    type: SignalType
    symbol: str
    price: float
    quantity: int
    reason: str = ""
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None
    timestamp: Any = None


@dataclass
class RiskParams:
    """风险参数"""
    # 仓位管理
    max_position_size: float = 0.1  # 单个标的最大仓位比例
    max_portfolio_risk: float = 0.02  # 组合最大风险暴露
    position_sizing_method: str = "fixed_fractional"  # 仓位大小计算方法

    # 止损止盈
    stop_loss_pct: float = 0.10  # 止损百分比
    take_profit_pct: float = 0.20  # 止盈百分比
    trailing_stop_pct: Optional[float] = 0.05  # 移动止损百分比

    # 波动率调整
    use_volatility_adjustment: bool = True
    volatility_period: int = 20  # 波动率计算周期


class BaseStrategy(ABC):
    """策略基类"""

    def __init__(self, name: str = "Unnamed Strategy", risk_params: Optional[RiskParams] = None):
        self.name = name
        self.risk_params = risk_params or RiskParams()
        self.initialized = False
        self.signals: list[Signal] = []
        self.positions: dict[str, Position] = {}

        # 性能跟踪
        self.performance_history: list[dict] = []
        self.trade_history: list[dict] = []

    def on_init(self, broker: Broker) -> None:
        """策略初始化"""
        self.initialized = True
        self.broker = broker
        self._setup()

    @abstractmethod
    def _setup(self) -> None:
        """策略设置（子类实现）"""
        pass

    def on_bar(self, bars: dict[str, Bar]) -> list[Signal]:
        """处理K线数据，生成交易信号"""
        if not self.initialized:
            self.on_init(self.broker)

        # 清空之前的信号
        self.signals.clear()

        # 执行策略逻辑
        self._on_bar(bars)

        # 应用风险管理
        self._apply_risk_management(bars)

        return self.signals.copy()

    @abstractmethod
    def _on_bar(self, bars: dict[str, Bar]) -> None:
        """策略核心逻辑（子类实现）"""
        pass

    def on_tick(self, tick: dict[str, Any]) -> Optional[Signal]:
        """处理Tick数据（可选）"""
        return None

    def on_order(self, order: Order) -> None:
        """处理订单事件"""
        pass

    def on_trade(self, trade: dict) -> None:
        """处理成交事件"""
        self.trade_history.append(trade)

    def on_position(self, positions: dict[str, Position]) -> None:
        """更新持仓信息"""
        self.positions = positions

    def calculate_position_size(self, symbol: str, price: float,
                               risk_per_trade: float = 0.02) -> int:
        """计算基于风险的仓位大小"""
        if self.broker is None:
            return 0

        equity = self.broker.equity
        if equity <= 0 or price <= 0:
            return 0

        if self.risk_params.position_sizing_method == "fixed_fractional":
            # 固定分数法
            risk_amount = equity * risk_per_trade
            stop_loss_amount = price * self.risk_params.stop_loss_pct

            if stop_loss_amount <= 0:
                return 0

            shares = int(risk_amount / stop_loss_amount)

            # 应用最大仓位限制
            max_shares = int((equity * self.risk_params.max_position_size) / price)
            return min(shares, max_shares)

        elif self.risk_params.position_sizing_method == "kelly":
            # 凯利公式
            win_rate = 0.5  # 默认胜率，实际应从历史数据计算
            win_loss_ratio = 2.0  # 默认盈亏比

            kelly_fraction = win_rate - ((1 - win_rate) / win_loss_ratio)
            position_value = equity * kelly_fraction * self.risk_params.max_position_size

            return int(position_value / price)

        else:
            # 默认固定仓位
            return int((equity * 0.1) / price)

    def generate_signal(self, signal_type: SignalType, symbol: str,
                       price: float, reason: str = "") -> Optional[Signal]:
        """生成交易信号"""
        if price <= 0:
            return None

        # 计算仓位大小
        quantity = self.calculate_position_size(symbol, price)
        if quantity <= 0:
            return None

        # 设置止损止盈
        stop_loss = None
        take_profit = None

        if signal_type == SignalType.BUY:
            if self.risk_params.stop_loss_pct > 0:
                stop_loss = price * (1 - self.risk_params.stop_loss_pct)
            if self.risk_params.take_profit_pct > 0:
                take_profit = price * (1 + self.risk_params.take_profit_pct)
        elif signal_type == SignalType.SELL:
            if self.risk_params.stop_loss_pct > 0:
                stop_loss = price * (1 + self.risk_params.stop_loss_pct)
            if self.risk_params.take_profit_pct > 0:
                take_profit = price * (1 - self.risk_params.take_profit_pct)

        signal = Signal(
            type=signal_type,
            symbol=symbol,
            price=price,
            quantity=quantity,
            reason=reason,
            stop_loss=stop_loss,
            take_profit=take_profit
        )

        self.signals.append(signal)
        return signal

    def _apply_risk_management(self, bars: dict[str, Bar]) -> None:
        """应用风险管理"""
        if not self.risk_params.trailing_stop_pct:
            return

        for symbol, position in self.positions.items():
            if position.quantity == 0 or symbol not in bars:
                continue

            current_price = bars[symbol].close
            entry_price = position.avg_price

            if entry_price <= 0:
                continue

            # 计算移动止损
            if position.quantity > 0:  # 多头
                highest_since_entry = max(entry_price, current_price)
                trailing_stop = highest_since_entry * (1 - self.risk_params.trailing_stop_pct)

                if current_price <= trailing_stop:
                    self.generate_signal(
                        SignalType.SELL,
                        symbol,
                        current_price,
                        reason="移动止损触发"
                    )

            elif position.quantity < 0:  # 空头
                lowest_since_entry = min(entry_price, current_price)
                trailing_stop = lowest_since_entry * (1 + self.risk_params.trailing_stop_pct)

                if current_price >= trailing_stop:
                    self.generate_signal(
                        SignalType.BUY,
                        symbol,
                        current_price,
                        reason="移动止损触发"
                    )

    def record_performance(self, metrics: dict[str, Any]) -> None:
        """记录性能指标"""
        self.performance_history.append(metrics)

    def get_performance_summary(self) -> dict[str, Any]:
        """获取策略性能摘要"""
        if not self.performance_history:
            return {}

        latest = self.performance_history[-1]
        return {
            "strategy_name": self.name,
            "total_return": latest.get("total_return", 0),
            "sharpe_ratio": latest.get("sharpe_ratio", 0),
            "max_drawdown": latest.get("max_drawdown", 0),
            "win_rate": latest.get("win_rate", 0),
            "total_trades": len(self.trade_history)
        }


class MovingAverageCrossStrategy(BaseStrategy):
    """移动平均线交叉策略（增强版）"""

    def __init__(
        self,
        fast: int = 5,
        slow: int = 20,
        name: str = "MA交叉",
        risk_params: Optional[RiskParams] = None,
        volume_period: int = 20,
        use_volume_filter: bool = True,
        volume_threshold: float = 1.5,
    ):
        super().__init__(name=name, risk_params=risk_params)
        self.fast_period = fast
        self.slow_period = slow
        self.volume_period = volume_period
        self.use_volume_filter = use_volume_filter
        self.volume_threshold = volume_threshold
        self._price_history: dict[str, list[float]] = {}
        self._volume_history: dict[str, list[float]] = {}

    def _setup(self) -> None:
        """策略设置"""
        # 初始化参数
        if self.fast_period <= 0 or self.slow_period <= 0 or self.fast_period >= self.slow_period:
            raise ValueError("fast_period必须小于slow_period且都大于0")

    def _on_bar(self, bars: dict[str, Bar]) -> None:
        """策略核心逻辑"""
        for symbol, bar in bars.items():
            # 更新价格历史
            if symbol not in self._price_history:
                self._price_history[symbol] = []
                self._volume_history[symbol] = []

            self._price_history[symbol].append(bar.close)
            self._volume_history[symbol].append(bar.volume or 0)

            # 保持历史数据长度
            max_len = max(self.slow_period, self.volume_period) + 10
            if len(self._price_history[symbol]) > max_len:
                self._price_history[symbol] = self._price_history[symbol][-max_len:]
                self._volume_history[symbol] = self._volume_history[symbol][-max_len:]

            # 检查是否有足够数据
            if len(self._price_history[symbol]) < self.slow_period:
                continue

            # 计算移动平均线
            closes = self._price_history[symbol]
            fast_ma = np.mean(closes[-self.fast_period:])
            slow_ma = np.mean(closes[-self.slow_period:])

            # 计算成交量
            if self.use_volume_filter and len(self._volume_history[symbol]) >= self.volume_period:
                current_volume = self._volume_history[symbol][-1]
                avg_volume = np.mean(self._volume_history[symbol][-self.volume_period:])
                volume_ratio = current_volume / avg_volume if avg_volume > 0 else 1.0
            else:
                volume_ratio = 1.0

            # 获取当前持仓
            current_position = self.positions.get(symbol)
            current_qty = current_position.quantity if current_position else 0

            # 生成交易信号
            if current_qty == 0:
                # 没有持仓，检查入场信号
                if fast_ma > slow_ma and volume_ratio > self.volume_threshold:
                    # 金叉买入
                    self.generate_signal(
                        SignalType.BUY,
                        symbol,
                        bar.close,
                        reason=f"MA金叉: fast={fast_ma:.2f}, slow={slow_ma:.2f}"
                    )
                elif fast_ma < slow_ma and volume_ratio > self.volume_threshold:
                    # 死叉卖出（可以做空）
                    self.generate_signal(
                        SignalType.SELL,
                        symbol,
                        bar.close,
                        reason=f"MA死叉: fast={fast_ma:.2f}, slow={slow_ma:.2f}"
                    )

            elif current_qty > 0:
                # 持有多头，检查出场信号
                if fast_ma < slow_ma:
                    # 死叉平仓
                    self.generate_signal(
                        SignalType.SELL,
                        symbol,
                        bar.close,
                        reason="MA死叉平仓"
                    )

            elif current_qty < 0:
                # 持有空头，检查出场信号
                if fast_ma > slow_ma:
                    # 金叉平仓
                    self.generate_signal(
                        SignalType.BUY,
                        symbol,
                        bar.close,
                        reason="MA金叉平仓"
                    )


@dataclass
class BreakoutStrategy(BaseStrategy):
    """突破策略"""

    # 策略参数
    lookback_period: int = 20
    breakout_multiplier: float = 1.0
    use_atr: bool = True
    atr_period: int = 14

    # 内部状态
    _high_history: dict[str, list[float]] = field(default_factory=dict)
    _low_history: dict[str, list[float]] = field(default_factory=dict)
    _atr_history: dict[str, list[float]] = field(default_factory=dict)

    def _setup(self) -> None:
        """策略设置"""
        pass

    def _calculate_atr(self, highs: list[float], lows: list[float],
                      closes: list[float], period: int) -> float:
        """计算平均真实波幅"""
        if len(highs) < period or len(lows) < period or len(closes) < period:
            return 0.0

        tr_values = []
        for i in range(1, len(closes)):
            high_low = highs[i] - lows[i]
            high_close = abs(highs[i] - closes[i-1])
            low_close = abs(lows[i] - closes[i-1])
            tr = max(high_low, high_close, low_close)
            tr_values.append(tr)

        if len(tr_values) < period:
            return 0.0

        return np.mean(tr_values[-period:])

    def _on_bar(self, bars: dict[str, Bar]) -> None:
        """策略核心逻辑"""
        for symbol, bar in bars.items():
            # 更新历史数据
            if symbol not in self._high_history:
                self._high_history[symbol] = []
                self._low_history[symbol] = []

            self._high_history[symbol].append(bar.high)
            self._low_history[symbol].append(bar.low)

            # 保持历史数据长度
            max_len = max(self.lookback_period, self.atr_period) + 10
            if len(self._high_history[symbol]) > max_len:
                self._high_history[symbol] = self._high_history[symbol][-max_len:]
                self._low_history[symbol] = self._low_history[symbol][-max_len:]

            # 检查是否有足够数据
            if len(self._high_history[symbol]) < self.lookback_period:
                continue

            # 计算突破水平
            recent_highs = self._high_history[symbol][-self.lookback_period:]
            recent_lows = self._low_history[symbol][-self.lookback_period:]

            resistance = max(recent_highs)
            support = min(recent_lows)

            # 计算ATR（如果使用）
            if self.use_atr:
                closes = [bar.close]
                atr = self._calculate_atr(
                    self._high_history[symbol],
                    self._low_history[symbol],
                    closes,
                    self.atr_period
                )
                breakout_threshold = atr * self.breakout_multiplier
            else:
                breakout_threshold = 0

            # 获取当前持仓
            current_position = self.positions.get(symbol)
            current_qty = current_position.quantity if current_position else 0

            # 检查突破信号
            if current_qty == 0:
                # 向上突破阻力位
                if bar.close > resistance + breakout_threshold:
                    self.generate_signal(
                        SignalType.BUY,
                        symbol,
                        bar.close,
                        reason=f"向上突破: {bar.close:.2f} > {resistance:.2f}"
                    )
                # 向下跌破支撑位
                elif bar.close < support - breakout_threshold:
                    self.generate_signal(
                        SignalType.SELL,
                        symbol,
                        bar.close,
                        reason=f"向下突破: {bar.close:.2f} < {support:.2f}"
                    )

            # 检查出场信号（基于相反的突破）
            elif current_qty > 0 and bar.close < support:
                self.generate_signal(
                    SignalType.SELL,
                    symbol,
                    bar.close,
                    reason="跌破支撑位出场"
                )

            elif current_qty < 0 and bar.close > resistance:
                self.generate_signal(
                    SignalType.BUY,
                    symbol,
                    bar.close,
                    reason="突破阻力位出场"
                )
