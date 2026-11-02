# encoding:utf-8
import os, json, requests, datetime
import pandas as pd
import numpy as np
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
DATA_FILE = "kline_data.json"
# ====================================================

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
                quotes.append({
                    "name": name, "code": code, "price": price, "pct": pct,
                    "open": float(parts[1]) if parts[1] else 0, 
                    "high": max(float(parts[2]), float(parts[3])), 
                    "low": min(float(parts[2]), float(parts[3])),
                    "oi": float(parts[13]) if parts[13] else 0
                })
        return quotes
    except: return []

def get_vix():
    try:
        vix_data = yf.Ticker("^VIX").history(period="2d")
        if len(vix_data) >= 2:
            vix_last = vix_data['Close'].iloc[-1]
            vix_prev = vix_data['Close'].iloc[-2]
            vix_pct = round((vix_last - vix_prev) / vix_prev * 100, 2)
            return f"{vix_last:.2f} ({vix_pct:+.2f}%)"
    except: pass
    return "获取失败"

def update_history(name, code, price, high, low):
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r") as f: history = json.load(f)
    else: history = {}
    key = f"{name}_{code}"
    if key not in history: history[key] = []
    today = datetime.datetime.now().strftime("%Y-%m-%d")
    updated = False
    for row in history[key]:
        if row["date"] == today:
            row["close"] = price
            row["high"] = max(row.get("high", price), high)
            row["low"] = min(row.get("low", price), low)
            updated = True
            break
    if not updated:
        history[key].append({"date": today, "close": price, "high": high, "low": low})
    with open(DATA_FILE, "w") as f: json.dump(history, f)
    return history[key]

def fetch_kline_multi_source(name, code):
    symbol_sina = f"{name}{code}"
    prefix = {"甲醇": "MA", "PVC": "V", "白糖": "SR"}.get(name, "")
    symbol_tx = f"{prefix}{code}"
    secid = f"{'115' if name in ['甲醇', '白糖'] else '114'}.{symbol_tx}"
    headers = {"User-Agent": "Mozilla/5.0"}
    
    try:
        url_em = f"https://push2his.eastmoney.com/api/qt/stock/kline/get?secid={secid}&fields1=f1,f2,f3,f4,f5,f6&fields2=f51,f52,f53,f54,f55,f56&klt=101&fqt=0&end=20500101&lmt=120"
        res = requests.get(url_em, headers=headers, timeout=5).json()
        if res.get('data') and res['data'].get('klines'):
            return [{'close': float(k.split(',')[2]), 'high': float(k.split(',')[3]), 'low': float(k.split(',')[4])} for k in res['data']['klines']]
    except: pass
    try:
        url_tx = f"https://web.ifzq.gtimg.cn/appstock/app/kline/kline?param={symbol_tx},day,,,120"
        res = requests.get(url_tx, headers=headers, timeout=5).json()
        return [{'close': float(k[2]), 'high': float(k[3]), 'low': float(k[4])} for k in res['data'][symbol_tx]['day']]
    except: pass
    try:
        url_sina = f"https://stock2.finance.sina.com.cn/futures/api/jsonp.php/var%20_{symbol_sina}=/InnerFuturesNewService.getDailyKLine?symbol={symbol_sina}"
        headers_sina = {"Referer": "https://finance.sina.com.cn", **headers}
        res = requests.get(url_sina, headers=headers_sina, timeout=5).text
        data = json.loads(res.split('(')[1].split(');')[0])
        return [{'close': float(k['c']), 'high': float(k['h']), 'low': float(k['l'])} for k in data]
    except: pass
    return None

