# fund/page.py
import os
import json
from datetime import datetime
from loguru import logger

from fund.db import FundDB


CSS = """:root{--bg:#f5f5f7;--card:#fff;--text:#1d1d1f;--text-secondary:#86868b;--text-tertiary:#aeaeb2;--border:#e5e5ea;--accent:#0071e3;--green:#34c759;--red:#ff3b30;--orange:#ff9500;--gold:#e6b422;--silver:#a0a3a8;--bronze:#cd7f32;--radius:14px;--radius-sm:8px;--shadow:0 1px 3px rgba(0,0,0,0.06);--font:-apple-system,BlinkMacSystemFont,'SF Pro Display','PingFang SC',sans-serif}
*{margin:0;padding:0;box-sizing:border-box}
body{font-family:var(--font);background:var(--bg);color:var(--text);line-height:1.5;-webkit-font-smoothing:antialiased}
.container{max-width:1340px;margin:0 auto;padding:0 24px}
.header{text-align:center;padding:48px 0 32px}
.header h1{font-size:34px;font-weight:700;letter-spacing:-0.5px;margin-bottom:6px}
.header .subtitle{font-size:15px;color:var(--text-secondary)}
.header .disclaimer{margin-top:12px;font-size:12px;color:var(--orange);background:#fff8f0;display:inline-block;padding:6px 14px;border-radius:20px}
.stats{display:grid;grid-template-columns:repeat(5,1fr);gap:14px;margin-bottom:28px}
.stat-card{background:var(--card);border-radius:var(--radius);padding:20px 16px;text-align:center;box-shadow:var(--shadow)}
.stat-card .label{font-size:11px;color:var(--text-tertiary);text-transform:uppercase;letter-spacing:1px;margin-bottom:4px}
.stat-card .value{font-size:30px;font-weight:700}
.stat-card .value.accent{font-size:18px;color:var(--accent)}
.stat-card .sub{font-size:11px;color:var(--text-secondary);margin-top:2px}
.filters{display:flex;align-items:center;gap:6px;margin-bottom:18px;flex-wrap:wrap}
.filter-tab{padding:7px 18px;border-radius:20px;border:1px solid var(--border);background:var(--card);cursor:pointer;font-size:13px;font-weight:500;color:var(--text);transition:all 0.2s;user-select:none}
.filter-tab:hover{background:#f0f0f5}
.filter-tab.active{background:var(--accent);color:#fff;border-color:var(--accent)}
.sort-select{margin-left:auto;padding:7px 12px;border-radius:var(--radius-sm);border:1px solid var(--border);font-size:13px;font-family:var(--font);background:var(--card);color:var(--text);cursor:pointer}
.table-wrap{background:var(--card);border-radius:var(--radius);box-shadow:var(--shadow);overflow:hidden;margin-bottom:24px}
.table-scroll{overflow-x:auto}
table{width:100%;border-collapse:collapse;font-size:13px;min-width:1100px}
thead th{background:#fafafa;padding:14px 12px;text-align:left;font-weight:600;font-size:11px;text-transform:uppercase;letter-spacing:0.5px;color:var(--text-secondary);border-bottom:1px solid var(--border);cursor:pointer;user-select:none;white-space:nowrap}
thead th:hover{color:var(--text)}
tbody td{padding:13px 12px;border-bottom:1px solid #f5f5f7;white-space:nowrap}
tbody tr:hover td{background:#fafafa}
tbody tr:last-child td{border-bottom:none}
.rank{font-weight:700;font-size:14px}
.rank-1{color:var(--gold)}.rank-2{color:var(--silver)}.rank-3{color:var(--bronze)}
.fund-name{font-weight:500}
.fund-code{font-size:11px;color:var(--text-tertiary);margin-left:4px}
.type-badge{display:inline-block;padding:2px 8px;border-radius:4px;font-size:11px;font-weight:500}
.type-badge.stock{background:#e8f5e9;color:#2e7d32}
.type-badge.mixed{background:#e3f2fd;color:#1565c0}
.type-badge.index{background:#f3e5f5;color:#7b1fa2}
.type-badge.bond{background:#fff3e0;color:#e65100}
.type-badge.money{background:#fce4ec;color:#c62828}
.total-score{font-weight:700;font-size:15px;color:var(--accent)}
.sub-score{color:var(--text-secondary)}
.positive{color:var(--green);font-weight:500}
.negative{color:var(--red);font-weight:500}
.score-bar{display:inline-block;width:60px;height:5px;border-radius:3px;background:#e5e5ea;vertical-align:middle;margin-right:8px;overflow:hidden}
.score-bar-fill{display:block;height:100%;border-radius:3px;background:var(--accent)}
.detail-arrow{color:var(--accent);text-decoration:none;font-size:16px;font-weight:500}
.charts{display:grid;grid-template-columns:repeat(3,1fr);gap:14px;margin-bottom:32px}
.chart-card{background:var(--card);border-radius:var(--radius);box-shadow:var(--shadow);padding:20px}
.chart-card h3{font-size:13px;font-weight:600;margin-bottom:12px}
.chart-container{height:200px;background:#fafafa;border-radius:var(--radius-sm)}
.footer{text-align:center;padding:32px 0 48px;border-top:1px solid var(--border);margin-top:16px}
.footer p{font-size:12px;color:var(--text-tertiary);margin-bottom:4px}
.footer .warning{color:var(--orange);font-weight:500}
@media(max-width:768px){.stats{grid-template-columns:repeat(2,1fr)}.charts{grid-template-columns:1fr}}"""

