"""
量化交易框架

一个完整的量化交易回测框架，支持多种策略和数据分析工具。
"""

__version__ = "1.1.0"
__author__ = "Quant Team"
__license__ = "MIT"

__all__ = [
    # 核心引擎
    "BacktestEngine",
    "BacktestResult",
    "EventBacktestEngine",
    "EventBacktestResult",

    # 策略
    "BaseStrategy",
    "MovingAverageCrossStrategy",
    "BreakoutStrategy",
    "PlatformBreakoutStrategy",

    # 配置
    "BacktestConfig",
    "BrokerConfig",
    "PlatformBreakoutConfig",
    "RiskParams",

    # 数据模块
    "Bar",
    "EquityPoint",
    "Fill",
    "Order",
    "Position",
    "Trade",

    # 数据管理
    "load_bars_from_csv",
    "load_bars_from_csv_dir",
    "write_bars_to_csv",
    "fetch_daily_bars_eastmoney",

    # 绩效评估
    "Metrics",

    # 股票池和基本面
    "Universe",
    "FundamentalsStore",
    "FundamentalPoint",

    # 事件引擎
    "EventStrategy",
    "MarketFrame",

    # 类型定义
    "SignalType",
    "OrderType",
    "Exchange",
    "Industry",

    # 命令行接口
    "main",
]

# 核心引擎
# from .advanced_engine import AdvancedBacktestEngine  # 模块不存在，暂时注释

# 命令行接口
from .cli import main

# 数据管理
from .data import (
    fetch_daily_bars_eastmoney,
    load_bars_from_csv,
    load_bars_from_csv_dir,
    write_bars_to_csv,
)
from .engine import BacktestEngine, BacktestResult

# 事件引擎
from .event_engine import EventBacktestEngine, EventBacktestResult, EventStrategy, MarketFrame
from .fundamentals import FundamentalPoint, FundamentalsStore

# 绩效评估
# 指标
from .metrics import (
    Metrics,
    # calculate_max_drawdown_details,  # 函数不存在，暂时注释
    # calculate_sharpe_ratio,  # 函数不存在，暂时注释
    # calculate_sortino_ratio,  # 函数不存在，暂时注释
)
# from .metrics_calculator import MetricsCalculator  # 模块不存在，暂时注释
from .platform_breakout import PlatformBreakoutConfig, PlatformBreakoutStrategy

# 策略
# 类型定义
from .strategy import (
    BaseStrategy,
    BreakoutStrategy,
    MovingAverageCrossStrategy,
    OrderType,
    RiskParams,
    SignalType,
    # Strategy,  # 类不存在，暂时注释
)

# 配置
# 数据模块
from .types import BacktestConfig, Bar, BrokerConfig, EquityPoint, Fill, Order, Position, Trade

# 股票池和基本面
from .universe import Exchange, Industry, Universe, UniverseRecord
