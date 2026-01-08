from __future__ import annotations

import csv
import logging
from bisect import bisect_right
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Optional


def parse_date_flexible(value: str) -> date:
    """
    灵活解析日期字符串
    支持格式: YYYY-MM-DD, YYYY/MM/DD, YYYY.MM.DD
    """
    if not value or not value.strip():
        raise ValueError("日期字符串为空")

    value = value.strip()

    # 移除时间部分（如果有）
    if ' ' in value:
        value = value.split(' ')[0]

    # 尝试不同的分隔符
    for separator in ['-', '/', '.']:
        if separator in value:
            parts = value.split(separator)
            if len(parts) == 3:
                try:
                    year, month, day = map(int, parts)
                    # 简单的日期验证
                    if year < 1900 or year > 2100:
                        continue
                    if month < 1 or month > 12:
                        continue
                    if day < 1 or day > 31:
                        continue
                    return date(year, month, day)
                except (ValueError, TypeError):
                    continue

    raise ValueError(f"无法解析日期: {value}")


@dataclass(frozen=True)
class FundamentalPoint:
    """基本面数据点"""
    dt: date
    pe_ttm: Optional[float] = None
    market_cap: Optional[float] = None
    avg_amount_20d: Optional[float] = None
    pb: Optional[float] = None  # 新增：市净率
    ps_ttm: Optional[float] = None  # 新增：市销率
    roe: Optional[float] = None  # 新增：净资产收益率

    def is_valid(self) -> bool:
        """检查数据是否有效"""
        # PE应为正数或None
        if self.pe_ttm is not None and self.pe_ttm <= 0:
            return False

        # 市值应为正数或None
        if self.market_cap is not None and self.market_cap <= 0:
            return False

        # 成交额应为正数或None
        if self.avg_amount_20d is not None and self.avg_amount_20d <= 0:
            return False

        return True

    def to_dict(self) -> dict[str, any]:
        """转换为字典"""
        return {
            'date': self.dt.isoformat(),
            'pe_ttm': self.pe_ttm,
            'market_cap': self.market_cap,
            'avg_amount_20d': self.avg_amount_20d,
            'pb': self.pb,
            'ps_ttm': self.ps_ttm,
            'roe': self.roe
        }


