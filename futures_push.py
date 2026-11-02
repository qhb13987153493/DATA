# encoding:utf-8
import os, json, requests, datetime

# ================= 你的账户核心数据 =================
CAPITAL = 289485
POSITIONS = [
    {"name": "甲醇2701", "dir": "空", "lots": 7, "avg": 2889.43, "pnl": -37910},
    {"name": "甲醇2701", "dir": "多", "lots": 2, "avg": 3051.50, "pnl": 7590},
    {"name": "PVC2701", "dir": "空", "lots": 13, "avg": 5096.46, "pnl": -11735},
]
TOTAL_PNL = -42055
MULTIPLIER = {"甲醇": 10, "PVC": 5, "白糖": 10}
# ====================================================

def get_quotes():
    symbols = {"甲醇": "nf_MA2701", "PVC": "nf_V2701", "白糖": "nf_SR2701"}
    url = "http://hq.sinajs.cn/list=" + ",".join(symbols.values())
    headers = {"Referer": "http://finance.sina.com.cn"}
    data = requests.get(url, headers=headers, timeout=10).text
    quotes = []
    for line in data.strip().split('\n'):
        parts = line.split('"')[1].split(',')
        if len(parts) > 8:
            name_code = parts[0]
            name = "".join([c for c in name_code if not c.isdigit()])
            code = "".join([c for c in name_code if c.isdigit()])
            val1 = float(parts[2]) if parts[2] else 0
            val2 = float(parts[3]) if parts[3] else 0
            high = max(val1, val2)
            low = min(val1, val2)
            price = float(parts[8]) if parts[8] else float(parts[4])
            pre_settle = float(parts[4]) if parts[4] else 1
            pct = round((price - pre_settle) / pre_settle * 100, 2) if pre_settle != 0 else 0
            color = "#b71c1c" if pct >= 0 else "#1b5e20"
            quotes.append({"name": name, "code": code, "price": price, "pct": pct, "high": high, "low": low, "color": color})
    return quotes

def get_simple_analysis(q):
    diff = (q["high"] - q["low"]) if q["high"] > q["low"] else 10
    amp = round(diff / q["price"] * 100, 2)
    
    # 1. 大白话判定趋势阶段
    if q["pct"] > 2.0: 
        stage = "疯狂拉升阶段"
        trend_desc = "涨得很凶，容易上头，千万别在此时追高。"
    elif q["pct"] > 0.5: 
        stage = "稳步爬升阶段"
        trend_desc = "慢慢往上涨，走得很稳。"
    elif q["pct"] < -2.0: 
        stage = "加速跳水阶段"
        trend_desc = "跌得太猛，像接飞刀，千万别急着去抄底。"
    elif q["pct"] < -0.5: 
        stage = "阴跌磨人阶段"
        trend_desc = "慢慢往下跌，反弹没啥力气，尽量别碰。"
    else: 
        stage = "横盘睡觉阶段"
        trend_desc = "不上不下，在里面来回晃荡，方向不明。"

    # 2. 大白话判定买卖力量（量价）
    if amp > 2.5 and q["pct"] > 0: 
        volume = "今天成交量很大，大家都在抢着买，抢得很激烈。"
    elif amp > 2.5 and q["pct"] < 0: 
        volume = "今天成交量很大，大家都在恐慌卖，抛压很重。"
    elif amp < 1.5 and q["pct"] > 0: 
        volume = "没什么成交量，慢慢往上蹭，没多少人真的跟风。"
    elif amp < 1.5 and q["pct"] < 0: 
        volume = "没什么成交量，大家都在熬，跌也跌不动了。"
    else: 
        volume = "买卖双方都在试探，谁也没占到大便宜。"

    support = round(q["low"] - diff * 0.2, 1)
    pressure = round(q["high"] + diff * 0.2, 1)
    
    return stage, trend_desc, volume, support, pressure

