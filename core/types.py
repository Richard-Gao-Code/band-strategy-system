from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from enum import Enum
from typing import ClassVar, Literal


class Side(Enum):
    """交易方向枚举"""
    BUY = "buy"
    SELL = "sell"

    @classmethod
    def from_str(cls, value: str) -> Side:
        """从字符串创建枚举"""
        value_lower = value.lower().strip()
        for side in cls:
            if side.value == value_lower:
                return side
        raise ValueError(f"Invalid side: {value}")


@dataclass(frozen=True, slots=True)
class Bar:
    """K线数据
    
    Attributes:
        symbol: 股票代码
        dt: 日期
        open: 开盘价
        high: 最高价
        low: 最低价
        close: 收盘价
        volume: 成交量
        index: 索引位置（用于快速访问）
    """
    symbol: str
    dt: date
    open: float
    high: float
    low: float
    close: float
    volume: float | None = None
    index: int = 0

    # 验证方法
    def __post_init__(self) -> None:
        """数据验证"""
        if not self.symbol:
            raise ValueError("Symbol cannot be empty")

        if self.open <= 0 or self.high <= 0 or self.low <= 0 or self.close <= 0:
            raise ValueError(f"Prices must be positive: {self}")

        if self.low > self.high:
            raise ValueError(f"Low ({self.low}) cannot be greater than high ({self.high})")

        # 放宽校验：允许开盘价/收盘价偶尔超出最高/最低（数据源可能存在异常或不同口径）

        if self.volume is not None and self.volume < 0:
            raise ValueError(f"Volume cannot be negative: {self.volume}")

    @property
    def typical_price(self) -> float:
        """典型价格：(high + low + close) / 3"""
        return (self.high + self.low + self.close) / 3.0

    @property
    def hl2(self) -> float:
        """高低价平均值：(high + low) / 2"""
        return (self.high + self.low) / 2.0

    @property
    def range(self) -> float:
        """价格波动范围：high - low"""
        return self.high - self.low

    @property
    def body(self) -> float:
        """K线实体长度：abs(close - open)"""
        return abs(self.close - self.open)

    def to_dict(self) -> dict:
        """转换为字典"""
        return {
            "symbol": self.symbol,
            "dt": self.dt.isoformat(),
            "open": self.open,
            "high": self.high,
            "low": self.low,
            "close": self.close,
            "volume": self.volume,
            "index": self.index
        }

    @classmethod
    def from_dict(cls, data: dict) -> Bar:
        """从字典创建Bar对象"""
        from datetime import datetime  # 局部导入避免循环

        data = data.copy()
        if isinstance(data["dt"], str):
            data["dt"] = datetime.fromisoformat(data["dt"]).date()
        return cls(**data)


@dataclass(frozen=True, slots=True)
class Fill:
    """成交记录"""
    side: Side
    qty: int
    price: float
    fee: float
    dt: date
    symbol: str | None = None

    def __post_init__(self) -> None:
        if self.qty <= 0:
            raise ValueError(f"Quantity must be positive: {self.qty}")
        if self.price <= 0:
            raise ValueError(f"Price must be positive: {self.price}")
        if self.fee < 0:
            raise ValueError(f"Fee cannot be negative: {self.fee}")

    @property
    def notional(self) -> float:
        """名义金额：qty * price"""
        return self.qty * self.price

    @property
    def net_amount(self) -> float:
        """净额：买入为负，卖出为正"""
        amount = self.notional + (self.fee if self.side == Side.BUY else -self.fee)
        return -amount if self.side == Side.BUY else amount

    def to_dict(self) -> dict:
        return {
            "side": self.side.value,
            "qty": self.qty,
            "price": self.price,
            "fee": self.fee,
            "dt": self.dt.isoformat(),
            "symbol": self.symbol,
            "notional": self.notional
        }


@dataclass(slots=True)
class Position:
    """简单仓位（用于基础Broker）"""
    qty: int
    avg_price: float
    symbol: str | None = None

    def __post_init__(self) -> None:
        if self.qty < 0:
            raise ValueError(f"Position quantity cannot be negative: {self.qty}")
        if self.qty > 0 and self.avg_price <= 0:
            raise ValueError(
                f"Average price must be positive for non-zero position: {self.avg_price}"
            )

    def market_value(self, current_price: float) -> float:
        """当前市值"""
        return self.qty * current_price if self.qty > 0 else 0.0

    def unrealized_pnl(self, current_price: float) -> float:
        """未实现盈亏"""
        if self.qty == 0:
            return 0.0
        return self.qty * (current_price - self.avg_price)


