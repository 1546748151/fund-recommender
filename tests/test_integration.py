# tests/test_integration.py
import os
import json
import pytest
from fund.db import FundDB
from fund.score import ScoreEngine
from fund.report import ReportCLI
from fund.page import PageBuilder


def test_full_pipeline(tmp_path):
    """端到端测试：data -> score -> report -> page"""
    db_path = str(tmp_path / "test.db")
    output_dir = str(tmp_path / "output")
    config = {
        "data": {"db_path": db_path, "request_delay": 0},
        "weights": {"risk_adj": 0.45, "performance": 0.35, "fund_quality": 0.20},
        "risk_adj": {"sharpe_ratio": 0.15, "max_drawdown": 0.15, "calmar_ratio": 0.15},
        "performance": {"return_1y": 0.10, "return_2y": 0.10, "return_3y": 0.10, "volatility": 0.05},
        "fund_quality": {"fund_size": 0.05, "fee_rate": 0.05, "fund_age": 0.05, "inst_ratio": 0.05},
        "score": {"min_fund_age_years": 3, "optimal_size_min": 1, "optimal_size_max": 50,
                  "optimal_inst_min": 0.20, "optimal_inst_max": 0.60},
        "page": {"output_dir": output_dir, "top_n": 10},
        "fund_types": ["股票型", "混合型", "指数型", "债券型", "货币型"],
    }

    db = FundDB(db_path)
    assert db is not None

    # Insert sample data covering multiple fund types
    db.save_funds([
        {
            "code": "000001", "name": "基金A", "fund_type": "混合型",
            "fund_size": 30.0, "fee_rate": 1.20, "establish_date": "2015-01-01",
            "inst_ratio": 0.40, "manager_name": "经理A",
            "return_1y": 25.0, "return_2y": 40.0, "return_3y": 60.0,
            "volatility": 16.0, "sharpe_ratio": 1.80, "max_drawdown": 15.0,
            "calmar_ratio": 1.70,
        },
        {
            "code": "000002", "name": "基金B", "fund_type": "混合型",
            "fund_size": 15.0, "fee_rate": 1.50, "establish_date": "2018-06-01",
            "inst_ratio": 0.25, "manager_name": "经理B",
            "return_1y": 18.0, "return_2y": 30.0, "return_3y": 45.0,
            "volatility": 20.0, "sharpe_ratio": 1.20, "max_drawdown": 22.0,
            "calmar_ratio": 0.90,
        },
        {
            "code": "000003", "name": "基金C", "fund_type": "债券型",
            "fund_size": 80.0, "fee_rate": 0.60, "establish_date": "2010-03-15",
            "inst_ratio": 0.55, "manager_name": "经理C",
            "return_1y": 6.0, "return_2y": 10.0, "return_3y": 15.0,
            "volatility": 3.0, "sharpe_ratio": 2.50, "max_drawdown": 2.0,
            "calmar_ratio": 3.00,
        },
    ])

    # Step 2: Score
    engine = ScoreEngine(db=db, config=config)
    scores = engine.run(date_str="2026-05-17")
    assert len(scores) > 0

    # Fund A should score higher than Fund B (better metrics in all dimensions)
    score_a = next(s for s in scores if s["code"] == "000001")
    score_b = next(s for s in scores if s["code"] == "000002")
    assert score_a["total_score"] > score_b["total_score"], \
        f"Fund A ({score_a['total_score']}) should outscore Fund B ({score_b['total_score']})"

    # Fund C (bond) should NOT be compared against Fund A (mixed) - they're in different types
    score_c = next(s for s in scores if s["code"] == "000003")
    assert score_c["fund_type"] == "债券型"

    # Step 3: Report (just verify no crash)
    report = ReportCLI(db=db, config=config)
    report.table()
    report.card("000001")

    # Step 4: Page generation
    page = PageBuilder(db=db, config=config)
    page.build()

    # Verify all output files exist
    assert os.path.exists(os.path.join(output_dir, "index.html"))
    assert os.path.exists(os.path.join(output_dir, "data.json"))
    assert os.path.exists(os.path.join(output_dir, "detail.html"))
    assert os.path.exists(os.path.join(output_dir, "history.html"))

    # Verify data.json structure
    with open(os.path.join(output_dir, "data.json"), "r", encoding="utf-8") as f:
        jdata = json.load(f)
    assert jdata["date"] == "2026-05-17"
    assert len(jdata["scores"]) == 3
    assert jdata["total_funds"] == 3

    # Verify index.html contains key elements
    with open(os.path.join(output_dir, "index.html"), "r", encoding="utf-8") as f:
        index_html = f.read()
    assert "FundRecommender" in index_html
    assert "echarts" in index_html
    assert "基金A" in index_html
    assert "tableBody" in index_html

    # Verify detail.html loads
    with open(os.path.join(output_dir, "detail.html"), "r", encoding="utf-8") as f:
        detail_html = f.read()
    assert "data.json" in detail_html
