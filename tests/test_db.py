# tests/test_db.py
import os
import sqlite3
import pytest
from fund.db import FundDB


@pytest.fixture
def test_db_path(tmp_path):
    return str(tmp_path / "test_fund.db")


@pytest.fixture
def db(test_db_path):
    return FundDB(test_db_path)


def test_db_init_creates_tables(db, test_db_path):
    conn = sqlite3.connect(test_db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
    tables = [row[0] for row in cursor.fetchall()]
    assert "funds" in tables
    assert "fund_nav" in tables
    assert "fund_managers" in tables
    assert "score_snapshots" in tables
    conn.close()


def test_save_funds(db):
    funds_data = [
        {
            "code": "110011",
            "name": "易方达中小盘精选",
            "fund_type": "混合型",
            "fund_size": 38.2,
            "fee_rate": 1.50,
            "establish_date": "2008-06-19",
            "inst_ratio": 0.35,
            "manager_name": "张坤",
        }
    ]
    db.save_funds(funds_data)
    result = db.get_fund_by_code("110011")
    assert result is not None
    assert result["name"] == "易方达中小盘精选"


def test_save_score_snapshot(db):
    scores = [
        {
            "code": "110011",
            "date": "2026-05-17",
            "total_score": 87.3,
            "risk_score": 85.0,
            "perf_score": 91.0,
            "quality_score": 82.0,
            "rank_in_type": 1,
        }
    ]
    db.save_score_snapshot(scores)
    history = db.get_score_history("110011")
    assert len(history) == 1
    assert history[0]["total_score"] == 87.3