@dataclass(frozen=True, slots=True)
class BrokerConfig:
    """经纪人配置"""
    # 佣金费率 (默认0.03%)
    commission_rate: float = 0.0003
    # 滑点（基点，默认2bps）
    slippage_bps: float = 2.0
    # 最低佣金（默认5元）
    min_commission: float = 5.0
    # 印花税率 (默认0.1%)
    stamp_duty_rate: float = 0.001
    # 比例滑点（默认0.1%）
    slippage_rate: float = 0.001
    # 交易单位（默认100股）
    lot_size: int = 100

    # 验证器
    MIN_COMMISSION_RATE: ClassVar[float] = 0.0
    MAX_COMMISSION_RATE: ClassVar[float] = 0.01  # 1%
    MIN_SLIPPAGE_BPS: ClassVar[float] = 0.0
    MAX_SLIPPAGE_BPS: ClassVar[float] = 50.0  # 0.5%

    def __post_init__(self) -> None:
        if not (self.MIN_COMMISSION_RATE <= self.commission_rate <= self.MAX_COMMISSION_RATE):
            raise ValueError(
                f"Commission rate must be between {self.MIN_COMMISSION_RATE} and {self.MAX_COMMISSION_RATE}"
            )

        if not (self.MIN_SLIPPAGE_BPS <= self.slippage_bps <= self.MAX_SLIPPAGE_BPS):
            raise ValueError(
                f"Slippage bps must be between {self.MIN_SLIPPAGE_BPS} and {self.MAX_SLIPPAGE_BPS}"
            )

        if self.min_commission < 0:
            raise ValueError(f"Minimum commission cannot be negative: {self.min_commission}")

        if not (0 <= self.stamp_duty_rate <= 0.01):  # 最多1%
            raise ValueError(f"Stamp duty rate must be between 0 and 0.01: {self.stamp_duty_rate}")

        if not (0 <= self.slippage_rate <= 0.01):  # 最多1%
            raise ValueError(f"Slippage rate must be between 0 and 0.01: {self.slippage_rate}")

        if self.lot_size <= 0:
            raise ValueError(f"Lot size must be positive: {self.lot_size}")

    @property
    def slippage_percentage(self) -> float:
        """滑点百分比"""
        return self.slippage_bps / 10000.0

    def calculate_slippage(self, price: float, side: Side) -> float:
        """计算滑点后的价格"""
        slippage = price * self.slippage_rate
        return price + slippage if side == Side.BUY else price - slippage

    def calculate_commission(self, notional: float) -> float:
        """计算佣金"""
        commission = abs(notional) * self.commission_rate
        return max(commission, self.min_commission)


@dataclass(frozen=True, slots=True)
class BacktestConfig:
    """回测配置"""
    initial_cash: float = 1_000_000.0
    broker: BrokerConfig = field(default_factory=BrokerConfig)
    benchmark_symbol: str | None = None

    def __post_init__(self) -> None:
        if self.initial_cash <= 0:
            raise ValueError(f"Initial cash must be positive: {self.initial_cash}")


@dataclass(frozen=True, slots=True)
class Order:
    """交易订单"""
    symbol: str
    qty: int
    side: Side
    dt: date
    reason: str = ""
    initial_stop: float | None = None  # 初始止损价
    open_price: float | None = None
    limit_price: float | None = None

    def __post_init__(self) -> None:
        if not self.symbol:
            raise ValueError("Symbol cannot be empty")
        if self.qty <= 0:
            raise ValueError(f"Order quantity must be positive: {self.qty}")
        if self.open_price is not None and self.open_price <= 0:
            raise ValueError(f"Order open_price must be positive: {self.open_price}")
        if self.limit_price is not None and self.limit_price <= 0:
            raise ValueError(f"Order limit_price must be positive: {self.limit_price}")

    @property
    def is_buy(self) -> bool:
        """是否为买入订单"""
        return self.side == Side.BUY

    @property
    def is_sell(self) -> bool:
        """是否为卖出订单"""
        return self.side == Side.SELL


@dataclass(frozen=True, slots=True)
class EquityPoint:
    """权益曲线点"""
    dt: date
    equity: float
    returns: float = 0.0

    def __post_init__(self) -> None:
        if self.equity < 0:
            raise ValueError(f"Equity cannot be negative: {self.equity}")

    def to_dict(self) -> dict:
        return {
            "dt": self.dt.isoformat(),
            "equity": self.equity
        }


