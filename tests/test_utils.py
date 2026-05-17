# tests/test_utils.py
import os
import tempfile
from fund.utils import load_config, percentile_rank


def test_load_config():
    config_content = """
data:
  db_path: "./test.db"
weights:
  risk_adj: 0.5
"""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
        f.write(config_content)
        tmp_path = f.name

    try:
        config = load_config(tmp_path)
        assert config["data"]["db_path"] == "./test.db"
        assert config["weights"]["risk_adj"] == 0.5
    finally:
        os.unlink(tmp_path)


def test_percentile_rank_highest_is_100():
    values = [1.0, 2.0, 3.0, 4.0, 5.0]
    result = percentile_rank(values, 5.0)
    assert result == 100.0


def test_percentile_rank_lowest_is_0():
    values = [1.0, 2.0, 3.0, 4.0, 5.0]
    result = percentile_rank(values, 1.0)
    assert result == 0.0


def test_percentile_rank_median_is_50():
    values = [1.0, 2.0, 3.0, 4.0, 5.0]
    result = percentile_rank(values, 3.0)
    assert result == 50.0


def test_percentile_rank_reverse():
    """反向排名：值越小排名越高 (用于回撤、波动率)"""
    values = [1.0, 2.0, 3.0, 4.0, 5.0]
    result = percentile_rank(values, 1.0, reverse=True)
    assert result == 100.0
    result = percentile_rank(values, 5.0, reverse=True)
    assert result == 0.0
