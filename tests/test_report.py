# tests/test_report.py
import pytest
from fund.db import FundDB
from fund.report import ReportCLI


@pytest.fixture
def report_cli():
    db = FundDB(":memory:")
    db.save_funds([
        {
            "code": "110011", "name": "test fund", "fund_type": "混合型",
            "fund_size": 38.2, "fee_rate": 1.50, "establish_date": "2008-06-19",
            "inst_ratio": 0.35, "manager_name": "",
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
    return ReportCLI(db=db, config={"fund_types": ["混合型"]})


def test_report_table(report_cli, capsys):
    report_cli.table(fund_type="混合型", top_n=10)
    captured = capsys.readouterr()
    assert "test fund" in captured.out


def test_report_card(report_cli, capsys):
    report_cli.card(code="110011")
    captured = capsys.readouterr()
    assert "test fund" in captured.out
    assert "87.3" in captured.out
