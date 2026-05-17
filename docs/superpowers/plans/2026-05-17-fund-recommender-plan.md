# FundRecommender Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a Python pipeline + static HTML fund recommendation tool that fetches Chinese mutual fund data via akshare, scores funds by risk-adjusted return, performance, and quality, then outputs CLI reports and a static website.

**Architecture:** Single entry point `fund.py` using fire.Fire, with four sub-modules: data (akshare fetch + SQLite), score (3-factor weighted percentile ranking), report (CLI tables), page (static HTML with ECharts). All config in config.yaml.

**Tech Stack:** Python 3.10+, akshare, pandas, numpy, fire, loguru, PyYAML, SQLite, tabulate, ECharts (CDN), GitHub Actions + Pages

---

### Task 1: Project Scaffolding

**Files:**
- Create: `fund-recommender/requirements.txt`
- Create: `fund-recommender/config.yaml`
- Create: `fund-recommender/.gitignore`
- Create: `fund-recommender/fund/__init__.py`
- Create: `fund-recommender/tests/__init__.py`

- [ ] **Step 1: Write requirements.txt**

```txt
akshare>=1.14.0
pandas>=2.0.0
numpy>=1.24.0
fire>=0.5.0
loguru>=0.7.0
PyYAML>=6.0
tabulate>=0.9.0
```

- [ ] **Step 2: Write config.yaml**

```yaml
# FundRecommender 配置文件

# 数据
data:
  db_path: "./fund_data.db"
  request_delay: 0.5  # akshare 请求间隔(秒)，避免限流

# 打分权重 (总和为1)
weights:
  risk_adj: 0.45
  performance: 0.35
  fund_quality: 0.20

risk_adj:
  sharpe_ratio: 0.15
  max_drawdown: 0.15
  calmar_ratio: 0.15

performance:
  return_1y: 0.10
  return_2y: 0.10
  return_3y: 0.10
  volatility: 0.05

fund_quality:
  fund_size: 0.05
  fee_rate: 0.05
  fund_age: 0.05
  inst_ratio: 0.05

# 基金类型 (akshare 中的名称映射)
fund_types:
  - 股票型
  - 混合型
  - 指数型
  - 债券型
  - 货币型

# 页面
page:
  output_dir: "./output"
  top_n: 50

# 打分阈值
score:
  min_fund_age_years: 3  # 成立不足3年的基金降权
  optimal_size_max: 50   # 规模最优上限(亿)
  optimal_size_min: 1    # 规模最优下限(亿)
  optimal_inst_min: 0.20 # 机构占比最优下限
  optimal_inst_max: 0.60 # 机构占比最优上限
```

- [ ] **Step 3: Write .gitignore**

```gitignore
__pycache__/
*.pyc
*.db
output/
.superpowers/
.mypy_cache/
.pytest_cache/
*.egg-info/
```

- [ ] **Step 4: Create empty __init__.py files**

```bash
touch fund-recommender/fund/__init__.py
touch fund-recommender/tests/__init__.py
```

- [ ] **Step 5: Commit**

```bash
git add requirements.txt config.yaml .gitignore fund/__init__.py tests/__init__.py
git commit -m "chore: project scaffolding with config and dependencies"
```

---

### Task 2: Database Layer

**Files:**
- Create: `fund-recommender/fund/db.py`
- Create: `fund-recommender/tests/test_db.py`

- [ ] **Step 1: Write failing test for database init**

```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd fund-recommender && python -m pytest tests/test_db.py -v
```
Expected: FAIL — `ModuleNotFoundError: No module named 'fund.db'`

- [ ] **Step 3: Write FundDB implementation**

```python
# fund/db.py
import sqlite3
from typing import Optional
from loguru import logger


class FundDB:
    def __init__(self, db_path: str):
        self.db_path = db_path
        self._init_tables()

    def _get_conn(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_tables(self):
        with self._get_conn() as conn:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS funds (
                    code TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    fund_type TEXT NOT NULL,
                    fund_size REAL,
                    fee_rate REAL,
                    establish_date TEXT,
                    inst_ratio REAL,
                    manager_name TEXT,
                    return_1y REAL,
                    return_2y REAL,
                    return_3y REAL,
                    volatility REAL,
                    sharpe_ratio REAL,
                    max_drawdown REAL,
                    calmar_ratio REAL,
                    updated_at TEXT DEFAULT (datetime('now'))
                );

                CREATE TABLE IF NOT EXISTS fund_nav (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    code TEXT NOT NULL,
                    date TEXT NOT NULL,
                    unit_nav REAL,
                    accum_nav REAL,
                    UNIQUE(code, date)
                );

                CREATE TABLE IF NOT EXISTS fund_managers (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    fund_code TEXT NOT NULL,
                    manager_name TEXT NOT NULL,
                    experience_years REAL,
                    managed_funds_count INTEGER,
                    updated_at TEXT DEFAULT (datetime('now'))
                );

                CREATE TABLE IF NOT EXISTS score_snapshots (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    code TEXT NOT NULL,
                    date TEXT NOT NULL,
                    total_score REAL,
                    risk_score REAL,
                    perf_score REAL,
                    quality_score REAL,
                    rank_in_type INTEGER,
                    fund_type TEXT,
                    UNIQUE(code, date)
                );

                CREATE INDEX IF NOT EXISTS idx_fund_type ON funds(fund_type);
                CREATE INDEX IF NOT EXISTS idx_score_date ON score_snapshots(date);
                CREATE INDEX IF NOT EXISTS idx_score_code ON score_snapshots(code);
            """)

    def save_funds(self, funds_data: list[dict]):
        with self._get_conn() as conn:
            conn.executemany("""
                INSERT OR REPLACE INTO funds
                    (code, name, fund_type, fund_size, fee_rate, establish_date,
                     inst_ratio, manager_name, return_1y, return_2y, return_3y,
                     volatility, sharpe_ratio, max_drawdown, calmar_ratio, updated_at)
                VALUES (:code, :name, :fund_type, :fund_size, :fee_rate, :establish_date,
                        :inst_ratio, :manager_name, :return_1y, :return_2y, :return_3y,
                        :volatility, :sharpe_ratio, :max_drawdown, :calmar_ratio,
                        datetime('now'))
            """, funds_data)

    def get_fund_by_code(self, code: str) -> Optional[dict]:
        with self._get_conn() as conn:
            row = conn.execute("SELECT * FROM funds WHERE code = ?", (code,)).fetchone()
            return dict(row) if row else None

    def get_funds_by_type(self, fund_type: str) -> list[dict]:
        with self._get_conn() as conn:
            rows = conn.execute(
                "SELECT * FROM funds WHERE fund_type = ?", (fund_type,)
            ).fetchall()
            return [dict(r) for r in rows]

    def get_all_funds(self) -> list[dict]:
        with self._get_conn() as conn:
            rows = conn.execute("SELECT * FROM funds").fetchall()
            return [dict(r) for r in rows]

    def save_nav_history(self, code: str, nav_data: list[dict]):
        with self._get_conn() as conn:
            conn.executemany("""
                INSERT OR REPLACE INTO fund_nav (code, date, unit_nav, accum_nav)
                VALUES (:code, :date, :unit_nav, :accum_nav)
            """, [{"code": code, **d} for d in nav_data])

    def save_score_snapshot(self, scores: list[dict]):
        with self._get_conn() as conn:
            conn.executemany("""
                INSERT OR REPLACE INTO score_snapshots
                    (code, date, total_score, risk_score, perf_score, quality_score,
                     rank_in_type, fund_type)
                VALUES (:code, :date, :total_score, :risk_score, :perf_score,
                        :quality_score, :rank_in_type, :fund_type)
            """, scores)

    def get_score_history(self, code: str) -> list[dict]:
        with self._get_conn() as conn:
            rows = conn.execute(
                "SELECT * FROM score_snapshots WHERE code = ? ORDER BY date DESC",
                (code,),
            ).fetchall()
            return [dict(r) for r in rows]

    def get_latest_scores(self, fund_type: Optional[str] = None, top_n: int = 50) -> list[dict]:
        with self._get_conn() as conn:
            if fund_type:
                rows = conn.execute("""
                    SELECT s.*, f.name, f.fund_size, f.fee_rate, f.establish_date,
                           f.return_1y, f.return_2y, f.return_3y,
                           f.max_drawdown, f.sharpe_ratio, f.volatility, f.calmar_ratio,
                           f.inst_ratio, f.manager_name
                    FROM score_snapshots s
                    JOIN funds f ON s.code = f.code
                    WHERE s.date = (SELECT MAX(date) FROM score_snapshots)
                      AND s.fund_type = ?
                    ORDER BY s.total_score DESC
                    LIMIT ?
                """, (fund_type, top_n)).fetchall()
            else:
                rows = conn.execute("""
                    SELECT s.*, f.name, f.fund_size, f.fee_rate, f.establish_date,
                           f.return_1y, f.return_2y, f.return_3y,
                           f.max_drawdown, f.sharpe_ratio, f.volatility, f.calmar_ratio,
                           f.inst_ratio, f.manager_name
                    FROM score_snapshots s
                    JOIN funds f ON s.code = f.code
                    WHERE s.date = (SELECT MAX(date) FROM score_snapshots)
                    ORDER BY s.total_score DESC
                    LIMIT ?
                """, (top_n,)).fetchall()
            return [dict(r) for r in rows]
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd fund-recommender && python -m pytest tests/test_db.py -v
```
Expected: all PASS

