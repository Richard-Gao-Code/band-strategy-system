"""
参数性能数据模型
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime

from sqlalchemy import Column, DateTime, Float, Integer, JSON, String

from config.database import Base


class ParamPerformance(Base):
    """参数性能表"""

    __tablename__ = "param_performance"

    id = Column(Integer, primary_key=True, autoincrement=True)
    strategy_name = Column(String(100), nullable=False, index=True)
    param_hash = Column(String(32), unique=True, index=True)
    param_combo = Column(JSON, nullable=False)
    metrics = Column(JSON, nullable=False)
    test_date = Column(DateTime, default=datetime.utcnow, index=True)
    sample_size = Column(Integer, default=0)

    sharpe_ratio = Column(Float)
    win_rate = Column(Float)
    max_drawdown = Column(Float)
    stability_score = Column(Float, default=0.0)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "strategy_name": self.strategy_name,
            "param_hash": self.param_hash,
            "param_combo": self.param_combo,
            "metrics": self.metrics,
            "test_date": self.test_date.isoformat() if self.test_date else None,
            "sample_size": self.sample_size,
            "sharpe_ratio": self.sharpe_ratio,
            "win_rate": self.win_rate,
            "max_drawdown": self.max_drawdown,
            "stability_score": self.stability_score,
        }

    @classmethod
    def generate_param_hash(cls, param_combo):
        """生成参数哈希"""
        param_str = json.dumps(param_combo, sort_keys=True, ensure_ascii=False)
        return hashlib.md5(param_str.encode("utf-8")).hexdigest()


class OptimizationHistory(Base):
    """优化历史表"""

    __tablename__ = "optimization_history"

    id = Column(Integer, primary_key=True, autoincrement=True)
    optimization_date = Column(DateTime, default=datetime.utcnow, index=True)
    strategy_name = Column(String(100), index=True)
    optimization_type = Column(String(50))

    base_params = Column(JSON)
    optimized_params = Column(JSON)
    improvement_rate = Column(Float)

    iterations = Column(Integer, default=0)
    status = Column(String(20), default="completed")

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "optimization_date": self.optimization_date.isoformat() if self.optimization_date else None,
            "strategy_name": self.strategy_name,
            "optimization_type": self.optimization_type,
            "base_params": self.base_params,
            "optimized_params": self.optimized_params,
            "improvement_rate": self.improvement_rate,
            "iterations": self.iterations,
            "status": self.status,
        }
