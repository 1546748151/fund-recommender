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

        rows = []
        for i, s in enumerate(scores, 1):
            rows.append([
                i,
                s.get("name", ""),
                s.get("fund_type", ""),
                s.get("total_score", 0),
                s.get("risk_score", 0),
                s.get("perf_score", 0),
                s.get("quality_score", 0),
                f"{s.get('return_1y', 0):+.1f}%",
                f"{s.get('return_3y', 0):+.1f}%" if s.get("return_3y") else "-",
                f"{s.get('max_drawdown', 0):.1f}%" if s.get("max_drawdown") else "-",
                f"{s.get('fund_size', 0):.1f}" if s.get("fund_size") else "-",
                f"{s.get('fee_rate', 0):.2f}%" if s.get("fee_rate") else "-",
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
