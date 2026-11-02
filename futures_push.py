# encoding:utf-8
import os, json, requests, datetime

# ================= 你的账户核心数据 =================
CAPITAL = 289485
VIX = 17.52
POSITIONS = [
    {"name": "甲醇2701", "dir": "空", "lots": 7, "avg": 2889.43, "pnl": -37910},
    {"name": "甲醇2701", "dir": "多", "lots": 2, "avg": 3051.50, "pnl": 7590},
    {"name": "PVC2701", "dir": "空", "lots": 13, "avg": 5096.46, "pnl": -11735},
]
TOTAL_PNL = -42055
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

def build_html():
    now = (datetime.datetime.utcnow() + datetime.timedelta(hours=8)).strftime('%m-%d %H:%M')
    quotes = get_quotes()
    
    # 异动检测逻辑
    is_alert = False
    alert_msg = ""
    for q in quotes:
        if q["pct"] >= 2.5:
            is_alert = True
            alert_msg += f"🚨 {q['name']} 急涨 {q['pct']}%！ "
        elif q["pct"] <= -2.5:
            is_alert = True
            alert_msg += f"🚨 {q['name']} 急跌 {q['pct']}%！ "

    title = "🚨 盘面异动加急警报" if is_alert else "期货盯盘速查卡"
    
    html = f'<div style="font-family:-apple-system,sans-serif;max-width:600px;color:#222;font-size:14px;">'
    
    # 异动横幅
    if is_alert:
        html += f'<div style="background:#d32f2f;color:#fff;padding:12px;border-radius:8px;text-align:center;font-weight:bold;margin-bottom:10px;font-size:16px;">{alert_msg}<br>请立刻打开交易软件！</div>'

    html += f'<div style="background:linear-gradient(135deg,#1a3c6e,#2b5aa0);color:#fff;text-align:center;padding:12px;border-radius:8px;font-size:16px;font-weight:bold;">期货监控速查卡<br><span style="font-size:12px;">{now} | 权益:{CAPITAL:,}</span></div>'
    
    for q in quotes:
        trend = "偏强" if q["pct"] > 0.5 else ("偏弱" if q["pct"] < -0.5 else "震荡")
        diff = (q["high"] - q["low"]) if q["high"] > q["low"] else 10
        support = round(q["low"] - diff*0.2, 1)
        pressure = round(q["high"] + diff*0.2, 1)
        
        html += f'<div style="background:#f5f7fa;border-left:4px solid {q["color"]};border-radius:6px;padding:10px 12px;margin:10px 0;">'
        html += f'<div style="font-size:16px;font-weight:bold;margin-bottom:6px;">{q["name"]} <span style="font-size:12px;color:#666;">{q["code"]}</span></div>'
        html += f'<div style="margin-bottom:6px;"><span style="color:{q["color"]};font-size:18px;font-weight:bold;">{q["price"]}</span> <span style="color:{q["color"]};font-size:14px;">({q["pct"]:+.2f}%)</span> | <b>{trend}</b></div>'
        html += f'<div style="color:#444;font-size:13px;line-height:1.5;">'
        html += f'今日区间：<b>{q["low"]} - {q["high"]}</b><br>'
        html += f'📉 跌到 <b>{support}</b> 附近看有没有人接 ｜ 📈 涨到 <b>{pressure}</b> 附近有人卖<br>'
        html += f'👉 <b>怎么做：</b>盯紧 <b>{q["low"]}</b> 支撑和 <b>{q["high"]}</b> 压力，跌破防守，突破顺势。'
        html += f'</div></div>'

    if POSITIONS:
        html += f'<div style="background:#fdecec;border-left:4px solid #d32f2f;border-radius:6px;padding:10px 12px;margin:10px 0;">'
        html += f'<div style="font-size:16px;font-weight:bold;margin-bottom:6px;">⚠️ 持仓风控急救</div>'
        for p in POSITIONS:
            html += f'<div style="font-size:13px;line-height:1.6;">{p["name"]} <b>{p["dir"]}{p["lots"]}手</b> (均价{p["avg"]}) | <span style="color:#b71c1c;">{p["pnl"]:+}元</span></div>'
        html += f'<div style="margin-top:8px;font-size:13px;color:#7a4a00;background:#fff3e0;padding:6px;border-radius:4px;">'
        html += f'<b>纪律：</b>总浮亏 {TOTAL_PNL:,} 元。先减逆势单！跌破支撑减仓，放量突破压力全平认错；绝不加仓扛单。'
        html += f'</div></div>'

    html += f'<div style="color:#888;font-size:12px;text-align:center;margin-top:15px;">VIX: {VIX} ｜ 数据来源新浪财经，存在时滞，不构成投资建议</div>'
    return title, html

def main():
    token = os.environ.get("PUSHPLUS_TOKEN")
    if not token:
        print("❌ 未在Secrets中配置PUSHPLUS_TOKEN")
        return
    title, content = build_html()
    payload = {"token": token, "title": title, "content": content, "template": "html"}
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