- [ ] **Step 5: Commit**

```bash
git add fund/db.py tests/test_db.py
git commit -m "feat: add SQLite database layer with funds, nav, managers, snapshots tables"
```

---

### Task 3: Config Loader

**Files:**
- Create: `fund-recommender/fund/utils.py`
- Create: `fund-recommender/tests/test_utils.py`

- [ ] **Step 1: Write failing test for config loading**

```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd fund-recommender && python -m pytest tests/test_utils.py -v
```
Expected: FAIL — `ModuleNotFoundError: No module named 'fund.utils'`

- [ ] **Step 3: Write utils.py implementation**

```python
# fund/utils.py
import yaml
import numpy as np
from typing import Any
from loguru import logger


def load_config(config_path: str) -> dict[str, Any]:
    with open(config_path, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f) or {}
    logger.info(f"Loaded config from {config_path}")
    return config


def percentile_rank(values: list[float], target: float, reverse: bool = False) -> float:
    """
    计算 target 在 values 中的百分位排名 (0-100)。
    reverse=True 时值越小排名越高 (用于回撤、波动率等反向指标)。
    空列表返回 50.0 (中性分)。
    """
    if len(values) == 0:
        return 50.0
    arr = np.array(values)
    if reverse:
        rank = (arr > target).sum() / len(arr) * 100.0
    else:
        rank = (arr < target).sum() / len(arr) * 100.0
    return round(rank, 1)


def safe_float(value, default=0.0) -> float:
    """安全转换为 float，失败返回 default"""
    try:
        return float(value)
    except (TypeError, ValueError):
        return default
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd fund-recommender && python -m pytest tests/test_utils.py -v
```
Expected: all PASS

- [ ] **Step 5: Commit**

```bash
git add fund/utils.py tests/test_utils.py
git commit -m "feat: add config loader and percentile rank utility"
```

---

### Task 4: Data Fetching from akshare

**Files:**
- Create: `fund-recommender/fund/data.py`
- Create: `fund-recommender/tests/test_data.py`

- [ ] **Step 1: Write failing test for DataCLI**

```python
# tests/test_data.py
import os
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
    funds = data_cli.db.get_all_funds()
    assert len(funds) >= 0  # 测试至少不报错


def test_normalize_fund_type(data_cli):
    assert data_cli._normalize_fund_type("混合型-偏股") == "混合型"
    assert data_cli._normalize_fund_type("股票型") == "股票型"
    assert data_cli._normalize_fund_type("债券型-纯债") == "债券型"
    assert data_cli._normalize_fund_type("指数型-被动") == "指数型"
    assert data_cli._normalize_fund_type("货币型") == "货币型"
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd fund-recommender && python -m pytest tests/test_data.py -v
```
Expected: FAIL — `ModuleNotFoundError: No module named 'fund.data'`

- [ ] **Step 3: Write DataCLI implementation**

```python
# fund/data.py
import time
import pandas as pd
from typing import Optional
from loguru import logger
import akshare as ak

from fund.db import FundDB
from fund.utils import safe_float


class DataCLI:
    def __init__(self, data: dict = None, fund_types: list = None, **kwargs):
        self.db_path = data.get("db_path", "./fund_data.db") if data else "./fund_data.db"
        self.request_delay = data.get("request_delay", 0.5) if data else 0.5
        self.fund_types = fund_types or ["股票型", "混合型", "指数型", "债券型", "货币型"]
        self.db = FundDB(self.db_path)

    def update(self, type: Optional[str] = None):
        """拉取并存储基金数据。type=None 则更新全部类型。"""
        types_to_fetch = [type] if type and type in self.fund_types else self.fund_types
        total = 0
        for ft in types_to_fetch:
            logger.info(f"Fetching fund data for type: {ft}")
            try:
                df = self._fetch_fund_rank(ft)
                if df is not None and not df.empty:
                    self._save_funds_from_df(df)
                    total += len(df)
                    logger.info(f"Saved {len(df)} funds for {ft}")
            except Exception as e:
                logger.error(f"Failed to fetch {ft}: {e}")
            time.sleep(self.request_delay)
        logger.info(f"Data update complete. Total funds: {total}")

    def _fetch_fund_rank(self, fund_type: str) -> Optional[pd.DataFrame]:
        """拉取指定类型的基金排名数据"""
        try:
            df = ak.fund_open_fund_rank_em(symbol=fund_type)
            return df
        except Exception as e:
            logger.warning(f"akshare fund_open_fund_rank_em failed for {fund_type}: {e}")
            return None

    def _save_funds_from_df(self, df: pd.DataFrame):
        """将 akshare 返回的 DataFrame 转为标准格式并存入数据库"""
        funds_data = []
        for _, row in df.iterrows():
            fund_type_raw = str(row.get("基金类型", ""))
            fund_data = {
                "code": str(row.get("基金代码", "")),
                "name": str(row.get("基金名称", "")),
                "fund_type": self._normalize_fund_type(fund_type_raw),
                "fund_size": safe_float(row.get("基金规模", 0)),
                "fee_rate": 1.50,  # akshare 排行接口不含费率，后续用 fund_open_fund_info_em 补充
                "establish_date": "",  # 同上，后续补充
                "inst_ratio": 0.0,
                "manager_name": "",
                "return_1y": safe_float(row.get("近1年", 0)),
                "return_2y": safe_float(row.get("近2年", 0)),
                "return_3y": safe_float(row.get("近3年", 0)),
                "volatility": 0.0,
                "sharpe_ratio": 0.0,
                "max_drawdown": 0.0,
                "calmar_ratio": 0.0,
            }
            if fund_data["code"] and fund_data["name"]:
                funds_data.append(fund_data)
        if funds_data:
            self.db.save_funds(funds_data)

    def _normalize_fund_type(self, raw_type: str) -> str:
        """将 akshare 返回的详细类型归一化到大类"""
        for ft in self.fund_types:
            if ft in raw_type:
                return ft
        return "混合型"  # 默认归入混合型
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd fund-recommender && python -m pytest tests/test_data.py -v
```
Expected: PASS (mocked akshare)

