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

# 获取实时期货价格 (包含开、高、低、现价)
def get_realtime_quotes():
    symbols = {"甲醇": "nf_MA2701", "PVC": "nf_V2701", "白糖": "nf_SR2701"}
    url = "http://hq.sinajs.cn/list=" + ",".join(symbols.values())
    headers = {"Referer": "http://finance.sina.com.cn"}
    try:
        data = requests.get(url, headers=headers, timeout=10).text
        quotes = []
        for line in data.strip().split('\n'):
            parts = line.split('"')[1].split(',')
            if len(parts) > 8:
                name_code = parts[0]
                name = "".join([c for c in name_code if not c.isdigit()])
                code = "".join([c for c in name_code if c.isdigit()])
                
                open_p = float(parts[1]) if parts[1] else 0
                high_p = float(parts[2]) if parts[2] else 0
                low_p = float(parts[3]) if parts[3] else 0
                price = float(parts[8]) if parts[8] else float(parts[4])
                pre_settle = float(parts[4]) if parts[4] else 1
                
                pct = round((price - pre_settle) / pre_settle * 100, 2) if pre_settle != 0 else 0
                color = "#b71c1c" if pct >= 0 else "#1b5e20"
                
                quotes.append({
                    "name": name, "code": code, "price": price, "pct": pct, "color": color,
                    "open": open_p, "high": max(high_p, low_p), "low": min(high_p, low_p)
                })
        return quotes
    except Exception as e:
        return []

# ================= 日内指标推演算法 =================
def get_dynamic_analysis(q):
    open_p = q["open"]
    high_p = q["high"]
    low_p = q["low"]
    price = q["price"]
    
    if high_p == low_p:
        return "日内震荡", "今天还没啥波动，都在观望。", "动能未明", "温度未知"
        
    # 算振幅
    amp = round((high_p - low_p) / low_p * 100, 2)
    
    # 1. 判断大方向 (价格在日内区间的位置)
    # 如果收盘价在日内最高点的 80% 以上，说明强势
    if price >= low_p + (high_p - low_p) * 0.8:
        stage = "多头强势"
        trend_desc = f"价格收在全天最高点附近（{price}），大方向偏多，多头占绝对优势。"
    # 如果收盘价在日内最低点的 20% 以下，说明弱势
    elif price <= low_p + (high_p - low_p) * 0.2:
        stage = "空头强势"
        trend_desc = f"价格收在全天最低点附近（{price}），大方向偏空，空头在疯狂砸盘。"
    else:
        stage = "多空震荡"
        trend_desc = "价格卡在全天中间位置，多空双方互道SB，没分出胜负。"

    # 2. 判断资金动能 (开盘价与现价的关系)
    if price > open_p and price >= high_p - (high_p - low_p) * 0.1:
        macd_momentum = "开盘后就一路往上拉，资金在抢筹码，多头动能极其充沛。"
    elif price < open_p and price <= low_p + (high_p - low_p) * 0.1:
        macd_momentum = "开盘后就一路往下砸，资金在疯狂出逃，空头动能极强。"
    elif price > open_p:
        macd_momentum = "虽然收红，但冲高回落了，资金在逢高撤退，上方压力大。"
    elif price < open_p:
        macd_momentum = "虽然收绿，但探底回升了，资金在逢低接盘，下方有支撑。"
    else:
        macd_momentum = "围绕开盘价上下震荡，资金没明确方向。"

    # 3. 判断短线情绪 (振幅)
    if amp > 3.0:
        kdj_momentum = f"今天振幅高达{amp}%，波动极其剧烈，短线情绪过热，随时会暴力洗盘。"
    elif amp > 1.5:
        kdj_momentum = f"今天振幅{amp}%，波动正常，跟着大方向做就行。"
    else:
        kdj_momentum = f"今天振幅只有{amp}%，像一潭死水，尽量别去碰。"
        
    return stage, trend_desc, macd_momentum, kdj_momentum

