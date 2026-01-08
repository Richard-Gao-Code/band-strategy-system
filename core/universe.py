from __future__ import annotations

import csv
import logging
from dataclasses import dataclass
from datetime import date, datetime
from enum import Enum
from pathlib import Path
from typing import Optional


class Exchange(Enum):
    """交易所枚举"""
    SHANGHAI = "SH"  # 上海
    SHENZHEN = "SZ"  # 深圳
    BEIJING = "BJ"   # 北京
    HK = "HK"        # 香港
    UNKNOWN = "UNK"  # 未知


class Industry(Enum):
    """行业分类（简化版）"""
    FINANCIAL = "金融"
    TECHNOLOGY = "科技"
    CONSUMER = "消费"
    INDUSTRIAL = "工业"
    MATERIALS = "材料"
    HEALTHCARE = "医疗"
    ENERGY = "能源"
    REAL_ESTATE = "房地产"
    UTILITIES = "公用事业"
    OTHER = "其他"


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

    # 尝试解析时间戳（如果适用）
    try:
        dt = datetime.fromisoformat(value.replace('Z', '+00:00'))
        return dt.date()
    except (ValueError, TypeError):
        pass

    raise ValueError(f"无法解析日期: {value}")


@dataclass(frozen=True)
class UniverseRecord:
    """股票信息记录"""
    symbol: str
    name: Optional[str] = None
    list_date: Optional[date] = None
    delist_date: Optional[date] = None
    exchange: Exchange = Exchange.UNKNOWN
    industry: Optional[Industry] = None
    is_st: bool = False
    is_suspended: bool = False
    is_bj: bool = False
    market_cap: Optional[float] = None  # 市值（亿元）

    @property
    def is_active(self) -> bool:
        """是否活跃（未退市）"""
        if self.delist_date is not None:
            return False
        return True

    @property
    def list_days(self, current_date: Optional[date] = None) -> Optional[int]:
        """上市天数"""
        if self.list_date is None:
            return None

        if current_date is None:
            current_date = date.today()

        return (current_date - self.list_date).days

    def passes_filters(self, dt: date, min_list_days: int = 120,
                      exclude_st: bool = True, exclude_bj: bool = True,
                      min_market_cap: Optional[float] = None) -> bool:
        """
        检查是否通过过滤条件
        
        参数:
            dt: 检查日期
            min_list_days: 最小上市天数
            exclude_st: 是否排除ST股票
            exclude_bj: 是否排除北交所股票
            min_market_cap: 最小市值要求（亿元）
        """
        # 检查是否已退市
        if self.delist_date is not None and dt >= self.delist_date:
            return False

        # 检查ST
        if exclude_st and self.is_st:
            return False

        # 检查北交所
        if exclude_bj and self.is_bj:
            return False

        # 检查上市天数
        if self.list_date is not None:
            list_days = (dt - self.list_date).days
            if list_days < min_list_days:
                return False

        # 检查停牌
        if self.is_suspended:
            return False

        # 检查市值
        if min_market_cap is not None and self.market_cap is not None:
            if self.market_cap < min_market_cap:
                return False

        return True

    def to_dict(self) -> dict[str, any]:
        """转换为字典"""
        return {
            'symbol': self.symbol,
            'name': self.name,
            'list_date': self.list_date.isoformat() if self.list_date else None,
            'delist_date': self.delist_date.isoformat() if self.delist_date else None,
            'exchange': self.exchange.value,
            'industry': self.industry.value if self.industry else None,
            'is_st': self.is_st,
            'is_suspended': self.is_suspended,
            'is_bj': self.is_bj,
            'market_cap': self.market_cap,
            'is_active': self.is_active
        }