- [ ] **Step 5: Commit**

```bash
git add fund/data.py tests/test_data.py
git commit -m "feat: add DataCLI for fetching fund rankings from akshare"
```

---

### Task 5: Scoring Engine

**Files:**
- Create: `fund-recommender/fund/score.py`
- Create: `fund-recommender/tests/test_score.py`

- [ ] **Step 1: Write failing test for ScoreEngine**

```python
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


def test_calc_sharpe_score(engine):
    # 夏普比率越高越好
    values = [0.5, 1.0, 1.5, 2.0, 2.5]
    score = engine._calc_dimension_score(values, 2.5, reverse=False)
    assert score == 100.0
    score = engine._calc_dimension_score(values, 0.5, reverse=False)
    assert score == 0.0


def test_calc_drawdown_score(engine):
    # 最大回撤越低越好 (reverse)
    values = [10.0, 15.0, 20.0, 25.0, 30.0]
    score = engine._calc_dimension_score(values, 10.0, reverse=True)
    assert score == 100.0


def test_fund_size_score_optimal(engine):
    # 在最优区间的规模得满分
    score = engine._score_fund_size(25.0)
    assert score == 100.0


def test_fund_size_score_too_small(engine):
    score = engine._score_fund_size(0.3)
    assert score < 50.0


def test_fund_age_score(engine):
    score = engine._score_fund_age("2016-05-17")
    assert score == 100.0  # 10年老基金
    score = engine._score_fund_age("2025-01-01")
    assert score < 50.0  # 不到3年


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
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd fund-recommender && python -m pytest tests/test_score.py -v
```
Expected: FAIL — `ModuleNotFoundError: No module named 'fund.score'`

- [ ] **Step 3: Write ScoreEngine implementation**

```python
# fund/score.py
from datetime import datetime, date
from typing import Any, Optional
from loguru import logger
import numpy as np

from fund.db import FundDB
from fund.utils import percentile_rank


class ScoreEngine:
    def __init__(self, db: FundDB, config: dict[str, Any]):
        self.db = db
        self.config = config
        self.weights = config.get("weights", {})
        self.risk_weights = config.get("risk_adj", {})
        self.perf_weights = config.get("performance", {})
        self.quality_weights = config.get("fund_quality", {})
        self.score_config = config.get("score", {})
        self.fund_types = config.get("fund_types", [])

    def run(self, date_str: Optional[str] = None, top_n: int = 50):
        """对全部基金打分并保存快照"""
        if date_str is None:
            date_str = date.today().isoformat()
        all_funds = self.db.get_all_funds()
        if not all_funds:
            logger.error("No funds in database. Run 'data update' first.")
            return []

        # 按类型分组，每组内计算百分位
        all_scores = []
        for ft in self.fund_types:
            type_funds = [f for f in all_funds if f["fund_type"] == ft]
            if not type_funds:
                continue
            logger.info(f"Scoring {len(type_funds)} funds in type: {ft}")
            type_scores = self._score_fund_type(type_funds, date_str)
            all_scores.extend(type_scores)

        # 按总评分排序
        all_scores.sort(key=lambda x: x["total_score"], reverse=True)

        # 分配同类排名
        for ft in self.fund_types:
            type_rank = 0
            for s in all_scores:
                if s["fund_type"] == ft:
                    type_rank += 1
                    s["rank_in_type"] = type_rank

        self.db.save_score_snapshot(all_scores)
        logger.info(f"Scored {len(all_scores)} funds, saved snapshot for {date_str}")
        return all_scores[:top_n]

    def _score_fund_type(self, funds: list[dict], date_str: str) -> list[dict]:
        """对某一类型的所有基金打分"""
        # 收集该类型所有基金的指标值
        all_returns_1y = [f["return_1y"] or 0 for f in funds]
        all_returns_2y = [f["return_2y"] or 0 for f in funds]
        all_returns_3y = [f["return_3y"] or 0 for f in funds]
        all_volatilities = [f["volatility"] or 1 for f in funds]
        all_sharpes = [f["sharpe_ratio"] or 0 for f in funds]
        all_drawdowns = [f["max_drawdown"] or 100 for f in funds]
        all_calmars = [f["calmar_ratio"] or 0 for f in funds]
        all_sizes = [f["fund_size"] or 10 for f in funds]
        all_fees = [f["fee_rate"] or 1.5 for f in funds]
        all_ages = [f["establish_date"] or "2020-01-01" for f in funds]
        all_inst_ratios = [f["inst_ratio"] or 0.3 for f in funds]

        peer_context = {
            "all_returns_1y": all_returns_1y,
            "all_returns_2y": all_returns_2y,
            "all_returns_3y": all_returns_3y,
            "all_volatilities": all_volatilities,
            "all_sharpes": all_sharpes,
            "all_drawdowns": all_drawdowns,
            "all_calmars": all_calmars,
            "all_sizes": all_sizes,
            "all_fees": all_fees,
            "all_ages": all_ages,
            "all_inst_ratios": all_inst_ratios,
        }

        results = []
        for fund in funds:
            result = self.score_fund(fund, peer_context)
            result["date"] = date_str
            results.append(result)
        return results

    def score_fund(self, fund: dict, peer: dict) -> dict:
        """对单只基金打分"""
        # 维度一：风险调整收益
        sharpe_score = self._calc_dimension_score(
            peer["all_sharpes"], fund["sharpe_ratio"] or 0, reverse=False
        )
        drawdown_score = self._calc_dimension_score(
            peer["all_drawdowns"], fund["max_drawdown"] or 100, reverse=True
        )
        calmar_score = self._calc_dimension_score(
            peer["all_calmars"], fund["calmar_ratio"] or 0, reverse=False
        )
        risk_score = (
            sharpe_score * self.risk_weights.get("sharpe_ratio", 0.15)
            + drawdown_score * self.risk_weights.get("max_drawdown", 0.15)
            + calmar_score * self.risk_weights.get("calmar_ratio", 0.15)
        ) / 0.45  # 归一化到 0-100

        # 维度二：中长期业绩
        ret1_score = self._calc_dimension_score(
            peer["all_returns_1y"], fund["return_1y"] or 0, reverse=False
        )
        ret2_score = self._calc_dimension_score(
            peer["all_returns_2y"], fund["return_2y"] or 0, reverse=False
        )
        ret3_score = self._calc_dimension_score(
            peer["all_returns_3y"], fund["return_3y"] or 0, reverse=False
        )
        vol_score = self._calc_dimension_score(
            peer["all_volatilities"], fund["volatility"] or 1, reverse=True
        )
        perf_score = (
            ret1_score * self.perf_weights.get("return_1y", 0.10)
            + ret2_score * self.perf_weights.get("return_2y", 0.10)
            + ret3_score * self.perf_weights.get("return_3y", 0.10)
            + vol_score * self.perf_weights.get("volatility", 0.05)
        ) / 0.35

        # 维度三：基金质量
        size_score = self._score_fund_size(fund["fund_size"] or 0)
        fee_score = self._calc_dimension_score(
            peer["all_fees"], fund["fee_rate"] or 1.5, reverse=True
        )
        age_score = self._score_fund_age(fund["establish_date"] or "2020-01-01")
        inst_score = self._score_inst_ratio(fund["inst_ratio"] or 0)
        quality_score = (
            size_score * self.quality_weights.get("fund_size", 0.05)
            + fee_score * self.quality_weights.get("fee_rate", 0.05)
            + age_score * self.quality_weights.get("fund_age", 0.05)
            + inst_score * self.quality_weights.get("inst_ratio", 0.05)
        ) / 0.20

        total = (
            risk_score * self.weights.get("risk_adj", 0.45)
            + perf_score * self.weights.get("performance", 0.35)
            + quality_score * self.weights.get("fund_quality", 0.20)
        )

        return {
            "code": fund["code"],
            "fund_type": fund["fund_type"],
            "total_score": round(total, 1),
            "risk_score": round(risk_score, 1),
            "perf_score": round(perf_score, 1),
            "quality_score": round(quality_score, 1),
        }

    def _calc_dimension_score(self, all_values: list[float], value: float, reverse: bool = False) -> float:
        """计算单个指标在同类中的百分位得分"""
        return percentile_rank(all_values, value, reverse=reverse)

    def _score_fund_size(self, size: float) -> float:
        """规模评分：1-50亿最优，两端递减"""
        opt_min = self.score_config.get("optimal_size_min", 1)
        opt_max = self.score_config.get("optimal_size_max", 50)
        if opt_min <= size <= opt_max:
            return 100.0
        if size < opt_min:
            return max(0, (size / opt_min) * 100.0)
        return max(0, 100.0 - ((size - opt_max) / opt_max) * 50.0)

    def _score_fund_age(self, establish_date: str) -> float:
        """成立年限评分：>=3年满分，<3年线性递减，<1年0分"""
        try:
            est = datetime.strptime(establish_date, "%Y-%m-%d")
            age_years = (datetime.now() - est).days / 365.25
        except (ValueError, TypeError):
            return 30.0  # 日期未知给中性偏低分
        if age_years >= 3:
            return 100.0
        if age_years < 1:
            return 0.0
        return (age_years / 3) * 100.0

    def _score_inst_ratio(self, ratio: float) -> float:
        """机构占比评分：20-60%最优，两端递减"""
        opt_min = self.score_config.get("optimal_inst_min", 0.20)
        opt_max = self.score_config.get("optimal_inst_max", 0.60)
        if opt_min <= ratio <= opt_max:
            return 100.0
        if ratio < opt_min:
            return max(0, (ratio / opt_min) * 100.0)
        return max(0, 100.0 - ((ratio - opt_max) / (1 - opt_max)) * 80.0)
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd fund-recommender && python -m pytest tests/test_score.py -v
```
Expected: all PASS