def build_html():
    now = (datetime.datetime.utcnow() + datetime.timedelta(hours=8)).strftime('%m-%d %H:%M')
    quotes = get_realtime_quotes()

    html = f'<div style="font-family:-apple-system,sans-serif;max-width:600px;color:#000;font-size:14px;">'
    html += f'<div style="background:linear-gradient(135deg,#1a3c6e,#2b5aa0);color:#fff;text-align:center;padding:12px;border-radius:8px;font-size:16px;font-weight:bold;">期货深度盯盘（日内版）<br><span style="font-size:12px;">{now} | 权益:{CAPITAL:,}</span></div>'

    html += f'<div style="font-size:16px;font-weight:bold;margin:15px 0 10px 0;text-align:center;color:#000;">📌 核心速览（多红空绿）</div>'

    for q in quotes:
        stage, trend_desc, macd_desc, kdj_desc = get_dynamic_analysis(q)
        
        if q["pct"] > 0:
            bg_color, border_color = "#fff5f5", "#ff4d4f"
        elif q["pct"] < 0:
            bg_color, border_color = "#f6ffed", "#52c41a"
        else:
            bg_color, border_color = "#f5f5f5", "#d9d9d9"

        html += f'<div style="background:{bg_color}; border:2px solid {border_color}; border-radius:8px; padding:12px; margin-bottom:12px; box-shadow:0 2px 4px rgba(0,0,0,0.05);">'
        
        html += f'<div style="font-size:16px; font-weight:bold; color:#000; margin-bottom:8px; border-bottom:1px dashed #ccc; padding-bottom:6px;">'
        html += f'{q["name"]} {q["code"]}：<span style="color:{q["color"]}; font-size:20px;">{q["price"]}</span> <span style="color:{q["color"]}; font-size:14px;">({q["pct"]:+.2f}%)</span>'
        html += f'</div>'
        
        html += f'<div style="color:#000; font-size:14px; line-height:1.7;">'
        html += f'👉 <b>当前阶段：</b><span style="font-size:16px; font-weight:bold;">{stage}</span><br>'
        html += f'💬 <b>大白话趋势：</b>{trend_desc}<br>'
        html += f'🔥 <b>资金动能：</b>{macd_desc}<br>'
        html += f'🌡️ <b>短线温度：</b>{kdj_desc}'
        html += f'</div></div>'

    html += f'<div style="background:#fff3e0;border-left:4px solid #f57c00;border-radius:6px;padding:12px;margin:15px 0 10px 0;">'
    html += f'<div style="font-size:16px;font-weight:bold;margin-bottom:8px;color:#000;">💰 资金阶梯分配表</div>'
    for q in quotes:
        m = MULTIPLIER.get(q["name"], 10)
        margin = round(q["price"] * m * 0.10)
        first = max(int(CAPITAL * 0.20 / margin), 1)
        add_lot = max(int(CAPITAL * 0.30 / margin), 1)
        cap = max(int(CAPITAL * 0.60 / margin), 1)
        html += f'<div style="font-size:13px;line-height:1.6;margin-bottom:6px;color:#000;">'
        html += f'<b>{q["name"]}</b>：首仓买 <b>{first}手</b> → 加仓到 {first+add_lot}手 → 最多不超过 <b>{cap}手</b>'
        html += f'</div>'
    html += f'<div style="font-size:12px;color:#000;margin-top:6px;font-weight:bold;">⚠️ 注意：上限是“最多能买这么多”，不是让你全买满！</div>'
    html += f'</div>'

    if POSITIONS:
        html += f'<div style="background:#ffebee;border-left:4px solid #d32f2f;border-radius:6px;padding:12px;margin:10px 0;">'
        html += f'<div style="font-size:16px;font-weight:bold;margin-bottom:8px;color:#000;">🚨 持仓急救（总亏 {TOTAL_PNL:,} 元）</div>'
        for p in POSITIONS:
            html += f'<div style="font-size:13px;line-height:1.6;margin-bottom:4px;color:#000;">{p["name"]} <b>{p["dir"]}{p["lots"]}手</b> (均价{p["avg"]}) | 盈亏: {p["pnl"]:+}元</div>'
        html += f'<div style="font-size:13px;color:#000;background:#fff;padding:8px;border-radius:4px;margin-top:8px;border:1px solid #ffcdd2;">'
        html += f'<b>大白话建议：</b>你手里拿的是空单，如果上面的分析显示目前是“多头强势”，千万别逆势加仓，赶紧找机会减仓。'
        html += f'</div></div>'

    html += f'<div style="color:#666;font-size:12px;text-align:center;margin-top:15px;">数据来源：新浪财经 | 综合日内趋势判定</div>'
    return html

def main():
    token = os.environ.get("PUSHPLUS_TOKEN")
    if not token:
        print("❌ 未在Secrets中配置PUSHPLUS_TOKEN")
        return
    content = build_html()
    payload = {"token": token, "title": "期货深度盯盘（日内版）", "content": content, "template": "html"}
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
