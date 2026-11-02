# encoding:utf-8
import os, json, requests, datetime
import pandas as pd
import yfinance as yf

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

# 获取实时期货价格
def get_realtime_quotes():
    symbols = {"甲醇": "nf_MA2701", "PVC": "nf_V2701", "白糖": "nf_SR2701"}
    url = "http://hq.sinajs.cn/list=" + ",".join(symbols.values())
    headers = {"Referer": "http://finance.sina.com.cn"}
    try:
        data = requests.get(url, headers=headers, timeout=10).text
        quotes = []
        for line in data.strip().split('\n'):
            parts = line.split('"')[1].split(',')
            if len(parts) > 14:
                name_code = parts[0]
                name = "".join([c for c in name_code if not c.isdigit()])
                code = "".join([c for c in name_code if c.isdigit()])
                price = float(parts[8]) if parts[8] else float(parts[4])
                pre_settle = float(parts[4]) if parts[4] else 1
                pct = round((price - pre_settle) / pre_settle * 100, 2) if pre_settle != 0 else 0
                color = "#b71c1c" if pct >= 0 else "#1b5e20"
                quotes.append({
                    "name": name, "code": code, "price": price, "pct": pct, "color": color,
                    "open": float(parts[1]) if parts[1] else 0, 
                    "high": max(float(parts[2]), float(parts[3])), 
                    "low": min(float(parts[2]), float(parts[3])),
                    "oi": float(parts[13]) if parts[13] else 0
                })
        return quotes
    except:
        return []

# 获取 VIX
def get_vix():
    try:
        vix_data = yf.Ticker("^VIX").history(period="2d")
        if len(vix_data) >= 2:
            vix_last = vix_data['Close'].iloc[-1]
            vix_prev = vix_data['Close'].iloc[-2]
            vix_pct = round((vix_last - vix_prev) / vix_prev * 100, 2)
            return f"{vix_last:.2f} ({vix_pct:+.2f}%)"
    except:
        pass
    return "17.52 (获取失败)"

# ================= 多平台容灾获取K线 =================
def fetch_kline_multi_source(name, code):
    symbol_sina = f"{name}{code}"
    prefix = {"甲醇": "MA", "PVC": "V", "白糖": "SR"}.get(name, "")
    symbol_tx = f"{prefix}{code}"
    
    # 东财 Secid: 甲醇/白糖 115，PVC 114
    secid_prefix = "115" if name in ["甲醇", "白糖"] else "114"
    secid = f"{secid_prefix}.{symbol_tx}"
    
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}

    # 尝试 1：东方财富
    try:
        url_em = f"https://push2his.eastmoney.com/api/qt/stock/kline/get?secid={secid}&fields1=f1,f2,f3,f4,f5,f6&fields2=f51,f52,f53,f54,f55,f56&klt=101&fqt=0&end=20500101&lmt=120"
        res = requests.get(url_em, headers=headers, timeout=5).json()
        if res.get('data') and res['data'].get('klines'):
            klines = res['data']['klines']
            return [{'close': float(k.split(',')[2]), 'high': float(k.split(',')[3]), 'low': float(k.split(',')[4])} for k in klines]
    except:
        pass

    # 尝试 2：腾讯财经
    try:
        url_tx = f"https://web.ifzq.gtimg.cn/appstock/app/kline/kline?param={symbol_tx},day,,,120"
        res = requests.get(url_tx, headers=headers, timeout=5).json()
        klines = res['data'][symbol_tx]['day']
        return [{'close': float(k[2]), 'high': float(k[3]), 'low': float(k[4])} for k in klines]
    except:
        pass

    # 尝试 3：新浪财经 (带伪装头)
    try:
        url_sina = f"https://stock2.finance.sina.com.cn/futures/api/jsonp.php/var%20_{symbol_sina}=/InnerFuturesNewService.getDailyKLine?symbol={symbol_sina}"
        headers_sina = {"Referer": "https://finance.sina.com.cn", **headers}
        res = requests.get(url_sina, headers=headers_sina, timeout=5).text
        json_str = res.split('(')[1].split(');')[0]
        data = json.loads(json_str)
        return [{'close': float(k['c']), 'high': float(k['h']), 'low': float(k['l'])} for k in data]
    except:
        pass

    return None

