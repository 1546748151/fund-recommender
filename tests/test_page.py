# tests/test_page.py
import os
import json
import pytest
from fund.db import FundDB
from fund.page import PageBuilder


@pytest.fixture
def od_templates(tmp_path):
    template_dir = tmp_path / "od_templates"
    template_dir.mkdir()
    index_html = """<!DOCTYPE html>
<html lang="zh-CN">
<head><meta charset="UTF-8"><title>FundRecommender</title>
<style>:root{--bg:#f5f5f7;--accent:#0071e3}.container{max-width:1340px}.stats{display:grid}</style>
</head>
<body><div class="container"><header class="header"><h1>FundRecommender</h1></header>
<div id="topCards"></div><div id="typeTabs"></div><table><tbody id="tableBody"></tbody></table>
<div id="chartTypeAvg"></div><div id="chartRiskReturn"></div><div id="chartTypeDist"></div>
<footer class="footer"><p class="warning">免责声明</p></footer></div></body></html>"""
    (template_dir / "index.html").write_text(index_html, encoding="utf-8")

    detail_html = """<!DOCTYPE html>
<html lang="zh-CN">
<head><meta charset="UTF-8"><title>详情</title>
<style>:root{--accent:#0071e3}</style></head>
<body><div id="fundHero"></div><div id="fundAnalysis"></div>
<div id="chartRadar"></div><div id="chartHistory"></div></body></html>"""
    (template_dir / "detail.html").write_text(detail_html, encoding="utf-8")
    return str(template_dir)


@pytest.fixture
def page_builder(tmp_path, od_templates):
    db = FundDB(":memory:")
    db.save_funds([{
        "code": "110011", "name": "易方达中小盘", "fund_type": "混合型",
        "fund_size": 38.2, "fee_rate": 1.50, "establish_date": "2008-06-19",
        "inst_ratio": 0.35, "manager_name": "张坤",
        "return_1y": 32.5, "return_2y": 45.2, "return_3y": 68.2,
        "volatility": 18.5, "sharpe_ratio": 1.82, "max_drawdown": 18.3,
        "calmar_ratio": 1.78,
    }])
    db.save_score_snapshot([{
        "code": "110011", "date": "2026-05-18", "total_score": 87.3,
        "risk_score": 85.0, "perf_score": 91.0, "quality_score": 82.0,
        "rank_in_type": 1, "fund_type": "混合型",
    }])
    config = {
        "page": {"output_dir": str(tmp_path / "output"), "top_n": 50, "od_template_dir": od_templates},
        "fund_types": ["混合型"],
    }
    return PageBuilder(db=db, config=config)


def test_load_od_template(page_builder):
    html = page_builder._load_od_template("index")
    assert "FundRecommender" in html
    assert ":root" in html
    assert "topCards" in html


def test_build_uses_od_css(page_builder):
    page_builder.build()
    output_index = os.path.join(page_builder.output_dir, "index.html")
    with open(output_index, encoding="utf-8") as f:
        html = f.read()
    assert ":root" in html
    assert "--bg" in html
    assert "--accent" in html
    assert "tableBody" in html


def test_build_creates_all_files(page_builder):
    page_builder.build()
    assert os.path.exists(os.path.join(page_builder.output_dir, "index.html"))
    assert os.path.exists(os.path.join(page_builder.output_dir, "detail.html"))
    assert os.path.exists(os.path.join(page_builder.output_dir, "history.html"))
    assert os.path.exists(os.path.join(page_builder.output_dir, "data.json"))


def test_data_json_structure(page_builder):
    page_builder.build()
    with open(os.path.join(page_builder.output_dir, "data.json"), encoding="utf-8") as f:
        data = json.load(f)
    assert len(data["scores"]) == 1
    assert data["scores"][0]["code"] == "110011"
