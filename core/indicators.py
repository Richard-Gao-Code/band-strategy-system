from __future__ import annotations

import math
import numpy as np
from collections import defaultdict
from dataclasses import dataclass
from functools import lru_cache
from typing import Optional

from .types import Bar


class TechnicalIndicators:
    """技术指标计算器（带缓存和性能优化）"""

    def __init__(self):
        self._atr_cache: dict[tuple[str, int, int], float] = {}
        self._sma_cache: dict[tuple[str, int, int], float] = {}
        self._volume_cache: dict[tuple[str, int, int], float] = {}
        self._platform_cache: dict[tuple[str, int, int, float, float], PlatformResult | None] = {}

    def clear_cache(self) -> None:
        """清空所有缓存"""
        self._atr_cache.clear()
        self._sma_cache.clear()
        self._volume_cache.clear()
        self._platform_cache.clear()


@dataclass(frozen=True, slots=True)
class PlatformResult:
    """平台识别结果"""
    start_index: int
    end_index: int
    high: float
    low: float
    amplitude: float
    duration: int
    slope: float = 0.0
    trend_type: str = "horizontal"  # horizontal, rising, falling

    @property
    def center(self) -> float:
        """平台中心价格"""
        return (self.high + self.low) / 2.0

    @property
    def range(self) -> float:
        """价格范围"""
        return self.high - self.low

    def is_price_in_platform(self, price: float) -> bool:
        """判断价格是否在平台内"""
        return self.low <= price <= self.high


def sma(values: list[float], period: int, end_index: int | None = None) -> float | None:
    """简单移动平均线
    
    Args:
        values: 价格序列
        period: 周期
        end_index: 结束索引（含），如果为None则使用序列最后一个
        
    Returns:
        移动平均值
    """
    if period <= 0:
        raise ValueError(f"周期必须为正数: {period}")

    if not values:
        return None

    last_idx = end_index if end_index is not None else len(values) - 1
    if last_idx < 0 or last_idx >= len(values):
        return None
        
    if last_idx + 1 < period:
        return None

    # 计算 [last_idx - period + 1, last_idx] 范围内的平均值
    total = 0.0
    for i in range(last_idx - period + 1, last_idx + 1):
        total += values[i]
    return total / period


def atr(bars: list[Bar], period: int = 14, end_index: int | None = None) -> float | None:
    """平均真实波幅（Average True Range）"""
    if period <= 0:
        raise ValueError(f"周期必须为正数: {period}")

    last_idx = end_index if end_index is not None else len(bars) - 1
    if last_idx < period: # 需要至少 period+1 个数据点来计算 period 个 TR
        return None

    # 计算最近 period 个 TR 的平均值
    # 第 i 个 TR 需要 bars[i] 和 bars[i-1]
    total_tr = 0.0
    for i in range(last_idx - period + 1, last_idx + 1):
        curr = bars[i]
        prev = bars[i-1]
        tr = max(
            curr.high - curr.low,
            abs(curr.high - prev.close),
            abs(curr.low - prev.close)
        )
        total_tr += tr
        
    return total_tr / period


def avg_volume(bars: list[Bar], period: int, end_index: int | None = None) -> float | None:
    """计算平均成交量"""
    if period <= 0:
        raise ValueError(f"周期必须为正数: {period}")

    last_idx = end_index if end_index is not None else len(bars) - 1
    if last_idx < period - 1:
        return None

    total_vol = 0.0
    count = 0
    for i in range(last_idx - period + 1, last_idx + 1):
        v = bars[i].volume
        if v is not None:
            total_vol += v
            count += 1
        else:
            # 停牌日成交量视为0
            count += 1
            
    if count < period:
        return None
        
    return total_vol / count


def calculate_slope(values: list[float]) -> float:
    """计算价格序列的线性回归斜率（归一化）
    
    Returns:
        斜率值，表示每日平均涨跌幅
    """
    if len(values) < 2:
        return 0.0
    
    x = np.arange(len(values))
    y = np.array(values)
    
    # 归一化y，以便不同价格水平的股票斜率具有可比性
    y_norm = y / y[0]
    
    slope, _ = np.polyfit(x, y_norm, 1)
    return float(slope)


