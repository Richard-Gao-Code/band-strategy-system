from __future__ import annotations

from dataclasses import dataclass, asdict, is_dataclass
from enum import Enum
from math import sqrt
from typing import Any, Optional

from .types import EquityPoint, Trade


class RiskFreeRateType(Enum):
    FIXED = "fixed"
    DYNAMIC = "dynamic"


@dataclass(frozen=True)
class DrawdownDetail:
    max_drawdown: float
    drawdown_start_index: int
    drawdown_end_index: int
    drawdown_start_date: str
    drawdown_end_date: str
    drawdown_duration: int
    recovery_date: Optional[str] = None


@dataclass(frozen=True)
class Metrics:
    # 基础指标
    final_equity: float
    initial_equity: float
    total_return: float
    annual_return: float
    cagr: float

    # 风险指标
    max_drawdown: float
    max_drawdown_detail: Optional[DrawdownDetail]
    sharpe: float
    sortino: float
    calmar: float
    volatility: float
    downside_volatility: float

    # 交易指标
    trade_count: int
    win_rate: float
    profit_factor: float
    avg_win: float
    avg_loss: float
    avg_r_multiple: float
    largest_win: float
    largest_loss: float
    all_trade_pnls: list[float]  # 新增：所有交易的盈亏列表

    # 比率指标
    win_loss_ratio: float
    expectancy: float
    k_ratio: float
    tail_ratio: float

    # 时间指标
    total_days: int
    profitable_days: float
    losing_days: float
    best_day: float
    worst_day: float
    monthly_returns: dict[int, dict[int, float]]  # 新增：月度收益率 {year: {month: return}}

    @staticmethod
    def from_equity_curve(curve: list[EquityPoint], trades: list[Trade],
                         risk_free_rate: float = 0.02,
                         trading_days_per_year: int = 252) -> Metrics:
        """从净值曲线和交易记录计算完整的绩效指标"""
        if not curve:
            return Metrics.create_empty_metrics()

        # 基本净值数据
        equities = [p.equity for p in curve]
        dates = [p.dt for p in curve]

        # 初始和最终净值
        initial_equity = equities[0]
        final_equity = equities[-1]

        # 收益率计算
        total_return = Metrics._calculate_total_return(initial_equity, final_equity)
        daily_returns = Metrics._calculate_daily_returns(equities)
        annual_return = Metrics._calculate_annual_return(daily_returns, trading_days_per_year)
        cagr = Metrics._calculate_cagr(initial_equity, final_equity, len(curve), trading_days_per_year)

        # 风险指标
        max_drawdown, drawdown_detail = Metrics._calculate_max_drawdown(equities, dates)
        volatility = Metrics._calculate_volatility(daily_returns, trading_days_per_year)
        downside_volatility = Metrics._calculate_downside_volatility(daily_returns, trading_days_per_year)

        # 比率指标
        sharpe = Metrics._calculate_sharpe_ratio(daily_returns, risk_free_rate, trading_days_per_year)
        sortino = Metrics._calculate_sortino_ratio(daily_returns, risk_free_rate, trading_days_per_year)
        calmar = Metrics._calculate_calmar_ratio(cagr, max_drawdown)

        # 交易指标
        trade_metrics = Metrics._calculate_trade_metrics(trades)

        # 时间指标
        time_metrics = Metrics._calculate_time_metrics(daily_returns)
        
        # 月度收益
        monthly_returns = Metrics._calculate_monthly_returns(curve)

        return Metrics(
            final_equity=float(final_equity),
            initial_equity=float(initial_equity),
            total_return=float(total_return),
            annual_return=float(annual_return),
            cagr=float(cagr),
            max_drawdown=float(max_drawdown),
            max_drawdown_detail=drawdown_detail,
            sharpe=float(sharpe),
            sortino=float(sortino),
            calmar=float(calmar),
            volatility=float(volatility),
            downside_volatility=float(downside_volatility),
            trade_count=trade_metrics['trade_count'],
            win_rate=float(trade_metrics['win_rate']),
            profit_factor=float(trade_metrics['profit_factor']),
            avg_win=float(trade_metrics['avg_win']),
            avg_loss=float(trade_metrics['avg_loss']),
            avg_r_multiple=float(trade_metrics['avg_r_multiple']),
            largest_win=float(trade_metrics['largest_win']),
            largest_loss=float(trade_metrics['largest_loss']),
            all_trade_pnls=[float(t.pnl) for t in trades],
            win_loss_ratio=float(trade_metrics['win_loss_ratio']),
            expectancy=float(trade_metrics['expectancy']),
            k_ratio=float(Metrics._calculate_k_ratio(daily_returns)),
            tail_ratio=float(Metrics._calculate_tail_ratio(daily_returns)),
            total_days=len(curve),
            profitable_days=float(time_metrics['profitable_days']),
            losing_days=float(time_metrics['losing_days']),
            best_day=float(time_metrics['best_day']),
            worst_day=float(time_metrics['worst_day']),
            monthly_returns=monthly_returns
        )

    @staticmethod
    def create_empty_metrics() -> Metrics:
        """创建空的绩效指标"""
        return Metrics(
            final_equity=0.0,
            initial_equity=0.0,
            total_return=0.0,
            annual_return=0.0,
            cagr=0.0,
            max_drawdown=0.0,
            max_drawdown_detail=None,
            sharpe=0.0,
            sortino=0.0,
            calmar=0.0,
            volatility=0.0,
            downside_volatility=0.0,
            trade_count=0,
            win_rate=0.0,
            profit_factor=0.0,
            avg_win=0.0,
            avg_loss=0.0,
            avg_r_multiple=0.0,
            largest_win=0.0,
            largest_loss=0.0,
            all_trade_pnls=[],
            win_loss_ratio=0.0,
            expectancy=0.0,
            k_ratio=0.0,
            tail_ratio=0.0,
            total_days=0,
            profitable_days=0.0,
            losing_days=0.0,
            best_day=0.0,
            worst_day=0.0,
            monthly_returns={}
        )

    @staticmethod
    def _calculate_monthly_returns(curve: list[EquityPoint]) -> dict[int, dict[int, float]]:
        """计算月度收益率"""
        if not curve:
            return {}

        # 按月分组
        monthly_equities = {}
        for p in curve:
            dt_str = str(p.dt)
            try:
                # 假设日期格式为 YYYY-MM-DD
                year = int(dt_str[:4])
                month = int(dt_str[5:7])
            except (ValueError, IndexError):
                continue

            if year not in monthly_equities:
                monthly_equities[year] = {}
            if month not in monthly_equities[year]:
                monthly_equities[year][month] = []
            monthly_equities[year][month].append(p.equity)

        # 计算每月收益
        monthly_returns = {}
        # 初始净值作为第一个月的比较基础
        prev_month_end_equity = curve[0].equity

        years = sorted(monthly_equities.keys())
        for year in years:
            monthly_returns[year] = {}
            months = sorted(monthly_equities[year].keys())
            for month in months:
                month_end_equity = monthly_equities[year][month][-1]
                monthly_returns[year][month] = (month_end_equity / prev_month_end_equity) - 1.0
                prev_month_end_equity = month_end_equity

        return monthly_returns

    @staticmethod
    def _calculate_total_return(initial: float, final: float) -> float:
        """计算总收益率"""
        if initial == 0:
            return 0.0
        return (final / initial) - 1.0

    @staticmethod
    def _calculate_daily_returns(equities: list[float]) -> list[float]:
        """计算日收益率"""
        returns = []
        for i in range(1, len(equities)):
            if equities[i-1] == 0:
                returns.append(0.0)
            else:
                returns.append((equities[i] / equities[i-1]) - 1.0)
        return returns

    @staticmethod
    def _calculate_annual_return(daily_returns: list[float], trading_days: int) -> float:
        """计算年化收益率"""
        if not daily_returns:
            return 0.0
        mean_return = sum(daily_returns) / len(daily_returns)
        return mean_return * trading_days

    @staticmethod
    def _calculate_cagr(initial: float, final: float, total_days: int, trading_days: int) -> float:
        """计算年化复合增长率"""
        if initial <= 0 or total_days <= 1:
            return 0.0
        years = (total_days - 1) / trading_days
        if years <= 0:
            return 0.0
        return (final / initial) ** (1 / years) - 1

    @staticmethod
    def _calculate_max_drawdown(equities: list[float], dates: list) -> tuple[float, Optional[DrawdownDetail]]:
        """计算最大回撤及其详细信息"""
        if not equities:
            return 0.0, None

        peak = equities[0]
        max_dd = 0.0
        dd_start_idx = 0
        dd_end_idx = 0
        current_dd_start = 0

        for i, e in enumerate(equities):
            if e > peak:
                peak = e
                current_dd_start = i

            dd = (e / peak) - 1.0 if peak != 0 else 0.0
            if dd < max_dd:
                max_dd = dd
                dd_start_idx = current_dd_start
                dd_end_idx = i

        # 计算恢复日期
        recovery_idx = None
        if dd_end_idx < len(equities) - 1:
            for i in range(dd_end_idx + 1, len(equities)):
                if equities[i] >= equities[dd_start_idx]:
                    recovery_idx = i
                    break

        detail = DrawdownDetail(
            max_drawdown=abs(max_dd),
            drawdown_start_index=dd_start_idx,
            drawdown_end_index=dd_end_idx,
            drawdown_start_date=str(dates[dd_start_idx]) if dd_start_idx < len(dates) else "",
            drawdown_end_date=str(dates[dd_end_idx]) if dd_end_idx < len(dates) else "",
            drawdown_duration=dd_end_idx - dd_start_idx,
            recovery_date=str(dates[recovery_idx]) if recovery_idx and recovery_idx < len(dates) else None
        )

        return abs(max_dd), detail

    @staticmethod
    def _calculate_volatility(returns: list[float], trading_days: int) -> float:
        """计算年化波动率"""
        if len(returns) < 2:
            return 0.0
        variance = sum((r - sum(returns)/len(returns)) ** 2 for r in returns) / (len(returns) - 1)
        return sqrt(variance) * sqrt(trading_days)

    @staticmethod
    def _calculate_downside_volatility(returns: list[float], trading_days: int) -> float:
        """计算下行波动率"""
        if len(returns) < 2:
            return 0.0
        mean_return = sum(returns) / len(returns)
        downside_returns = [r for r in returns if r < mean_return]
        if not downside_returns:
            return 0.0
        variance = sum((r - mean_return) ** 2 for r in downside_returns) / len(downside_returns)
        return sqrt(variance) * sqrt(trading_days)

    @staticmethod
    def _calculate_sharpe_ratio(returns: list[float], risk_free_rate: float, trading_days: int) -> float:
        """计算夏普比率"""
        if len(returns) < 2:
            return 0.0

        # 将年化无风险利率转换为日利率
        daily_rf = risk_free_rate / trading_days
        excess_returns = [r - daily_rf for r in returns]
        mean_excess = sum(excess_returns) / len(excess_returns)

        if mean_excess == 0:
            return 0.0

        variance = sum((r - mean_excess) ** 2 for r in excess_returns) / (len(excess_returns) - 1)
        if variance <= 0:
            return 0.0

        std_dev = sqrt(variance)
        return (mean_excess / std_dev) * sqrt(trading_days) if std_dev != 0 else 0.0

    @staticmethod
    def _calculate_sortino_ratio(returns: list[float], risk_free_rate: float, trading_days: int) -> float:
        """计算索提诺比率（只考虑下行风险）"""
        if len(returns) < 2:
            return 0.0

        daily_rf = risk_free_rate / trading_days
        excess_returns = [r - daily_rf for r in returns]
        mean_excess = sum(excess_returns) / len(excess_returns)

        if mean_excess == 0:
            return 0.0

        # 只计算负的超额收益的标准差
        downside_returns = [r for r in excess_returns if r < 0]
        if not downside_returns:
            return 0.0

        downside_variance = sum(r ** 2 for r in downside_returns) / len(downside_returns)
        downside_std = sqrt(downside_variance) if downside_variance > 0 else 0.0

        return (mean_excess / downside_std) * sqrt(trading_days) if downside_std != 0 else 0.0

    @staticmethod
    def _calculate_calmar_ratio(cagr: float, max_drawdown: float) -> float:
        """计算Calmar比率"""
        if max_drawdown == 0:
            return 0.0 if cagr == 0 else float('inf')
        return cagr / abs(max_drawdown)

    @staticmethod
    def _calculate_trade_metrics(trades: list[Trade]) -> dict[str, Any]:
        """计算交易相关指标"""
        if not trades:
            return {
                'trade_count': 0,
                'win_rate': 0.0,
                'profit_factor': 0.0,
                'avg_win': 0.0,
                'avg_loss': 0.0,
                'avg_r_multiple': 0.0,
                'largest_win': 0.0,
                'largest_loss': 0.0,
                'win_loss_ratio': 0.0,
                'expectancy': 0.0
            }

        win_trades = [t for t in trades if t.pnl > 0]
        loss_trades = [t for t in trades if t.pnl < 0]

        win_count = len(win_trades)
        loss_count = len(loss_trades)
        total_count = len(trades)

        # 胜率
        win_rate = win_count / total_count if total_count > 0 else 0.0

        # 总盈利和总亏损
        total_profit = sum(t.pnl for t in win_trades)
        total_loss = abs(sum(t.pnl for t in loss_trades))

        # 盈利因子
        profit_factor = total_profit / total_loss if total_loss > 0 else (total_profit if total_profit > 0 else 0.0)

        # 平均盈利和平均亏损
        avg_win = total_profit / win_count if win_count > 0 else 0.0
        avg_loss = total_loss / loss_count if loss_count > 0 else 0.0

        # 最大盈利和最大亏损
        largest_win = max((t.pnl for t in win_trades), default=0.0)
        largest_loss = min((t.pnl for t in loss_trades), default=0.0)

        # 盈亏比
        if abs(avg_loss) < 1e-9:
             win_loss_ratio = float('inf') if avg_win > 0 else 0.0
        else:
             win_loss_ratio = avg_win / abs(avg_loss)

        # R乘数（如果可用）
        r_multiples = [t.r_multiple for t in trades if t.r_multiple is not None]
        avg_r_multiple = sum(r_multiples) / len(r_multiples) if r_multiples else 0.0

        # 期望值
        expectancy = (win_rate * avg_win) - ((1 - win_rate) * abs(avg_loss))

        return {
            'trade_count': total_count,
            'win_rate': win_rate,
            'profit_factor': profit_factor,
            'avg_win': avg_win,
            'avg_loss': avg_loss,
            'avg_r_multiple': avg_r_multiple,
            'largest_win': largest_win,
            'largest_loss': largest_loss,
            'win_loss_ratio': win_loss_ratio,
            'expectancy': expectancy
        }

    @staticmethod
    def _calculate_k_ratio(returns: list[float]) -> float:
        """计算K比率（衡量收益率曲线的直线性）"""
        if len(returns) < 2:
            return 0.0

        # 计算累计收益
        cumulative_returns = [1.0]
        for r in returns:
            cumulative_returns.append(cumulative_returns[-1] * (1 + r))

        # 使用线性回归计算斜率
        x = list(range(len(cumulative_returns)))
        y = cumulative_returns

        n = len(x)
        sum_x = sum(x)
        sum_y = sum(y)
        sum_xy = sum(x[i] * y[i] for i in range(n))
        sum_x2 = sum(x_i ** 2 for x_i in x)

        slope = (n * sum_xy - sum_x * sum_y) / (n * sum_x2 - sum_x ** 2) if (n * sum_x2 - sum_x ** 2) != 0 else 0

        return slope * 1000  # 放大便于比较

    @staticmethod
    def _calculate_tail_ratio(returns: list[float]) -> float:
        """计算尾部比率（衡量极端收益与极端损失的比例）"""
        if len(returns) < 10:
            return 0.0

        # 取最好和最差的10%的收益
        sorted_returns = sorted(returns)
        n = len(sorted_returns)
        best_count = max(1, n // 10)
        worst_count = max(1, n // 10)

        best_avg = sum(sorted_returns[-best_count:]) / best_count
        worst_avg = sum(sorted_returns[:worst_count]) / worst_count

        if worst_avg == 0:
            return 0.0 if best_avg == 0 else float('inf')

        return abs(best_avg / worst_avg)

    @staticmethod
    def _calculate_time_metrics(returns: list[float]) -> dict[str, Any]:
        """计算时间相关指标"""
        if not returns:
            return {
                'profitable_days': 0.0,
                'losing_days': 0.0,
                'best_day': 0.0,
                'worst_day': 0.0
            }

        profitable_days = sum(1 for r in returns if r > 0)
        losing_days = sum(1 for r in returns if r < 0)

        return {
            'profitable_days': profitable_days / len(returns) if returns else 0.0,
            'losing_days': losing_days / len(returns) if returns else 0.0,
            'best_day': max(returns, default=0.0),
            'worst_day': min(returns, default=0.0)
        }

    def to_dict(self) -> dict[str, Any]:
        """将Metrics转换为字典"""
        out: dict[str, Any] = {}
        for key, value in self.__dict__.items():
            if key.startswith("_"):
                continue
            if is_dataclass(value):
                out[key] = asdict(value)
            else:
                out[key] = value
        return out

    def summary(self) -> str:
        """生成绩效摘要"""
        lines = [
            "=== 绩效摘要 ===",
            f"初始净值: {self.initial_equity:.2f}",
            f"最终净值: {self.final_equity:.2f}",
            f"总收益率: {self.total_return:.2%}",
            f"年化收益率: {self.annual_return:.2%}",
            f"CAGR: {self.cagr:.2%}",
            f"最大回撤: {self.max_drawdown:.2%}",
            f"夏普比率: {self.sharpe:.3f}",
            f"索提诺比率: {self.sortino:.3f}",
            f"Calmar比率: {self.calmar:.3f}",
            f"年化波动率: {self.volatility:.2%}",
            f"交易次数: {self.trade_count}",
            f"胜率: {self.win_rate:.2%}",
            f"盈利因子: {self.profit_factor:.3f}",
            f"期望值: {self.expectancy:.3f}",
            f"盈亏比: {self.win_loss_ratio:.3f}"
        ]

        if self.max_drawdown_detail:
            lines.append(f"最大回撤期间: {self.max_drawdown_detail.drawdown_start_date} 至 {self.max_drawdown_detail.drawdown_end_date}")
            lines.append(f"回撤持续时间: {self.max_drawdown_detail.drawdown_duration}天")
            if self.max_drawdown_detail.recovery_date:
                lines.append(f"回撤恢复日期: {self.max_drawdown_detail.recovery_date}")

        return "\n".join(lines)