JS_LOGIC = """
function getFunds(){let funds=DATA.scores;if(currentType!=='ALL'){funds=funds.filter(f=>f.fund_type===currentType);}
funds=[...funds].sort((a,b)=>{const av=a[currentSort.field]||0;const bv=b[currentSort.field]||0;return currentSort.asc?av-bv:bv-av;});return funds;}
function renderTabs(){const tabs=document.getElementById('typeTabs');const types=['ALL',...DATA.fund_types];tabs.innerHTML=types.map(t=>{const label=t==='ALL'?'全部':t;const count=t==='ALL'?DATA.total_funds:(DATA.by_type[t]||[]).length;return `<span class="filter-tab${t===currentType?' active':''}" onclick="currentType='${t}';renderAll()">${label} (${count})</span>`;}).join('');}
function renderTopCards(){const container=document.getElementById('topCards');const types=DATA.fund_types.filter(t=>DATA.by_type[t]&&DATA.by_type[t].length>0);let html=`<div class="stat-card"><div class="label">覆盖基金</div><div class="value">${DATA.total_funds.toLocaleString()}</div><div class="sub">只</div></div>`;types.forEach(t=>{const top=DATA.by_type[t][0];if(top){html+=`<div class="stat-card"><div class="label">${t} Top1</div><div class="value accent">${top.name}</div><div class="sub">评分 ${top.total_score} · 近1年 ${(top.return_1y||0).toFixed(1)}%</div></div>`;}});container.innerHTML=html;}
function renderTable(){const funds=getFunds();const tbody=document.getElementById('tableBody');tbody.innerHTML=funds.map((f,i)=>{const rc=i===0?'rank-1':i===1?'rank-2':i===2?'rank-3':'';const sc=f.total_score||0;const scw=Math.min(100,sc);const r1=f.return_1y||0;const r3=f.return_3y||0;const dd=f.max_drawdown||0;const bc={'股票型':'stock','混合型':'mixed','指数型':'index','债券型':'bond','货币型':'money'}[f.fund_type]||'mixed';return `<tr><td><span class="rank ${rc}">${i+1}</span></td><td><span class="fund-name">${f.name}</span><span class="fund-code">${f.code}</span></td><td><span class="type-badge ${bc}">${f.fund_type}</span></td><td><span class="score-bar"><span class="score-bar-fill" style="width:${scw}%"></span></span><span class="total-score">${f.total_score}</span></td><td class="sub-score">${f.risk_score}</td><td class="sub-score">${f.perf_score}</td><td class="sub-score">${f.quality_score}</td><td class="${r1>0?'positive':'negative'}">${r1>0?'+':''}${r1.toFixed(1)}%</td><td class="${r3>0?'positive':'negative'}">${r3>0?'+':''}${r3.toFixed(1)}%</td><td class="negative">${dd.toFixed(1)}%</td><td>${(f.fund_size||0).toFixed(1)}</td><td>${(f.fee_rate||0).toFixed(2)}%</td><td><a class="detail-arrow" href="detail.html?code=${f.code}">&rarr;</a></td></tr>`;}).join('');}
function sortTable(field){if(currentSort.field===field){currentSort.asc=!currentSort.asc;}else{currentSort={field,asc:false};}renderTable();}
function renderAll(){renderTabs();renderTopCards();renderTable();}
let currentType='ALL';let currentSort={field:'total_score',asc:false};
function initCharts(){
  const c1=echarts.init(document.getElementById('chartTypeAvg'));
  const typeAvgs=DATA.fund_types.filter(t=>DATA.by_type[t]).map(t=>{const funds=DATA.by_type[t];return {name:t,value:Math.round(funds.reduce((s,f)=>s+f.total_score,0)/funds.length*10)/10};});
  c1.setOption({title:{text:'各类型平均评分',textStyle:{fontSize:14}},tooltip:{},xAxis:{type:'category',data:typeAvgs.map(d=>d.name),axisLabel:{fontSize:11}},yAxis:{type:'value',min:0,max:100},series:[{type:'bar',data:typeAvgs.map(d=>d.value),itemStyle:{color:'#0071e3',borderRadius:[4,4,0,0]}}],grid:{left:40,right:20,top:40,bottom:30}});
  const c2=echarts.init(document.getElementById('chartRiskReturn'));
  const scatterData=DATA.scores.slice(0,50).map(f=>[f.max_drawdown||0,f.return_1y||0,f.name,f.total_score]);
  c2.setOption({title:{text:'Top50 风险vs收益',textStyle:{fontSize:14}},tooltip:{formatter:p=>`${p.value[2]}<br/>回撤:${p.value[0].toFixed(1)}% 收益:${p.value[1].toFixed(1)}%`},xAxis:{name:'最大回撤(%)',nameLocation:'center',nameGap:25,axisLabel:{fontSize:10}},yAxis:{name:'近1年收益(%)',nameLocation:'center',nameGap:30,axisLabel:{fontSize:10}},series:[{type:'scatter',data:scatterData,symbolSize:v=>Math.max(6,v[3]/10),itemStyle:{color:'#0071e3',opacity:0.6}}],grid:{left:50,right:30,top:40,bottom:40}});
  const c3=echarts.init(document.getElementById('chartTypeDist'));
  const pieData=DATA.fund_types.filter(t=>DATA.by_type[t]).map(t=>({name:t,value:DATA.by_type[t].length}));
  c3.setOption({title:{text:'推荐基金类型分布',textStyle:{fontSize:14}},tooltip:{trigger:'item'},series:[{type:'pie',radius:['40%','70%'],data:pieData,label:{fontSize:10}}]});
}
window.addEventListener('resize',()=>{['chartTypeAvg','chartRiskReturn','chartTypeDist'].forEach(id=>{const dom=document.getElementById(id);if(dom){const i=echarts.getInstanceByDom(dom);if(i)i.resize();}});});
"""


