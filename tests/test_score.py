# tests/test_score.py
import pytest
from fund.db import FundDB
from fund.score import ScoreEngine


@pytest.fixture
def config():
    return {
        "data": {"db_path": ":memory:"},
        "weights": {"risk_adj": 0.45, "performance": 0.35, "fund_quality": 0.20},
        "risk_adj": {"sharpe_ratio": 0.15, "max_drawdown": 0.15, "calmar_ratio": 0.15},
        "performance": {"return_1y": 0.10, "return_2y": 0.10, "return_3y": 0.10, "volatility": 0.05},
        "fund_quality": {"fund_size": 0.05, "fee_rate": 0.05, "fund_age": 0.05, "inst_ratio": 0.05},
        "score": {
            "min_fund_age_years": 3,
            "optimal_size_min": 1, "optimal_size_max": 50,
            "optimal_inst_min": 0.20, "optimal_inst_max": 0.60,
        },
        "fund_types": ["股票型", "混合型"],
    }


@pytest.fixture
def engine(config):
    db = FundDB(":memory:")
    return ScoreEngine(db=db, config=config)


def test_score_engine_init(engine):
    assert engine.weights["risk_adj"] == 0.45


def test_fund_size_score_optimal(engine):
    score = engine._score_fund_size(25.0)
    assert score == 100.0


def test_fund_size_score_too_small(engine):
    score = engine._score_fund_size(0.3)
    assert score < 50.0


def test_fund_age_score(engine):
    score = engine._score_fund_age("2016-05-17")
    assert score == 100.0


def test_fund_age_score_young(engine):
    score = engine._score_fund_age("2025-01-01")
    assert score < 50.0


def test_inst_ratio_score_optimal(engine):
    score = engine._score_inst_ratio(0.40)
    assert score == 100.0


def test_score_fund(engine):
    fund = {
        "code": "110011",
        "name": "test fund",
        "fund_type": "混合型",
        "return_1y": 32.5,
        "return_2y": 45.2,
        "return_3y": 68.2,
        "volatility": 18.5,
        "sharpe_ratio": 1.82,
        "max_drawdown": 18.3,
        "calmar_ratio": 1.78,
        "fund_size": 38.2,
        "fee_rate": 1.50,
        "establish_date": "2008-06-19",
        "inst_ratio": 0.35,
    }
    result = engine.score_fund(fund, {
        "all_returns_1y": [10.0, 32.5, 20.0],
        "all_returns_2y": [15.0, 45.2, 25.0],
        "all_returns_3y": [20.0, 68.2, 30.0],
        "all_volatilities": [22.0, 18.5, 25.0],
        "all_sharpes": [0.8, 1.82, 1.0],
        "all_drawdowns": [25.0, 18.3, 30.0],
        "all_calmars": [0.5, 1.78, 0.8],
        "all_sizes": [10.0, 38.2, 60.0],
        "all_fees": [1.50, 1.50, 1.20],
        "all_ages": ["2008-06-19", "2008-06-19", "2010-01-01"],
        "all_inst_ratios": [0.20, 0.35, 0.50],
    })
    assert "total_score" in result
    assert 0 <= result["total_score"] <= 100
    assert "risk_score" in result
    assert "perf_score" in result
    assert "quality_score" in result
