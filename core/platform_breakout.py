from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import date
from typing import Optional

from .broker import PortfolioBroker
from .event_engine import EventStrategy, MarketFrame
from .fundamentals import FundamentalsStore
from .indicators import atr, avg_volume, find_platform, sma
from .types import Bar, Order, Side
from .universe import Universe

# 设置日志
logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class PlatformBreakoutConfig:
    """平台突破策略配置"""
    # 平台检测参数
    platform_min_days: int = 7
    platform_max_days: int = 360
    platform_max_amplitude: float = 0.25  # 平台最大振幅 25%

    # 成交量确认参数
    volume_lookback: int = 5
    volume_multiple: float = 1.5

    # 趋势过滤参数
    price_ma_days: int = 20
    require_index_confirm: bool = True
    index_symbol: str = "000300.SH"  # 沪深300
    index_ma_days: int = 20

    # 风险管理参数
    risk_per_trade: float = 0.01  # 每笔交易风险1%
    max_symbol_exposure: float = 0.20  # 单个股票最大暴露20%
    max_total_exposure: float = 0.80  # 总暴露80%

    # 止损参数
    stop_atr_days: int = 14
    initial_stop_atr_mult: float = 1.5  # 初始止损 ATR倍数
    trailing_activate_profit: float = 0.15  # 15%盈利后激活移动止损
    trailing_atr_mult: float = 2.0  # 移动止损 ATR倍数
    initial_stop_pct: Optional[float] = None
    breakout_min_pct: float = 0.03  # 最小突破幅度，默认 3%
    gap_open_max_pct: float = 0.01  # 跳空买入上限，默认 1%

    # 出场参数
    max_holding_days: int = 250
    enable_trend_exit: bool = False

    # 账户风险管理
    account_drawdown_pause: float = 0.15  # 15%回撤暂停交易
    auto_resume_drawdown_pause: bool = True
    loss_streak_pause_count: int = 3  # 连续3笔亏损暂停
    loss_streak_pause_pct: float = 0.05  # 累计亏损5%暂停
    auto_resume_loss_pause: bool = False

    # 涨跌停板处理
    limit_up_pct: float = 0.10  # 涨停板10%
    limit_down_pct: float = 0.10  # 跌停板10%

    # 平台优化参数
    platform_max_single_day_pct: float = 0.11  # 平台内单日最大涨跌幅限制
    platform_min_slope: float = -0.005  # 平台内线性回归斜率下限
    platform_max_slope: float = 0.005  # 平台内线性回归斜率上限

    # 基本面过滤参数
    min_list_days: int = 120  # 上市至少120天
    min_avg_amount_20d: float = 0.0  # 20日平均成交额1亿
    min_market_cap: float = 0.0  # 市值至少500亿
    pe_ttm_max: float = 60.0  # PE TTM不超过60倍
    enable_pe_filter: bool = False

    # 性能优化参数
    max_symbols_per_day: int = 5  # 每日最大关注股票数

    auto_profile_enable: bool = False
    auto_profile_mcap_threshold: float = 200.0

    # 扫描参数
    scan_recent_days: int = 1  # 扫描最近N天的信号


@dataclass(frozen=True)
class EntryIntent:
    """入场意图"""
    symbol: str
    breakout_dt: date
    platform_high: float
    platform_low: float
    initial_stop: float
    index_ok: bool
    volume_ok: bool
    breakout_price: float

    @property
    def risk_per_share(self) -> float:
        """每股风险"""
        return self.breakout_price - self.initial_stop

    @property
    def risk_reward_ratio(self, target_price: float) -> float:
        """风险收益比"""
        if self.risk_per_share <= 0:
            return 0.0
        reward = target_price - self.breakout_price
        return reward / self.risk_per_share


@dataclass
class PositionTracker:
    """持仓跟踪器"""
    symbol: str
    entry_date: date
    entry_price: float
    entry_index: int
    quantity: int
    initial_stop: Optional[float] = None
    highest_price: Optional[float] = None
    trailing_active: bool = False
    trailing_stop: Optional[float] = None
    exit_reason: Optional[str] = None
    exit_price: Optional[float] = None

    def update_trailing_stop(self, current_bar: Bar, atr_val: float,
                           trailing_atr_mult: float) -> None:
        """更新移动止损"""
        if self.highest_price is None or current_bar.high > self.highest_price:
            self.highest_price = current_bar.high

        if self.highest_price is not None:
            new_trailing_stop = self.highest_price - (atr_val * trailing_atr_mult)
            # 确保移动止损价永不下降
            if self.trailing_stop is None or new_trailing_stop > self.trailing_stop:
                self.trailing_stop = new_trailing_stop

    def should_trailing_activate(self, current_price: float,
                               activate_profit: float) -> bool:
        """检查是否应该激活移动止损"""
        if self.entry_price <= 0:
            return False
        profit_pct = (current_price / self.entry_price) - 1.0
        return profit_pct >= activate_profit


