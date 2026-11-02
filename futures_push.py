# encoding:utf-8
import os, json, requests, datetime
import pandas as pd
import numpy as np
import yfinance as yf

# ================= 你的账户核心数据 =================
CAPITAL = 289485
RISK_PER_TRADE = round(CAPITAL * 0.01) # 单笔风控上限：约 2895 元
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

# 获取宏观数据：WTI原油、美元指数、VIX
def get_macro_data():
    oil_price, oil_pct = 0, 0
    dxy_price, dxy_pct = 0, 0
    vix_str = "获取失败"
    
    try:
        oil_data = yf.Ticker("CL=F").history(period="2d")
        if len(oil_data) >= 2:
            oil_price = oil_data['Close'].iloc[-1]
            oil_pct = round((oil_price - oil_data['Close'].iloc[-2]) / oil_data['Close'].iloc[-2] * 100, 2)
    except: pass
    
    try:
        dxy_data = yf.Ticker("DX-Y.NYB").history(period="2d")
        if len(dxy_data) >= 2:
            dxy_price = dxy_data['Close'].iloc[-1]
            dxy_pct = round((dxy_price - dxy_data['Close'].iloc[-2]) / dxy_data['Close'].iloc[-2] * 100, 2)
    except: pass
    
    try:
        vix_data = yf.Ticker("^VIX").history(period="2d")
        if len(vix_data) >= 2:
            vix_last = vix_data['Close'].iloc[-1]
            vix_pct = round((vix_last - vix_data['Close'].iloc[-2]) / vix_data['Close'].iloc[-2] * 100, 2)
            vix_str = f"{vix_last:.2f} ({vix_pct:+.2f}%)"
    except: pass
    
    return oil_price, oil_pct, dxy_price, dxy_pct, vix_str

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