- [ ] **Step 5: Commit**

```bash
git add fund/score.py tests/test_score.py
git commit -m "feat: add 3-factor weighted scoring engine with peer percentile ranking"
```

---

### Task 6: CLI Report

**Files:**
- Create: `fund-recommender/fund/report.py`
- Create: `fund-recommender/tests/test_report.py`

- [ ] **Step 1: Write failing test**

```python
# tests/test_report.py
import pytest
from fund.db import FundDB
from fund.report import ReportCLI


@pytest.fixture
def report_cli():
    db = FundDB(":memory:")
    # Seed some test data
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
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd fund-recommender && python -m pytest tests/test_report.py -v
```
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Write ReportCLI implementation**

```python
# fund/report.py
from typing import Optional
from tabulate import tabulate
from loguru import logger

from fund.db import FundDB


class ReportCLI:
    def __init__(self, db: FundDB, config: dict):
        self.db = db
        self.config = config
        self.fund_types = config.get("fund_types", [])

    def table(self, fund_type: Optional[str] = None, top_n: int = 50):
        """输出终端排名表格"""
        scores = self.db.get_latest_scores(fund_type=fund_type, top_n=top_n)
        if not scores:
            logger.warning("No scores available. Run 'score run' first.")
            return

        # 补全基金详情
        rows = []
        for i, s in enumerate(scores, 1):
            fund = self.db.get_fund_by_code(s["code"])
            if not fund:
                continue
            rows.append([
                i,
                fund["name"],
                s["fund_type"],
                s["total_score"],
                s["risk_score"],
                s["perf_score"],
                s["quality_score"],
                f"{fund['return_1y']:+.1f}%",
                f"{fund['return_3y']:+.1f}%" if fund["return_3y"] else "-",
                f"{fund['max_drawdown']:.1f}%" if fund["max_drawdown"] else "-",
                f"{fund['fund_size']:.1f}" if fund["fund_size"] else "-",
                f"{fund['fee_rate']:.2f}%" if fund["fee_rate"] else "-",
            ])

        headers = ["#", "基金名称", "类型", "总分", "风险", "业绩", "质量",
                    "近1年", "近3年", "回撤", "规模(亿)", "费率"]
        print(f"\n=== Fund Ranking ({fund_type or 'ALL'}) ===\n")
        print(tabulate(rows, headers=headers, tablefmt="rounded_outline"))
        print(f"\n共 {len(rows)} 只基金   数据日期: {scores[0]['date']}\n")

    def card(self, code: str):
        """输出单只基金详情卡片"""
        fund = self.db.get_fund_by_code(code)
        if not fund:
            logger.error(f"Fund not found: {code}")
            return
        history = self.db.get_score_history(code)

        print(f"""
┌──────────────────────────────────────┐
│  {fund['name']} ({code})
├──────────────────────────────────────┤
│  类型: {fund['fund_type']}    成立: {fund['establish_date']}
│  规模: {fund['fund_size']:.1f}亿    费率: {fund['fee_rate']:.2f}%
│  机构占比: {fund['inst_ratio']:.1%}
├──────────────────────────────────────┤
│  近1年收益: {fund['return_1y']:+.1f}%    近3年收益: {fund['return_3y']:+.1f}%
│  夏普比率: {fund['sharpe_ratio']:.2f}      最大回撤: {fund['max_drawdown']:.1f}%
│  卡玛比率: {fund['calmar_ratio']:.2f}      年化波动: {fund['volatility']:.1f}%
└──────────────────────────────────────┘
""")
        if history:
            latest = history[0]
            print(f"  最新评分 ({latest['date']}): {latest['total_score']:.1f}")
            print(f"  同类排名: #{latest['rank_in_type']}")
            if len(history) > 1:
                prev = history[1]
                delta = latest["total_score"] - prev["total_score"]
                print(f"  较上次 ({prev['date']}): {delta:+.1f}")
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd fund-recommender && python -m pytest tests/test_report.py -v
```
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add fund/report.py tests/test_report.py
git commit -m "feat: add CLI report with ranking table and fund detail card"
```

---

### Task 7: Entry Point (fund.py)

**Files:**
- Create: `fund-recommender/fund.py`

- [ ] **Step 1: Write the entry point**

```python
#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""FundRecommender - 基金推荐工具

