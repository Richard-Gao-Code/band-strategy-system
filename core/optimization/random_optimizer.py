"""
随机搜索优化器 - 作为性能基线
"""

from __future__ import annotations

import random
from typing import Any, Dict

from .base_optimizer import BaseOptimizer, OptimizationResult


class RandomOptimizer(BaseOptimizer):
    """随机搜索优化器"""

    async def optimize(self, n_iterations: int = 50, objective: str = "sharpe_ratio") -> OptimizationResult:
        print(f"[优化器] 随机搜索开始: {self.strategy_name}")

        best_score = -float("inf")
        best_params = None
        history = []

        for i in range(n_iterations):
            params = self._generate_random_params()
            score = random.uniform(0.5, 2.0)

            history.append({"iteration": i, "params": params, "score": score})

            if score > best_score:
                best_score = score
                best_params = params

        return OptimizationResult(
            success=True,
            best_params=best_params or {},
            best_score=best_score,
            iterations=n_iterations,
            history=history,
            metadata={"optimizer": "random"},
        )

    def _generate_random_params(self) -> Dict[str, Any]:
        """根据参数空间生成随机参数"""
        params = {}
        for param_name, space in self.param_space.items():
            if isinstance(space, dict) and "min" in space and "max" in space:
                if "type" in space and space["type"] == "int":
                    params[param_name] = random.randint(int(space["min"]), int(space["max"]))
                else:
                    params[param_name] = random.uniform(space["min"], space["max"])
            elif isinstance(space, list):
                params[param_name] = random.choice(space)
            elif isinstance(space, dict) and "choices" in space:
                params[param_name] = random.choice(space["choices"])

        return params