# 核心专业算法：结合 ATR 与近期高低点动态计算盈亏比点位
def get_tech_analysis(q):
    name, code = q["name"], q["code"]
    price, high, low = q["price"], q["high"], q["low"]
    data = fetch_kline_multi_source(name, code)
    source_label = "历史数据"
    stage, desc, mom, kdj = "", "", "", ""
    action_plan = ""

    # 兜底计算：用今日振幅做基础
    diff = (high - low) if high > low else price * 0.01
    
    if not data:
        history_list = update_history(name, code, price, high, low)
        if len(history_list) < 20:
            stage, desc = "观望", "数据不足20天，暂用日内振幅推演。"
            source_label = f"自建库({len(history_list)}/20)"
            action_plan = f"🛑 多看少动：在 {round(low,0)} 到 {round(high,0)} 之间震荡，最好等均线数据齐全后再开单。"
            return stage, desc, mom, kdj, source_label, action_plan
        else:
            data = history_list
            source_label = "自建库分析"

    try:
        df = pd.DataFrame(data)
        df['MA20'] = df['close'].rolling(window=20).mean()
        df['MA60'] = df['close'].rolling(window=60).mean()
        exp1 = df['close'].ewm(span=12, adjust=False).mean()
        exp2 = df['close'].ewm(span=26, adjust=False).mean()
        df['DIFF'] = exp1 - exp2
        df['DEA'] = df['DIFF'].ewm(span=9, adjust=False).mean()
        df['MACD'] = (df['DIFF'] - df['DEA']) * 2
        
        # 计算 ATR (14天真实波幅均值) 用于动态止损
        df['TR'] = np.maximum(df['high'] - df['low'], 
                              np.maximum(abs(df['high'] - df['close'].shift()), 
                                         abs(df['low'] - df['close'].shift())))
        atr = df['TR'].rolling(window=14).mean().iloc[-1]
        
        low_min = df['low'].rolling(window=9).min()
        high_max = df['high'].rolling(window=9).max()
        rsv = (df['close'] - low_min) / (high_max - low_min) * 100
        df['K'] = rsv.ewm(com=2, adjust=False).mean()
        df['D'] = df['K'].ewm(com=2, adjust=False).mean()
        df['J'] = 3 * df['K'] - 2 * df['D']

        last, prev = df.iloc[-1], df.iloc[-2]
        ma20 = last['MA20'] if not pd.isna(last['MA20']) else price
        ma60 = last['MA60'] if not pd.isna(last['MA60']) else price
        
        # 近期极值支撑压力
        recent_high = df['high'].tail(10).max()
        recent_low = df['low'].tail(10).min()

        # 1. 判定阶段并生成【动态盈亏比】战术
        if last['close'] > ma20 and ma20 > ma60:
            if last['J'] > 80 or (last['MACD'] > 0 and last['MACD'] < prev['MACD']):
                stage = "多头后期"
                desc = "大方向还在涨，但短线严重超买，动能衰竭，随时会变盘回调，千万别追多！"
                # 后期抓反转：止损极小（突破前高），止盈看MA20
                stop_loss = recent_high + (atr * 0.5)
                take_profit = ma20
                action_plan = f"⚠️ 准备做空：冲高到 <b>{recent_high:.0f}</b> 附近试 1 手空。<br>🚫 止损：<b>{stop_loss:.0f}</b>（假突破认错，亏得极少）。<br>💰 止盈：<b>{take_profit:.0f}</b> 附近平空（抓大回调）。"
            elif last['MACD'] > 0 and last['MACD'] > prev['MACD']:
                stage = "多头中期"
                desc = "红柱放大，均线多头排列，趋势正猛，回踩就是上车机会。"
                # 中期顺势：回踩加多，跌破MA20止损，看前高
                buy_point = ma20 + (atr * 0.2)
                stop_loss = ma20 - (atr * 1.0)
                take_profit = recent_high
                action_plan = f"🚀 顺势做多：回踩 <b>{buy_point:.0f}</b> 附近加 1 手多。<br>🚫 止损：<b>{stop_loss:.0f}</b>（跌破均线防守）。<br>💰 止盈：<b>{take_profit:.0f}</b> 附近减仓。"
            else:
                stage = "多头初期"
                desc = "刚站上均线，多头开始试探发力，观察能否站稳。"
                # 初期试仓：现价附近轻仓，跌破前低止损，盈亏比 1:3
                buy_point = price
                stop_loss = recent_low - (atr * 0.5)
                take_profit = price + (price - stop_loss) * 2.5
                action_plan = f"🌱 试仓做多：现价 <b>{buy_point:.0f}</b> 或回踩轻仓进 1 手多。<br>🚫 止损：<b>{stop_loss:.0f}</b>（跌破前低绝对离场）。<br>💰 止盈：<b>{take_profit:.0f}</b> 附近（以大博小）。"
        elif last['close'] < ma20 and ma20 < ma60:
            if last['J'] < 20 or (last['MACD'] < 0 and last['MACD'] > prev['MACD']):
                stage = "空头后期"
                desc = "大方向还在跌，但短线严重超卖，动能衰竭，随时会变盘反弹，千万别追空！"
                # 后期抓反弹：止损极小（跌破前低），止盈看MA20
                stop_loss = recent_low - (atr * 0.5)
                take_profit = ma20
                action_plan = f"⚠️ 准备做多：砸到 <b>{recent_low:.0f}</b> 附近试 1 手多。<br>🚫 止损：<b>{stop_loss:.0f}</b>（假跌破认错）。<br>💰 止盈：<b>{take_profit:.0f}</b> 附近平多（吃反弹）。"
            elif last['MACD'] < 0 and last['MACD'] < prev['MACD']:
                stage = "空头中期"
                desc = "绿柱放大，均线空头排列，趋势极弱，反弹就是诱多。"
                # 中期顺势：反弹加空
                sell_point = ma20 - (atr * 0.2)
                stop_loss = ma20 + (atr * 1.0)
                take_profit = recent_low
                action_plan = f"🔪 顺势做空：反弹到 <b>{sell_point:.0f}</b> 附近加 1 手空。<br>🚫 止损：<b>{stop_loss:.0f}</b>（突破均线防守）。<br>💰 止盈：<b>{take_profit:.0f}</b> 附近减仓。"
            else:
                stage = "空头初期"
                desc = "刚跌破均线，空头开始试探砸盘，观察能否破位。"
                sell_point = price
                stop_loss = recent_high + (atr * 0.5)
                take_profit = price - (stop_loss - price) * 2.5
                action_plan = f"🌱 试仓做空：现价 <b>{sell_point:.0f}</b> 或反弹轻仓进 1 手空。<br>🚫 止损：<b>{stop_loss:.0f}</b>（突破前高绝对离场）。<br>💰 止盈：<b>{take_profit:.0f}</b> 附近（以大博小）。"
        else:
            stage = "观望"
            desc = "多空在均线附近纠缠，方向不明，没分出胜负。"
            action_plan = f"🛑 多看少动：等突破 {recent_high:.0f} 或跌破 {recent_low:.0f} 再进场，现在开单容易被来回扫止损。"

        # 动能与温度
        if last['MACD'] > 0 and prev['MACD'] <= 0: mom = "刚出红柱（金叉），资金进场。"
        elif last['MACD'] > 0 and last['MACD'] > prev['MACD']: mom = "红柱放大，多头动能强。"
        elif last['MACD'] < 0 and prev['MACD'] >= 0: mom = "刚出绿柱（死叉），资金撤退。"
        elif last['MACD'] < 0 and last['MACD'] < prev['MACD']: mom = "绿柱放大，空头动能强。"
        else: mom = "红绿柱缩小，快变盘了。"
        
        if last['J'] > 80: kdj = f"J值{last['J']:.0f}，严重超买。"
        elif last['J'] < 20: kdj = f"J值{last['J']:.0f}，严重超卖。"
        else: kdj = f"J值{last['J']:.0f}，情绪正常。"

        return stage, desc, mom, kdj, source_label, action_plan
    except:
        return "观望", "解析异常。", "未知", "未知", "报错", "观望为主。"

