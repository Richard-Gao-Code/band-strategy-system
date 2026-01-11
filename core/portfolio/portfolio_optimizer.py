from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Literal, Mapping, Optional, Sequence, Tuple, Union

import numpy as np
import pandas as pd


ReturnsInput = Union[pd.DataFrame, Mapping[str, Sequence[float]]]
OptimizationEngine = Literal["basic", "pypfopt"]
OptimizationMethod = Literal["equal_weight", "inverse_volatility", "min_variance"]


@dataclass(frozen=True)
class PortfolioOptimizationResult:
    method: str
    weights: Dict[str, float]
    expected_return: float
    expected_risk: float
    sharpe: float
    risk_metrics: Dict[str, float] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "method": self.method,
            "weights": dict(self.weights),
            "expected_return": float(self.expected_return),
            "expected_risk": float(self.expected_risk),
            "sharpe": float(self.sharpe),
            "risk_metrics": dict(self.risk_metrics),
            "metadata": dict(self.metadata),
        }


class PortfolioOptimizer:
    def __init__(
        self,
        engine: OptimizationEngine = "basic",
        risk_free_rate: float = 0.0,
        weight_bounds: Tuple[float, float] = (0.0, 1.0),
        frequency: int = 252,
    ) -> None:
        self.engine = str(engine)
        self.risk_free_rate = float(risk_free_rate)
        self.weight_bounds = (float(weight_bounds[0]), float(weight_bounds[1]))
        self.frequency = int(frequency)

    def optimize(self, returns: ReturnsInput, method: OptimizationMethod) -> PortfolioOptimizationResult:
        if method == "equal_weight":
            return self.optimize_equal_weight(returns)
        if method == "inverse_volatility":
            return self.optimize_inverse_volatility(returns)
        if method == "min_variance":
            return self.optimize_min_variance(returns)
        raise ValueError(f"Unsupported optimization method: {method}")

    def optimize_equal_weight(self, returns: ReturnsInput) -> PortfolioOptimizationResult:
        returns_df = self._to_returns_df(returns)
        n = int(returns_df.shape[1])
        raw = {k: 1.0 / n for k in returns_df.columns}
        weights = self._project_to_bounds_simplex(raw, self.weight_bounds)
        mu, cov = self._estimate_mu_cov_basic(returns_df)
        exp_ret, exp_vol, exp_sharpe = self._portfolio_performance(mu, cov, weights)
        risk_metrics = self._basic_risk_metrics(weights, mu, cov)
        return PortfolioOptimizationResult(
            method="equal_weight",
            weights=weights,
            expected_return=float(exp_ret),
            expected_risk=float(exp_vol),
            sharpe=float(exp_sharpe),
            risk_metrics=risk_metrics,
            metadata={"engine": self.engine},
        )

    def optimize_inverse_volatility(self, returns: ReturnsInput) -> PortfolioOptimizationResult:
        returns_df = self._to_returns_df(returns)
        mu, cov = self._estimate_mu_cov_basic(returns_df)
        variances = np.diag(cov.values).astype("float64", copy=False)
        if not np.isfinite(variances).all():
            raise ValueError("Cannot compute variance from returns")
        if (variances <= 0.0).any():
            raise ValueError("Volatility must be positive for inverse volatility weighting")

        vol = np.sqrt(variances)
        inv = 1.0 / vol
        total = float(np.sum(inv))
        if not np.isfinite(total) or total <= 0.0:
            raise ValueError("Cannot compute inverse volatility weights")

        raw = {k: float(inv[i] / total) for i, k in enumerate(returns_df.columns)}
        weights = self._project_to_bounds_simplex(raw, self.weight_bounds)
        exp_ret, exp_vol, exp_sharpe = self._portfolio_performance(mu, cov, weights)
        risk_metrics = self._basic_risk_metrics(weights, mu, cov)
        return PortfolioOptimizationResult(
            method="inverse_volatility",
            weights=weights,
            expected_return=float(exp_ret),
            expected_risk=float(exp_vol),
            sharpe=float(exp_sharpe),
            risk_metrics=risk_metrics,
            metadata={"engine": self.engine},
        )

    def optimize_min_variance(self, returns: ReturnsInput) -> PortfolioOptimizationResult:
        returns_df = self._to_returns_df(returns)
        mu, cov = self._estimate_mu_cov_basic(returns_df)
        keys = list(returns_df.columns)
        cov_m = cov.values
        ones = np.ones(len(keys), dtype="float64")
        inv_cov = np.linalg.pinv(cov_m)
        v = inv_cov @ ones
        raw = {k: float(v[i]) for i, k in enumerate(keys)}
        weights = self._project_to_bounds_simplex(raw, self.weight_bounds)
        exp_ret, exp_vol, exp_sharpe = self._portfolio_performance(mu, cov, weights)
        risk_metrics = self._basic_risk_metrics(weights, mu, cov)
        return PortfolioOptimizationResult(
            method="min_variance",
            weights=weights,
            expected_return=float(exp_ret),
            expected_risk=float(exp_vol),
            sharpe=float(exp_sharpe),
            risk_metrics=risk_metrics,
            metadata={"engine": self.engine},
        )

    def _to_returns_df(self, returns: ReturnsInput) -> pd.DataFrame:
        if isinstance(returns, pd.DataFrame):
            df = returns.copy()
        elif isinstance(returns, Mapping):
            df = pd.DataFrame({k: pd.Series(v, dtype="float64") for k, v in returns.items()})
        else:
            raise TypeError("returns must be a pandas.DataFrame or a mapping of strategy_id -> returns sequence")

        df = df.replace([np.inf, -np.inf], np.nan).dropna(axis=0, how="any")
        if df.empty:
            raise ValueError("returns is empty after dropping NaN/inf")
        if df.shape[1] < 2:
            raise ValueError("returns must contain at least 2 strategies")
        if df.shape[0] < 2:
            raise ValueError("returns must contain at least 2 observations")
        df = df.astype("float64")
        return df

    def _maybe_pypfopt(self) -> Optional[Dict[str, Any]]:
        try:
            from pypfopt import expected_returns, risk_models
            from pypfopt.efficient_frontier import EfficientFrontier
        except Exception as e:
            return None

        hrp_opt = None
        try:
            from pypfopt.hierarchical_risk_parity import HRPOpt

            hrp_opt = HRPOpt
        except Exception:
            hrp_opt = None

        return {
            "expected_returns": expected_returns,
            "risk_models": risk_models,
            "EfficientFrontier": EfficientFrontier,
            "HRPOpt": hrp_opt,
        }

    def _estimate_mu_cov_basic(self, returns_df: pd.DataFrame) -> Tuple[pd.Series, pd.DataFrame]:
        mu = returns_df.mean() * float(self.frequency)
        cov = returns_df.cov() * float(self.frequency)
        if cov.isnull().values.any():
            raise ValueError("Covariance matrix contains NaN")
        return mu, cov

    def _portfolio_performance(
        self,
        mu: pd.Series,
        cov: pd.DataFrame,
        weights: Mapping[str, float],
    ) -> Tuple[float, float, float]:
        keys = list(mu.index)
        w = np.array([float(weights.get(k, 0.0)) for k in keys], dtype="float64")
        exp_ret = float(np.dot(mu.values, w))
        exp_vol = float(np.sqrt(np.dot(w.T, np.dot(cov.values, w))))
        sharpe = float((exp_ret - self.risk_free_rate) / exp_vol) if exp_vol > 0 else float("-inf")
        return exp_ret, exp_vol, sharpe

    def _project_to_bounds_simplex(
        self,
        weights: Mapping[str, float],
        bounds: Tuple[float, float],
    ) -> Dict[str, float]:
        keys = list(weights.keys())
        v = np.array([float(weights[k]) for k in keys], dtype="float64")
        if not np.isfinite(v).all():
            raise ValueError("Weights contain non-finite values")

        lower, upper = float(bounds[0]), float(bounds[1])
        if lower > upper:
            raise ValueError("Invalid weight bounds")
        if lower * len(keys) - 1.0 > 1e-12 or 1.0 - upper * len(keys) > 1e-12:
            raise ValueError("Bounds make sum-to-one infeasible")

        total = float(v.sum())
        if np.isfinite(total) and total > 0.0:
            v_norm = v / total
            if abs(float(v_norm.sum()) - 1.0) <= 1e-12 and (v_norm >= lower - 1e-12).all() and (v_norm <= upper + 1e-12).all():
                return {k: float(v_norm[i]) for i, k in enumerate(keys)}

        w = self._project_capped_simplex(v, lower, upper)
        out = {k: float(w[i]) for i, k in enumerate(keys)}
        return out

    def _project_capped_simplex(self, v: np.ndarray, lower: float, upper: float) -> np.ndarray:
        lo = float(lower)
        hi = float(upper)
        if lo == hi:
            return np.full_like(v, lo, dtype="float64")

        def s(lam: float) -> float:
            w = np.clip(v - lam, lo, hi)
            return float(w.sum())

        lam_low = float(np.min(v) - hi)
        lam_high = float(np.max(v) - lo)

        sum_low = s(lam_low)
        sum_high = s(lam_high)

        if sum_low < 1.0 - 1e-12 or sum_high > 1.0 + 1e-12:
            raise ValueError("Unable to project weights onto feasible simplex")

        for _ in range(80):
            lam_mid = 0.5 * (lam_low + lam_high)
            sum_mid = s(lam_mid)
            if abs(sum_mid - 1.0) <= 1e-12:
                break
            if sum_mid > 1.0:
                lam_low = lam_mid
            else:
                lam_high = lam_mid

        w = np.clip(v - 0.5 * (lam_low + lam_high), lo, hi)
        total = float(w.sum())
        if not np.isfinite(total) or abs(total - 1.0) > 1e-8:
            w = w / total
        return w

    def _basic_risk_metrics(self, weights: Mapping[str, float], mu: pd.Series, cov: pd.DataFrame) -> Dict[str, float]:
        keys = list(mu.index)
        w = np.array([float(weights.get(k, 0.0)) for k in keys], dtype="float64")
        cov_m = cov.values
        port_var = float(np.dot(w.T, np.dot(cov_m, w)))
        max_w = float(np.max(w)) if len(w) else float("nan")
        min_w = float(np.min(w)) if len(w) else float("nan")
        effective_n = float(1.0 / np.sum(np.square(w))) if np.sum(np.square(w)) > 0 else float("nan")
        if port_var <= 0:
            return {"diversification_ratio": float("nan"), "effective_n": effective_n, "max_weight": max_w, "min_weight": min_w}

        indiv_vol = np.sqrt(np.diag(cov_m))
        weighted_vol = float(np.dot(indiv_vol, w))
        port_vol = float(np.sqrt(port_var))
        diversification_ratio = float(weighted_vol / port_vol) if port_vol > 0 else float("nan")
        return {
            "diversification_ratio": diversification_ratio,
            "effective_n": effective_n,
            "max_weight": max_w,
            "min_weight": min_w,
        }