class Universe:
    """股票池管理"""

    def __init__(self, records: dict[str, UniverseRecord]) -> None:
        self._records = records
        self._logger = logging.getLogger(__name__)
        self._logger.info(f"股票池初始化完成，共加载 {len(self._records)} 只股票")

        # 创建缓存
        self._active_symbols_cache: Optional[list[str]] = None
        self._industry_cache: Optional[dict[Industry, list[str]]] = None

    @staticmethod
    def load_csv(path: Path, encoding: str = "utf-8-sig") -> Universe:
        """
        从CSV文件加载股票池
        
        CSV格式支持以下列名（不区分大小写）：
        - symbol, code, 代码: 股票代码
        - name, 名称: 股票名称
        - list_date, ipo_date, 上市日期: 上市日期
        - delist_date, 退市日期: 退市日期
        - exchange, 交易所: 交易所代码（SH/SZ/BJ/HK）
        - industry, 行业: 行业分类
        - is_st, st, ST: 是否ST（1/0, true/false, yes/no）
        - is_suspended, 停牌: 是否停牌
        - is_bj, bj, 北交所: 是否北交所
        - market_cap, 市值: 市值（亿元）
        """
        if not path.exists():
            raise FileNotFoundError(f"股票池文件不存在: {path}")

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
                            return Universe._parse_reader(reader)
                    except UnicodeDecodeError:
                        continue
                raise ValueError(f"无法解码文件: {path}")

            reader = csv.DictReader(f)
            return Universe._parse_reader(reader)

    @staticmethod
    def _parse_reader(reader) -> Universe:
        """解析CSV阅读器"""
        records: dict[str, UniverseRecord] = {}

        for row_idx, row in enumerate(reader, start=2):  # 从第2行开始（包含标题）
            try:
                # 获取股票代码（必需）
                symbol = Universe._get_value(row, "symbol", "code", "代码")
                if not symbol:
                    continue

                # 获取股票名称
                name = Universe._get_value(row, "name", "名称")

                # 解析上市日期
                list_date = None
                list_date_str = Universe._get_value(row, "list_date", "ipo_date", "上市日期")
                if list_date_str:
                    try:
                        list_date = parse_date_flexible(list_date_str)
                    except ValueError as e:
                        Universe._logger.warning(f"第{row_idx}行上市日期解析失败: {e}")

                # 解析退市日期
                delist_date = None
                delist_date_str = Universe._get_value(row, "delist_date", "退市日期")
                if delist_date_str:
                    try:
                        delist_date = parse_date_flexible(delist_date_str)
                    except ValueError as e:
                        Universe._logger.warning(f"第{row_idx}行退市日期解析失败: {e}")

                # 解析交易所
                exchange = Exchange.UNKNOWN
                exchange_str = Universe._get_value(row, "exchange", "交易所")
                if exchange_str:
                    exchange_str = exchange_str.upper()
                    for ex in Exchange:
                        if ex.value == exchange_str:
                            exchange = ex
                            break

                # 解析行业
                industry = None
                industry_str = Universe._get_value(row, "industry", "行业")
                if industry_str:
                    for ind in Industry:
                        if ind.value == industry_str:
                            industry = ind
                            break

                # 解析布尔值字段
                def parse_bool(*keys: str) -> bool:
                    value = Universe._get_value(row, *keys)
                    if not value:
                        return False
                    value = value.lower().strip()
                    return value in {"1", "true", "yes", "y", "是"}

                is_st = parse_bool("is_st", "st", "ST")
                is_suspended = parse_bool("is_suspended", "停牌")
                is_bj = parse_bool("is_bj", "bj", "北交所")

                # 解析市值
                market_cap = None
                market_cap_str = Universe._get_value(row, "market_cap", "市值")
                if market_cap_str:
                    try:
                        market_cap_str = market_cap_str.replace(',', '').strip()
                        if market_cap_str:
                            market_cap = float(market_cap_str)
                    except (ValueError, TypeError):
                        pass

                # 创建记录
                record = UniverseRecord(
                    symbol=symbol,
                    name=name,
                    list_date=list_date,
                    delist_date=delist_date,
                    exchange=exchange,
                    industry=industry,
                    is_st=is_st,
                    is_suspended=is_suspended,
                    is_bj=is_bj,
                    market_cap=market_cap
                )

                records[symbol] = record

            except Exception as e:
                Universe._logger.error(f"第{row_idx}行解析错误: {e}")
                continue

        return Universe(records)

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

    def get(self, symbol: str) -> Optional[UniverseRecord]:
        """获取股票信息"""
        return self._records.get(symbol)

    def passes_static_filters(self, symbol: str, dt: date,
                            min_list_days: int = 120) -> bool:
        """
        检查股票是否通过静态过滤器
        
        参数:
            symbol: 股票代码
            dt: 检查日期
            min_list_days: 最小上市天数
        """
        record = self._records.get(symbol)
        if record is None:
            return True  # 如果没有记录，假设通过

        return record.passes_filters(
            dt=dt,
            min_list_days=min_list_days,
            exclude_st=True,
            exclude_bj=True
        )

    def get_active_symbols(self, dt: Optional[date] = None) -> list[str]:
        """获取活跃股票列表"""
        if dt is None:
            dt = date.today()

        active_symbols = []
        for symbol, record in self._records.items():
            if record.passes_filters(dt, min_list_days=0):
                active_symbols.append(symbol)

        return active_symbols

    def get_symbols_by_industry(self, industry: Industry) -> list[str]:
        """获取指定行业的股票列表"""
        symbols = []
        for symbol, record in self._records.items():
            if record.industry == industry and record.is_active:
                symbols.append(symbol)

        return symbols

    def filter_symbols(self, condition_func) -> list[str]:
        """根据条件过滤股票"""
        return [symbol for symbol, record in self._records.items()
                if condition_func(record)]

    def get_stats(self) -> dict[str, any]:
        """获取股票池统计信息"""
        total = len(self._records)
        active = len(self.get_active_symbols())
        st_count = sum(1 for r in self._records.values() if r.is_st)
        bj_count = sum(1 for r in self._records.values() if r.is_bj)

        # 行业统计
        industry_stats = {}
        for industry in Industry:
            count = sum(1 for r in self._records.values() if r.industry == industry)
            if count > 0:
                industry_stats[industry.value] = count

        return {
            "total_symbols": total,
            "active_symbols": active,
            "st_symbols": st_count,
            "bj_symbols": bj_count,
            "inactive_symbols": total - active,
            "industry_distribution": industry_stats
        }

    def get_exchange_symbols(self, exchange: Exchange) -> list[str]:
        """获取指定交易所的股票列表"""
        return [symbol for symbol, record in self._records.items()
                if record.exchange == exchange and record.is_active]

    def search_symbols(self, query: str, by_name: bool = True,
                      by_symbol: bool = True) -> list[str]:
        """搜索股票"""
        query = query.lower().strip()
        results = []

        for symbol, record in self._records.items():
            if not record.is_active:
                continue

            matched = False

            # 按代码搜索
            if by_symbol and query in symbol.lower():
                matched = True

            # 按名称搜索
            if by_name and record.name and query in record.name.lower():
                matched = True

            if matched:
                results.append(symbol)

        return results

    def validate_symbol(self, symbol: str, dt: date) -> dict[str, any]:
        """验证股票在指定日期的状态"""
        record = self._records.get(symbol)
        if record is None:
            return {
                "valid": False,
                "reason": "not_in_universe",
                "symbol": symbol
            }

        is_valid = record.passes_filters(dt)

        result = {
            "valid": is_valid,
            "symbol": symbol,
            "name": record.name,
            "list_date": record.list_date.isoformat() if record.list_date else None,
            "is_st": record.is_st,
            "is_bj": record.is_bj,
            "is_suspended": record.is_suspended,
            "delist_date": record.delist_date.isoformat() if record.delist_date else None,
            "industry": record.industry.value if record.industry else None,
            "exchange": record.exchange.value
        }

        if not is_valid:
            # 找出具体原因
            reasons = []
            if record.delist_date and dt >= record.delist_date:
                reasons.append("delisted")
            if record.is_st:
                reasons.append("st")
            if record.is_bj:
                reasons.append("bj")
            if record.is_suspended:
                reasons.append("suspended")
            if record.list_date and (dt - record.list_date).days < 120:
                reasons.append("new_listing")

            result["reasons"] = reasons

        return result
