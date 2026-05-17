# fund/score.py
from datetime import datetime, date
from typing import Any, Optional
from loguru import logger

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

        all_scores = []
        for ft in self.fund_types:
            type_funds = [f for f in all_funds if f["fund_type"] == ft]
            if not type_funds:
                continue
            logger.info(f"Scoring {len(type_funds)} funds in type: {ft}")
            type_scores = self._score_fund_type(type_funds, date_str)
            all_scores.extend(type_scores)

        all_scores.sort(key=lambda x: x["total_score"], reverse=True)

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
        ) / 0.45

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
        return percentile_rank(all_values, value, reverse=reverse)

    def _score_fund_size(self, size: float) -> float:
        opt_min = self.score_config.get("optimal_size_min", 1)
        opt_max = self.score_config.get("optimal_size_max", 50)
        if opt_min <= size <= opt_max:
            return 100.0
        if size < opt_min:
            return max(0, (size / opt_min) * 100.0)
        return max(0, 100.0 - ((size - opt_max) / opt_max) * 50.0)

    def _score_fund_age(self, establish_date: str) -> float:
        try:
            est = datetime.strptime(establish_date, "%Y-%m-%d")
            age_years = (datetime.now() - est).days / 365.25
        except (ValueError, TypeError):
            return 30.0
        if age_years >= 3:
            return 100.0
        if age_years < 1:
            return 0.0
        return (age_years / 3) * 100.0

    def _score_inst_ratio(self, ratio: float) -> float:
        opt_min = self.score_config.get("optimal_inst_min", 0.20)
        opt_max = self.score_config.get("optimal_inst_max", 0.60)
        if opt_min <= ratio <= opt_max:
            return 100.0
        if ratio < opt_min:
            return max(0, (ratio / opt_min) * 100.0)
        return max(0, 100.0 - ((ratio - opt_max) / (1 - opt_max)) * 80.0)