class PlatformBreakoutStrategy(EventStrategy):
    """平台突破策略（增强版）"""

    def __init__(
        self,
        bars: list[Bar],
        config: PlatformBreakoutConfig | None = None,
        universe: Optional[Universe] = None,
        fundamentals: Optional[FundamentalsStore] = None,
        strategy_name: str = "PlatformBreakout"
    ) -> None:
        self.strategy_name = strategy_name

        self.config = config or PlatformBreakoutConfig()
        self.universe = universe
        self.fundamentals = fundamentals

        # 数据处理
        self.bars_by_symbol: dict[str, list[Bar]] = self._organize_bars_by_symbol(bars)
        self.index_by_symbol_date = self._create_date_index()

        # 策略状态
        self.entry_intents: dict[str, EntryIntent] = {}
        self.all_entry_intents: list[EntryIntent] = []  # 记录所有产生的信号
        self.pending_exits: set[str] = set()
        self.position_trackers: dict[str, PositionTracker] = {}

        # 风险管理状态
        self.paused_new_entries = False
        self.pause_reason = ""
        self.peak_equity: Optional[float] = None
        self.initial_cash: Optional[float] = None
        self.processed_trades = 0
        self.loss_streak_count = 0
        self.loss_streak_amount = 0.0

        # 缓存
        self.last_close_prices: dict[str, float] = {}
        self.exit_reasons: dict[str, str] = {}
        self.exit_details: dict[str, dict[str, any]] = {}
        self._sma_cache: dict[tuple[str, int, date], float] = {}
        self._atr_cache: dict[tuple[str, int, date], float] = {}
        self._platform_cache: dict[tuple[str, date], Optional[any]] = {}

        # 信号分析日志
        self.signal_logs: list[dict[str, any]] = []
        # 决策日志（用于输出详细的入场出场原因）
        self.decision_logs: list[str] = []
        # 策略验证数据
        self.validation_data: dict[str, any] = {
            "atr_table": [],
            "index_table": [],
            "buy_execution_table": []
        }

        logger.info(f"平台突破策略初始化完成，配置: {self.config}")

    def _organize_bars_by_symbol(self, bars: list[Bar]) -> dict[str, list[Bar]]:
        """按股票代码组织K线数据"""
        by_symbol: dict[str, list[Bar]] = {}
        for bar in bars:
            by_symbol.setdefault(bar.symbol, []).append(bar)

        # 按日期排序
        for symbol in by_symbol:
            by_symbol[symbol].sort(key=lambda x: x.dt)

        return by_symbol

    def _create_date_index(self) -> dict[str, dict[date, int]]:
        """创建日期索引"""
        index_by_symbol_date: dict[str, dict[date, int]] = {}

        for symbol, bars in self.bars_by_symbol.items():
            date_index: dict[date, int] = {}
            for i, bar in enumerate(bars):
                date_index[bar.dt] = i
            index_by_symbol_date[symbol] = date_index

        return index_by_symbol_date

    def _get_symbol_index(self, symbol: str, dt: date) -> Optional[int]:
        """获取指定日期在股票数据中的索引"""
        date_index = self.index_by_symbol_date.get(symbol)
        if date_index is None:
            return None
        return date_index.get(dt)

    def _get_history_to_date(self, symbol: str, dt: date) -> list[Bar] | None:
        """获取到指定日期的历史数据"""
        idx = self._get_symbol_index(symbol, dt)
        if idx is None:
            return None

        return self.bars_by_symbol[symbol][:idx + 1]

    def _get_close_series(self, symbol: str, dt: date) -> list[float] | None:
        """获取到指定日期的收盘价序列"""
        history = self._get_history_to_date(symbol, dt)
        if history is None:
            return None

        return [bar.close for bar in history]

    def _check_index_confirmation(self, dt: date) -> bool:
        """检查指数确认"""
        if not self.config.require_index_confirm:
            return True

        symbol = self.config.index_symbol
        idx = self._get_symbol_index(symbol, dt)
        if idx is None:
            return False

        cache_key = (symbol, self.config.index_ma_days, dt)
        if cache_key in self._sma_cache:
            ma_value = self._sma_cache[cache_key]
        else:
            bars = self.bars_by_symbol.get(symbol)
            if not bars or len(bars) < self.config.index_ma_days:
                return False
            
            closes = [b.close for b in bars]
            ma_value = sma(closes, self.config.index_ma_days, end_index=idx)
            if ma_value is not None:
                self._sma_cache[cache_key] = ma_value
            else:
                return False

        current_close = self.bars_by_symbol[symbol][idx].close
        return current_close > ma_value

    def _check_price_filter(self, symbol: str, dt: date) -> bool:
        """检查价格过滤器（是否在均线之上）"""
        idx = self._get_symbol_index(symbol, dt)
        if idx is None:
            return False

        cache_key = (symbol, self.config.price_ma_days, dt)
        if cache_key in self._sma_cache:
            ma_value = self._sma_cache[cache_key]
        else:
            bars = self.bars_by_symbol.get(symbol)
            if not bars or len(bars) < self.config.price_ma_days:
                return False
            
            closes = [b.close for b in bars]
            ma_value = sma(closes, self.config.price_ma_days, end_index=idx)
            if ma_value is not None:
                self._sma_cache[cache_key] = ma_value
            else:
                return False

        current_close = self.bars_by_symbol[symbol][idx].close
        return current_close > ma_value

    def _get_market_cap(self, symbol: str, dt: date) -> Optional[float]:
        if self.fundamentals is not None:
            p = self.fundamentals.latest_on_or_before(symbol, dt)
            if p is not None and p.market_cap is not None:
                return p.market_cap

        if self.universe is not None:
            rec = self.universe.get(symbol)
            if rec is not None and rec.market_cap is not None:
                return rec.market_cap

        return None

    def _classify_auto_profile(self, symbol: str, dt: date) -> Optional[str]:
        if not self.config.auto_profile_enable:
            return None

        mcap = self._get_market_cap(symbol, dt)
        if mcap is None:
            return None

        is_gem_like = symbol.startswith("300") or symbol.startswith("688")
        is_large = mcap >= float(self.config.auto_profile_mcap_threshold)

        if not is_gem_like:
            return "A" if is_large else "B"

        return "C" if is_large else "D"

    def _get_effective_params(self, symbol: str, dt: date) -> dict[str, any]:
        profile = self._classify_auto_profile(symbol, dt)
        mcap = self._get_market_cap(symbol, dt) if profile is not None else None

        amp = float(self.config.platform_max_amplitude)
        single = float(self.config.platform_max_single_day_pct)
        breakout_min = float(self.config.breakout_min_pct)
        gap_max = float(self.config.gap_open_max_pct)

        if profile == "B":
            amp += 0.05
            single += 0.05
            breakout_min -= 0.005
            gap_max += 0.01
        elif profile == "C":
            amp += 0.10
            single += 0.10
            breakout_min -= 0.010
            gap_max += 0.02
        elif profile == "D":
            amp += 0.15
            single += 0.15
            breakout_min -= 0.015
            gap_max += 0.03

        amp = max(0.01, min(1.0, amp))
        single = max(0.01, min(1.0, single))
        breakout_min = max(0.0, breakout_min)
        gap_max = max(0.0, min(0.50, gap_max))

        return {
            "profile": profile,
            "market_cap": mcap,
            "platform_max_amplitude": amp,
            "platform_max_single_day_pct": single,
            "breakout_min_pct": breakout_min,
            "gap_open_max_pct": gap_max,
        }

    def _check_fundamental_filters(self, symbol: str, dt: date) -> bool:
        """检查基本面过滤器"""
        # 股票池过滤
        if self.universe is not None:
            if not self.universe.passes_static_filters(
                symbol=symbol,
                dt=dt,
                min_list_days=self.config.min_list_days
            ):
                return False

        # 基本面数据过滤
        if self.fundamentals is not None:
            fundamental_point = self.fundamentals.latest_on_or_before(symbol, dt)
            if fundamental_point is None:
                logger.debug(f"股票 {symbol} 在 {dt} 无基本面数据")
                return False

            # 成交额过滤
            if (fundamental_point.avg_amount_20d is not None and
                fundamental_point.avg_amount_20d < self.config.min_avg_amount_20d):
                return False

            # 市值过滤
            if (fundamental_point.market_cap is not None and
                fundamental_point.market_cap < self.config.min_market_cap):
                return False

            # PE过滤
            if self.config.enable_pe_filter:
                if fundamental_point.pe_ttm is None:
                    return False
                if fundamental_point.pe_ttm >= self.config.pe_ttm_max:
                    return False

        return True

    def _check_volume_confirmation(self, history: list[Bar]) -> bool:
        """检查成交量确认"""
        if len(history) < self.config.volume_lookback + 1:
            return False

        today_volume = history[-1].volume
        if today_volume is None:
            return False

        avg_volume_val = avg_volume(history[:-1], self.config.volume_lookback)
        if avg_volume_val is None:
            return False

        return today_volume > (avg_volume_val * self.config.volume_multiple)

    def _is_limit_up(self, bar: Bar, prev_close: Optional[float]) -> bool:
        """判断是否为涨停板（无法买入）"""
        if prev_close is None or prev_close <= 0:
            return False

        limit_up_price = prev_close * (1.0 + self.config.limit_up_pct)
        tolerance = 0.001  # 允许微小误差

        return abs(bar.close - limit_up_price) <= tolerance and bar.open == bar.high == bar.low == bar.close

    def _is_limit_down(self, bar: Bar, prev_close: Optional[float]) -> bool:
        """判断是否为跌停板（无法卖出）"""
        if prev_close is None or prev_close <= 0:
            return False

        limit_down_price = prev_close * (1.0 - self.config.limit_down_pct)
        tolerance = 0.001  # 允许微小误差

        return abs(bar.close - limit_down_price) <= tolerance and bar.open == bar.high == bar.low == bar.close

    def _update_risk_management_state(self, broker: PortfolioBroker) -> None:
        """更新风险管理状态"""
        if self.peak_equity is None:
            self.peak_equity = broker.equity
            self.initial_cash = broker.equity
            return

        # 更新峰值净值
        if broker.equity > self.peak_equity:
            self.peak_equity = broker.equity

        if self.peak_equity <= 0:
            return

        # 计算回撤
        current_drawdown = (broker.equity / self.peak_equity) - 1.0

        # 回撤暂停逻辑
        if current_drawdown <= -self.config.account_drawdown_pause:
            if not self.paused_new_entries:
                logger.warning(f"账户回撤 {current_drawdown:.2%} 超过阈值，暂停新交易")
            self.paused_new_entries = True
            self.pause_reason = "drawdown"
        elif (self.pause_reason == "drawdown" and
              self.config.auto_resume_drawdown_pause and
              current_drawdown > -self.config.account_drawdown_pause):
            if self.paused_new_entries:
                logger.info("账户回撤恢复，重新允许交易")
            self.paused_new_entries = False
            self.pause_reason = ""

        # 更新交易记录
        while self.processed_trades < len(broker.trades):
            trade = broker.trades[self.processed_trades]
            self.processed_trades += 1

            if trade.pnl < 0:
                self.loss_streak_count += 1
                self.loss_streak_amount += -trade.pnl
            else:
                self.loss_streak_count = 0
                self.loss_streak_amount = 0.0

            # 连续亏损暂停逻辑
            if (self.loss_streak_count >= self.config.loss_streak_pause_count or
                (self.initial_cash is not None and
                 self.loss_streak_amount >= (self.initial_cash * self.config.loss_streak_pause_pct))):
                if not self.paused_new_entries:
                    logger.warning(f"连续亏损 {self.loss_streak_count} 次，暂停新交易")
                self.paused_new_entries = True
                self.pause_reason = "loss_streak"

        # 恢复逻辑
        if self.pause_reason == "loss_streak" and self.config.auto_resume_loss_pause:
            self.paused_new_entries = False
            self.pause_reason = ""

    def _calculate_position_size(self, symbol: str, entry_price: float,
                               initial_stop: float, broker: PortfolioBroker) -> int:
        """计算仓位大小
        
        验证公式：可买入股数 = 总资金×1% / (买入价 - 初始止损价)
        限制条件：单票仓位 ≤ 20%
        """
        equity = broker.equity

        # 计算每股风险
        risk_per_share = entry_price - initial_stop
        if risk_per_share <= 0:
            # 如果风险为负（异常情况），至少给一个极小的正值以防除零，或者直接返回0
            logger.warning(f"股票 {symbol} 风险计算异常: 买入价={entry_price:.2f}, 止损价={initial_stop:.2f}")
            return 0

        # 1. 基于 1% 风险模型的股数
        # 可买入股数 = 总资金 * 风险比例 / 每股风险
        risk_amount = equity * self.config.risk_per_trade
        risk_shares = int(risk_amount / risk_per_share)

        # 2. 基于单票最大 20% 仓位限制的股数
        # 最大允许金额 = 总资金 * 20%
        max_exposure_amount = equity * self.config.max_symbol_exposure
        exposure_shares = int(max_exposure_amount / entry_price)

        # 3. 考虑账户总仓位限制 (max_total_exposure, 默认80%)
        current_total_exposure = 0.0
        for pos_symbol, position in broker.positions.items():
            if position.qty > 0:
                # 使用最近已知的收盘价估算市值
                last_price = self.last_close_prices.get(pos_symbol)
                if last_price:
                    current_total_exposure += position.qty * last_price
                else:
                    # 如果没有收盘价（刚买入当天），用买入价
                    current_total_exposure += position.qty * position.entry_price

        max_total_exposure_amount = equity * self.config.max_total_exposure
        remaining_exposure = max_total_exposure_amount - current_total_exposure
        
        if remaining_exposure <= 0:
            logger.debug(f"账户总仓位已满，无法买入 {symbol}")
            return 0
            
        remaining_shares = int(remaining_exposure / entry_price)

        # 取三者最小值，确保同时满足：风险控制、单票限额、总仓位限额
        target_shares = min(risk_shares, exposure_shares, remaining_shares)

        # 调整为整手数（通常 A 股为 100 股一手）
        if broker.config.lot_size > 0:
            target_shares = (target_shares // broker.config.lot_size) * broker.config.lot_size

        return max(0, target_shares)

    def _calculate_buy_price(self, open_price: float, prev_close: float, max_gap: float) -> tuple[float, bool]:
        """
        计算实际买入价，考虑跳空限制
        如果跳空超过max_gap，按限价买入
        """
        if prev_close <= 0:
            return open_price, False

        gap = (open_price - prev_close) / prev_close
        
        if gap > max_gap:
            # 跳空过大，使用限价
            limit_price = prev_close * (1.0 + max_gap)
            return limit_price, True  # 限价成交
        else:
            return open_price, False  # 开盘价成交

    def on_open(self, i: int, frame: MarketFrame, broker: PortfolioBroker) -> None:
        """开盘处理"""
        # 处理平仓
        for symbol in list(self.pending_exits):
            bar = frame.bars.get(symbol)
            if bar is None:
                continue

            prev_close = self.last_close_prices.get(symbol)
            if self._is_limit_down(bar, prev_close=prev_close):
                logger.info(f"股票 {symbol} 跌停，无法卖出")
                continue

            position_qty = broker.position_qty(symbol)
            if position_qty <= 0:
                self.pending_exits.discard(symbol)
                continue

            # 创建平仓订单
            order = Order(
                symbol=symbol,
                qty=position_qty,
                side=Side.SELL,
                dt=frame.dt,
                reason=self.exit_reasons.get(symbol, "exit")
            )

            broker.execute_order_open(order, bar, i)

            # 记录决策日志 [出场]
            # 示例格式：
            # [出场] 2020-12-28 600975
            #   触发：初始止损
            #   当日最低价：8.01 < 止损价8.05
            #   卖出价：8.04
            #   持仓天数：25
            #   盈亏：-3.21%
            tracker = self.position_trackers.get(symbol)
            if tracker:
                reason_map = {
                    "stop_loss": "初始止损",
                    "trailing_stop": "移动止损",
                    "max_holding_days": "最大持有天数",
                    "trend_exit": "趋势走弱",
                    "take_profit": "追踪止盈"
                }
                reason_str = reason_map.get(order.reason, order.reason)
                exit_price = bar.open * (1.0 - broker.config.slippage_rate)
                
                # 获取止损价
                final_stop = tracker.initial_stop
                if tracker.trailing_stop is not None:
                    if tracker.initial_stop is not None:
                        final_stop = max(tracker.initial_stop, tracker.trailing_stop)
                    else:
                        final_stop = tracker.trailing_stop
                
                pnl_pct = (exit_price / tracker.entry_price - 1.0) * 100
                holding_days = i - tracker.entry_index
                
                exit_log = (
                    f"[出场] {frame.dt} {symbol}<br>"
                    f"&nbsp;&nbsp;触发：{reason_str}<br>"
                    f"&nbsp;&nbsp;当日最低价：{bar.low:.2f} < 止损价{final_stop if final_stop else 0:.2f}<br>"
                    f"&nbsp;&nbsp;卖出价：{exit_price:.2f}<br>"
                    f"&nbsp;&nbsp;持仓天数：{holding_days}<br>"
                    f"&nbsp;&nbsp;盈亏：{pnl_pct:.2f}%"
                )
                if order.reason == "trend_exit":
                    det = self.exit_details.get(symbol)
                    if det and det.get("type") == "trend_exit":
                        exit_log += (
                            f"<br>&nbsp;&nbsp;趋势条件：收盘{det.get('close'):.2f} < {det.get('ma_days')}日均线{det.get('ma'):.2f}"
                        )
                self.decision_logs.append(exit_log)

            # 清理状态
            self.pending_exits.discard(symbol)
            self.exit_reasons.pop(symbol, None)
            self.entry_intents.pop(symbol, None)
            self.position_trackers.pop(symbol, None)
            self.exit_details.pop(symbol, None)

        # 处理开仓
        for symbol, intent in list(self.entry_intents.items()):
            bar = frame.bars.get(symbol)
            if bar is None:
                self.entry_intents.pop(symbol, None)
                continue

            # 检查涨停
            prev_close = self.last_close_prices.get(symbol)
            if self._is_limit_up(bar, prev_close=prev_close):
                logger.info(f"股票 {symbol} 涨停，无法买入")
                self.entry_intents.pop(symbol, None)
                continue

            # 检查是否已有持仓
            if broker.position_qty(symbol) != 0:
                self.entry_intents.pop(symbol, None)
                continue

            prev_close = self.last_close_prices.get(symbol)
            effective_open = bar.open
            is_limited = False
            
            if prev_close and prev_close > 0:
                eff_gap = self._get_effective_params(symbol, frame.dt).get("gap_open_max_pct", self.config.gap_open_max_pct)
                effective_open, is_limited = self._calculate_buy_price(
                    bar.open, 
                    prev_close, 
                    eff_gap
                )

            entry_price = effective_open * (1.0 + broker.config.slippage_rate)
            idx_entry = self._get_symbol_index(symbol, frame.dt)
            atr_val_entry = atr(self.bars_by_symbol.get(symbol, []), self.config.stop_atr_days, end_index=idx_entry) if idx_entry is not None else None
            use_pct = self.config.initial_stop_pct is not None and self.config.initial_stop_pct > 0
            if use_pct:
                initial_stop = entry_price * (1.0 - self.config.initial_stop_pct)
            elif atr_val_entry is not None:
                initial_stop = entry_price - (atr_val_entry * self.config.initial_stop_atr_mult)
            else:
                initial_stop = intent.initial_stop

            # 确保止损不低于0
            initial_stop = max(0.01, initial_stop)

            # 计算仓位大小
            position_size = self._calculate_position_size(
                symbol, entry_price, initial_stop, broker
            )

            if position_size <= 0:
                self.entry_intents.pop(symbol, None)
                continue

            # 创建开仓订单
            order = Order(
                symbol=symbol,
                qty=position_size,
                side=Side.BUY,
                dt=frame.dt,
                reason="breakout",
                initial_stop=initial_stop,
                open_price=effective_open,
            )

            broker.execute_order_open(order, bar, i)

            # 记录决策日志 [入场]
            # 示例格式：
            # [入场] 2020-12-03 600975
            #   买入价：8.31（前日收盘8.35，跳空-0.5%）
            #   买入数量：23,500股
            #   仓位：19.5%
            #   初始止损价：8.05
            atr_val = atr(self._get_history_to_date(symbol, intent.breakout_dt), self.config.stop_atr_days)
            prev_close = self.last_close_prices.get(symbol, bar.open)
            gap_pct = (bar.open / prev_close - 1.0) * 100 if prev_close else 0.0
            pos_pct = (position_size * entry_price) / broker.equity * 100
            
            entry_log = (
                f"[入场] {frame.dt} {symbol}<br>"
                f"&nbsp;&nbsp;买入价：{entry_price:.2f}（前日收盘{prev_close:.2f}，跳空{gap_pct:.1f}%）<br>"
                f"&nbsp;&nbsp;买入数量：{position_size:,}股<br>"
                f"&nbsp;&nbsp;仓位：{pos_pct:.1f}%<br>"
                f"&nbsp;&nbsp;初始止损价：{initial_stop:.2f}"
            )
            if is_limited:
                entry_log += f"<br>&nbsp;&nbsp;跳空限制：开盘{bar.open:.2f}→限价{effective_open:.2f}"
            self.decision_logs.append(entry_log)

            # 记录持仓跟踪
            self.position_trackers[symbol] = PositionTracker(
                symbol=symbol,
                entry_date=frame.dt,
                entry_price=entry_price,
                entry_index=i,
                quantity=position_size,
                initial_stop=intent.initial_stop
            )

            logger.info(f"开仓 {symbol}: 价格={entry_price:.2f}, 数量={position_size}, "
                       f"止损={intent.initial_stop:.2f}")

            # 清理入场意图
            self.entry_intents.pop(symbol, None)

    def on_close(self, i: int, frame: MarketFrame, broker: PortfolioBroker) -> list[Order]:
        """收盘处理"""
        # 更新收盘价缓存
        for symbol, bar in frame.bars.items():
            self.last_close_prices[symbol] = bar.close

        # 更新风险管理状态
        self._update_risk_management_state(broker)

        # 收集策略验证数据 (大盘指数最近3天)
        idx_bar = frame.bars.get(self.config.index_symbol)
        if idx_bar:
            self.validation_data["index_table"].append({
                "date": frame.dt.isoformat(),
                "symbol": self.config.index_symbol,
                "close": idx_bar.close,
                "high": idx_bar.high,
                "low": idx_bar.low,
                "volume": idx_bar.volume
            })
        for sym, bar in frame.bars.items():
            idx = self._get_symbol_index(sym, frame.dt)
            if idx is not None:
                atr_val = atr(self.bars_by_symbol[sym], self.config.stop_atr_days, end_index=idx)
                prev_close = self.bars_by_symbol[sym][idx-1].close if idx >= 1 else bar.open
                tr = max(bar.high - bar.low, abs(bar.high - prev_close), abs(bar.low - prev_close))
                if atr_val is not None:
                    self.validation_data["atr_table"].append({
                        "date": frame.dt.isoformat(),
                        "symbol": sym,
                        "close": bar.close,
                        "high": bar.high,
                        "low": bar.low,
                        "tr": tr,
                        "atr": atr_val
                    })

        # 收集ATR验证数据 (针对特定日期和股票)
        # 2016-11-03 是用户要求的验证日期
        target_stock = "600975"
        target_date = date(2016, 11, 3)
        # 收集目标日期前后5天的数据
        if abs((frame.dt - target_date).days) <= 5:
            if target_stock in frame.bars:
                history = self._get_history_to_date(target_stock, frame.dt)
                if history:
                    atr_val = atr(history, self.config.stop_atr_days)
                    bar = frame.bars[target_stock]
                    # 计算 TR (True Range)
                    prev_close = history[-2].close if len(history) >= 2 else bar.open
                    tr = max(bar.high - bar.low, abs(bar.high - prev_close), abs(bar.low - prev_close))
                    
                    self.validation_data["atr_table"].append({
                        "date": frame.dt.isoformat(),
                        "symbol": target_stock,
                        "close": bar.close,
                        "high": bar.high,
                        "low": bar.low,
                        "tr": tr,
                        "atr": atr_val
                    })

        # 检查持仓出场条件
        for symbol, tracker in list(self.position_trackers.items()):
            if tracker.quantity <= 0:
                continue

            current_bar = frame.bars.get(symbol)
            if current_bar is None:
                continue

            # OPTIMIZATION: Use index instead of history slice where possible
            # But here we need history for ATR calculation
            # Let's use cached ATR if possible or optimize get_history
            
            # Use cached index
            idx = self._get_symbol_index(symbol, frame.dt)
            if idx is None:
                continue
                
            current_price = current_bar.close

            # 更新最高价
            tracker.highest_price = (
                current_bar.high if tracker.highest_price is None
                else max(tracker.highest_price, current_bar.high)
            )

            # 检查是否激活移动止损
            if not tracker.trailing_active:
                profit_pct = (current_price / tracker.entry_price) - 1.0 if tracker.entry_price > 0 else 0.0
                if tracker.should_trailing_activate(current_price, self.config.trailing_activate_profit):
                    tracker.trailing_active = True
                    logger.info(f"股票 {symbol} 盈利达到{self.config.trailing_activate_profit:.1%}，激活移动止损")
                    self.decision_logs.append(
                        f"[移动止损激活] {frame.dt} {symbol}<br>"
                        f"&nbsp;&nbsp;价格：{current_price:.2f} 入场价：{tracker.entry_price:.2f} 盈利：{profit_pct*100:.1f}%"
                    )

            # 计算ATR并更新移动止损
            if tracker.trailing_active:
                # Use index-based ATR
                bars = self.bars_by_symbol.get(symbol)
                atr_val = atr(bars, self.config.stop_atr_days, end_index=idx)
                
                if atr_val is not None:
                    profit_pct = (current_price / tracker.entry_price) - 1.0 if tracker.entry_price > 0 else 0.0
                    atr_mult = self.config.trailing_atr_mult
                    if profit_pct >= 0.30:
                        if tracker.highest_price is not None and current_price <= tracker.highest_price * (1.0 - 0.05):
                            self.pending_exits.add(symbol)
                            self.exit_reasons[symbol] = "take_profit"
                            continue
                        atr_mult = 1.5
                    elif profit_pct >= 0.20:
                        atr_mult = 1.5
                    elif profit_pct >= 0.10:
                        atr_mult = 2.5
                    prev_ts = tracker.trailing_stop
                    tracker.update_trailing_stop(current_bar, atr_val, atr_mult)
                    if tracker.trailing_stop is not None and tracker.trailing_stop != prev_ts:
                        self.decision_logs.append(
                            f"[移动止损更新] {frame.dt} {symbol}<br>"
                            f"&nbsp;&nbsp;ATR：{atr_val:.3f} 倍数：{atr_mult:.2f} 止损：{tracker.trailing_stop:.2f}"
                        )

            # 确定最终止损价
            final_stop = tracker.initial_stop
            if tracker.trailing_stop is not None:
                if tracker.initial_stop is not None:
                    final_stop = max(tracker.initial_stop, tracker.trailing_stop)
                else:
                    final_stop = tracker.trailing_stop

            pos = broker.positions.get(symbol)
            if pos is not None:
                pos.trailing_active = tracker.trailing_active
                pos.trailing_stop = tracker.trailing_stop

            # 收集买入执行验证数据 (如果这是第一天持仓)
            if i == tracker.entry_index and len(self.validation_data["buy_execution_table"]) < 3:
                self.validation_data["buy_execution_table"].append({
                    "symbol": symbol,
                    "date": frame.dt.isoformat(),
                    "entry_price": tracker.entry_price,
                    "qty": tracker.quantity,
                    "initial_stop": tracker.initial_stop,
                    "risk_per_share": tracker.entry_price - (tracker.initial_stop or 0)
                })

            # 检查止损（按当日最低价触发）
            if final_stop is not None and current_bar.low <= final_stop:
                self.pending_exits.add(symbol)
                reason = "stop_loss"
                if (tracker.trailing_active and tracker.trailing_stop is not None and
                    final_stop == tracker.trailing_stop):
                    reason = "trailing_stop"
                self.exit_reasons[symbol] = reason
                continue

            # 检查最大持有天数
            holding_days = i - tracker.entry_index + 1
            if holding_days > self.config.max_holding_days:
                self.pending_exits.add(symbol)
                self.exit_reasons[symbol] = "max_holding_days"
                continue

            # 检查趋势出场
            if self.config.enable_trend_exit:
                idx2 = self._get_symbol_index(symbol, frame.dt)
                bars2 = self.bars_by_symbol.get(symbol)
                ma_val = None
                if idx2 is not None and bars2 and len(bars2) >= self.config.price_ma_days:
                    closes2 = [b.close for b in bars2]
                    ma_val = sma(closes2, self.config.price_ma_days, end_index=idx2)
                
                # 只有当均线值 > 初始止损价时，才启用趋势止损
                # 这避免了在入场初期均线可能低于成本或刚超过成本时，过早被噪音震出
                # 仅当趋势明确向上，均线保护线已经抬高到风险线之上时才生效
                if ma_val is not None and tracker.initial_stop is not None and ma_val > tracker.initial_stop:
                    if not self._check_price_filter(symbol, frame.dt):
                        self.pending_exits.add(symbol)
                        self.exit_reasons[symbol] = "trend_exit"
                        if ma_val is not None:
                            self.exit_details[symbol] = {
                                "type": "trend_exit",
                                "close": current_bar.close,
                                "ma_days": self.config.price_ma_days,
                                "ma": ma_val
                            }
                        continue

        # 扫描突破机会
        breakout_candidates = []

        # 检查指数确认 (先计算一次)
        index_ok = self._check_index_confirmation(frame.dt)

        for symbol, bar in frame.bars.items():
            # 跳过指数
            if symbol == self.config.index_symbol:
                continue

            # 获取基本面和均线状态 (用于日志)
            # Use optimized check_price_filter which uses caching
            fund_ok = self._check_fundamental_filters(symbol, frame.dt)
            trend_ok = self._check_price_filter(symbol, frame.dt)
            has_position = broker.position_qty(symbol) != 0
            
            # 检查是否有足够数据
            idx = self._get_symbol_index(symbol, frame.dt)
            if idx is None or idx <= self.config.platform_min_days:
                continue

            eff = self._get_effective_params(symbol, frame.dt)

            # 寻找平台
            # OPTIMIZATION: Pass full bars list and index, avoiding slice
            platform = find_platform(
                self.bars_by_symbol[symbol],
                end_index_inclusive=idx - 1,
                min_days=self.config.platform_min_days,
                max_days=self.config.platform_max_days,
                max_amplitude=eff["platform_max_amplitude"],
                max_single_day_pct=eff["platform_max_single_day_pct"],
                min_slope=self.config.platform_min_slope,
                max_slope=self.config.platform_max_slope,
            )

            # 计算成交量倍数 (量比)
            # OPTIMIZATION: Use index-based avg_volume
            vol_ratio = 0.0
            if idx > self.config.volume_lookback:
                # Use cached or direct calculation without slice
                avg_vol = avg_volume(self.bars_by_symbol[symbol], self.config.volume_lookback, end_index=idx-1)
                if avg_vol and avg_vol > 0:
                    vol_ratio = bar.volume / avg_vol

            # 记录信号 analysis 日志
            signal_info = {
                "date": frame.dt.isoformat(),
                "symbol": symbol,
                "profile": eff.get("profile"),
                "market_cap": eff.get("market_cap"),
                "eff_platform_amp": eff.get("platform_max_amplitude"),
                "eff_platform_max_single_day_pct": eff.get("platform_max_single_day_pct"),
                "eff_breakout_min_pct": eff.get("breakout_min_pct"),
                "eff_gap_open_max_pct": eff.get("gap_open_max_pct"),
                "index_ok": index_ok,
                "trend_ok": trend_ok,
                "fund_ok": fund_ok,
                "has_position": has_position,
                "platform_found": platform is not None,
                "platform_high": platform.high if platform else None,
                "platform_low": platform.low if platform else None,
                "platform_amp": platform.amplitude if platform else None,
                "platform_slope": platform.slope if platform else None,
                "platform_type": platform.trend_type if platform else None,
                "close": bar.close,
                "vol_ratio": vol_ratio,
                "is_breakout": bar.close > platform.high if platform else False,
                "volume_ok": vol_ratio > self.config.volume_multiple,
                "atr": None,
                "initial_stop": None,
                "final_signal": 0
            }

            # 如果已经持仓，不再产生新信号，但记录日志
            if has_position:
                self.signal_logs.append(signal_info)
                continue

            # 如果不满足基础过滤，直接记录并跳过
            if not fund_ok or not trend_ok or not index_ok or self.paused_new_entries:
                self.signal_logs.append(signal_info)
                continue

            if platform is None:
                self.signal_logs.append(signal_info)
                continue

            # 解构平台信息
            platform_high = platform.high

            # 检查是否突破
            if bar.close <= platform_high:
                self.signal_logs.append(signal_info)
                continue
            breakout_ratio = (bar.close / platform_high) - 1.0
            if breakout_ratio < float(eff.get("breakout_min_pct", self.config.breakout_min_pct)):
                self.signal_logs.append(signal_info)
                continue

            # 检查成交量确认
            volume_ok = signal_info["volume_ok"]
            if not volume_ok:
                self.signal_logs.append(signal_info)
                continue

            # 计算止损
            # OPTIMIZATION: Use index-based ATR
            atr_val = atr(self.bars_by_symbol[symbol], self.config.stop_atr_days, end_index=idx)
            
            signal_info["atr"] = atr_val
            if atr_val is None:
                self.signal_logs.append(signal_info)
                continue

            use_pct = self.config.initial_stop_pct is not None and self.config.initial_stop_pct > 0
            if use_pct:
                initial_stop = bar.close * (1.0 - self.config.initial_stop_pct)
            else:
                initial_stop = bar.close - (atr_val * self.config.initial_stop_atr_mult)
            
            # 修复止损价计算为负的问题
            if initial_stop <= 0:
                initial_stop = max(0.01, bar.close * 0.5)
                logger.warning(f"股票 {symbol} 在 {frame.dt} 止损价计算为负，已调整为 {initial_stop:.2f}")

            signal_info["initial_stop"] = initial_stop
            signal_info["final_signal"] = 1
            self.signal_logs.append(signal_info)

            # 记录详细的信号日志 [信号]
            # 示例格式：
            # [信号] 2020-12-02 600975
            #   平台识别：高点8.33，低点7.65，振幅8.89% ✓
            #   突破验证：收盘8.35 > 高点8.33，突破幅度0.24%
            #   成交量：量比1.8 > 1.5 ✓
            #   ATR计算：0.19
            #   初始止损：8.35 - 0.19×1.5 = 8.05
            #   信号生成：买入 ✓
            breakout_pct = (bar.close / platform_high - 1.0) * 100
            
            stop_calc_str = ""
            if use_pct:
                stop_calc_str = f"{bar.close:.2f} × (1 - {self.config.initial_stop_pct:.2%}) = {initial_stop:.2f}"
            else:
                stop_calc_str = f"{bar.close:.2f} - {atr_val:.3f}×{self.config.initial_stop_atr_mult} = {initial_stop:.2f}"
            
            signal_log = (
                f"[信号] {frame.dt} {symbol}<br>"
                f"&nbsp;&nbsp;平台识别：高点{platform.high:.2f}，低点{platform.low:.2f}，振幅{platform.amplitude*100:.2f}% <span class='text-green-500'>✓</span><br>"
                f"&nbsp;&nbsp;突破验证：收盘{bar.close:.2f} > 高点{platform.high:.2f}，突破幅度{breakout_pct:.2f}%<br>"
                f"&nbsp;&nbsp;成交量：量比{vol_ratio:.1f} > {self.config.volume_multiple} <span class='text-green-500'>✓</span><br>"
                f"&nbsp;&nbsp;ATR计算：{atr_val:.3f}<br>"
                f"&nbsp;&nbsp;初始止损：{stop_calc_str}<br>"
                f"&nbsp;&nbsp;信号生成：<span class='text-green-500 font-bold'>买入 ✓</span>"
            )
            self.decision_logs.append(signal_log)

            # 添加到候选列表
            breakout_candidates.append(
                (symbol, bar, platform_high, platform.low, initial_stop, bar.close - platform_high)
            )

        # 排序并筛选
        breakout_candidates.sort(key=lambda x: x[4], reverse=True)
        top_candidates = breakout_candidates[: self.config.max_symbols_per_day]
        for symbol, bar, platform_high, platform_low, initial_stop, _ in top_candidates:
            intent = EntryIntent(
                symbol=symbol,
                breakout_dt=frame.dt,
                platform_high=platform_high,
                platform_low=platform_low,
                initial_stop=initial_stop,
                index_ok=index_ok,
                volume_ok=True,
                breakout_price=bar.close
            )
            self.entry_intents[symbol] = intent
            self.all_entry_intents.append(intent)

            logger.info(f"发现突破机会: {symbol}, 平台高点={platform_high:.2f}, "
                       f"当前价={bar.close:.2f}, 止损={initial_stop:.2f}")

        return []

    def get_strategy_stats(self) -> dict[str, any]:
        """获取策略统计信息"""
        return {
            "strategy_name": self.name,
            "paused": self.paused_new_entries,
            "pause_reason": self.pause_reason,
            "pending_entries": len(self.entry_intents),
            "pending_exits": len(self.pending_exits),
            "active_positions": len(self.position_trackers),
            "peak_equity": self.peak_equity,
            "loss_streak": self.loss_streak_count,
            "loss_streak_amount": self.loss_streak_amount
        }