def build_html():
    now = (datetime.datetime.utcnow() + datetime.timedelta(hours=8)).strftime('%m-%d %H:%M')
    quotes = get_realtime_quotes()
    vix_str = get_vix()

    html = f'<div style="font-family:-apple-system,sans-serif;max-width:600px;color:#000;font-size:14px;">'
    html += f'<div style="background:linear-gradient(135deg,#1a3c6e,#2b5aa0);color:#fff;text-align:center;padding:12px;border-radius:8px;font-size:16px;font-weight:bold;">期货实战下单指令<br><span style="font-size:12px;">{now} | 权益:{CAPITAL:,}</span></div>'

    html += f'<div style="background:#f5f7fa;border:1px solid #d9d9d9;border-radius:6px;padding:8px;margin:10px 0;font-size:14px;text-align:center;color:#000;">'
    html += f'🌍 <b>外围情绪 VIX：</b><span style="color:#b71c1c;font-weight:bold;">{vix_str}</span>'
    html += f'</div>'

    html += f'<div style="font-size:16px;font-weight:bold;margin:15px 0 10px 0;text-align:center;color:#000;">📌 核心速览（多红/空绿/观望灰）</div>'

    for q in quotes:
        stage, trend_desc, macd_desc, kdj_desc, data_source, action_plan = get_tech_analysis(q)
        
        if "空头" in stage:
            bg_color, border_color = "#f6ffed", "#52c41a" 
        elif "多头" in stage:
            bg_color, border_color = "#fff5f5", "#ff4d4f" 
        else:
            bg_color, border_color = "#f5f5f5", "#d9d9d9" 

        html += f'<div style="background:{bg_color}; border:2px solid {border_color}; border-radius:8px; padding:12px; margin-bottom:12px; box-shadow:0 2px 4px rgba(0,0,0,0.05);">'
        
        html += f'<div style="font-size:16px; font-weight:bold; color:#000; margin-bottom:8px; border-bottom:1px dashed #ccc; padding-bottom:6px;">'
        html += f'{q["name"]} {q["code"]}：<span style="font-size:20px;">{q["price"]}</span> <span style="font-size:14px;">({q["pct"]:+.2f}%)</span>'
        html += f'<span style="font-size:10px; color:#888; float:right; margin-top:5px;">{data_source}</span>'
        html += f'</div>'
        
        html += f'<div style="color:#000; font-size:14px; line-height:1.7;">'
        html += f'👉 <b>当前阶段：</b><span style="font-size:16px; font-weight:bold;">{stage}</span><br>'
        html += f'💬 <b>大白话趋势：</b>{trend_desc}<br>'
        html += f'🔥 <b>资金动能：</b>{macd_desc}<br>'
        html += f'🌡️ <b>短线温度：</b>{kdj_desc}<br>'
        
        # 实战填单模块
        html += f'<div style="background:#fff; border:2px solid {border_color}; padding:10px; border-radius:6px; margin-top:10px; box-shadow:0 1px 3px rgba(0,0,0,0.1);">'
        html += f'<div style="font-size:15px; font-weight:bold; color:{border_color}; margin-bottom:6px;">🎯 专业盈亏比挂单：</div>'
        html += f'<div style="font-size:14px; font-weight:bold; color:#000; line-height:1.8;">{action_plan}</div>'
        html += f'</div>'
        
        html += f'</div></div>'

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
        html += f'<div style="font-size:13px;color:#000;background:#fff;padding:8px;border-radius:4px;margin-top:8px;border:1px solid #ffcdd2;"><b>大白话建议：</b>你手里拿的是空单，如果分析显示“多头强势”，赶紧逢高减仓；如果跌破上述的支撑位，空单可以继续拿。</div></div>'

    return html

def main():
    token = os.environ.get("PUSHPLUS_TOKEN")
    if not token: return
    content = build_html()
    payload = {"token": token, "title": "期货实战下单指令", "content": content, "template": "html"}
    try:
        resp = requests.post("https://www.pushplus.plus/send", json=payload, timeout=30)
        print("✅ 推送成功" if resp.json().get("code") == 200 else "❌ 失败")
    except Exception as e:
        print(f"❌ 网络错误: {e}")

if __name__ == "__main__":
    main()
