import numpy as np
import pandas as pd
import pytest

from core.portfolio import PortfolioOptimizer


def _make_returns(seed: int = 7, n: int = 252) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    a = rng.normal(loc=0.0006, scale=0.010, size=n)
    b = rng.normal(loc=0.0003, scale=0.020, size=n)
    c = rng.normal(loc=0.0002, scale=0.030, size=n)
    return pd.DataFrame({"s1": a, "s2": b, "s3": c})


def test_equal_weight_weights_sum_to_one():
    opt = PortfolioOptimizer(engine="basic", risk_free_rate=0.0, frequency=252)
    res = opt.optimize_equal_weight(_make_returns())
    assert set(res.weights.keys()) == {"s1", "s2", "s3"}
    assert abs(sum(res.weights.values()) - 1.0) < 1e-10
    assert all(0.0 <= w <= 1.0 for w in res.weights.values())
    assert res.method == "equal_weight"
    assert res.expected_risk > 0


def test_inverse_volatility_prefers_low_vol():
    opt = PortfolioOptimizer(engine="basic", risk_free_rate=0.0, frequency=252)
    df = _make_returns()
    res = opt.optimize_inverse_volatility(df)
    assert abs(sum(res.weights.values()) - 1.0) < 1e-10
    cov = df.cov() * 252
    vol = pd.Series(np.sqrt(np.diag(cov.values)), index=df.columns)
    sorted_by_vol = vol.sort_values(ascending=True).index.tolist()
    sorted_by_weight = sorted(res.weights.keys(), key=lambda k: res.weights[k], reverse=True)
    assert sorted_by_weight == sorted_by_vol
    assert res.expected_risk > 0


def test_min_variance_weights_sum_to_one():
    opt = PortfolioOptimizer(engine="basic", risk_free_rate=0.0, frequency=252)
    res = opt.optimize_min_variance(_make_returns())
    assert abs(sum(res.weights.values()) - 1.0) < 1e-10
    assert all(0.0 <= w <= 1.0 for w in res.weights.values())
    assert res.expected_risk > 0


def test_invalid_returns_raise():
    opt = PortfolioOptimizer(engine="basic", risk_free_rate=0.0, frequency=252)
    with pytest.raises(ValueError):
        opt.optimize_equal_weight(pd.DataFrame())
    with pytest.raises(ValueError):
        opt.optimize_equal_weight(pd.DataFrame({"s1": [0.01, 0.02]}))
    with pytest.raises(ValueError):
        opt.optimize_equal_weight(pd.DataFrame({"s1": [0.01, np.nan], "s2": [0.02, 0.03]}))


def test_inverse_volatility_zero_vol_raises():
    opt = PortfolioOptimizer(engine="basic", risk_free_rate=0.0, frequency=252)
    df = pd.DataFrame({"s1": [0.0] * 30, "s2": np.linspace(0.0, 0.01, 30)})
    with pytest.raises(ValueError):
        opt.optimize_inverse_volatility(df)