# ================= 核心职业交易逻辑 =================
def get_tech_analysis(q):
    name, code = q["name"], q["code"]
    price, high, low, open_p = q["price"], q["high"], q["low"], q["open"]
    data = fetch_kline_multi_source(name, code)
    source_label = "历史数据"
    
    stop_loss = 0
    action_plan = ""
    order_type = "观望" 
    
    diff = (high - low) if high > low else price * 0.01
    atr = diff / 2

    if not data:
        history_list = update_history(name, code, price, high, low)
        if len(history_list) < 20:
            source_label = f"自建库({len(history_list)}/20)"
            amp = round(diff / low * 100, 2) if low > 0 else 0
            if price >= low + diff * 0.7 and price > open_p: 
                stage, desc = "多头中期(日内)", "收在相对高点，日内多头占优。"
                order_type = "做多"
                stop_loss = low - (atr * 0.3)
                action_plan = f"🛑 数据不足轻仓试多：现价 <b>{price}</b> 附近轻仓。<br>🚫 止损：<b>{stop_loss:.0f}</b>（跌破今日低点）。"
            elif price <= low + diff * 0.3 and price < open_p: 
                stage, desc = "空头中期(日内)", "收在相对低点，日内空头占优。"
                order_type = "做空"
                stop_loss = high + (atr * 0.3)
                action_plan = f"🛑 数据不足轻仓试空：现价 <b>{price}</b> 附近轻仓。<br>🚫 止损：<b>{stop_loss:.0f}</b>（突破今日高点）。"
            else: 
                stage, desc = "观望", "卡在中间，日内多空没分出胜负。"
                order_type = "观望"
                stop_loss = 0
                action_plan = f"🛑 多看少动：在 <b>{low:.0f} - {high:.0f}</b> 之间等突破。暂不建议开仓。"
            
            mom = "日内资金波动平稳。" if amp < 2.5 else "日内资金异动剧烈，多空交战激烈。"
            kdj = f"振幅{amp}%，波动剧烈。" if amp > 2.5 else f"振幅{amp}%，波动正常。"
            return stage, desc, mom, kdj, source_label, action_plan, order_type, price, stop_loss
        else:
            data = history_list
            source_label = "自建库分析"

    try:
        df = pd.DataFrame(data)
        df['MA20'] = df['close'].rolling(window=20).mean()
        df['MA60'] = df['close'].rolling(window=60).mean()
        
        # ================= 布林带计算 (20日, 2倍标准差) =================
        df['std'] = df['close'].rolling(window=20).std()
        df['upper_band'] = df['MA20'] + (df['std'] * 2)
        df['lower_band'] = df['MA20'] - (df['std'] * 2)
        
        exp1 = df['close'].ewm(span=12, adjust=False).mean()
        exp2 = df['close'].ewm(span=26, adjust=False).mean()
        df['DIFF'] = exp1 - exp2
        df['DEA'] = df['DIFF'].ewm(span=9, adjust=False).mean()
        df['MACD'] = (df['DIFF'] - df['DEA']) * 2
        
        df['TR'] = np.maximum(df['high'] - df['low'], 
                              np.maximum(abs(df['high'] - df['close'].shift()), 
                                         abs(df['low'] - df['close'].shift())))
        atr_val = df['TR'].rolling(window=14).mean().iloc[-1]
        atr = atr_val if not pd.isna(atr_val) else atr
        
        low_min = df['low'].rolling(window=9).min()
        high_max = df['high'].rolling(window=9).max()
        rsv = (df['close'] - low_min) / (high_max - low_min) * 100
        df['K'] = rsv.ewm(com=2, adjust=False).mean()
        df['D'] = df['K'].ewm(com=2, adjust=False).mean()
        df['J'] = 3 * df['K'] - 2 * df['D']

        last, prev = df.iloc[-1], df.iloc[-2]
        ma20 = last['MA20'] if not pd.isna(last['MA20']) else price
        ma60 = last['MA60'] if not pd.isna(last['MA60']) else price
        upper_band = last['upper_band'] if not pd.isna(last['upper_band']) else price * 2
        lower_band = last['lower_band'] if not pd.isna(last['lower_band']) else price * 0.5
        
        recent_high = df['high'].tail(10).max()
        recent_low = df['low'].tail(10).min()

        # 核心逻辑：加入布林带极值拦截
        if last['close'] > ma20 and ma20 > ma60:
            # 优先检查布林带是否顶破上轨
            if last['close'] >= upper_band:
                stage = "多头极值(超买)"
                desc = "价格已顶破布林带上轨！乖离率极大，随时有暴跌风险。"
                order_type = "观望"
                stop_loss = 0
                action_plan = f"🚫 严禁追多：获利多单在 <b>{recent_high:.0f}</b> 附近立刻止盈落袋。<br>👀 极端观望：等价格回踩 MA20 ({ma20:.0f}) 附近再看。"
            elif last['J'] > 80 or (last['MACD'] > 0 and last['MACD'] < prev['MACD']):
                stage = "多头后期"
                desc = "动能衰竭，随时变盘。绝不摸顶做空，耐心等跌破 MA20。"
                order_type = "观望"
                stop_loss = 0
                action_plan = f"🛡️ 只平多不开空：多单在 <b>{recent_high:.0f}</b> 落袋。<br>👀 跌破 <b>{ma20:.0f}</b> 才是右侧做空点。"
            elif last['MACD'] > 0 and last['MACD'] > prev['MACD']:
                stage = "多头中期"
                desc = "红柱放大，趋势正猛，回踩上车。"
                order_type = "做多"
                stop_loss = ma20 - (atr * 1.0)
                action_plan = f"🚀 顺势做多：回踩 <b>{ma20 + (atr*0.2):.0f}</b> 加 1 手多。<br>🚫 止损：<b>{stop_loss:.0f}</b>。"
            else:
                stage = "多头初期"
                desc = "刚站上均线，多头试探发力。"
                order_type = "做多"
                stop_loss = recent_low - (atr * 0.5)
                action_plan = f"🌱 试仓做多：现价 <b>{price}</b> 轻仓进 1 手多。<br>🚫 止损：<b>{stop_loss:.0f}</b>。"
        
        elif last['close'] < ma20 and ma20 < ma60:
            # 优先检查布林带是否跌破下轨
            if last['close'] <= lower_band:
                stage = "空头极值(超卖)"
                desc = "价格已跌破布林带下轨！乖离率极大，随时有报复性反弹风险。"
                order_type = "观望"
                stop_loss = 0
                action_plan = f"🚫 严禁追空：获利空单在 <b>{recent_low:.0f}</b> 附近立刻止盈落袋。<br>👀 极端观望：等价格反抽 MA20 ({ma20:.0f}) 附近再看。"
            elif last['J'] < 20 or (last['MACD'] < 0 and last['MACD'] > prev['MACD']):
                stage = "空头后期"
                desc = "空头动能衰竭，随时反弹。绝不抄底做多，耐心等突破 MA20。"
                order_type = "观望"
                stop_loss = 0
                action_plan = f"🛡️ 只平空不开多：空单在 <b>{recent_low:.0f}</b> 落袋。<br>👀 突破 <b>{ma20:.0f}</b> 才是右侧做多点。"
            elif last['MACD'] < 0 and last['MACD'] < prev['MACD']:
                stage = "空头中期"
                desc = "绿柱放大，趋势极弱，反弹诱多。"
                order_type = "做空"
                stop_loss = ma20 + (atr * 1.0)
                action_plan = f"🔪 顺势做空：反弹到 <b>{ma20 - (atr*0.2):.0f}</b> 加 1 手空。<br>🚫 止损：<b>{stop_loss:.0f}</b>。"
            else:
                stage = "空头初期"
                desc = "刚跌破均线，空头试探砸盘。"
                order_type = "做空"
                stop_loss = recent_high + (atr * 0.5)
                action_plan = f"🌱 试仓做空：现价 <b>{price}</b> 轻仓进 1 手空。<br>🚫 止损：<b>{stop_loss:.0f}</b>。"
        else:
            stage = "观望"
            desc = "多空在均线附近纠缠，方向不明。"
            order_type = "观望"
            stop_loss = 0
            action_plan = f"🛑 多看少动：等突破 {recent_high:.0f} 或跌破 {recent_low:.0f} 再进场。"

        if last['MACD'] > 0 and prev['MACD'] <= 0: mom = "刚出红柱（金叉），资金进场。"
        elif last['MACD'] > 0 and last['MACD'] > prev['MACD']: mom = "红柱放大，多头动能强。"
        elif last['MACD'] < 0 and prev['MACD'] >= 0: mom = "刚出绿柱（死叉），资金撤退。"
        elif last['MACD'] < 0 and last['MACD'] < prev['MACD']: mom = "绿柱放大，空头动能强。"
        else: mom = "红绿柱缩小，快变盘了。"
        
        if last['J'] > 80: kdj = f"J值{last['J']:.0f}，严重超买。"
        elif last['J'] < 20: kdj = f"J值{last['J']:.0f}，严重超卖。"
        else: kdj = f"J值{last['J']:.0f}，情绪正常。"

        return stage, desc, mom, kdj, source_label, action_plan, order_type, price, stop_loss
    except:
        return "观望", "解析异常。", "未知", "未知", "报错", "观望为主。", "观望", price, 0

