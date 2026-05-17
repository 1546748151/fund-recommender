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
