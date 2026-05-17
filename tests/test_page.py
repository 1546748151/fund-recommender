# tests/test_page.py
import os
import json
import pytest
from fund.db import FundDB
from fund.page import PageBuilder


@pytest.fixture
def page_builder(tmp_path):
    db = FundDB(":memory:")
    db.save_funds([
        {
            "code": "110011", "name": "易方达中小盘", "fund_type": "混合型",
            "fund_size": 38.2, "fee_rate": 1.50, "establish_date": "2008-06-19",
            "inst_ratio": 0.35, "manager_name": "张坤",
            "return_1y": 32.5, "return_2y": 45.2, "return_3y": 68.2,
            "volatility": 18.5, "sharpe_ratio": 1.82, "max_drawdown": 18.3,
            "calmar_ratio": 1.78,
        }
    ])
    db.save_score_snapshot([
        {
            "code": "110011", "date": "2026-05-17", "total_score": 87.3,
            "risk_score": 85.0, "perf_score": 91.0, "quality_score": 82.0,
            "rank_in_type": 1, "fund_type": "混合型",
        }
    ])
    config = {
        "page": {"output_dir": str(tmp_path / "output"), "top_n": 50},
        "fund_types": ["混合型"],
    }
    return PageBuilder(db=db, config=config)


def test_build_creates_index(page_builder):
    page_builder.build()
    index_path = os.path.join(page_builder.output_dir, "index.html")
    assert os.path.exists(index_path)


def test_build_creates_data_json(page_builder):
    page_builder.build()
    data_path = os.path.join(page_builder.output_dir, "data.json")
    assert os.path.exists(data_path)
    with open(data_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    assert len(data["scores"]) == 1
    assert data["scores"][0]["code"] == "110011"


def test_build_creates_detail_page(page_builder):
    page_builder.build()
    detail_path = os.path.join(page_builder.output_dir, "detail.html")
    assert os.path.exists(detail_path)


def test_build_creates_history_page(page_builder):
    page_builder.build()
    history_path = os.path.join(page_builder.output_dir, "history.html")
    assert os.path.exists(history_path)
