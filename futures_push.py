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
            name = parts[0]
            price = float(parts[8]) if parts[8] else float(parts[4])
            pct = round((price - float(parts[4])) / float(parts[4]) * 100, 2) if parts[4] != '0.000' else 0
            color = "#b71c1c" if pct >= 0 else "#1b5e20"
            quotes.append({"name": name, "price": price, "pct": pct, "color": color})
    return quotes

def build_html():
    now = datetime.datetime.now().strftime('%Y-%m-%d %H:%M')
    quotes = get_quotes()
    html = f'<div style="font-family:sans-serif;max-width:600px;color:#222;">'
    html += f'<div style="background:#1a3c6e;color:#fff;text-align:center;padding:12px;border-radius:8px;font-size:17px;">期货速查卡<br>{now}</div>'
    for q in quotes:
        html += f'<div style="background:#f5f7fa;border-radius:8px;padding:10px;margin:10px 0;">'
        html += f'<b>{q["name"]}</b> <span style="color:{q["color"]};font-weight:bold;">{q["price"]} ({q["pct"]:+.2f}%)</span>'
        html += f'</div>'
    html += f'<div style="color:#888;font-size:12px;text-align:center;margin-top:10px;">数据仅供参考，不构成投资建议</div>'
    return html

def main():
    token = os.environ.get("PUSHPLUS_TOKEN")
    if not token:
        print("❌ 未在Secrets中配置PUSHPLUS_TOKEN")
        return
    content = build_html()
    payload = {"token": token, "title": "期货速查卡", "content": content, "template": "html"}
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
