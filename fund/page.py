# fund/page.py
import os
import json
from datetime import datetime
from loguru import logger

from fund.db import FundDB


class PageBuilder:
    def __init__(self, db: FundDB, config: dict):
        self.db = db
        self.config = config
        page_cfg = config.get("page", {})
        self.output_dir = page_cfg.get("output_dir", "./output")
        self.top_n = page_cfg.get("top_n", 50)
        self.template_dir = page_cfg.get("od_template_dir", "")
        self.fund_types = config.get("fund_types", [])

    def _load_od_template(self, name: str) -> str:
        path = os.path.join(self.template_dir, f"{name}.html")
        if not os.path.exists(path):
            logger.warning(f"OD template not found: {path}, using fallback")
            return self._fallback_template(name)
        with open(path, "r", encoding="utf-8") as f:
            html = f.read()
        logger.info(f"Loaded OD template: {path} ({len(html)} bytes)")
        return html

    def _fallback_template(self, name: str) -> str:
        if name == "index":
            return '<!DOCTYPE html><html lang="zh-CN"><head><meta charset="UTF-8"><title>FundRecommender</title><style>:root{--accent:#0071e3}</style></head><body><div class="container"><div id="topCards"></div><div id="typeTabs"></div><table><tbody id="tableBody"></tbody></table><div id="chartTypeAvg"></div><div id="chartRiskReturn"></div><div id="chartTypeDist"></div></div></body></html>'
        if name == "detail":
            return '<!DOCTYPE html><html lang="zh-CN"><head><meta charset="UTF-8"><title>Fund Detail</title><style>:root{--accent:#0071e3}</style></head><body><div id="fundHero"></div><div id="fundAnalysis"></div><div id="chartRadar"></div></body></html>'
        return '<!DOCTYPE html><html><body></body></html>'

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

    def _inject_echarts_cdn(self, html: str) -> str:
        cdn = '<script src="https://cdn.jsdelivr.net/npm/echarts@5.5.0/dist/echarts.min.js"></script>\n</head>'
        return html.replace('</head>', cdn)

    def _inject_index_js(self, html: str, data: dict) -> str:
        funds_json = json.dumps(data, ensure_ascii=False)
        js_block = f"""<script>const DATA = {funds_json};</script>
<script>
let currentType='ALL';let currentSort={{field:'total_score',asc:false}};
function getFunds(){{let funds=DATA.scores;if(currentType!=='ALL'){{funds=funds.filter(f=>f.fund_type===currentType);}}funds=[...funds].sort((a,b)=>{{const av=a[currentSort.field]||0;const bv=b[currentSort.field]||0;return currentSort.asc?av-bv:bv-av;}});return funds;}}
function renderTabs(){{const tabs=document.getElementById('typeTabs');if(!tabs)return;const types=['ALL',...DATA.fund_types];tabs.innerHTML=types.map(t=>{{const label=t==='ALL'?'全部':t;const count=t==='ALL'?DATA.total_funds:(DATA.by_type[t]||[]).length;return '<span class="filter-tab'+(t===currentType?' active':'')+'" data-type="'+t+'">'+label+' ('+count+')</span>';}}).join('');}}
function renderTopCards(){{const container=document.getElementById('topCards');if(!container)return;const types=DATA.fund_types.filter(t=>DATA.by_type[t]&&DATA.by_type[t].length>0);let html='<div class="stat-card"><div class="label">覆盖基金</div><div class="value">'+DATA.total_funds.toLocaleString()+'</div><div class="sub">只</div></div>';types.forEach(t=>{{const top=DATA.by_type[t][0];if(top){{html+='<div class="stat-card"><div class="label">'+t+' Top1</div><div class="value accent">'+top.name+'</div><div class="sub">评分 '+top.total_score+' . 近1年 '+(top.return_1y||0).toFixed(1)+'%</div></div>';}}}});container.innerHTML=html;}}
function renderTable(){{const tbody=document.getElementById('tableBody');if(!tbody)return;const funds=getFunds();const bg={{'股票型':'stock','混合型':'mixed','指数型':'index','债券型':'bond'}};tbody.innerHTML=funds.map((f,i)=>{{const rc=i===0?'rank-1':i===1?'rank-2':i===2?'rank-3':'';const bc=bg[f.fund_type]||'mixed';const r1=f.return_1y||0;const r3=f.return_3y||0;const dd=f.max_drawdown||0;const sc=Math.min(100,f.total_score||0);return '<tr><td><span class="rank '+rc+'">'+(i+1)+'</span></td><td><span class="fund-name">'+f.name+'</span><span class="fund-code">'+f.code+'</span></td><td><span class="type-badge '+bc+'">'+f.fund_type+'</span></td><td><span class="score-bar"><span class="score-bar-fill" style="width:'+sc+'%"></span></span><span class="total-score">'+f.total_score+'</span></td><td class="sub-score">'+f.risk_score+'</td><td class="sub-score">'+f.perf_score+'</td><td class="sub-score">'+f.quality_score+'</td><td class="'+(r1>0?'positive':'negative')+'">'+(r1>0?'+':'')+r1.toFixed(1)+'%</td><td class="'+(r3>0?'positive':'negative')+'">'+(r3>0?'+':'')+r3.toFixed(1)+'%</td><td class="negative">'+dd.toFixed(1)+'%</td><td>'+(f.fund_size||0).toFixed(1)+'</td><td>'+(f.fee_rate||0).toFixed(2)+'%</td><td><a class="detail-arrow" href="detail.html?code='+f.code+'">&rarr;</a></td></tr>';}}).join('');}}
function sortTable(field){{if(currentSort.field===field){{currentSort.asc=!currentSort.asc;}}else{{currentSort={{field,asc:false}};}}renderTable();}}
function setupSortableHeaders(){{const ths=document.querySelectorAll('thead th');const fieldMap={{'总评分':'total_score','风险得分':'risk_score','业绩得分':'perf_score','质量得分':'quality_score','近1年':'return_1y','近3年':'return_3y','最大回撤':'max_drawdown','规模(亿)':'fund_size','费率':'fee_rate'}};ths.forEach(th=>{{const text=th.textContent.trim();const field=fieldMap[text];if(field){{th.style.cursor='pointer';th.title='点击排序';th.addEventListener('click',()=>sortTable(field));}}}});const sel=document.querySelector('.sort-select');if(sel){{const optMap={{'总评分':'total_score','近1年收益':'return_1y','近3年收益':'return_3y','夏普比率':'sharpe_ratio','最大回撤':'max_drawdown'}};sel.addEventListener('change',function(){{const f=optMap[this.value.trim()];if(f){{currentSort={{field:f,asc:false}};renderTable();}}}});}}const tabContainer=document.getElementById('typeTabs');if(tabContainer){{tabContainer.addEventListener('click',function(e){{const tab=e.target.closest('.filter-tab');if(tab){{currentType=tab.getAttribute('data-type');renderAll();}}}});}}}}
function renderAll(){{renderTabs();renderTopCards();renderTable();setupSortableHeaders();}}
function initCharts(){{if(typeof echarts==='undefined')return;const c1Dom=document.getElementById('chartTypeAvg');if(c1Dom){{const c1=echarts.init(c1Dom);const typeAvgs=DATA.fund_types.filter(t=>DATA.by_type[t]).map(t=>{{const funds=DATA.by_type[t];return {{name:t,value:Math.round(funds.reduce((s,f)=>s+f.total_score,0)/funds.length*10)/10}};}});c1.setOption({{title:{{text:'各类型平均评分',textStyle:{{fontSize:14}}}},tooltip:{{}},xAxis:{{type:'category',data:typeAvgs.map(d=>d.name),axisLabel:{{fontSize:11}}}},yAxis:{{type:'value',min:0,max:100}},series:[{{type:'bar',data:typeAvgs.map(d=>d.value),itemStyle:{{color:'#0071e3',borderRadius:[4,4,0,0]}}}}],grid:{{left:40,right:20,top:40,bottom:30}}}});}}const c2Dom=document.getElementById('chartRiskReturn');if(c2Dom){{const c2=echarts.init(c2Dom);const scatterData=DATA.scores.slice(0,50).map(f=>[f.max_drawdown||0,f.return_1y||0,f.name,f.total_score]);c2.setOption({{title:{{text:'Top50 风险vs收益',textStyle:{{fontSize:14}}}},tooltip:{{formatter:p=>p.value[2]+'<br/>回撤:'+p.value[0].toFixed(1)+'% 收益:'+p.value[1].toFixed(1)+'%'}},xAxis:{{name:'最大回撤(%)',nameLocation:'center',nameGap:25,axisLabel:{{fontSize:10}}}},yAxis:{{name:'近1年收益(%)',nameLocation:'center',nameGap:30,axisLabel:{{fontSize:10}}}},series:[{{type:'scatter',data:scatterData,symbolSize:v=>Math.max(6,v[3]/10),itemStyle:{{color:'#0071e3',opacity:0.6}}}}],grid:{{left:50,right:30,top:40,bottom:40}}}});}}const c3Dom=document.getElementById('chartTypeDist');if(c3Dom){{const c3=echarts.init(c3Dom);const pieData=DATA.fund_types.filter(t=>DATA.by_type[t]).map(t=>({{name:t,value:DATA.by_type[t].length}}));c3.setOption({{title:{{text:'推荐基金类型分布',textStyle:{{fontSize:14}}}},tooltip:{{trigger:'item'}},series:[{{type:'pie',radius:['40%','70%'],data:pieData,label:{{fontSize:10}}}}]}});}}}}
window.addEventListener('resize',()=>{{['chartTypeAvg','chartRiskReturn','chartTypeDist'].forEach(id=>{{const dom=document.getElementById(id);if(dom){{const inst=echarts.getInstanceByDom(dom);if(inst)inst.resize();}}}});}});
</script>
</body>"""
        return html.replace('</body>', js_block)

    def _write_index_html(self, data: dict):
        html = self._load_od_template("index")
        html = self._inject_echarts_cdn(html)
        html = self._inject_index_js(html, data)
        init_js = "<script>renderAll();initCharts();</script>\n</body>"
        html = html.replace('</body>', init_js)
        with open(os.path.join(self.output_dir, "index.html"), "w", encoding="utf-8") as f:
            f.write(html)

    def _write_detail_html(self):
        html = self._load_od_template("detail")
        html = self._inject_echarts_cdn(html)
        js_block = """<script>
const params=new URLSearchParams(window.location.search);
const code=params.get('code');
fetch('data.json').then(r=>r.json()).then(data=>{
  const f=data.scores.find(s=>s.code===code);
  if(!f){document.getElementById('fundHero').innerHTML='<h2>基金未找到</h2>';return;}
  const bg={'股票型':'stock','混合型':'mixed','指数型':'index','债券型':'bond'};
  const bc=bg[f.fund_type]||'mixed';const r1=f.return_1y||0;
  document.getElementById('fundHero').innerHTML=
    '<h1>'+f.name+'</h1><p class="code">'+f.code+' . <span class="type-badge '+bc+'">'+f.fund_type+'</span></p>'+
    '<div class="meta-grid">'+
    '<div class="meta-item"><div class="label">总评分</div><div class="value" style="color:var(--accent)">'+f.total_score+'</div></div>'+
    '<div class="meta-item"><div class="label">同类排名</div><div class="value">#'+f.rank_in_type+'</div></div>'+
    '<div class="meta-item"><div class="label">成立日期</div><div class="value">'+(f.establish_date||'-')+'</div></div>'+
    '<div class="meta-item"><div class="label">基金规模</div><div class="value">'+(f.fund_size||0).toFixed(1)+' 亿</div></div>'+
    '<div class="meta-item"><div class="label">管理费率</div><div class="value">'+(f.fee_rate||0).toFixed(2)+'%</div></div>'+
    '<div class="meta-item"><div class="label">基金经理</div><div class="value">'+(f.manager_name||'-')+'</div></div>'+
    '<div class="meta-item"><div class="label">机构占比</div><div class="value">'+((f.inst_ratio||0)*100).toFixed(1)+'%</div></div>'+
    '<div class="meta-item"><div class="label">近1年收益</div><div class="value" style="color:'+(r1>0?'var(--green)':'var(--red)')+'">'+(r1>0?'+':'')+r1.toFixed(1)+'%</div></div>'+
    '</div>'+
    '<div class="score-row">'+
    '<div class="score-box"><div class="num">'+f.risk_score+'</div><div class="lbl">风险调整收益</div></div>'+
    '<div class="score-box"><div class="num">'+f.perf_score+'</div><div class="lbl">中长期业绩</div></div>'+
    '<div class="score-box"><div class="num">'+f.quality_score+'</div><div class="lbl">基金质量</div></div>'+
    '<div class="score-box"><div class="num" style="color:'+(r1>0?'var(--green)':'var(--red)')+'">'+(r1>0?'+':'')+r1.toFixed(1)+'%</div><div class="lbl">近1年收益</div></div>'+
    '</div>';
  document.getElementById('fundAnalysis').innerHTML=
    '该基金综合评分'+f.total_score+'，同类排名#'+f.rank_in_type+'。夏普比率'+(f.sharpe_ratio||0).toFixed(2)+'，最大回撤'+(f.max_drawdown||0).toFixed(1)+'%。适合中长期持有，需警惕市场波动风险。';
  const radarDom=document.getElementById('chartRadar');
  if(radarDom&&typeof echarts!=='undefined'){
    const radar=echarts.init(radarDom);
    radar.setOption({title:{text:'评分雷达图',textStyle:{fontSize:14}},radar:{indicator:[
      {name:'风险调整',max:100},{name:'长期业绩',max:100},{name:'基金质量',max:100},
      {name:'近1年收益',max:100},{name:'风险控制',max:100}]},
      series:[{type:'radar',data:[{value:[f.risk_score,f.perf_score,f.quality_score,
      Math.min(100,(f.return_1y||0)+50),100-(f.max_drawdown||0)],name:f.name,
      areaStyle:{color:'rgba(0,113,227,0.2)'},lineStyle:{color:'#0071e3'}}]}]});
  }
});
</script></body>"""
        html = html.replace('</body>', js_block)
        with open(os.path.join(self.output_dir, "detail.html"), "w", encoding="utf-8") as f:
            f.write(html)

    def _write_history_html(self):
        html = """<!DOCTYPE html>
<html lang="zh-CN">
<head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>FundRecommender - 历史追踪</title>
<script src="https://cdn.jsdelivr.net/npm/echarts@5.5.0/dist/echarts.min.js"></script>
<style>
:root{--bg:#f5f5f7;--card:#fff;--text:#1d1d1f;--text-secondary:#86868b;--border:#e5e5ea;--accent:#0071e3;--radius:14px;--shadow:0 1px 3px rgba(0,0,0,0.06);--font:-apple-system,BlinkMacSystemFont,'SF Pro Display','PingFang SC',sans-serif}
*{margin:0;padding:0;box-sizing:border-box}
body{font-family:var(--font);background:var(--bg);color:var(--text);line-height:1.5}
.container{max-width:1200px;margin:0 auto;padding:24px}
.back-link{display:inline-block;margin-bottom:16px;color:var(--accent);text-decoration:none}
.chart-box{height:360px;background:var(--card);border-radius:var(--radius);padding:20px;box-shadow:var(--shadow)}
.footer{text-align:center;padding:32px 0;border-top:1px solid var(--border);margin-top:24px;font-size:12px;color:var(--text-secondary)}
</style></head>
<body><div class="container">
<a class="back-link" href="index.html">&larr; 返回排行榜</a>
<h2 style="margin-bottom:16px">评分历史追踪</h2>
<div class="chart-box" id="chartTrend"></div>
<footer class="footer"><p>⚠️ 本工具仅提供基于历史数据的基金质量评分和排序，不构成任何投资建议。</p></footer>
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
</script></body></html>"""
        with open(os.path.join(self.output_dir, "history.html"), "w", encoding="utf-8") as f:
            f.write(html)