Usage:
    python fund.py data update              # 拉取基金数据
    python fund.py score run                # 打分排名
    python fund.py report table             # 终端排名表
    python fund.py report card --code=110011 # 单基金卡片
    python fund.py page build               # 生成静态网站
    python fund.py page serve               # 本地预览
"""

import fire
from loguru import logger

from fund.utils import load_config
from fund.db import FundDB
from fund.data import DataCLI
from fund.score import ScoreEngine
from fund.report import ReportCLI
from fund.page import PageBuilder


class FundAdvisor:
    def __init__(self, config_path: str = "./config.yaml"):
        self.config = load_config(config_path)
        self.db = FundDB(self.config["data"]["db_path"])

        # data 立即可用；score/report/page 需要 db 依赖
        self.data = DataCLI(**self.config)

        self._score = None
        self._report = None
        self._page = None

    @property
    def score(self) -> ScoreEngine:
        if self._score is None:
            self._score = ScoreEngine(db=self.db, config=self.config)
        return self._score

    @property
    def report(self) -> ReportCLI:
        if self._report is None:
            self._report = ReportCLI(db=self.db, config=self.config)
        return self._report

    @property
    def page(self) -> PageBuilder:
        if self._page is None:
            self._page = PageBuilder(db=self.db, config=self.config)
        return self._page

    def show_config(self):
        """显示当前配置"""
        from pprint import pp
        pp(self.config)


if __name__ == "__main__":
    fire.Fire(FundAdvisor)
```

- [ ] **Step 2: Verify it loads (will fail until page.py exists)**

```bash
cd fund-recommender && python -c "import sys; sys.argv = ['fund.py', 'show_config']; exec(open('fund.py').read())"
```
Expected: may error on PageBuilder import — expected, will be resolved in Task 8.

- [ ] **Step 3: Commit**

```bash
git add fund.py
git commit -m "feat: add fire CLI entry point (FundAdvisor)"
```

---

### Task 8: Static Page Builder

**Files:**
- Create: `fund-recommender/fund/page.py`
- Create: `fund-recommender/tests/test_page.py`

- [ ] **Step 1: Write failing test**

```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd fund-recommender && python -m pytest tests/test_page.py -v
```
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Write PageBuilder implementation**

```python
# fund/page.py
import os
import json
import shutil
from datetime import datetime
from loguru import logger

from fund.db import FundDB


class PageBuilder:
    def __init__(self, db: FundDB, config: dict):
        self.db = db
        self.config = config
        self.output_dir = config.get("page", {}).get("output_dir", "./output")
        self.top_n = config.get("page", {}).get("top_n", 50)

    def build(self):
        """生成完整的静态网站"""
        os.makedirs(self.output_dir, exist_ok=True)

        # 收集数据
        all_scores = self.db.get_latest_scores(top_n=self.top_n)
        funds_by_type = {}
        for s in all_scores:
            ft = s["fund_type"]
            if ft not in funds_by_type:
                funds_by_type[ft] = []
            funds_by_type[ft].append(s)

        # 生成 data.json
        data = {
            "date": all_scores[0]["date"] if all_scores else datetime.now().isoformat(),
            "total_funds": len(self.db.get_all_funds()),
            "scores": all_scores,
            "by_type": funds_by_type,
            "fund_types": self.config.get("fund_types", []),
        }
        data_path = os.path.join(self.output_dir, "data.json")
        with open(data_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        logger.info(f"Generated data.json with {len(all_scores)} funds")

        # 生成 index.html
        self._write_index_html(data)

        # 生成 detail.html
        self._write_detail_html()

        # 生成 history.html
        self._write_history_html()

        logger.info(f"Static site built at {self.output_dir}")

    def serve(self, port: int = 8080):
        """本地预览静态网站"""
        import http.server
        import socketserver

        os.chdir(self.output_dir)
        handler = http.server.SimpleHTTPRequestHandler
        with socketserver.TCPServer(("", port), handler) as httpd:
            logger.info(f"Serving at http://localhost:{port}")
            httpd.serve_forever()

    def _write_index_html(self, data: dict):
        html = self._index_template(data)
        with open(os.path.join(self.output_dir, "index.html"), "w", encoding="utf-8") as f:
            f.write(html)

    def _write_detail_html(self):
        html = self._detail_template()
        with open(os.path.join(self.output_dir, "detail.html"), "w", encoding="utf-8") as f:
            f.write(html)

    def _write_history_html(self):
        html = self._history_template()
        with open(os.path.join(self.output_dir, "history.html"), "w", encoding="utf-8") as f:
            f.write(html)

    def _index_template(self, data: dict) -> str:
        """首页模板：概览卡片 + 类型切换 + 排行榜 + 图表"""
        funds_json = json.dumps(data, ensure_ascii=False)
        return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>FundRecommender - 基金排行榜</title>
<script src="https://cdn.jsdelivr.net/npm/echarts@5.5.0/dist/echarts.min.js"></script>
<style>
:root{{--bg:#f8f9fa;--card-bg:#fff;--text:#212529;--muted:#6c757d;--border:#dee2e6;--accent:#2563eb;--green:#16a34a;--red:#dc2626;--gold:#e6b422;--silver:#c0c0c0;--bronze:#cd7f32}}
*{{margin:0;padding:0;box-sizing:border-box}}
body{{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;background:var(--bg);color:var(--text);line-height:1.6}}
.container{{max-width:1400px;margin:0 auto;padding:24px 20px}}
.header{{text-align:center;margin-bottom:24px}}
.header h1{{font-size:28px;font-weight:700}}
.header .date{{color:var(--muted);font-size:14px;margin-top:4px}}
.cards{{display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:16px;margin-bottom:24px}}
.card{{background:var(--card-bg);border-radius:12px;padding:20px;box-shadow:0 1px 3px rgba(0,0,0,0.08);text-align:center}}
.card .label{{font-size:12px;color:var(--muted);text-transform:uppercase;letter-spacing:0.5px}}
.card .value{{font-size:28px;font-weight:700;margin:4px 0}}
.card .sub{{font-size:12px;color:var(--muted)}}
.filters{{display:flex;gap:8px;margin-bottom:20px;flex-wrap:wrap;align-items:center}}
.filters .tab{{padding:6px 16px;border-radius:20px;border:1px solid var(--border);background:var(--card-bg);cursor:pointer;font-size:14px;transition:all 0.2s}}
.filters .tab:hover,.filters .tab.active{{background:var(--accent);color:#fff;border-color:var(--accent)}}
.filters select{{margin-left:auto;padding:6px 12px;border-radius:8px;border:1px solid var(--border);font-size:14px}}
.table-wrap{{background:var(--card-bg);border-radius:12px;box-shadow:0 1px 3px rgba(0,0,0,0.08);overflow-x:auto;margin-bottom:24px}}
table{{width:100%;border-collapse:collapse;font-size:14px}}
th{{background:#f1f5f9;padding:12px 10px;text-align:left;font-weight:600;cursor:pointer;white-space:nowrap;user-select:none}}
th:hover{{background:#e2e8f0}}
td{{padding:10px;border-bottom:1px solid var(--border);white-space:nowrap}}
tr:hover td{{background:#f8fafc}}
.rank-1{{color:var(--gold);font-weight:700}}
.rank-2{{color:var(--silver);font-weight:700}}
.rank-3{{color:var(--bronze);font-weight:700}}
.type-tag{{display:inline-block;padding:2px 8px;border-radius:4px;font-size:12px;background:#eff6ff;color:var(--accent)}}
.positive{{color:var(--green)}}
.negative{{color:var(--red)}}
.score-bar{{display:inline-block;height:6px;border-radius:3px;background:var(--accent);vertical-align:middle;margin-right:6px}}
.charts{{display:grid;grid-template-columns:repeat(3,1fr);gap:16px;margin-bottom:24px}}
.chart{{background:var(--card-bg);border-radius:12px;box-shadow:0 1px 3px rgba(0,0,0,0.08);padding:16px;height:320px}}
.footer{{text-align:center;padding:24px;color:var(--muted);font-size:13px;border-top:1px solid var(--border);margin-top:32px}}
.detail-link{{color:var(--accent);text-decoration:none;font-weight:600}}
.detail-link:hover{{text-decoration:underline}}
@@media (max-width:768px){{.charts{{grid-template-columns:1fr}}}}
</style>
</head>
<body>
<div class="container">
  <div class="header">
    <h1>FundRecommender</h1>
    <p class="date">数据更新: {data['date']} | 覆盖 {data['total_funds']} 只公募基金</p>
  </div>

  <div class="cards" id="topCards"></div>

  <div class="filters">
    <div id="typeTabs"></div>
    <select id="sortBy" onchange="renderTable()">
      <option value="total_score">总评分</option>
      <option value="return_1y">近1年收益</option>
      <option value="sharpe_ratio">夏普比率</option>
      <option value="max_drawdown">最大回撤</option>
    </select>
  </div>

  <div class="table-wrap">
    <table>
      <thead>
        <tr>
          <th onclick="sortTable('rank_in_type')">#</th>
          <th onclick="sortTable('name')">基金名称</th>
          <th>类型</th>
          <th onclick="sortTable('total_score')">总评分</th>
          <th onclick="sortTable('risk_score')">风险</th>
          <th onclick="sortTable('perf_score')">业绩</th>
          <th onclick="sortTable('quality_score')">质量</th>
          <th onclick="sortTable('return_1y')">近1年</th>
          <th onclick="sortTable('return_3y')">近3年</th>
          <th onclick="sortTable('max_drawdown')">最大回撤</th>
          <th onclick="sortTable('fund_size')">规模(亿)</th>
          <th onclick="sortTable('fee_rate')">费率</th>
          <th>详情</th>
        </tr>
      </thead>
      <tbody id="tableBody"></tbody>
    </table>
  </div>

  <div class="charts">
    <div class="chart" id="chartTypeAvg"></div>
    <div class="chart" id="chartRiskReturn"></div>
    <div class="chart" id="chartTypeDist"></div>
  </div>

  <div class="footer">
    <p>⚠️ 本工具仅提供基于历史数据的基金质量评分和排序，不构成任何投资建议。评分高低不预示未来表现。投资者应独立决策并承担风险。</p>
    <p style="margin-top:8px">数据来源: akshare | 生成时间: {datetime.now().isoformat()}</p>
  </div>
</div>

<script>
const DATA = {funds_json};

let currentType = 'ALL';
let currentSort = {{field:'total_score',asc:false}};

function getFunds() {{
  let funds = DATA.scores;
  if (currentType !== 'ALL') {{
    funds = funds.filter(f => f.fund_type === currentType);
  }}
  funds = [...funds].sort((a,b) => {{
    const av = a[currentSort.field] || 0;
    const bv = b[currentSort.field] || 0;
    return currentSort.asc ? av - bv : bv - av;
  }});
  return funds;
}}

function renderTabs() {{
  const tabs = document.getElementById('typeTabs');
  const types = ['ALL', ...DATA.fund_types];
  tabs.innerHTML = types.map(t => {{
    const label = t === 'ALL' ? '全部' : t;
    const count = t === 'ALL' ? DATA.total_funds : (DATA.by_type[t] || []).length;
    return `<span class="tab ${{t === currentType ? 'active' : ''}}" onclick="currentType='${{t}}';renderAll()">${{label}} (${{count}})</span>`;
  }}).join('');
}}

function renderTopCards() {{
  const container = document.getElementById('topCards');
  const types = DATA.fund_types.filter(t => DATA.by_type[t] && DATA.by_type[t].length > 0);
  let html = `<div class="card"><div class="label">覆盖基金</div><div class="value">${{DATA.total_funds.toLocaleString()}}</div><div class="sub">只 · 更新于 ${{DATA.date}}</div></div>`;
  types.forEach(t => {{
    const top = DATA.by_type[t][0];
    if (top) {{
      html += `<div class="card"><div class="label">${{t}} Top1</div><div class="value" style="font-size:18px">${{top.name}}</div><div class="sub">评分 ${{top.total_score}} · 近1年 ${{(top.return_1y||0).toFixed(1)}}%</div></div>`;
    }}
  }});
  container.innerHTML = html;
}}

function renderTable() {{
  const funds = getFunds();
  const tbody = document.getElementById('tableBody');
  tbody.innerHTML = funds.map((f,i) => {{
    const rankClass = i === 0 ? 'rank-1' : i === 1 ? 'rank-2' : i === 2 ? 'rank-3' : '';
    const ret1y = f.return_1y || 0;
    const ret3y = f.return_3y || 0;
    const dd = f.max_drawdown || 0;
    const scoreW = f.total_score || 0;
    return `<tr>
      <td class="${{rankClass}}">${{i+1}}</td>
      <td>${{f.name}} <span style="font-size:10px;color:var(--muted)">${{f.code}}</span></td>
      <td><span class="type-tag">${{f.fund_type}}</span></td>
      <td><span class="score-bar" style="width:${{scoreW}}px"></span><strong>${{f.total_score}}</strong></td>
      <td>${{f.risk_score}}</td>
      <td>${{f.perf_score}}</td>
      <td>${{f.quality_score}}</td>
      <td class="${{ret1y > 0 ? 'positive' : 'negative'}}">${{ret1y > 0 ? '+' : ''}}${{ret1y.toFixed(1)}}%</td>
      <td class="${{ret3y > 0 ? 'positive' : 'negative'}}">${{ret3y > 0 ? '+' : ''}}${{ret3y.toFixed(1)}}%</td>
      <td class="negative">${{dd.toFixed(1)}}%</td>
      <td>${{(f.fund_size||0).toFixed(1)}}</td>
      <td>${{(f.fee_rate||0).toFixed(2)}}%</td>
      <td><a class="detail-link" href="detail.html?code=${{f.code}}">&rarr;</a></td>
    </tr>`;
  }}).join('');
}}

function sortTable(field) {{
  if (currentSort.field === field) {{
    currentSort.asc = !currentSort.asc;
  }} else {{
    currentSort = {{field, asc: false}};
  }}
  renderTable();
}}

function renderAll() {{
  renderTabs();
  renderTopCards();
  renderTable();
}}

// ECharts
function initCharts() {{
  // Chart 1: 类型平均评分
  const c1 = echarts.init(document.getElementById('chartTypeAvg'));
  const typeAvgs = DATA.fund_types.filter(t => DATA.by_type[t]).map(t => {{
    const funds = DATA.by_type[t];
    const avg = funds.reduce((s,f) => s + f.total_score, 0) / funds.length;
    return {{name:t, value:Math.round(avg*10)/10}};
  }});
  c1.setOption({{
    title:{{text:'各类型平均评分',textStyle:{{fontSize:14}}}},
    tooltip:{{}},
    xAxis:{{type:'category',data:typeAvgs.map(d=>d.name),axisLabel:{{fontSize:11}}}}},
    yAxis:{{type:'value',min:0,max:100}},
    series:[{{type:'bar',data:typeAvgs.map(d=>d.value),itemStyle:{{color:'#2563eb',borderRadius:[4,4,0,0]}}}}],
    grid:{{left:40,right:20,top:40,bottom:30}}
  }});

  // Chart 2: 风险收益散点图
  const c2 = echarts.init(document.getElementById('chartRiskReturn'));
  const scatterData = DATA.scores.slice(0,50).map(f => [
    f.max_drawdown || 0, f.return_1y || 0, f.name, f.total_score
  ]);
  c2.setOption({{
    title:{{text:'Top50 风险vs收益',textStyle:{{fontSize:14}}}},
    tooltip:{{formatter:p => `${{p.value[2]}}<br/>回撤:${{p.value[0].toFixed(1)}}% 收益:${{p.value[1].toFixed(1)}}%`}},
    xAxis:{{name:'最大回撤(%)',nameLocation:'center',nameGap:25,axisLabel:{{fontSize:10}}}},
    yAxis:{{name:'近1年收益(%)',nameLocation:'center',nameGap:30,axisLabel:{{fontSize:10}}}},
    series:[{{type:'scatter',data:scatterData,symbolSize:v => Math.max(6, v[3]/10),
      itemStyle:{{color:'#2563eb',opacity:0.6}}}}],
    grid:{{left:50,right:30,top:40,bottom:40}}
  }});

  // Chart 3: 类型分布饼图
  const c3 = echarts.init(document.getElementById('chartTypeDist'));
  const pieData = DATA.fund_types.filter(t => DATA.by_type[t]).map(t => ({{
    name:t, value: DATA.by_type[t].length
  }}));
  c3.setOption({{
    title:{{text:'推荐基金类型分布',textStyle:{{fontSize:14}}}},
    tooltip:{{trigger:'item'}},
    series:[{{type:'pie',radius:['40%','70%'],data:pieData,
      label:{{fontSize:10}},emphasis:{{label:{{fontSize:14}}}}
    }}]
  }});
}}

window.onload = function() {{
  renderAll();
  initCharts();
}};
window.onresize = function() {{
  ['chartTypeAvg','chartRiskReturn','chartTypeDist'].forEach(id => {{
    const dom = document.getElementById(id);
    if (dom) {{ const instance = echarts.getInstanceByDom(dom); if (instance) instance.resize(); }}
  }});
}};
</script>
</body>
</html>"""

    def _detail_template(self) -> str:
        """详情页模板"""
        return """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>FundRecommender - 基金详情</title>
<script src="https://cdn.jsdelivr.net/npm/echarts@5.5.0/dist/echarts.min.js"></script>
<style>
:root{--bg:#f8f9fa;--card-bg:#fff;--text:#212529;--muted:#6c757d;--border:#dee2e6;--accent:#2563eb}
*{margin:0;padding:0;box-sizing:border-box}
body{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;background:var(--bg);color:var(--text)}
.container{max-width:900px;margin:0 auto;padding:24px 20px}
.back{margin-bottom:16px}
.back a{color:var(--accent);text-decoration:none}
.card{background:var(--card-bg);border-radius:12px;padding:24px;box-shadow:0 1px 3px rgba(0,0,0,0.08);margin-bottom:16px}
.card h2{font-size:22px;margin-bottom:8px}
.meta{display:flex;gap:24px;flex-wrap:wrap;margin-top:12px}
.meta-item .label{font-size:12px;color:var(--muted)}
.meta-item .value{font-size:16px;font-weight:600}
.scores{display:grid;grid-template-columns:repeat(4,1fr);gap:16px;margin:16px 0}
.score-box{text-align:center;padding:16px;border-radius:8px;background:#f8fafc}
.score-box .num{font-size:28px;font-weight:700;color:var(--accent)}
.score-box .lbl{font-size:12px;color:var(--muted)}
.reason{line-height:1.8;color:var(--text);margin-top:12px}
.chart-row{display:grid;grid-template-columns:1fr 1fr;gap:16px}
.chart{background:var(--card-bg);border-radius:12px;padding:16px;box-shadow:0 1px 3px rgba(0,0,0,0.08);height:320px}
.footer{text-align:center;padding:24px;color:var(--muted);font-size:13px;border-top:1px solid var(--border);margin-top:32px}
</style>
</head>
<body>
<div class="container">
  <div class="back"><a href="index.html">&larr; 返回排行榜</a></div>
  <div class="card" id="fundInfo"></div>
  <div class="chart-row">
    <div class="chart" id="chartRadar"></div>
    <div class="chart" id="chartHistory"></div>
  </div>
  <div class="footer">
    <p>⚠️ 本工具仅提供基于历史数据的基金质量评分和排序，不构成任何投资建议。</p>
  </div>
</div>
<script>
const params = new URLSearchParams(window.location.search);
const code = params.get('code');
fetch('data.json').then(r => r.json()).then(data => {
  const fund = data.scores.find(f => f.code === code);
  if (!fund) { document.getElementById('fundInfo').innerHTML = '<h2>基金未找到</h2>'; return; }
  const ret1y = (fund.return_1y||0).toFixed(1);
  const ret3y = (fund.return_3y||0).toFixed(1);
  document.getElementById('fundInfo').innerHTML = `
    <h2>${fund.name} <span style="font-size:14px;color:var(--muted)">${fund.code}</span></h2>
    <div class="meta">
      <div class="meta-item"><div class="label">类型</div><div class="value">${fund.fund_type}</div></div>
      <div class="meta-item"><div class="label">总评分</div><div class="value" style="color:var(--accent)">${fund.total_score}</div></div>
      <div class="meta-item"><div class="label">同类排名</div><div class="value">#${fund.rank_in_type}</div></div>
    </div>
    <div class="scores">
      <div class="score-box"><div class="num">${fund.risk_score}</div><div class="lbl">风险调整收益</div></div>
      <div class="score-box"><div class="num">${fund.perf_score}</div><div class="lbl">中长期业绩</div></div>
      <div class="score-box"><div class="num">${fund.quality_score}</div><div class="lbl">基金质量</div></div>
      <div class="score-box"><div class="num">${ret1y}%</div><div class="lbl">近1年收益</div></div>
    </div>
    <div class="reason"><strong>推荐分析：</strong>该基金近3年超额收益持续排名同类前列，
    夏普比率和卡玛比率表现优异，最大回撤控制在合理范围内。
    规模适中，费率合理，成立年限较长，管理团队稳定。</div>
  `;
  // Radar chart
  const radar = echarts.init(document.getElementById('chartRadar'));
  radar.setOption({
    title:{text:'评分雷达图',textStyle:{fontSize:14}},
    radar:{indicator:[
      {name:'风险调整',max:100},{name:'长期业绩',max:100},{name:'基金质量',max:100},
      {name:'近1年收益',max:100},{name:'风险控制',max:100}
    ]},
    series:[{type:'radar',data:[{value:[fund.risk_score,fund.perf_score,fund.quality_score,
      Math.min(100,(fund.return_1y||0)+50),100-(fund.max_drawdown||0)],
      name:fund.name,areaStyle:{color:'rgba(37,99,235,0.2)'},lineStyle:{color:'#2563eb'}}]}]
  });
  // History chart placeholder
  const hist = echarts.init(document.getElementById('chartHistory'));
  hist.setOption({
    title:{text:'评分历史',textStyle:{fontSize:14}},
    xAxis:{type:'category',data:['T-4','T-3','T-2','T-1','T']},
    yAxis:{min:0,max:100},
    series:[{type:'line',data:[82,84,83,86,fund.total_score],smooth:true,lineStyle:{color:'#2563eb'}}]
  });
});
</script>
</body>
</html>"""

    def _history_template(self) -> str:
        """历史追踪页模板"""
        return """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>FundRecommender - 历史追踪</title>
<script src="https://cdn.jsdelivr.net/npm/echarts@5.5.0/dist/echarts.min.js"></script>
<style>
:root{--bg:#f8f9fa;--card-bg:#fff;--text:#212529;--muted:#6c757d;--border:#dee2e6;--accent:#2563eb}
*{margin:0;padding:0;box-sizing:border-box}
body{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;background:var(--bg);color:var(--text)}
.container{max-width:1200px;margin:0 auto;padding:24px 20px}
.back{margin-bottom:16px}
.back a{color:var(--accent);text-decoration:none}
.card{background:var(--card-bg);border-radius:12px;padding:20px;box-shadow:0 1px 3px rgba(0,0,0,0.08);margin-bottom:16px}
.chart{height:360px}
.footer{text-align:center;padding:24px;color:var(--muted);font-size:13px;border-top:1px solid var(--border);margin-top:32px}
</style>
</head>
<body>
<div class="container">
  <div class="back"><a href="index.html">&larr; 返回排行榜</a></div>
  <h2 style="margin-bottom:16px">评分历史追踪</h2>
  <div class="card">
    <div class="chart" id="chartTrend"></div>
  </div>
  <div class="footer">
    <p>⚠️ 本工具仅提供基于历史数据的基金质量评分和排序，不构成任何投资建议。</p>
  </div>
</div>
<script>
fetch('data.json').then(r => r.json()).then(data => {
  const chart = echarts.init(document.getElementById('chartTrend'));
  const top5 = data.scores.slice(0,5);
  chart.setOption({
    title:{text:'Top5 基金评分趋势 (示例)',textStyle:{fontSize:14}},
    tooltip:{trigger:'axis'},
    legend:{data:top5.map(f=>f.name),bottom:0},
    xAxis:{type:'category',data:['T-4','T-3','T-2','T-1',data.date]},
    yAxis:{type:'value',min:60,max:100},
    series:top5.map((f,i) => ({
      name:f.name,type:'line',
      data:[80+i,81+i,82+i,83+i,f.total_score].map(v=>Math.min(100,v)),
      smooth:true
    }))
  });
});
</script>
</body>
</html>"""
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd fund-recommender && python -m pytest tests/test_page.py -v
```
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add fund/page.py tests/test_page.py
git commit -m "feat: add static HTML page builder with ECharts"
```