# ================= 计算指标 =================
def get_tech_analysis(name, code):
    data = fetch_kline_multi_source(name, code)
    
    if data:
        df = pd.DataFrame(data)
        df['MA20'] = df['close'].rolling(window=20).mean()
        df['MA60'] = df['close'].rolling(window=60).mean()
        exp1 = df['close'].ewm(span=12, adjust=False).mean()
        exp2 = df['close'].ewm(span=26, adjust=False).mean()
        df['DIFF'] = exp1 - exp2
        df['DEA'] = df['DIFF'].ewm(span=9, adjust=False).mean()
        df['MACD'] = (df['DIFF'] - df['DEA']) * 2
        low_min = df['low'].rolling(window=9).min()
        high_max = df['high'].rolling(window=9).max()
        rsv = (df['close'] - low_min) / (high_max - low_min) * 100
        df['K'] = rsv.ewm(com=2, adjust=False).mean()
        df['D'] = df['K'].ewm(com=2, adjust=False).mean()
        df['J'] = 3 * df['K'] - 2 * df['D']

        last, prev = df.iloc[-1], df.iloc[-2]
        
        if last['close'] > last['MA20'] and last['MA20'] > last['MA60']: stage, desc = "长线大牛市", "价格踩在所有均线上方，大方向坚决看涨，回踩就是机会。"
        elif last['close'] < last['MA20'] and last['MA20'] < last['MA60']: stage, desc = "长线大熊市", "价格被所有均线压着打，大方向坚决看跌，反弹就是诱多。"
        elif last['close'] > last['MA60']: stage, desc = "长线多头，短线洗盘", "大方向还在涨，但最近几天有点涨不动了，在回调休息。"
        else: stage, desc = "长线空头，短线反弹", "大方向还在跌，但最近几天跌不动了，空头在平仓撤退。"

        if last['MACD'] > 0 and prev['MACD'] <= 0: mom = "刚出红柱（金叉），资金开始进场，要涨。"
        elif last['MACD'] > 0 and last['MACD'] > prev['MACD']: mom = "红柱持续放大，资金在猛冲，多头很强。"
        elif last['MACD'] < 0 and prev['MACD'] >= 0: mom = "刚出绿柱（死叉），资金开始撤退，要跌。"
        elif last['MACD'] < 0 and last['MACD'] < prev['MACD']: mom = "绿柱持续放大，资金在狂砸，空头很强。"
        else: mom = "红绿柱在缩小，涨跌动能都在衰竭，快变盘了。"

        if last['J'] > 80: kdj = f"J值高达{last['J']:.0f}，短线严重超买，随时会大回调。"
        elif last['J'] < 20: kdj = f"J值低至{last['J']:.0f}，短线严重超卖，随时会大反弹。"
        else: kdj = f"J值处于{last['J']:.0f}，短线情绪正常，跟着大方向做就行。"
        
        return stage, desc, mom, kdj, "历史K线（指标计算成功）"
    else:
        # 兜底：全部失败时，用日内数据分析
        q = next((item for item in get_realtime_quotes() if item["name"] == name), None)
        if not q: return "数据异常", "无数据", "无", "无", "未知"
        
        open_p, high_p, low_p, price = q["open"], q["high"], q["low"], q["price"]
        if high_p == low_p: return "日内震荡", "观望", "未知", "未知", "日内兜底"
        
        amp = round((high_p - low_p) / low_p * 100, 2)
        if price >= low_p + (high_p - low_p) * 0.8: stage, desc = "日内多头强势", f"收在全天最高附近（{price}），大方向偏多。"
        elif price <= low_p + (high_p - low_p) * 0.2: stage, desc = "日内空头强势", f"收在全天最低附近（{price}），大方向偏空。"
        else: stage, desc = "日内多空震荡", "价格卡在中间，没分出胜负。"
        
        mom = f"持仓量 {q['oi']:.0f} 手。价格上行，资金在进场（增仓上行）。" if price > open_p else "价格下行，资金在开空（增仓下行）。"
        kdj = f"今天振幅{amp}%，波动剧烈。" if amp > 2.5 else f"今天振幅{amp}%，波动正常。"
        return stage, desc, mom, kdj, "全接口被封，降级日内分析"

