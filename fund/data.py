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
                "fee_rate": 1.50,
                "establish_date": "",
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
        return "混合型"
