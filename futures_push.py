# encoding:utf-8
import os, json, requests, datetime

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
            
            # 兼容处理新浪接口的数据错位：强行判断谁高谁低
            val1 = float(parts[2]) if parts[2] else 0
            val2 = float(parts[3]) if parts[3] else 0
            high = max(val1, val2)
            low = min(val1, val2)
            
            price = float(parts[8]) if parts[8] else float(parts[4])
            pre_settle = float(parts[4]) if parts[4] else 1
            
            pct = round((price - pre_settle) / pre_settle * 100, 2) if pre_settle != 0 else 0
            color = "#b71c1c" if pct >= 0 else "#1b5e20"
            
            quotes.append({
                "name": name, "code": code, "price": price, "pct": pct, 
                "high": high, "low": low, "color": color
            })
    return quotes

def build_html():
    now = (datetime.datetime.utcnow() + datetime.timedelta(hours=8)).strftime('%m-%d %H:%M')
    quotes = get_quotes()
    
    html = f'<div style="font-family:-apple-system,sans-serif;max-width:600px;color:#222;font-size:14px;">'
    html += f'<div style="background:linear-gradient(135deg,#1a3c6e,#2b5aa0);color:#fff;text-align:center;padding:12px;border-radius:8px;font-size:16px;font-weight:bold;">期货实时速查卡<br><span style="font-size:12px;">{now}</span></div>'
    
    for q in quotes:
        trend = "偏强" if q["pct"] > 0.5 else ("偏弱" if q["pct"] < -0.5 else "震荡")
        # 如果高低点一样（可能还没开盘），给个默认偏移量
        diff = (q["high"] - q["low"]) if q["high"] > q["low"] else 10
        support = round(q["low"] - diff*0.2, 1)
        pressure = round(q["high"] + diff*0.2, 1)
        
        html += f'<div style="background:#f5f7fa;border-left:4px solid {q["color"]};border-radius:6px;padding:10px 12px;margin:10px 0;box-shadow:0 2px 4px rgba(0,0,0,0.05);">'
        html += f'<div style="font-size:16px;font-weight:bold;margin-bottom:6px;">{q["name"]} <span style="font-size:12px;color:#666;">{q["code"]}</span></div>'
        html += f'<div style="margin-bottom:6px;"><span style="color:{q["color"]};font-size:18px;font-weight:bold;">{q["price"]}</span> <span style="color:{q["color"]};font-size:14px;">({q["pct"]:+.2f}%)</span> | <b>{trend}</b></div>'
        html += f'<div style="color:#444;font-size:13px;line-height:1.5;">'
        html += f'今日区间：<b>{q["low"]} - {q["high"]}</b><br>'
        html += f'📉 跌到 <b>{support}</b> 附近看有没有人接 ｜ 📈 涨到 <b>{pressure}</b> 附近有人卖<br>'
        html += f'👉 <b>怎么做：</b>盯紧 <b>{q["low"]}</b> 支撑和 <b>{q["high"]}</b> 压力，跌破支撑防守，突破压力顺势。'
        html += f'</div></div>'
        
    html += f'<div style="color:#888;font-size:12px;text-align:center;margin-top:15px;">数据来源新浪财经，存在时滞，不构成投资建议</div>'
    return html

def main():
    token = os.environ.get("PUSHPLUS_TOKEN")
    if not token:
        print("❌ 未在Secrets中配置PUSHPLUS_TOKEN")
        return
    content = build_html()
    payload = {"token": token, "title": "期货实时速查卡", "content": content, "template": "html"}
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