class FundamentalsStore:
    """基本面数据存储"""

    def __init__(self, points_by_symbol: dict[str, list[FundamentalPoint]]) -> None:
        self._points_by_symbol = {}
        self._dates_by_symbol: dict[str, list[date]] = {}

        # 验证并过滤无效数据
        for symbol, points in points_by_symbol.items():
            valid_points = [p for p in points if p.is_valid()]
            if valid_points:
                valid_points.sort(key=lambda p: p.dt)
                self._points_by_symbol[symbol] = valid_points
                self._dates_by_symbol[symbol] = [p.dt for p in valid_points]

        self._logger = logging.getLogger(__name__)
        self._logger.info(f"基本面数据存储初始化完成，共加载 {len(self._points_by_symbol)} 只股票")

    @staticmethod
    def load_csv(path: Path, encoding: str = "utf-8-sig") -> FundamentalsStore:
        """
        从CSV文件加载基本面数据
        
        CSV格式支持以下列名（不区分大小写）：
        - symbol, code: 股票代码
        - date, dt, 日期: 日期
        - pe_ttm, pe, peTTM: PE TTM
        - market_cap, mkt_cap, total_mv, 总市值: 市值
        - avg_amount_20d, amount_20d_avg, avg_turnover_20d, 20日平均成交额: 20日平均成交额
        - pb, pbMRQ, 市净率: 市净率
        - ps_ttm, psTTM, 市销率: 市销率
        - roe, ROE, 净资产收益率: 净资产收益率
        """
        if not path.exists():
            raise FileNotFoundError(f"基本面数据文件不存在: {path}")

        with path.open("r", encoding=encoding, newline="") as f:
            # 尝试检测文件编码
            try:
                sample = f.read(1024)
                f.seek(0)
            except UnicodeDecodeError:
                # 如果默认编码失败，尝试其他编码
                encodings = ['gbk', 'gb2312', 'utf-8']
                for enc in encodings:
                    try:
                        with path.open("r", encoding=enc, newline="") as f2:
                            reader = csv.DictReader(f2)
                            return FundamentalsStore._parse_reader(reader)
                    except UnicodeDecodeError:
                        continue
                raise ValueError(f"无法解码文件: {path}")

            reader = csv.DictReader(f)
            return FundamentalsStore._parse_reader(reader)

    @staticmethod
    def _parse_reader(reader) -> FundamentalsStore:
        """解析CSV阅读器"""
        by_symbol: dict[str, list[FundamentalPoint]] = {}

        for row_idx, row in enumerate(reader, start=2):  # 从第2行开始（包含标题）
            try:
                # 获取股票代码
                symbol = FundamentalsStore._get_value(row, "symbol", "code")
                if not symbol:
                    continue

                # 获取日期
                date_str = FundamentalsStore._get_value(row, "date", "dt", "日期")
                if not date_str:
                    continue

                try:
                    dt = parse_date_flexible(date_str)
                except ValueError as e:
                    raise ValueError(f"第{row_idx}行日期解析错误: {e}")

                # 解析数值字段
                def parse_float(*keys: str) -> Optional[float]:
                    value = FundamentalsStore._get_value(row, *keys)
                    if not value:
                        return None
                    try:
                        # 移除千分位逗号等
                        value = value.replace(',', '').strip()
                        if not value:
                            return None
                        return float(value)
                    except (ValueError, TypeError):
                        return None

                # 创建基本面数据点
                point = FundamentalPoint(
                    dt=dt,
                    pe_ttm=parse_float("pe_ttm", "pe", "peTTM", "PE"),
                    market_cap=parse_float("market_cap", "mkt_cap", "total_mv", "总市值"),
                    avg_amount_20d=parse_float("avg_amount_20d", "amount_20d_avg",
                                              "avg_turnover_20d", "20日平均成交额"),
                    pb=parse_float("pb", "pbMRQ", "市净率"),
                    ps_ttm=parse_float("ps_ttm", "psTTM", "市销率"),
                    roe=parse_float("roe", "ROE", "净资产收益率")
                )

                by_symbol.setdefault(symbol, []).append(point)

            except Exception as e:
                raise ValueError(f"第{row_idx}行解析错误: {e}")

        return FundamentalsStore(by_symbol)

    @staticmethod
    def _get_value(row: dict[str, str], *keys: str) -> Optional[str]:
        """从行中获取值，支持多个可能的键名"""
        for key in keys:
            # 尝试精确匹配
            if key in row and row[key] and row[key].strip():
                return row[key].strip()

            # 尝试不区分大小写的匹配
            for actual_key in row.keys():
                if actual_key.lower() == key.lower() and row[actual_key] and row[actual_key].strip():
                    return row[actual_key].strip()

        return None

    def latest_on_or_before(self, symbol: str, dt: date) -> Optional[FundamentalPoint]:
        """
        获取指定日期前（含）的最新基本面数据
        
        参数:
            symbol: 股票代码
            dt: 日期
            
        返回:
            指定日期前的最新基本面数据点，如果没有则返回None
        """
        points = self._points_by_symbol.get(symbol)
        if not points:
            return None

        dates = self._dates_by_symbol[symbol]

        # 使用二分查找找到最后一个 <= dt 的索引
        idx = bisect_right(dates, dt) - 1

        if idx < 0:
            return None

        return points[idx]

    def get_all_points(self, symbol: str) -> list[FundamentalPoint]:
        """获取股票的所有基本面数据点"""
        return self._points_by_symbol.get(symbol, [])

    def get_date_range(self, symbol: str) -> Optional[tuple[date, date]]:
        """获取股票基本面数据的日期范围"""
        points = self._points_by_symbol.get(symbol)
        if not points:
            return None

        return (points[0].dt, points[-1].dt)

    def filter_by_condition(self, condition_func) -> dict[str, list[FundamentalPoint]]:
        """根据条件过滤基本面数据"""
        result: dict[str, list[FundamentalPoint]] = {}

        for symbol, points in self._points_by_symbol.items():
            filtered_points = [p for p in points if condition_func(p)]
            if filtered_points:
                result[symbol] = filtered_points

        return result

    def get_symbols(self) -> list[str]:
        """获取所有股票代码"""
        return list(self._points_by_symbol.keys())

    def has_symbol(self, symbol: str) -> bool:
        """检查是否包含指定股票"""
        return symbol in self._points_by_symbol

    def get_stats(self) -> dict[str, any]:
        """获取存储统计信息"""
        total_points = sum(len(points) for points in self._points_by_symbol.values())

        return {
            "symbol_count": len(self._points_by_symbol),
            "total_points": total_points,
            "avg_points_per_symbol": total_points / len(self._points_by_symbol) if self._points_by_symbol else 0
        }