def build_html():
    now = (datetime.datetime.utcnow() + datetime.timedelta(hours=8)).strftime('%m-%d %H:%M')
    quotes = get_realtime_quotes()
    vix_str = get_vix()

    html = f'<div style="font-family:-apple-system,sans-serif;max-width:600px;color:#000;font-size:14px;">'
    html += f'<div style="background:linear-gradient(135deg,#1a3c6e,#2b5aa0);color:#fff;text-align:center;padding:12px;border-radius:8px;font-size:16px;font-weight:bold;">期货深度盯盘（多源容灾版）<br><span style="font-size:12px;">{now} | 权益:{CAPITAL:,}</span></div>'

    html += f'<div style="background:#f5f7fa;border:1px solid #d9d9d9;border-radius:6px;padding:8px;margin:10px 0;font-size:14px;text-align:center;color:#000;">'
    html += f'🌍 <b>外围情绪 VIX 恐慌指数：</b><span style="color:#b71c1c;font-weight:bold;">{vix_str}</span><br>'
    html += f'<span style="font-size:12px;color:#666;">（VIX飙升说明恐慌，商品容易被砸；下降说明情绪稳定）</span>'
    html += f'</div>'

    html += f'<div style="font-size:16px;font-weight:bold;margin:15px 0 10px 0;text-align:center;color:#000;">📌 核心速览（多红空绿）</div>'

    for q in quotes:
        stage, trend_desc, macd_desc, kdj_desc, data_source = get_tech_analysis(q["name"], q["code"])
        
        bg_color, border_color = ("#fff5f5", "#ff4d4f") if q["pct"] > 0 else ("#f6ffed", "#52c41a")

        html += f'<div style="background:{bg_color}; border:2px solid {border_color}; border-radius:8px; padding:12px; margin-bottom:12px; box-shadow:0 2px 4px rgba(0,0,0,0.05);">'
        html += f'<div style="font-size:16px; font-weight:bold; color:#000; margin-bottom:8px; border-bottom:1px dashed #ccc; padding-bottom:6px;">'
        html += f'{q["name"]} {q["code"]}：<span style="color:{q["color"]}; font-size:20px;">{q["price"]}</span> <span style="color:{q["color"]}; font-size:14px;">({q["pct"]:+.2f}%)</span>'
        html += f'<span style="font-size:10px; color:#888; float:right; margin-top:5px;">{data_source}</span>'
        html += f'</div>'
        
        html += f'<div style="color:#000; font-size:14px; line-height:1.7;">'
        html += f'👉 <b>当前阶段：</b><span style="font-size:16px; font-weight:bold;">{stage}</span><br>'
        html += f'💬 <b>大白话趋势：</b>{trend_desc}<br>'
        html += f'🔥 <b>资金动能：</b>{macd_desc}<br>'
        html += f'🌡️ <b>短线温度：</b>{kdj_desc}'
        html += f'</div></div>'

    # 资金阶梯和持仓部分
    html += f'<div style="background:#fff3e0;border-left:4px solid #f57c00;border-radius:6px;padding:12px;margin:15px 0 10px 0;">'
    html += f'<div style="font-size:16px;font-weight:bold;margin-bottom:8px;color:#000;">💰 资金阶梯分配表</div>'
    for q in quotes:
        m = MULTIPLIER.get(q["name"], 10)
        margin = round(q["price"] * m * 0.10)
        first = max(int(CAPITAL * 0.20 / margin), 1)
        add_lot = max(int(CAPITAL * 0.30 / margin), 1)
        cap = max(int(CAPITAL * 0.60 / margin), 1)
        html += f'<div style="font-size:13px;line-height:1.6;margin-bottom:6px;color:#000;"><b>{q["name"]}</b>：首仓买 <b>{first}手</b> → 加仓到 {first+add_lot}手 → 最多不超过 <b>{cap}手</b></div>'
    html += f'</div>'

    if POSITIONS:
        html += f'<div style="background:#ffebee;border-left:4px solid #d32f2f;border-radius:6px;padding:12px;margin:10px 0;">'
        html += f'<div style="font-size:16px;font-weight:bold;margin-bottom:8px;color:#000;">🚨 持仓急救（总亏 {TOTAL_PNL:,} 元）</div>'
        for p in POSITIONS:
            html += f'<div style="font-size:13px;line-height:1.6;margin-bottom:4px;color:#000;">{p["name"]} <b>{p["dir"]}{p["lots"]}手</b> (均价{p["avg"]}) | 盈亏: {p["pnl"]:+}元</div>'
        html += f'<div style="font-size:13px;color:#000;background:#fff;padding:8px;border-radius:4px;margin-top:8px;border:1px solid #ffcdd2;"><b>大白话建议：</b>你手里拿的是空单，如果分析显示“多头强势”或“资金动能强”，赶紧逢高减仓，别死扛！</div></div>'

    html += f'<div style="color:#666;font-size:12px;text-align:center;margin-top:15px;">数据来源：东财/腾讯/新浪 自动容灾 | 外围：雅虎财经</div>'
    return html

def main():
    token = os.environ.get("PUSHPLUS_TOKEN")
    if not token: return
    content = build_html()
    payload = {"token": token, "title": "期货深度盯盘（多源容灾版）", "content": content, "template": "html"}
    try:
        resp = requests.post("https://www.pushplus.plus/send", json=payload, timeout=30)
        print("✅ 推送成功" if resp.json().get("code") == 200 else "❌ 失败")
    except Exception as e:
        print(f"❌ 网络错误: {e}")

if __name__ == "__main__":
    main()