def build_html():
    now = (datetime.datetime.utcnow() + datetime.timedelta(hours=8)).strftime('%m-%d %H:%M')
    quotes = get_realtime_quotes()
    oil_price, oil_pct, dxy_price, dxy_pct, vix_str = get_macro_data()

    html = f'<div style="font-family:-apple-system,sans-serif;max-width:600px;color:#000;font-size:14px;">'
    html += f'<div style="background:linear-gradient(135deg,#1a3c6e,#2b5aa0);color:#fff;text-align:center;padding:12px;border-radius:8px;font-size:16px;font-weight:bold;">期货实战下单指令<br><span style="font-size:12px;">{now} | 权益:{CAPITAL:,}</span></div>'

    # 宏观面板
    html += f'<div style="background:#f5f7fa;border:1px solid #d9d9d9;border-radius:6px;padding:8px;margin:10px 0;font-size:13px;text-align:center;color:#000;">'
    html += f'🌍 <b>VIX：</b><span style="color:#b71c1c;font-weight:bold;">{vix_str}</span>'
    if oil_price > 0:
        oil_color = "#b71c1c" if oil_pct > 0 else "#1b5e20"
        html += f' | 🛢️ <b>WTI：</b><span style="color:{oil_color};font-weight:bold;">{oil_price:.2f} ({oil_pct:+.2f}%)</span>'
    if dxy_price > 0:
        dxy_color = "#b71c1c" if dxy_pct > 0 else "#1b5e20"
        html += f'<br>💵 <b>美元指数：</b><span style="color:{dxy_color};font-weight:bold;">{dxy_price:.2f} ({dxy_pct:+.2f}%)</span>'
        if dxy_pct > 0.5:
            html += f'<span style="color:#d32f2f;font-weight:bold;font-size:12px;"> ⚠️ 美元拉升压制大宗！</span>'
    html += f'</div>'

    html += f'<div style="font-size:16px;font-weight:bold;margin:15px 0 10px 0;text-align:center;color:#000;">📌 核心速览（多红/空绿/观望灰）</div>'

    analysis_results = []

    for q in quotes:
        stage, trend_desc, macd_desc, kdj_desc, data_source, action_plan, order_type, buy_price, stop_loss = get_tech_analysis(q)
        analysis_results.append({"q": q, "order_type": order_type, "buy": buy_price, "stop": stop_loss})
        
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
        
        html += f'<div style="background:#fff; border:2px solid {border_color}; padding:10px; border-radius:6px; margin-top:10px; box-shadow:0 1px 3px rgba(0,0,0,0.1);">'
        html += f'<div style="font-size:15px; font-weight:bold; color:{border_color}; margin-bottom:6px;">🎯 专业右侧交易指令：</div>'
        html += f'<div style="font-size:14px; font-weight:bold; color:#000; line-height:1.8;">{action_plan}</div>'
        html += f'</div>'
        
        html += f'</div></div>'

    # ================= 修正后的 ATR 资金阶梯 =================
    html += f'<div style="background:#e3f2fd;border-left:4px solid #1e88e5;border-radius:6px;padding:12px;margin:15px 0 10px 0;">'
    html += f'<div style="font-size:16px;font-weight:bold;margin-bottom:6px;color:#000;">🛡️ 专业仓位控制 (死亏上限 {RISK_PER_TRADE}元)</div>'
    
    for res in analysis_results:
        q = res["q"]
        name = q["name"]
        mult = MULTIPLIER.get(name, 10)
        
        if res["order_type"] == "观望" or res["stop"] == 0:
            html += f'<div style="font-size:13px;line-height:1.6;margin-bottom:8px;color:#000;background:#fff;padding:8px;border-radius:4px;">'
            html += f'<b>{name}</b>：当前为【观望/极值】状态，系统未发出明确顺势信号，<b>不建议开新仓</b>。'
            html += f'</div>'
            continue

        points_loss = abs(res["buy"] - res["stop"])
        money_loss = points_loss * mult
        
        max_lots = max(int(RISK_PER_TRADE / money_loss), 1)
        first_lots = max(int(max_lots / 2), 1)
        
        html += f'<div style="font-size:13px;line-height:1.6;margin-bottom:8px;color:#000;background:#fff;padding:8px;border-radius:4px;border:1px solid #bbdefb;">'
        html += f'<b>{name} ({res["order_type"]})</b>：按挂单价 <b>{res["buy"]:.0f}</b> 进场，止损定在 <b>{res["stop"]:.0f}</b>。<br>'
        html += f'📉 1手亏损约 <b>{money_loss:.0f}</b> 元。最多只能下 <b>{max_lots} 手</b>。<br>'
        html += f'👉 <b>建议首仓下 {first_lots} 手</b>。'
        html += f'</div>'
        
    html += f'</div>'

    if POSITIONS:
        html += f'<div style="background:#ffebee;border-left:4px solid #d32f2f;border-radius:6px;padding:12px;margin:10px 0;">'
        html += f'<div style="font-size:16px;font-weight:bold;margin-bottom:8px;color:#000;">🚨 持仓急救（总亏 {TOTAL_PNL:,} 元）</div>'
        for p in POSITIONS:
            html += f'<div style="font-size:13px;line-height:1.6;margin-bottom:4px;color:#000;">{p["name"]} <b>{p["dir"]}{p["lots"]}手</b> (均价{p["avg"]}) | 盈亏: {p["pnl"]:+}元</div>'
        
        html += f'<div style="font-size:13px;color:#000;background:#fff;padding:8px;border-radius:4px;margin-top:8px;border:1px solid #ffcdd2;line-height:1.6;">'
        html += f'<b>职业纪律：</b><br>'
        html += f'1. 你的空单是逆势单，如果反弹到上面给的压力位，逢高减仓。<br>'
        html += f'2. <b>保本铁律</b>：盈利达 3000元，立刻推保本止损，保证不亏。<br>'
        html += f'3. 绝不扛单，绝不逆势加仓。'
        html += f'</div></div>'

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