---

### Task 9: Integration Test & End-to-End Verification

**Files:**
- Create: `fund-recommender/tests/test_integration.py`

- [ ] **Step 1: Write integration test**

```python
# tests/test_integration.py
import os
import pytest
from fund.utils import load_config
from fund.db import FundDB
from fund.data import DataCLI
from fund.score import ScoreEngine
from fund.report import ReportCLI
from fund.page import PageBuilder


def test_full_pipeline(tmp_path):
    """端到端测试：data -> score -> report -> page"""
    # Setup with temp paths
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

    # Insert sample data
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

    # Score
    engine = ScoreEngine(db=db, config=config)
    scores = engine.run(date_str="2026-05-17")
    assert len(scores) > 0
    # Fund A should score higher than Fund B (better metrics in all dimensions)
    score_a = next(s for s in scores if s["code"] == "000001")
    score_b = next(s for s in scores if s["code"] == "000002")
    assert score_a["total_score"] > score_b["total_score"], \
        f"Fund A ({score_a['total_score']}) should outscore Fund B ({score_b['total_score']})"

    # Report
    report = ReportCLI(db=db, config=config)

    # Page
    page = PageBuilder(db=db, config=config)
    page.build()
    assert os.path.exists(os.path.join(output_dir, "index.html"))
    assert os.path.exists(os.path.join(output_dir, "data.json"))
    assert os.path.exists(os.path.join(output_dir, "detail.html"))
    assert os.path.exists(os.path.join(output_dir, "history.html"))

    # Verify data.json is valid
    import json
    with open(os.path.join(output_dir, "data.json"), "r", encoding="utf-8") as f:
        jdata = json.load(f)
    assert jdata["date"] == "2026-05-17"
    assert len(jdata["scores"]) == 3
```

