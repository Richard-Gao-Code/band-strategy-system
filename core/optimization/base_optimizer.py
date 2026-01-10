"""
优化器抽象基类
定义所有优化器的统一接口
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Dict, List


@dataclass
class OptimizationResult:
    """优化结果数据类"""

    success: bool
    best_params: Dict[str, Any]
    best_score: float
    iterations: int
    history: List[Dict[str, Any]]
    metadata: Dict[str, Any]


class BaseOptimizer(ABC):
    """优化器基类"""

    def __init__(self, strategy_name: str, param_space: Dict[str, Any]):
        self.strategy_name = strategy_name
        self.param_space = param_space
        self.history = []

    @abstractmethod
    async def optimize(self, n_iterations: int = 50, objective: str = "sharpe_ratio") -> OptimizationResult:
        """
        执行优化

        Args:
            n_iterations: 迭代次数
            objective: 优化目标（sharpe_ratio, win_rate, stability_score）

        Returns:
            OptimizationResult
        """
        raise NotImplementedError
