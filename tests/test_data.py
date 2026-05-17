# tests/test_data.py
import pytest
from unittest.mock import patch, MagicMock
from fund.data import DataCLI


@pytest.fixture
def data_config():
    return {
        "data": {"db_path": ":memory:", "request_delay": 0.0},
        "fund_types": ["股票型", "混合型", "指数型", "债券型", "货币型"],
    }


@pytest.fixture
def data_cli(data_config):
    return DataCLI(**data_config)


def test_data_cli_init(data_cli):
    assert data_cli.db_path == ":memory:"
    assert len(data_cli.fund_types) == 5


@patch("fund.data.ak.fund_open_fund_rank_em")
def test_fetch_fund_rank(mock_rank, data_cli):
    import pandas as pd
    mock_rank.return_value = pd.DataFrame([
        {
            "基金代码": "110011",
            "基金名称": "易方达中小盘精选",
            "基金类型": "混合型-偏股",
            "近1年": "32.50",
            "近2年": "45.20",
            "近3年": "68.20",
            "基金规模": "38.20",
        }
    ])
    data_cli._fetch_fund_rank("混合型")
    df = data_cli._fetch_fund_rank("混合型")
    assert df is not None
    assert len(df) == 1


def test_normalize_fund_type(data_cli):
    assert data_cli._normalize_fund_type("混合型-偏股") == "混合型"
    assert data_cli._normalize_fund_type("股票型") == "股票型"
    assert data_cli._normalize_fund_type("债券型-纯债") == "债券型"
    assert data_cli._normalize_fund_type("指数型-被动") == "指数型"
    assert data_cli._normalize_fund_type("货币型") == "货币型"