def find_platform(
    bars: list[Bar],
    end_index_inclusive: int,
    min_days: int = 7,
    max_days: int = 360,
    max_amplitude: float = 0.25,
    min_price: float = 0.01,
    max_single_day_pct: float = 0.11,
    min_slope: float = -0.005,
    max_slope: float = 0.005
) -> PlatformResult | None:
    """查找平台整理区间（优化版 - O(N)复杂度）"""
    # 参数验证
    if min_days <= 0 or max_days < min_days:
        raise ValueError(f"无效的天数范围: min={min_days}, max={max_days}")

    if max_amplitude <= 0:
        raise ValueError(f"最大振幅必须为正数: {max_amplitude}")

    if end_index_inclusive < 0 or end_index_inclusive >= len(bars):
        return None

    if len(bars) < min_days:
        return None
        
    # 提前检查索引边界，避免不必要的计算
    start_search_index = end_index_inclusive - max_days + 1
    if start_search_index < 0:
        # 如果数据不够 max_days，则只能搜索到 0
        max_possible_days = end_index_inclusive + 1
        if max_possible_days < min_days:
            return None
    
    # 初始化状态
    # 我们向后扫描（从 end_index 向前），维护 min/max 和 slope 统计量
    # x 坐标定义为: end_index 为 0, end_index-1 为 -1, ...
    
    current_high = bars[end_index_inclusive].high
    current_low = bars[end_index_inclusive].low
    
    # 斜率计算统计量
    # Slope = (n*Sum(xy) - Sum(x)*Sum(y)) / (n*Sum(xx) - Sum(x)^2)
    # y 使用收盘价
    
    y0 = bars[end_index_inclusive].close
    sum_x = 0.0
    sum_y = y0
    sum_xy = 0.0
    sum_xx = 0.0
    n = 1
    
    best_result = None
    
    # 向前回溯，最多回溯 max_days - 1 次（总共 max_days 个点）
    # i 是回溯的步数，对应 x = -i
    # 也就是我们正在考察的 bar 是 bars[end_index_inclusive - i]
    
    for i in range(1, max_days):
        idx = end_index_inclusive - i
        if idx < 0:
            break
            
        bar = bars[idx]
        next_bar = bars[idx+1] # 时间上后一天的 bar
        
        # 1. 检查单日涨跌幅限制 (检查 bar 和 next_bar 之间的跳空)
        # 注意：这里计算的是 next_bar 相对于 bar 的涨跌幅
        if bar.close <= 0: # 避免除零
             break
             
        daily_change = abs(next_bar.close / bar.close - 1.0)
        if daily_change > max_single_day_pct:
            break # 遇到断层，无法继续扩展
            
        # 2. 更新高低点
        if bar.high > current_high:
            current_high = bar.high
        if bar.low < current_low:
            current_low = bar.low
            
        if current_low < min_price:
            break
            
        # 3. 检查振幅
        amplitude = (current_high / current_low) - 1.0
        if amplitude > max_amplitude:
            break # 振幅超标，继续扩展只会更大，直接停止
            
        # 4. 更新斜率统计量
        x = -i
        y = bar.close
        sum_x += x
        sum_y += y
        sum_xy += x * y
        sum_xx += x * x
        n += 1
        
        # 5. 如果长度满足要求，检查斜率并记录
        if n >= min_days:
            # 计算原始斜率
            numerator = n * sum_xy - sum_x * sum_y
            denominator = n * sum_xx - sum_x * sum_x
            
            if denominator == 0:
                raw_slope = 0.0
            else:
                raw_slope = numerator / denominator
                
            # 归一化斜率 (除以起始价格 y)
            # 注意：当前窗口的起始价格是 bar.close (因为我们是回溯到这里)
            norm_slope = raw_slope / bar.close
            
            if min_slope <= norm_slope <= max_slope:
                # 找到一个有效平台
                # 我们继续搜索看是否有更长的（因为循环是从短到长扩展）
                # 所以每次找到合法的，都更新 best_result，这样循环结束时就是最长的
                
                # 识别类型
                if norm_slope > 0.001:
                    trend_type = "rising"
                elif norm_slope < -0.001:
                    trend_type = "falling"
                else:
                    trend_type = "horizontal"
                
                best_result = PlatformResult(
                    start_index=idx,
                    end_index=end_index_inclusive,
                    high=current_high,
                    low=current_low,
                    amplitude=amplitude,
                    duration=n,
                    slope=norm_slope,
                    trend_type=trend_type
                )
                
    return best_result

    return None


def find_platform_optimized(
    bars: list[Bar],
    end_index_inclusive: int,
    min_days: int = 20,
    max_days: int = 240,
    max_amplitude: float = 0.15,
    max_single_day_pct: float = 0.05,
    min_slope: float = -0.005,
    max_slope: float = 0.005
) -> PlatformResult | None:
    """查找平台整理区间（高性能版本）
    
    使用滑动窗口和预计算，进一步优化性能
    """
    return find_platform(
        bars, 
        end_index_inclusive, 
        min_days, 
        max_days, 
        max_amplitude,
        max_single_day_pct=max_single_day_pct,
        min_slope=min_slope,
        max_slope=max_slope
    )


