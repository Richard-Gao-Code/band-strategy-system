"""贝叶斯优化器实现
基于scikit-optimize的高斯过程优化
"""

from __future__ import annotations

import inspect
from dataclasses import is_dataclass, replace
from typing import Any, Dict, Type

import numpy as np
from skopt import gp_minimize
from skopt.space import Categorical, Integer, Real
from skopt.utils import use_named_args

from ..types import BacktestConfig, BrokerConfig
from ..event_engine import EventBacktestEngine
from ..types import Bar
from config.database import get_db
from data.storage.repository import ParamPerformanceRepository

from .base_optimizer import BaseOptimizer, OptimizationResult


class BayesianOptimizer(BaseOptimizer):
    """贝叶斯优化器（高斯过程）"""
    
    def __init__(
        self,
        strategy_name: str,
        param_space: Dict[str, Any],
        data_provider: Any,
        strategy_class: Type,
        initial_cash: float = 1_000_000.0,
        benchmark_symbol: str | None = None,
        commission_rate: float = 0.0003,
        **kwargs,
    ):
        super().__init__(strategy_name, param_space)
        self.data_provider = data_provider
        self.strategy_class = strategy_class
        self.initial_cash = float(initial_cash)
        self.benchmark_symbol = benchmark_symbol
        self.commission_rate = float(commission_rate)
        self.objective = "sharpe_ratio"
        self._kwargs = dict(kwargs)
        self.skopt_space = self._convert_to_skopt_space(param_space)
        
    async def optimize(self, n_iterations: int = 50, objective: str = "sharpe_ratio") -> OptimizationResult:
        """
        执行贝叶斯优化
        
        Args:
            n_iterations: 总迭代次数（包括初始随机点）
            objective: 优化目标
            
        Returns:
            OptimizationResult
        """
        print(f"[贝叶斯优化器] 开始优化: {self.strategy_name}, 目标: {objective}")
        self.objective = objective
        
        # 初始随机点数量（处理小规模迭代）
        if n_iterations <= 2:
            n_initial_points = 1
        else:
            n_initial_points = min(max(2, int(n_iterations * 0.3)), n_iterations - 1)
        
        try:
            # 执行贝叶斯优化
            result = gp_minimize(
                func=self._objective_wrapper(),
                dimensions=self.skopt_space,
                n_calls=n_iterations,
                n_initial_points=n_initial_points,
                random_state=42,
                verbose=False
            )
            
            # 构建优化历史
            history = []
            for i, (params, score) in enumerate(zip(result.x_iters, result.func_vals)):
                history.append({
                    'iteration': i,
                    'params': self._decode_params(params),
                    'score': -score,  # skopt是最小化，我们取负
                    'acquisition': 'unknown'
                })
            
            # 获取最佳参数
            best_params = self._decode_params(result.x)
            best_score = -result.fun  # 转换回最大化
            
            print(f"[贝叶斯优化器] 完成: 最佳分数 = {best_score:.4f}")
            
            return OptimizationResult(
                success=True,
                best_params=best_params,
                best_score=best_score,
                iterations=n_iterations,
                history=history,
                metadata={
                    'optimizer': 'bayesian',
                    'model': 'gaussian_process',
                    'n_initial_points': n_initial_points,
                    'converged': result.specs.get('args', {}).get('callback', None) is not None
                }
            )
            
        except Exception as e:
            print(f"[贝叶斯优化器] 错误: {e}")
            return OptimizationResult(
                success=False,
                best_params={},
                best_score=0.0,
                iterations=0,
                history=[],
                metadata={'error': str(e)}
            )
    
    def _convert_to_skopt_space(self, param_space: Dict[str, Any]) -> list:
        """将我们的参数空间转换为skopt空间格式"""
        skopt_space = []
        
        for param_name, space_def in param_space.items():
            if isinstance(space_def, dict):
                if 'min' in space_def and 'max' in space_def:
                    if space_def.get('type') == 'int':
                        # 整数范围
                        skopt_space.append(
                            Integer(space_def['min'], space_def['max'], name=param_name)
                        )
                    else:
                        # 浮点数范围
                        skopt_space.append(
                            Real(space_def['min'], space_def['max'], name=param_name)
                        )
                elif 'choices' in space_def:
                    # 离散选择
                    skopt_space.append(
                        Categorical(space_def['choices'], name=param_name)
                    )
            elif isinstance(space_def, list):
                # 列表形式的离散值
                skopt_space.append(
                    Categorical(space_def, name=param_name)
                )
            else:
                raise ValueError(f"不支持的参数空间格式: {param_name} = {space_def}")
        
        return skopt_space
    
    def _objective_wrapper(self):
        """创建目标函数包装器"""
        @use_named_args(dimensions=self.skopt_space)
        def objective_function(**params):
            """实际的目标函数（需要负号因为skopt是最小化）"""
            score = self._evaluate_params(params)
            return -score  # skopt是最小化，所以我们取负
        
        return objective_function
    
    def _evaluate_params(self, params: Dict[str, Any]) -> float:
        """真实回测评估参数组合"""
        try:
            symbol = getattr(self.data_provider, "symbol", None)
            symbol = str(symbol).strip() if symbol is not None else ""
            if not symbol:
                symbol = "000001.SZ"

            bars: list[Bar] | None = None
            if hasattr(self.data_provider, "get_bars") and callable(getattr(self.data_provider, "get_bars")):
                bars = self.data_provider.get_bars(symbol)
            elif isinstance(self.data_provider, list):
                bars = self.data_provider
            elif isinstance(self.data_provider, dict):
                v = self.data_provider.get(symbol)
                if isinstance(v, list):
                    bars = v

            if not bars:
                return -float("inf")

            benchmark_bars = None
            if self.benchmark_symbol:
                if hasattr(self.data_provider, "get_bars") and callable(getattr(self.data_provider, "get_bars")):
                    benchmark_bars = self.data_provider.get_bars(self.benchmark_symbol)

            cfg = BacktestConfig(
                initial_cash=self.initial_cash,
                broker=BrokerConfig(
                    commission_rate=self.commission_rate,
                    slippage_bps=2.0,
                    min_commission=5.0,
                    stamp_duty_rate=0.0005,
                    slippage_rate=0.0001,
                ),
                benchmark_symbol=self.benchmark_symbol,
            )

            strategy = self._build_strategy(bars=bars, benchmark_bars=benchmark_bars, params=params)
            engine = EventBacktestEngine(config=cfg)
            result = engine.run(bars=bars, strategy=strategy, benchmark_bars=benchmark_bars)

            m = result.metrics
            if self.objective == "sharpe_ratio":
                score = float(m.sharpe) if m.sharpe is not None else -float("inf")
            elif self.objective == "total_return":
                score = float(m.total_return) if m.total_return is not None else -float("inf")
            elif self.objective == "win_rate":
                score = float(m.win_rate) if m.win_rate is not None else 0.0
            else:
                score = float(m.sharpe) if m.sharpe is not None else -float("inf")

            try:
                with get_db() as db:
                    ParamPerformanceRepository.save(
                        db,
                        {
                            "strategy_name": self.strategy_name,
                            "param_combo": dict(params),
                            "metrics": {
                                "total_return": m.total_return,
                                "cagr": m.cagr,
                                "max_drawdown": m.max_drawdown,
                                "sharpe": m.sharpe,
                                "win_rate": m.win_rate,
                                "trade_count": m.trade_count,
                                "final_equity": m.final_equity,
                            },
                            "sample_size": len(bars),
                            "sharpe_ratio": m.sharpe,
                            "win_rate": m.win_rate,
                            "max_drawdown": m.max_drawdown,
                            "stability_score": 0.0,
                        },
                    )
            except Exception:
                pass

            return score
        except Exception:
            return -float("inf")

    def _build_strategy(self, bars: list[Bar], benchmark_bars: list[Bar] | None, params: Dict[str, Any]):
        cls = self.strategy_class
        sig = inspect.signature(cls)
        call_kwargs: dict[str, Any] = {}
        if "bars" in sig.parameters:
            call_kwargs["bars"] = bars
        if "index_bars" in sig.parameters:
            call_kwargs["index_bars"] = benchmark_bars

        if "config" in sig.parameters:
            call_kwargs["config"] = None

        try:
            base_strategy = cls(**call_kwargs)
        except Exception:
            try:
                base_strategy = cls(bars)
            except Exception:
                base_strategy = cls()

        cfg = getattr(base_strategy, "config", None)
        cfg_overrides: dict[str, Any] = {}
        if cfg is not None and is_dataclass(cfg):
            cfg_fields = {f.name for f in getattr(cfg, "__dataclass_fields__", {}).values()} if hasattr(cfg, "__dataclass_fields__") else set()
            for k, v in params.items():
                if k in cfg_fields:
                    cfg_overrides[k] = v

        if cfg_overrides and cfg is not None and is_dataclass(cfg):
            new_cfg = replace(cfg, **cfg_overrides)
            if "config" in sig.parameters:
                call_kwargs["config"] = new_cfg
                try:
                    return cls(**call_kwargs)
                except Exception:
                    setattr(base_strategy, "config", new_cfg)
            else:
                setattr(base_strategy, "config", new_cfg)

        for k, v in params.items():
            if hasattr(base_strategy, k):
                try:
                    setattr(base_strategy, k, v)
                except Exception:
                    pass

        return base_strategy
    
    def _decode_params(self, skopt_params: list) -> Dict[str, Any]:
        """将skopt参数解码回我们的格式"""
        decoded = {}
        
        for i, (dim, value) in enumerate(zip(self.skopt_space, skopt_params)):
            param_name = dim.name
            # 处理不同类型
            if isinstance(dim, Integer):
                decoded[param_name] = int(value)
            elif isinstance(dim, Real):
                decoded[param_name] = float(value)
            else:
                decoded[param_name] = value
        
        return decoded
