"""优化器管理器 - 调度和执行优化任务"""

from __future__ import annotations

from typing import Any, Dict

from config.database import get_db
from data.storage.repository import OptimizationRepository

from .base_optimizer import BaseOptimizer
from .bayesian_optimizer import BayesianOptimizer


class OptimizerManager:
    """优化器管理器"""

    def __init__(self):
        self.active_tasks = {}

    def create_optimizer(
        self,
        optimizer_type: str,
        strategy_name: str,
        param_space: Dict[str, Any],
        **kwargs,
    ) -> BaseOptimizer:
        """创建优化器实例"""
        if optimizer_type == "random":
            from .random_optimizer import RandomOptimizer

            return RandomOptimizer(strategy_name=strategy_name, param_space=param_space, **kwargs)

        if optimizer_type == "bayesian":
            from .bayesian_optimizer import BayesianOptimizer

            required_params = ["data_provider", "strategy_class"]
            for param in required_params:
                if param not in kwargs:
                    raise ValueError(f"贝叶斯优化器需要参数: {param}")

            return BayesianOptimizer(
                strategy_name=strategy_name,
                param_space=param_space,
                data_provider=kwargs.get("data_provider"),
                strategy_class=kwargs.get("strategy_class"),
                initial_cash=kwargs.get("initial_cash", 1_000_000.0),
                benchmark_symbol=kwargs.get("benchmark_symbol"),
                commission_rate=kwargs.get("commission_rate", 0.0003),
                **{
                    k: v
                    for k, v in kwargs.items()
                    if k
                    not in {
                        "data_provider",
                        "strategy_class",
                        "initial_cash",
                        "benchmark_symbol",
                        "commission_rate",
                    }
                },
            )

        raise ValueError(f"不支持的优化器类型: {optimizer_type}")

    async def run_optimization(
        self,
        optimizer_type: str,
        strategy_name: str,
        param_space: Dict[str, Any],
        n_iterations: int = 50,
        objective: str = "sharpe_ratio",
        **kwargs,
    ) -> Dict[str, Any]:
        """运行优化任务"""
        print(f"开始优化任务: {strategy_name}, 算法: {optimizer_type}")

        optimizer = self.create_optimizer(
            optimizer_type=optimizer_type,
            strategy_name=strategy_name,
            param_space=param_space,
            **kwargs,
        )

        result = await optimizer.optimize(n_iterations=n_iterations, objective=objective)

        if result.success:
            with get_db() as db:
                OptimizationRepository.save(
                    db,
                    {
                        "strategy_name": strategy_name,
                        "optimization_type": optimizer_type,
                        "base_params": {},
                        "optimized_params": result.best_params,
                        "improvement_rate": result.best_score,
                        "iterations": result.iterations,
                        "status": "completed",
                    },
                )

        scores = [h.get("score") for h in result.history if isinstance(h, dict) and h.get("score") is not None]
        score_min = min(scores) if scores else None
        score_max = max(scores) if scores else None

        return {
            "success": result.success,
            "optimizer_type": optimizer_type,
            "strategy_name": strategy_name,
            "best_params": result.best_params,
            "best_score": result.best_score,
            "iterations": result.iterations,
            "history_summary": {
                "total_iterations": len(result.history),
                "score_range": (score_min, score_max),
            },
        }

    async def compare_optimizers(
        self,
        strategy_name: str,
        param_space: Dict[str, Any],
        n_iterations: int = 30,
    ) -> Dict[str, Any]:
        """比较不同优化器性能"""
        results: dict[str, Any] = {}

        for optimizer_type in ["random", "bayesian"]:
            print(f"\n比较优化器: {optimizer_type}")
            try:
                results[optimizer_type] = await self.run_optimization(
                    optimizer_type=optimizer_type,
                    strategy_name=strategy_name,
                    param_space=param_space,
                    n_iterations=n_iterations,
                )
            except Exception as e:
                print(f"优化器 {optimizer_type} 失败: {e}")
                results[optimizer_type] = {"error": str(e)}

        return results