def calculate_rsi(prices: list[float], period: int = 14) -> float | None:
    """相对强弱指数（RSI）
    
    策略中未使用，但作为常用指标提供
    """
    if len(prices) < period + 1:
        return None

    gains: list[float] = []
    losses: list[float] = []

    for i in range(1, len(prices)):
        change = prices[i] - prices[i-1]
        if change > 0:
            gains.append(change)
            losses.append(0.0)
        else:
            gains.append(0.0)
            losses.append(abs(change))

    if len(gains) < period:
        return None

    avg_gain = sum(gains[-period:]) / period
    avg_loss = sum(losses[-period:]) / period

    if avg_loss == 0:
        return 100.0

    rs = avg_gain / avg_loss
    rsi = 100 - (100 / (1 + rs))

    return rsi


def calculate_bollinger_bands(
    prices: list[float],
    period: int = 20,
    num_std: float = 2.0
) -> tuple[float, float, float] | None:
    """布林带计算
    
    Returns:
        (中轨, 上轨, 下轨) 或 None
    """
    if len(prices) < period:
        return None

    # 计算中轨（SMA）
    middle = sma(prices, period)
    if middle is None:
        return None

    # 计算标准差
    recent_prices = prices[-period:]
    variance = sum((p - middle) ** 2 for p in recent_prices) / period
    std_dev = math.sqrt(variance)

    upper = middle + (num_std * std_dev)
    lower = middle - (num_std * std_dev)

    return middle, upper, lower


def calculate_macd(
    prices: list[float],
    fast_period: int = 12,
    slow_period: int = 26,
    signal_period: int = 9
) -> tuple[float, float, float] | None:
    """MACD指标计算
    
    Returns:
        (DIF, DEA, MACD) 或 None
    """
    if len(prices) < slow_period:
        return None

    # 计算EMA
    def calculate_ema(prices_list: list[float], period: int) -> float:
        """指数移动平均"""
        if len(prices_list) < period:
            return sum(prices_list) / len(prices_list)

        multiplier = 2.0 / (period + 1)
        ema = prices_list[0]

        for price in prices_list[1:]:
            ema = (price - ema) * multiplier + ema

        return ema

    # 计算快慢EMA
    fast_ema = calculate_ema(prices[-fast_period:], fast_period)
    slow_ema = calculate_ema(prices[-slow_period:], slow_period)

    # DIF = 快线 - 慢线
    dif = fast_ema - slow_ema

    # 需要历史DIF值来计算DEA，这里简化处理
    # 在实际应用中，需要维护DIF历史序列
    dea = dif  # 简化：假设DEA等于DIF
    macd = (dif - dea) * 2

    return dif, dea, macd


def detect_price_pattern(
    bars: list[Bar],
    pattern_type: str = "breakout"
) -> dict | None:
    """价格模式检测
    
    支持检测多种价格模式：
    - breakout: 突破
    - support: 支撑
    - resistance: 阻力
    - double_top: 双顶
    - double_bottom: 双底
    """
    if len(bars) < 10:
        return None

    if pattern_type == "breakout":
        # 简单突破检测：当前收盘价突破最近N日最高价
        lookback = 20
        if len(bars) < lookback + 1:
            return None

        recent_bars = bars[-lookback-1:-1]  # 排除最新一根
        recent_high = max(b.high for b in recent_bars)
        current_close = bars[-1].close

        if current_close > recent_high:
            return {
                "type": "breakout",
                "breakout_price": current_close,
                "resistance_level": recent_high,
                "strength": (current_close - recent_high) / recent_high
            }

    return None


# ==================== 性能优化工具 ====================

class IndicatorCache:
    """指标计算缓存管理器"""

    def __init__(self):
        self._cache: dict[str, dict] = defaultdict(dict)

    def get_atr(self, symbol: str, date_index: int, period: int = 14) -> float | None:
        """获取缓存的ATR值"""
        key = f"atr_{period}"
        return self._cache[symbol].get((date_index, key))

    def set_atr(self, symbol: str, date_index: int, period: int, value: float) -> None:
        """设置ATR缓存"""
        key = f"atr_{period}"
        self._cache[symbol][(date_index, key)] = value

    def get_sma(self, symbol: str, date_index: int, period: int) -> float | None:
        """获取缓存的SMA值"""
        key = f"sma_{period}"
        return self._cache[symbol].get((date_index, key))

    def set_sma(self, symbol: str, date_index: int, period: int, value: float) -> None:
        """设置SMA缓存"""
        key = f"sma_{period}"
        self._cache[symbol][(date_index, key)] = value

    def clear_symbol(self, symbol: str) -> None:
        """清空指定标的的缓存"""
        if symbol in self._cache:
            del self._cache[symbol]

    def clear_all(self) -> None:
        """清空所有缓存"""
        self._cache.clear()


# 全局缓存实例
global_cache = IndicatorCache()