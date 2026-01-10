"""
数据访问仓库
"""

from __future__ import annotations

from sqlalchemy import desc
from sqlalchemy.orm import Session

from data.storage.models import OptimizationHistory, ParamPerformance


class ParamPerformanceRepository:
    """参数性能仓库"""

    @staticmethod
    def save(db: Session, data: dict) -> ParamPerformance:
        """保存性能数据"""
        param_hash = ParamPerformance.generate_param_hash(data["param_combo"])
        data["param_hash"] = param_hash

        existing = (
            db.query(ParamPerformance)
            .filter(
                ParamPerformance.param_hash == param_hash,
                ParamPerformance.strategy_name == data["strategy_name"],
            )
            .first()
        )

        if existing:
            for key, value in data.items():
                if hasattr(existing, key) and key != "id":
                    setattr(existing, key, value)
        else:
            existing = ParamPerformance(**data)
            db.add(existing)

        db.commit()
        db.refresh(existing)
        return existing

    @staticmethod
    def get_best(db: Session, strategy_name: str, limit: int = 10):
        """获取最佳参数"""
        return (
            db.query(ParamPerformance)
            .filter(ParamPerformance.strategy_name == strategy_name)
            .order_by(desc(ParamPerformance.sharpe_ratio), desc(ParamPerformance.win_rate))
            .limit(limit)
            .all()
        )


class OptimizationRepository:
    """优化历史仓库"""

    @staticmethod
    def save(db: Session, data: dict) -> OptimizationHistory:
        """保存优化记录"""
        record = OptimizationHistory(**data)
        db.add(record)
        db.commit()
        db.refresh(record)
        return record

    @staticmethod
    def get_optimization_history(db: Session, strategy_name: str, limit: int = 20):
        return (
            db.query(OptimizationHistory)
            .filter(OptimizationHistory.strategy_name == strategy_name)
            .order_by(desc(OptimizationHistory.optimization_date))
            .limit(int(limit))
            .all()
        )
