# encoding:utf-8
import os, json, requests, datetime

def get_quotes():
    # 新浪期货接口
    symbols = {"甲醇": "nf_MA2701", "PVC": "nf_V2701", "白糖": "nf_SR2701"}
    url = "http://hq.sinajs.cn/list=" + ",".join(symbols.values())
    headers = {"Referer": "http://finance.sina.com.cn"}
    data = requests.get(url, headers=headers, timeout=10).text
    quotes = []
    for line in data.strip().split('\n'):
        parts = line.split('"')[1].split(',')
        if len(parts) > 8:
            name_code = parts[0] # 例如：甲醇2701
            # 简单分离名字和代码
            name = "".join([c for c in name_code if not c.isdigit()])
            code = "".join([c for c in name_code if c.isdigit()])
            
            high = float(parts[2]) if parts[2] else 0
            low = float(parts[3]) if parts[3] else 0
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
    # 修正为北京时间 (UTC+8)
    now = (datetime.datetime.utcnow() + datetime.timedelta(hours=8)).strftime('%m-%d %H:%M')
    quotes = get_quotes()
    
    html = f'<div style="font-family:-apple-system,sans-serif;max-width:600px;color:#222;font-size:14px;">'
    html += f'<div style="background:linear-gradient(135deg,#1a3c6e,#2b5aa0);color:#fff;text-align:center;padding:12px;border-radius:8px;font-size:16px;font-weight:bold;">期货实时速查卡<br><span style="font-size:12px;">{now}</span></div>'
    
    for q in quotes:
        # 简单的自动分析规则
        trend = "偏强" if q["pct"] > 0.5 else ("偏弱" if q["pct"] < -0.5 else "震荡")
        support = round(q["low"] - (q["high"]-q["low"])*0.2, 1)
        pressure = round(q["high"] + (q["high"]-q["low"])*0.2, 1)
        
        html += f'<div style="background:#f5f7fa;border-left:4px solid {q["color"]};border-radius:6px;padding:10px 12px;margin:10px 0;box-shadow:0 2px 4px rgba(0,0,0,0.05);">'
        html += f'<div style="font-size:16px;font-weight:bold;margin-bottom:6px;">{q["name"]} <span style="font-size:12px;color:#666;">{q["code"]}</span></div>'
        html += f'<div style="margin-bottom:6px;"><span style="color:{q["color"]};font-size:18px;font-weight:bold;">{q["price"]}</span> <span style="color:{q["color"]};font-size:14px;">({q["pct"]:+.2f}%)</span> | <b>{trend}</b></div>'
        html += f'<div style="color:#444;font-size:13px;line-height:1.5;">'
        html += f'今日区间：{q["low"]} - {q["high"]}<br>'
        html += f'📉 跌到 <b>{support}</b> 附近看有没有人接 ｜ 📈 涨到 <b>{pressure}</b> 附近有人卖<br>'
        html += f'👉 <b>怎么做：</b>盯紧 {q["low"]} 支撑和 {q["high"]} 压力，突破顺势，跌破防守。'
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