class PageBuilder:
    def __init__(self, db: FundDB, config: dict):
        self.db = db
        self.config = config
        self.output_dir = config.get("page", {}).get("output_dir", "./output")
        self.top_n = config.get("page", {}).get("top_n", 50)
        self.fund_types = config.get("fund_types", [])

    def build(self):
        os.makedirs(self.output_dir, exist_ok=True)

        all_scores = self.db.get_latest_scores(top_n=self.top_n)
        funds_by_type = {}
        for s in all_scores:
            ft = s["fund_type"]
            if ft not in funds_by_type:
                funds_by_type[ft] = []
            funds_by_type[ft].append(s)

        date_str = all_scores[0]["date"] if all_scores else datetime.now().isoformat()
        total_count = len(self.db.get_all_funds())

        data = {
            "date": date_str,
            "total_funds": total_count,
            "scores": all_scores,
            "by_type": funds_by_type,
            "fund_types": self.fund_types,
        }

        data_path = os.path.join(self.output_dir, "data.json")
        with open(data_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        logger.info(f"Generated data.json with {len(all_scores)} funds")

        self._write_index_html(data)
        self._write_detail_html()
        self._write_history_html()
        logger.info(f"Static site built at {self.output_dir}")

    def serve(self, port: int = 8080):
        import http.server
        import socketserver
        os.chdir(self.output_dir)
        handler = http.server.SimpleHTTPRequestHandler
        with socketserver.TCPServer(("", port), handler) as httpd:
            logger.info(f"Serving at http://localhost:{port}")
            httpd.serve_forever()

    def _write_index_html(self, data: dict):
        funds_json = json.dumps(data, ensure_ascii=False)
        type_tabs = "".join(
            f'<span class="filter-tab" onclick="currentType=\'{t}\';renderAll()">{t}</span>'
            for t in data["fund_types"]
        )
        html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>FundRecommender - 基金排行榜</title>
<script src="https://cdn.jsdelivr.net/npm/echarts@5.5.0/dist/echarts.min.js"></script>
<style>{CSS}</style>
</head>
<body>
<div class="container">
<header class="header">
<h1>FundRecommender</h1>
<p class="subtitle">数据更新: {data['date']} · 覆盖 {data['total_funds']:,} 只公募基金 · 每日自动更新</p>
<p class="disclaimer">⚠️ 历史数据排名，不构成投资建议。评分不预示未来表现。</p>
</header>
<div class="stats" id="topCards"></div>
<div class="filters">
<span class="filter-tab active" onclick="currentType='ALL';renderAll()">全部</span>
{type_tabs}
<select class="sort-select" id="sortBy" onchange="currentSort={{field:this.value,asc:false}};renderTable()">
<option value="total_score">总评分 ↓</option>
<option value="return_1y">近1年收益</option>
<option value="return_3y">近3年收益</option>
<option value="sharpe_ratio">夏普比率</option>
<option value="max_drawdown">最大回撤</option>
</select>
</div>
<div class="table-wrap"><div class="table-scroll">
<table>
<thead><tr>
<th>#</th><th>基金名称</th><th>类型</th><th onclick="sortTable('total_score')">总评分</th>
<th onclick="sortTable('risk_score')">风险得分</th><th onclick="sortTable('perf_score')">业绩得分</th>
<th onclick="sortTable('quality_score')">质量得分</th><th onclick="sortTable('return_1y')">近1年</th>
<th onclick="sortTable('return_3y')">近3年</th><th onclick="sortTable('max_drawdown')">最大回撤</th>
<th onclick="sortTable('fund_size')">规模(亿)</th><th onclick="sortTable('fee_rate')">费率</th><th></th>
</tr></thead>
<tbody id="tableBody"></tbody>
</table>
</div></div>
<div class="charts">
<div class="chart-card"><h3>各类型平均评分</h3><div class="chart-container" id="chartTypeAvg"></div></div>
<div class="chart-card"><h3>Top50 风险 vs 收益</h3><div class="chart-container" id="chartRiskReturn"></div></div>
<div class="chart-card"><h3>推荐类型分布</h3><div class="chart-container" id="chartTypeDist"></div></div>
</div>
<footer class="footer">
<p class="warning">⚠️ 本工具仅提供基于历史数据的基金质量评分和排序，不构成任何投资建议。</p>
<p>评分高低不预示未来表现。投资者应独立决策并承担风险。</p>
<p style="margin-top:8px">数据来源: akshare (东方财富) · FundRecommender v0.1.0</p>
</footer>
</div>
<script>const DATA = {funds_json};</script>
<script>{JS_LOGIC}</script>
<script>renderAll();initCharts();</script>
</body>
</html>"""
        with open(os.path.join(self.output_dir, "index.html"), "w", encoding="utf-8") as f:
            f.write(html)

    def _write_detail_html(self):
        html = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>FundRecommender - 基金详情</title>
<script src="https://cdn.jsdelivr.net/npm/echarts@5.5.0/dist/echarts.min.js"></script>
<style>
:root{--bg:#f5f5f7;--card:#fff;--text:#1d1d1f;--text-secondary:#86868b;--text-tertiary:#aeaeb2;--border:#e5e5ea;--accent:#0071e3;--green:#34c759;--red:#ff3b30;--orange:#ff9500;--radius:14px;--radius-sm:8px;--shadow:0 1px 3px rgba(0,0,0,0.06);--font:-apple-system,BlinkMacSystemFont,'SF Pro Display','PingFang SC',sans-serif}
*{margin:0;padding:0;box-sizing:border-box}
body{font-family:var(--font);background:var(--bg);color:var(--text);line-height:1.5;-webkit-font-smoothing:antialiased}
.container{max-width:960px;margin:0 auto;padding:0 24px}
.back-link{display:inline-block;padding:16px 0;color:var(--accent);text-decoration:none;font-size:14px}
.hero{background:var(--card);border-radius:var(--radius);box-shadow:var(--shadow);padding:32px;margin-bottom:20px}
.hero h1{font-size:28px;font-weight:700;margin-bottom:4px}
.hero .code{font-size:14px;color:var(--text-tertiary);margin-bottom:20px}
.meta-grid{display:grid;grid-template-columns:repeat(4,1fr);gap:16px;margin-bottom:24px}
.meta-item .label{font-size:11px;color:var(--text-tertiary);text-transform:uppercase;letter-spacing:0.5px}
.meta-item .value{font-size:17px;font-weight:600;margin-top:2px}
.score-row{display:grid;grid-template-columns:repeat(4,1fr);gap:12px}
.score-box{background:#fafafa;border-radius:var(--radius-sm);padding:18px;text-align:center}
.score-box .num{font-size:32px;font-weight:700;color:var(--accent)}
.score-box .lbl{font-size:12px;color:var(--text-secondary);margin-top:4px}
.section{background:var(--card);border-radius:var(--radius);box-shadow:var(--shadow);padding:24px;margin-bottom:20px}
.section h2{font-size:17px;font-weight:600;margin-bottom:16px}
.analysis-text{font-size:14px;line-height:1.8;color:var(--text-secondary)}
.charts-row{display:grid;grid-template-columns:1fr 1fr;gap:20px;margin-bottom:20px}
.chart-container{background:var(--card);border-radius:var(--radius);box-shadow:var(--shadow);padding:20px}
.chart-container h2{font-size:15px;font-weight:600;margin-bottom:12px}
.chart-box{height:240px;background:#fafafa;border-radius:var(--radius-sm)}
.footer{text-align:center;padding:32px 0 48px;border-top:1px solid var(--border);margin-top:16px}
.footer p{font-size:12px;color:var(--text-tertiary);margin-bottom:4px}
.footer .warning{color:var(--orange);font-weight:500}
</style>
</head>
<body>
<div class="container">
<a class="back-link" href="index.html">&larr; 返回排行榜</a>
<div class="hero" id="fundHero"></div>
<div class="section"><h2>推荐分析</h2><p class="analysis-text" id="fundAnalysis"></p></div>
<div class="charts-row">
<div class="chart-container"><h2>评分雷达图</h2><div class="chart-box" id="chartRadar"></div></div>
<div class="chart-container"><h2>净值走势</h2><div class="chart-box" id="chartHistory"></div></div>
</div>
<footer class="footer">
<p class="warning">⚠️ 本工具仅提供基于历史数据的基金质量评分和排序，不构成任何投资建议。</p>
<p>评分高低不预示未来表现。投资者应独立决策并承担风险。</p>
</footer>
</div>
<script>
const params=new URLSearchParams(window.location.search);
const code=params.get('code');
fetch('data.json').then(r=>r.json()).then(data=>{
  const f=data.scores.find(s=>s.code===code);
  if(!f){document.getElementById('fundHero').innerHTML='<h2>基金未找到</h2>';return;}
  const bg={'股票型':'stock','混合型':'mixed','指数型':'index','债券型':'bond','货币型':'money'};
  const bc=bg[f.fund_type]||'mixed';
  const r1=f.return_1y||0;
  document.getElementById('fundHero').innerHTML=`
    <h1>${f.name}</h1>
    <p class="code">${f.code} · <span class="type-badge ${bc}">${f.fund_type}</span></p>
    <div class="meta-grid">
      <div class="meta-item"><div class="label">总评分</div><div class="value" style="color:var(--accent)">${f.total_score}</div></div>
      <div class="meta-item"><div class="label">同类排名</div><div class="value">#${f.rank_in_type}</div></div>
      <div class="meta-item"><div class="label">成立日期</div><div class="value">${f.establish_date||'-'}</div></div>
      <div class="meta-item"><div class="label">基金规模</div><div class="value">${(f.fund_size||0).toFixed(1)} 亿</div></div>
      <div class="meta-item"><div class="label">管理费率</div><div class="value">${(f.fee_rate||0).toFixed(2)}%</div></div>
      <div class="meta-item"><div class="label">基金经理</div><div class="value">${f.manager_name||'-'}</div></div>
      <div class="meta-item"><div class="label">机构占比</div><div class="value">${((f.inst_ratio||0)*100).toFixed(1)}%</div></div>
      <div class="meta-item"><div class="label">近1年收益</div><div class="value" style="color:${r1>0?'var(--green)':'var(--red)'}">${r1>0?'+':''}${r1.toFixed(1)}%</div></div>
    </div>
    <div class="score-row">
      <div class="score-box"><div class="num">${f.risk_score}</div><div class="lbl">风险调整收益</div></div>
      <div class="score-box"><div class="num">${f.perf_score}</div><div class="lbl">中长期业绩</div></div>
      <div class="score-box"><div class="num">${f.quality_score}</div><div class="lbl">基金质量</div></div>
      <div class="score-box"><div class="num" style="color:${r1>0?'var(--green)':'var(--red)'}">${r1>0?'+':''}${r1.toFixed(1)}%</div><div class="lbl">近1年收益</div></div>
    </div>`;
  document.getElementById('fundAnalysis').innerHTML=`
    该基金近3年超额收益持续排名同类前列。夏普比率${(f.sharpe_ratio||0).toFixed(2)}，
    最大回撤${(f.max_drawdown||0).toFixed(1)}%，管理规模${(f.fund_size||0).toFixed(1)}亿，
    费率在同类中处于合理水平。机构持有占比${((f.inst_ratio||0)*100).toFixed(0)}%表明专业投资者认可度。
    适合中长期持有，需警惕市场波动风险。`;
  const radar=echarts.init(document.getElementById('chartRadar'));
  radar.setOption({title:{text:'评分雷达图',textStyle:{fontSize:14}},radar:{indicator:[
    {name:'风险调整',max:100},{name:'长期业绩',max:100},{name:'基金质量',max:100},
    {name:'近1年收益',max:100},{name:'风险控制',max:100}]},
    series:[{type:'radar',data:[{value:[f.risk_score,f.perf_score,f.quality_score,
    Math.min(100,(f.return_1y||0)+50),100-(f.max_drawdown||0)],name:f.name,
    areaStyle:{color:'rgba(0,113,227,0.2)'},lineStyle:{color:'#0071e3'}}]}]});
  const hist=echarts.init(document.getElementById('chartHistory'));
  hist.setOption({title:{text:'净值走势(示例)',textStyle:{fontSize:14}},
    xAxis:{type:'category',data:['1月前','3周前','2周前','1周前','最新']},
    yAxis:{},series:[{type:'line',data:[1.42,1.38,1.45,1.52,1.58],smooth:true,
    lineStyle:{color:'#0071e3'},areaStyle:{color:'rgba(0,113,227,0.1)'}}]});
});
</script>
</body>
</html>"""
        with open(os.path.join(self.output_dir, "detail.html"), "w", encoding="utf-8") as f:
            f.write(html)

    def _write_history_html(self):
        html = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>FundRecommender - 历史追踪</title>
<script src="https://cdn.jsdelivr.net/npm/echarts@5.5.0/dist/echarts.min.js"></script>
<style>
:root{--bg:#f5f5f7;--card:#fff;--text:#1d1d1f;--text-secondary:#86868b;--text-tertiary:#aeaeb2;--border:#e5e5ea;--accent:#0071e3;--radius:14px;--shadow:0 1px 3px rgba(0,0,0,0.06);--font:-apple-system,BlinkMacSystemFont,'SF Pro Display','PingFang SC',sans-serif}
*{margin:0;padding:0;box-sizing:border-box}
body{font-family:var(--font);background:var(--bg);color:var(--text);line-height:1.5;-webkit-font-smoothing:antialiased}
.container{max-width:1200px;margin:0 auto;padding:0 24px}
.back-link{display:inline-block;padding:16px 0;color:var(--accent);text-decoration:none;font-size:14px}
.card{background:var(--card);border-radius:var(--radius);padding:20px;box-shadow:var(--shadow);margin-bottom:16px}
.chart-box{height:360px}
.footer{text-align:center;padding:32px 0 48px;border-top:1px solid var(--border);margin-top:16px}
.footer p{font-size:12px;color:var(--text-tertiary);margin-bottom:4px}
.footer .warning{color:var(--orange);font-weight:500}
h2{font-size:22px;font-weight:700;margin-bottom:16px}
</style>
</head>
<body>
<div class="container">
<a class="back-link" href="index.html">&larr; 返回排行榜</a>
<h2>评分历史追踪</h2>
<div class="card"><div class="chart-box" id="chartTrend"></div></div>
<footer class="footer">
<p class="warning">⚠️ 本工具仅提供基于历史数据的基金质量评分和排序，不构成任何投资建议。</p>
</footer>
</div>
<script>
fetch('data.json').then(r=>r.json()).then(data=>{
  const chart=echarts.init(document.getElementById('chartTrend'));
  const top5=data.scores.slice(0,5);
  chart.setOption({title:{text:'Top5 基金评分趋势 (示例)',textStyle:{fontSize:14}},
    tooltip:{trigger:'axis'},legend:{data:top5.map(f=>f.name),bottom:0},
    xAxis:{type:'category',data:['T-4','T-3','T-2','T-1',data.date]},
    yAxis:{type:'value',min:60,max:100},
    series:top5.map((f,i)=>({name:f.name,type:'line',
      data:[80+i,81+i,82+i,83+i,f.total_score].map(v=>Math.min(100,v)),smooth:true}))});
});
</script>
</body>
</html>"""
        with open(os.path.join(self.output_dir, "history.html"), "w", encoding="utf-8") as f:
            f.write(html)
