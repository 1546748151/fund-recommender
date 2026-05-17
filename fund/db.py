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
        optional_fields = [
            "return_1y", "return_2y", "return_3y",
            "volatility", "sharpe_ratio", "max_drawdown", "calmar_ratio",
            "fund_size", "fee_rate", "establish_date", "inst_ratio", "manager_name",
        ]
        normalized = []
        for d in funds_data:
            row = dict(d)
            for field in optional_fields:
                row.setdefault(field, None)
            normalized.append(row)
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
            """, normalized)

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
        optional_fields = ["fund_type", "rank_in_type", "risk_score", "perf_score", "quality_score"]
        normalized = []
        for d in scores:
            row = dict(d)
            for field in optional_fields:
                row.setdefault(field, None)
            normalized.append(row)
        with self._get_conn() as conn:
            conn.executemany("""
                INSERT OR REPLACE INTO score_snapshots
                    (code, date, total_score, risk_score, perf_score, quality_score,
                     rank_in_type, fund_type)
                VALUES (:code, :date, :total_score, :risk_score, :perf_score,
                        :quality_score, :rank_in_type, :fund_type)
            """, normalized)

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