def build_html():
    now = (datetime.datetime.utcnow() + datetime.timedelta(hours=8)).strftime('%m-%d %H:%M')
    quotes = get_quotes()

    html = f'<div style="font-family:-apple-system,sans-serif;max-width:600px;color:#222;font-size:14px;">'
    html += f'<div style="background:linear-gradient(135deg,#1a3c6e,#2b5aa0);color:#fff;text-align:center;padding:12px;border-radius:8px;font-size:16px;font-weight:bold;">期货速览大白话<br><span style="font-size:12px;">{now} | 权益:{CAPITAL:,}</span></div>'

    # ================= 第一部分：置顶速览 =================
    html += f'<div style="background:#e3f2fd;border:1px solid #90caf9;border-radius:8px;padding:12px;margin:12px 0;">'
    html += f'<div style="font-size:15px;font-weight:bold;color:#1565c0;margin-bottom:8px;">📌 核心速览（一眼看懂）</div>'
    
    for q in quotes:
        stage, trend_desc, volume, support, pressure = get_simple_analysis(q)
        html += f'<div style="margin-bottom:8px; padding-bottom:8px; border-bottom:1px dashed #90caf9;">'
        html += f'<b>{q["name"]} {q["code"]}</b>：<span style="color:{q["color"]};font-weight:bold;font-size:16px;">{q["price"]}</span> ({q["pct"]:+.2f}%)<br>'
        html += f'👉 <b>当前阶段：</b>{stage} <br>'
        html += f'💬 <b>一句话评价：</b>{trend_desc}'
        html += f'</div>'
    html += f'</div>'

    # ================= 第二部分：详细拆解 =================
    html += f'<div style="font-size:15px;font-weight:bold;margin:15px 0 10px 0;color:#333;">🔍 深度拆解分析</div>'

    for q in quotes:
        stage, trend_desc, volume, support, pressure = get_simple_analysis(q)
        html += f'<div style="background:#f5f7fa;border-left:4px solid {q["color"]};border-radius:6px;padding:12px;margin-bottom:12px;box-shadow:0 1px 3px rgba(0,0,0,0.05);">'
        html += f'<div style="font-size:16px;font-weight:bold;margin-bottom:8px;border-bottom:1px solid #ddd;padding-bottom:4px;">{q["name"]} {q["code"]}</div>'
        
        html += f'<div style="color:#444;font-size:13px;line-height:1.7;">'
        html += f'<b>👀 资金在干嘛：</b>{volume}<br>'
        html += f'<b>🧭 大方向：</b>目前价格在 <b>{q["low"]}</b> 到 <b>{q["high"]}</b> 之间。{trend_desc}<br>'
        html += f'<b>🧱 防守底线：</b><br>'
        html += f'跌到 <b>{support}</b> 附近，看有没有人愿意花钱接盘（跌不动了可以买）<br>'
        html += f'涨到 <b>{pressure}</b> 附近，看是不是有人大量抛售（涨不动了可以卖）'
        html += f'</div></div>'

    # ================= 第三部分：资金阶梯 =================
    html += f'<div style="background:#fff3e0;border-left:4px solid #f57c00;border-radius:6px;padding:12px;margin:10px 0;">'
    html += f'<div style="font-size:15px;font-weight:bold;margin-bottom:8px;color:#e65100;">💰 资金阶梯分配表</div>'
    for q in quotes:
        m = MULTIPLIER.get(q["name"], 10)
        margin = round(q["price"] * m * 0.10)
        first = max(int(CAPITAL * 0.20 / margin), 1)
        add_lot = max(int(CAPITAL * 0.30 / margin), 1)
        cap = max(int(CAPITAL * 0.60 / margin), 1)
        html += f'<div style="font-size:13px;line-height:1.6;margin-bottom:6px;">'
        html += f'<b>{q["name"]}</b>：占用的钱少。首仓买 <b>{first}手</b> → 涨对了再加仓到 {first+add_lot}手 → 最多绝对不超过 <b>{cap}手</b>'
        html += f'</div>'
    html += f'<div style="font-size:12px;color:#bf360c;margin-top:6px;font-weight:bold;">⚠️ 注意：上限是“最多能买这么多”，不是让你全买满！</div>'
    html += f'</div>'

    # ================= 第四部分：持仓急救 =================
    if POSITIONS:
        html += f'<div style="background:#ffebee;border-left:4px solid #d32f2f;border-radius:6px;padding:12px;margin:10px 0;">'
        html += f'<div style="font-size:15px;font-weight:bold;margin-bottom:8px;color:#b71c1c;">🚨 持仓急救（总亏 {TOTAL_PNL:,} 元）</div>'
        for p in POSITIONS:
            html += f'<div style="font-size:13px;line-height:1.6;margin-bottom:4px;">{p["name"]} <b>{p["dir"]}{p["lots"]}手</b> (均价{p["avg"]}) | 盈亏: {p["pnl"]:+}元</div>'
        html += f'<div style="font-size:13px;color:#b71c1c;background:#fff;padding:8px;border-radius:4px;margin-top:8px;border:1px solid #ffcdd2;">'
        html += f'<b>大白话建议：</b>你现在亏钱的都是“逆势单”。别死扛了！只要跌破了上面的支撑位，就赶紧减掉一半；如果放量涨过了压力位，剩下的全平掉认错。千万别再往里加钱了！'
        html += f'</div></div>'

    html += f'<div style="color:#888;font-size:12px;text-align:center;margin-top:15px;">数据来源新浪财经，不构成投资建议</div>'
    return html

def main():
    token = os.environ.get("PUSHPLUS_TOKEN")
    if not token:
        print("❌ 未在Secrets中配置PUSHPLUS_TOKEN")
        return
    content = build_html()
    payload = {"token": token, "title": "期货大白话速览", "content": content, "template": "html"}
    try:
        resp = requests.post("https://www.pushplus.plus/send", json=payload, timeout=30)
        result = resp.json()
        if result.get("code") == 200:
            print("✅ 推送成功")
        else:
            print(f"❌ 推送失败: {result.get('msg')}")
    except Exception as e:
        print(f"❌ 网络错误: {e}")

if __name__ == "__main__":
    main()