@dataclass(slots=True)
class PositionState:
    """仓位状态（用于PortfolioBroker）"""
    symbol: str
    qty: int
    avg_price: float
    entry_qty: int = 0
    entry_notional: float = 0.0
    entry_fee: float = 0.0
    entry_dt: date | None = None
    entry_price: float | None = None
    entry_index: int | None = None
    entry_index_confirmed: bool = False
    entry_reason: str = ""
    initial_stop: float | None = None
    trailing_active: bool = False
    trailing_stop: float | None = None
    highest_close: float | None = None

    def __post_init__(self) -> None:
        if not self.symbol:
            raise ValueError("Symbol cannot be empty")
        if self.qty < 0:
            raise ValueError(f"Position quantity cannot be negative: {self.qty}")
        if self.qty > 0 and self.avg_price <= 0:
            raise ValueError(f"Average price must be positive for non-zero position: {self.avg_price}")

        # 验证止损价格
        if self.initial_stop is not None and self.initial_stop <= 0:
            raise ValueError(f"Initial stop must be positive: {self.initial_stop}")
        if self.trailing_stop is not None and self.trailing_stop <= 0:
            raise ValueError(f"Trailing stop must be positive: {self.trailing_stop}")

    @property
    def is_open(self) -> bool:
        """仓位是否开立"""
        return self.qty > 0

    def market_value(self, current_price: float) -> float:
        """当前市值"""
        return self.qty * current_price if self.is_open else 0.0

    def unrealized_pnl(self, current_price: float) -> float:
        """未实现盈亏"""
        if not self.is_open:
            return 0.0
        return self.qty * (current_price - self.avg_price)

    def unrealized_pnl_percentage(self, current_price: float) -> float:
        """未实现盈亏百分比"""
        if not self.is_open or self.avg_price == 0:
            return 0.0
        return (current_price / self.avg_price) - 1.0

    def update_stop(self, current_price: float, atr: float | None = None) -> None:
        """更新止损价格
        
        Args:
            current_price: 当前价格
            atr: 平均真实波幅（用于动态止损）
        """
        if not self.is_open:
            return

        # 更新最高收盘价
        if self.highest_close is None or current_price > self.highest_close:
            self.highest_close = current_price

        # 动态更新跟踪止损
        if self.trailing_active and self.highest_close is not None and atr is not None:
            self.trailing_stop = self.highest_close - (atr * 2.0)  # 2倍ATR


@dataclass(frozen=True, slots=True)
class Trade:
    """交易记录"""
    symbol: str
    entry_dt: date
    exit_dt: date
    qty: int
    entry_price: float
    exit_price: float
    pnl: float
    r_multiple: float | None
    holding_days: int
    entry_reason: str = ""
    exit_reason: str = ""
    initial_stop: float | None = None
    trailing_stop: float | None = None
    entry_index_confirmed: bool = False

    def __post_init__(self) -> None:
        if not self.symbol:
            raise ValueError("Symbol cannot be empty")
        if self.qty <= 0:
            raise ValueError(f"Trade quantity must be positive: {self.qty}")
        if self.entry_price <= 0:
            raise ValueError(f"Entry price must be positive: {self.entry_price}")
        if self.exit_price <= 0:
            raise ValueError(f"Exit price must be positive: {self.exit_price}")
        if self.holding_days < 0:
            raise ValueError(f"Holding days cannot be negative: {self.holding_days}")
        if self.exit_dt < self.entry_dt:
            raise ValueError(f"Exit date ({self.exit_dt}) cannot be earlier than entry date ({self.entry_dt})")

    @property
    def entry_notional(self) -> float:
        """入场名义金额"""
        return self.qty * self.entry_price

    @property
    def exit_notional(self) -> float:
        """出场名义金额"""
        return self.qty * self.exit_price

    @property
    def pnl_percentage(self) -> float:
        """盈亏百分比"""
        if self.entry_price == 0:
            return 0.0
        return (self.exit_price / self.entry_price) - 1.0

    @property
    def annualized_return(self) -> float:
        """年化收益率"""
        if self.holding_days == 0 or self.pnl_percentage == 0:
            return 0.0
        return (1 + self.pnl_percentage) ** (365.0 / self.holding_days) - 1

    @property
    def is_winning(self) -> bool:
        """是否为盈利交易"""
        return self.pnl > 0

    @property
    def risk_amount(self) -> float | None:
        """风险金额（入场价 - 初始止损）"""
        if self.initial_stop is None or self.entry_price is None:
            return None
        return self.entry_price - self.initial_stop

    def to_dict(self) -> dict:
        """转换为字典"""
        return {
            "symbol": self.symbol,
            "entry_dt": self.entry_dt.isoformat(),
            "exit_dt": self.exit_dt.isoformat(),
            "qty": self.qty,
            "entry_price": self.entry_price,
            "exit_price": self.exit_price,
            "pnl": self.pnl,
            "pnl_percentage": self.pnl_percentage,
            "r_multiple": self.r_multiple,
            "holding_days": self.holding_days,
            "entry_reason": self.entry_reason,
            "exit_reason": self.exit_reason,
            "initial_stop": self.initial_stop,
            "trailing_stop": self.trailing_stop,
            "entry_index_confirmed": self.entry_index_confirmed,
            "is_winning": self.is_winning,
            "annualized_return": self.annualized_return
        }

    @classmethod
    def from_dict(cls, data: dict) -> Trade:
        """从字典创建Trade对象"""
        from datetime import datetime

        data = data.copy()
        # 转换日期字符串
        if isinstance(data["entry_dt"], str):
            data["entry_dt"] = datetime.fromisoformat(data["entry_dt"]).date()
        if isinstance(data["exit_dt"], str):
            data["exit_dt"] = datetime.fromisoformat(data["exit_dt"]).date()

        return cls(**data)


# 类型别名，方便使用
TradeSide = Literal["buy", "sell"]
PriceType = float
QuantityType = int
SymbolType = str