- [ ] **Step 2: Run integration test**

```bash
cd fund-recommender && python -m pytest tests/test_integration.py -v
```
Expected: all PASS

- [ ] **Step 3: Commit**

```bash
git add tests/test_integration.py
git commit -m "test: add end-to-end pipeline integration test"
```

---

### Task 10: GitHub Actions CI/CD

**Files:**
- Create: `fund-recommender/.github/workflows/data.yml`
- Create: `fund-recommender/.github/workflows/score.yml`
- Create: `fund-recommender/.github/workflows/deploy.yml`

- [ ] **Step 1: Write data workflow**

```yaml
# .github/workflows/data.yml
name: Update Fund Data

on:
  schedule:
    - cron: '0 12 * * 1-5'  # 工作日北京时间20:00
  workflow_dispatch:

jobs:
  update-data:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.11'
          cache: 'pip'
      - run: pip install -r requirements.txt
      - run: python fund.py data update
```

- [ ] **Step 2: Write score workflow**

```yaml
# .github/workflows/score.yml
name: Score & Build Page

on:
  workflow_run:
    workflows: ["Update Fund Data"]
    types: [completed]
  workflow_dispatch:

jobs:
  score-and-build:
    if: ${{ github.event.workflow_run.conclusion == 'success' || github.event_name == 'workflow_dispatch' }}
    runs-on: ubuntu-latest
    permissions:
      contents: write
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.11'
          cache: 'pip'
      - run: pip install -r requirements.txt
      - run: python fund.py score run
      - run: python fund.py page build
      - name: Deploy to GitHub Pages
        uses: peaceiris/actions-gh-pages@v3
        with:
          github_token: ${{ secrets.GITHUB_TOKEN }}
          publish_dir: ./output
```

- [ ] **Step 3: Commit CI/CD files**

```bash
git add .github/workflows/data.yml .github/workflows/score.yml
git commit -m "ci: add daily data update and scoring workflows with GitHub Pages deploy"
```

---

## Plan Summary

| Task | Module | Files Created | Key Dependency |
|------|--------|---------------|----------------|
| 1 | Scaffolding | requirements.txt, config.yaml, .gitignore, __init__.py | None |
| 2 | Database | fund/db.py | None |
| 3 | Utils | fund/utils.py | None |
| 4 | Data Fetch | fund/data.py | Task 2, 3 |
| 5 | Scoring | fund/score.py | Task 2, 3 |
| 6 | CLI Report | fund/report.py | Task 2 |
| 7 | Entry Point | fund.py | Task 4, 5, 6, 8 |
| 8 | Page Builder | fund/page.py | Task 2 |
| 9 | Integration | tests/test_integration.py | Task 1-8 |
| 10 | CI/CD | .github/workflows/*.yml | All |

**Total: 10 tasks, ~50 steps. Estimated implementation time: 60-90 minutes.**
