# encoding:utf-8
import os, json, requests, datetime
import pandas as pd
import numpy as np
import yfinance as yf

# ================= 你的账户核心数据 =================
CAPITAL = 289485
RISK_PER_TRADE = round(CAPITAL * 0.01)
POSITIONS = [
    {"name": "甲醇", "code": "2701", "dir": "空", "lots": 7, "avg": 2889.43},
    {"name": "甲醇", "code": "2701", "dir": "多", "lots": 2, "avg": 3051.50},
    {"name": "PVC", "code": "2701", "dir": "空", "lots": 13, "avg": 5096.46},
]
TOTAL_PNL = -42055
MULTIPLIER = {"甲醇": 10, "PVC": 5, "白糖": 10}
DATA_FILE = "kline_data.json"
# ====================================================

def get_realtime_quotes():
    symbols = {"甲醇": "nf_MA2701", "PVC": "nf_V2701", "白糖": "nf_SR2701", "焦煤": "nf_JM2701"}
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

def get_macro_data():
    oil_pct, dxy_pct, vix_str = 0, 0, "获取失败"
    try:
        oil_data = yf.Ticker("CL=F").history(period="2d")
        if len(oil_data) >= 2: oil_pct = round((oil_data['Close'].iloc[-1] - oil_data['Close'].iloc[-2]) / oil_data['Close'].iloc[-2] * 100, 2)
        dxy_data = yf.Ticker("DX-Y.NYB").history(period="2d")
        if len(dxy_data) >= 2: dxy_pct = round((dxy_data['Close'].iloc[-1] - dxy_data['Close'].iloc[-2]) / dxy_data['Close'].iloc[-2] * 100, 2)
        vix_data = yf.Ticker("^VIX").history(period="2d")
        if len(vix_data) >= 2: vix_str = f"{vix_data['Close'].iloc[-1]:.2f} ({round((vix_data['Close'].iloc[-1] - vix_data['Close'].iloc[-2]) / vix_data['Close'].iloc[-2] * 100, 2):+.2f}%)"
    except: pass
    return oil_pct, dxy_pct, vix_str

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
            row["close"] = price; row["high"] = max(row.get("high", price), high); row["low"] = min(row.get("low", price), low)
            updated = True; break
    if not updated: history[key].append({"date": today, "close": price, "high": high, "low": low})
    with open(DATA_FILE, "w") as f: json.dump(history, f)
    return history[key]

def fetch_kline_data(name, code, period="day"):
    prefix = {"甲醇": "MA", "PVC": "V", "白糖": "SR"}.get(name, "")
    symbol_tx = f"{prefix}{code}"
    headers = {"User-Agent": "Mozilla/5.0"}
    
    # 腾讯接口支持分钟线和日线
    try:
        url_tx = f"https://web.ifzq.gtimg.cn/appstock/app/kline/kline?param={symbol_tx},{period},,,120"
        res = requests.get(url_tx, headers=headers, timeout=5).json()
        return [{'close': float(k[2]), 'high': float(k[3]), 'low': float(k[4])} for k in res['data'][symbol_tx][period]]
    except: return None

def get_tech_analysis(q):
    name, code = q["name"], q["code"]
    price, high, low, open_p = q["price"], q["high"], q["low"], q["open"]
    data_d = fetch_kline_data(name, code, "day")
    data_60 = fetch_kline_data(name, code, "m60") # 60分钟线
    
    stop_loss, action_plan, order_type = 0, "", "观望"
    source_label = "历史数据"
    diff = (high - low) if high > low else price * 0.01
    atr = diff / 2

    if not data_d:
        history_list = update_history(name, code, price, high, low)
        if len(history_list) < 20:
            source_label = f"自建库({len(history_list)}/20)"
            amp = round(diff / low * 100, 2) if low > 0 else 0
            if price >= low + diff * 0.7 and price > open_p: 
                stage, desc = "多头中期(日内)", "日内多头占优。"; order_type = "做多"; stop_loss = low - (atr * 0.3)
                action_plan = f"🛑 轻仓试多：现价 <b>{price}</b>。<br>🚫 止损：<b>{stop_loss:.0f}</b>。"
            elif price <= low + diff * 0.3 and price < open_p: 
                stage, desc = "空头中期(日内)", "日内空头占优。"; order_type = "做空"; stop_loss = high + (atr * 0.3)
                action_plan = f"🛑 轻仓试空：现价 <b>{price}</b>。<br>🚫 止损：<b>{stop_loss:.0f}</b>。"
            else: 
                stage, desc = "观望", "卡在中间。"; order_type = "观望"; stop_loss = 0
                action_plan = f"🛑 多看少动。"
            return stage, desc, "日内波动", "日内波动", source_label, action_plan, order_type, price, stop_loss
        else:
            data_d = history_list; source_label = "自建库"

    try:
        df = pd.DataFrame(data_d)
        df['MA20'] = df['close'].rolling(window=20).mean(); df['MA60'] = df['close'].rolling(window=60).mean()
        df['std'] = df['close'].rolling(window=20).std()
        df['upper'] = df['MA20'] + (df['std'] * 2); df['lower'] = df['MA20'] - (df['std'] * 2)
        exp1 = df['close'].ewm(span=12, adjust=False).mean(); exp2 = df['close'].ewm(span=26, adjust=False).mean()
        df['DIFF'] = exp1 - exp2; df['DEA'] = df['DIFF'].ewm(span=9, adjust=False).mean(); df['MACD'] = (df['DIFF'] - df['DEA']) * 2
        df['TR'] = np.maximum(df['high'] - df['low'], np.maximum(abs(df['high'] - df['close'].shift()), abs(df['low'] - df['close'].shift())))
        atr = df['TR'].rolling(window=14).mean().iloc[-1]
        
        low_min = df['low'].rolling(window=9).min(); high_max = df['high'].rolling(window=9).max()
        rsv = (df['close'] - low_min) / (high_max - low_min) * 100
        df['K'] = rsv.ewm(com=2, adjust=False).mean(); df['D'] = df['K'].ewm(com=2, adjust=False).mean(); df['J'] = 3 * df['K'] - 2 * df['D']

        last, prev = df.iloc[-1], df.iloc[-2]
        ma20, ma60 = last['MA20'] if not pd.isna(last['MA20']) else price, last['MA60'] if not pd.isna(last['MA60']) else price
        upper, lower = last['upper'] if not pd.isna(last['upper']) else price*2, last['lower'] if not pd.isna(last['lower']) else price*0.5

        # 多周期共振过滤
        m60_overbought = False
        if data_60:
            df60 = pd.DataFrame(data_60)
            low60 = df60['low'].rolling(window=9).min(); high60 = df60['high'].rolling(window=9).max()
            rsv60 = (df60['close'] - low60) / (high60 - low60) * 100
            j60 = (3 * rsv60.ewm(com=2, adjust=False).mean() - 2 * rsv60.ewm(com=2, adjust=False).mean().ewm(com=2, adjust=False).mean()).iloc[-1]
            if j60 > 90: m60_overbought = True

        if last['close'] > ma20 and ma20 > ma60:
            if last['close'] >= upper: stage, desc, order_type, stop_loss = "多头极值(超买)", "顶破布林带上轨，防暴跌。", "观望", 0; action_plan = f"🚫 严禁追多，获利了结。"
            elif last['J'] > 80 or (last['MACD'] > 0 and last['MACD'] < prev['MACD']): stage, desc, order_type, stop_loss = "多头后期", "动能衰竭，等跌破MA20再反手。", "观望", 0; action_plan = f"🛡️ 只平多不开空。"
            elif m60_overbought: stage, desc, order_type, stop_loss = "日线多头", "⚠️但60分钟严重超买，短线有回调需求。", "观望", 0; action_plan = f"👀 等60分钟回调企稳，或等回踩 <b>{ma20:.0f}</b> 再进多。"
            else:
                stage, desc, order_type = "多头中期", "红柱放大，趋势正猛。", "做多"; stop_loss = ma20 - (atr * 1.0)
                action_plan = f"🚀 顺势做多：回踩 <b>{ma20 + (atr*0.2):.0f}</b> 加 1 手多。<br>🚫 止损：<b>{stop_loss:.0f}</b>。"
        
        elif last['close'] < ma20 and ma20 < ma60:
            if last['close'] <= lower: stage, desc, order_type, stop_loss = "空头极值(超卖)", "跌破布林带下轨，防报复性反弹。", "观望", 0; action_plan = f"🚫 严禁追空，获利了结。"
            elif last['J'] < 20 or (last['MACD'] < 0 and last['MACD'] > prev['MACD']): stage, desc, order_type, stop_loss = "空头后期", "动能衰竭，等突破MA20再反手。", "观望", 0; action_plan = f"🛡️ 只平空不开多。"
            else:
                stage, desc, order_type = "空头中期", "绿柱放大，趋势极弱。", "做空"; stop_loss = ma20 + (atr * 1.0)
                action_plan = f"🔪 顺势做空：反弹到 <b>{ma20 - (atr*0.2):.0f}</b> 加 1 手空。<br>🚫 止损：<b>{stop_loss:.0f}</b>。"
        else:
            stage, desc, order_type, stop_loss = "观望", "均线纠缠，方向不明。", "观望", 0; action_plan = "🛑 多看少动。"

        # 动能的兜底
        mom = "红柱放大，多头动能强。" if last['MACD']>0 and last['MACD']>prev['MACD'] else ("绿柱放大，空头动能强。" if last['MACD']<0 and last['MACD']<prev['MACD'] else "动能交替，面临变盘。")
        kdj = f"J值{last['J']:.0f}，" + ("严重超买。" if last['J']>80 else ("严重超卖。" if last['J']<20 else "情绪正常。"))

        return stage, desc, mom, kdj, source_label, action_plan, order_type, price, stop_loss
    except:
        return "观望", "解析异常。", "未知", "未知", "报错", "观望为主。", "观望", price, 0

# ================= 真实的持仓急救计算器 =================
def get_position_advice(pos, current_price):
    dir_str = pos['dir']
    mult = MULTIPLIER.get(pos['name'], 10)
    # 盈亏 = (现价 - 均价) * 手数 * 乘数 * (1 if 多 else -1)
    pnl = (current_price - pos['avg']) * pos['lots'] * mult if dir_str == "多" else (pos['avg'] - current_price) * pos['lots'] * mult
    
    if pnl < 0:
        # 亏损单处理
        if dir_str == "空":
            # 空单被套，解套点在均价，减仓点在现价上方阻力
            cut_price = current_price + (pos['avg'] - current_price) * 0.5 # 反弹一半减仓
            return f"⚠️ 浮亏 {int(pnl)}元。反弹到 <b>{cut_price:.0f}</b> 附近必须减半仓（平{int(pos['lots']/2)+1}手），避免深套。"
        else:
            cut_price = current_price - (current_price - pos['avg']) * 0.5
            return f"⚠️ 浮亏 {int(pnl)}元。跌破 <b>{cut_price:.0f}</b> 附近必须减半仓（平{int(pos['lots']/2)+1}手），避免深套。"
    else:
        # 盈利单处理
        return f"✅ 浮盈 {int(pnl)}元。**保本铁律**：立刻将止损推到开仓价 {pos['avg']}，让利润奔跑！"

def build_html():
    now = (datetime.datetime.utcnow() + datetime.timedelta(hours=8)).strftime('%m-%d %H:%M')
    quotes = get_realtime_quotes()
    oil_pct, dxy_pct, vix_str = get_macro_data()
    
    # 分离焦煤和主要品种
    coking_coal = next((q for q in quotes if q["name"] == "焦煤"), None)
    main_quotes = [q for q in quotes if q["name"] != "焦煤"]
    price_dict = {q["name"]: q["price"] for q in main_quotes}

    html = f'<div style="font-family:-apple-system,sans-serif;max-width:600px;color:#000;font-size:14px;">'
    html += f'<div style="background:linear-gradient(135deg,#1a3c6e,#2b5aa0);color:#fff;text-align:center;padding:12px;border-radius:8px;font-size:16px;font-weight:bold;">顶级期货实战指令<br><span style="font-size:12px;">{now} | 权益:{CAPITAL:,}</span></div>'

    # 宏观面板
    html += f'<div style="background:#f5f7fa;border:1px solid #d9d9d9;border-radius:6px;padding:8px;margin:10px 0;font-size:13px;text-align:center;color:#000;">'
    html += f'🌍 <b>VIX：</b>{vix_str} ｜ 🛢️ <b>WTI：</b>{oil_pct:+.2f}% ｜ 💵 <b>美元：</b>{dxy_pct:+.2f}%'
    if coking_coal:
        html += f'<br>⛏️ <b>焦煤(煤化工风向标)：</b>{coking_coal["pct"]:+.2f}%'
    if dxy_pct > 0.5 or (coking_coal and coking_coal["pct"] < -2.0):
        html += f'<span style="color:#d32f2f;font-weight:bold;font-size:12px;"> ⚠️ 宏观利空扰动，谨慎做多！</span>'
    html += f'</div>'

    analysis_results = []
    for q in main_quotes:
        stage, trend_desc, macd_desc, kdj_desc, source_label, action_plan, order_type, buy_price, stop_loss = get_tech_analysis(q)
        analysis_results.append({"q": q, "order_type": order_type, "buy": buy_price, "stop": stop_loss})
        
        color_map = {"空头": ("#f6ffed", "#52c41a"), "多头": ("#fff5f5", "#ff4d4f")}
        bg_color, border_color = "#f5f5f5", "#d9d9d9"
        for k, v in color_map.items():
            if k in stage: bg_color, border_color = v; break

        html += f'<div style="background:{bg_color}; border:2px solid {border_color}; border-radius:8px; padding:12px; margin-bottom:12px;">'
        html += f'<div style="font-size:16px; font-weight:bold; margin-bottom:8px; border-bottom:1px dashed #ccc; padding-bottom:6px;">'
        html += f'{q["name"]} {q["code"]}：<span style="font-size:20px;">{q["price"]}</span> ({q["pct"]:+.2f}%)<span style="font-size:10px; color:#888; float:right;">{source_label}</span></div>'
        html += f'<div style="font-size:14px; line-height:1.7;">👉 <b>阶段：</b>{stage}<br>💬 <b>趋势：</b>{trend_desc}<br>🔥 <b>动能：</b>{macd_desc}<br>🌡️ <b>温度：</b>{kdj_desc}<br>'
        html += f'<div style="background:#fff; border:2px solid {border_color}; padding:10px; border-radius:6px; margin-top:10px;"><div style="font-weight:bold; color:{border_color};">🎯 指令：</div>{action_plan}</div></div></div>'

    # 资金阶梯
    html += f'<div style="background:#e3f2fd;border-left:4px solid #1e88e5;border-radius:6px;padding:12px;margin:15px 0 10px 0;">'
    html += f'<div style="font-size:16px;font-weight:bold;margin-bottom:6px;color:#000;">🛡️ 仓位控制 (死亏上限 {RISK_PER_TRADE}元)</div>'
    for res in analysis_results:
        q, mult = res["q"], MULTIPLIER.get(res["q"]["name"], 10)
        if res["order_type"] == "观望" or res["stop"] == 0:
            html += f'<div style="font-size:13px;color:#000;background:#fff;padding:6px;margin-bottom:4px;border-radius:4px;"><b>{q["name"]}</b>：观望，不建议开新仓。</div>'
        else:
            points = abs(res["buy"] - res["stop"]); money = points * mult
            max_l, first_l = max(int(RISK_PER_TRADE / money), 1), max(int(RISK_PER_TRADE / money / 2), 1)
            html += f'<div style="font-size:13px;color:#000;background:#fff;padding:6px;margin-bottom:4px;border-radius:4px;"><b>{q["name"]} ({res["order_type"]})</b>：{res["buy"]:.0f}进场，{res["stop"]:.0f}止损。1手亏{money:.0f}元。最多<b>{max_l}手</b>，首仓<b>{first_l}手</b>。</div>'
    html += f'</div>'

    # ================= 真实的持仓急救计算器 =================
    if POSITIONS:
        html += f'<div style="background:#ffebee;border-left:4px solid #d32f2f;border-radius:6px;padding:12px;margin:10px 0;">'
        html += f'<div style="font-size:16px;font-weight:bold;margin-bottom:8px;color:#000;">🚨 持仓真实急救</div>'
        for p in POSITIONS:
            cur_price = price_dict.get(p['name'], 0)
            if cur_price > 0:
                advice = get_position_advice(p, cur_price)
                html += f'<div style="font-size:13px;line-height:1.6;margin-bottom:6px;background:#fff;padding:6px;border-radius:4px;border:1px solid #ffcdd2;">'
                html += f'<b>{p["name"]} {p["dir"]}{p["lots"]}手</b>：{advice}</div>'
        html += f'</div>'

    return html

def main():
    token = os.environ.get("PUSHPLUS_TOKEN")
    if not token: return
    content = build_html()
    payload = {"token": token, "title": "顶级期货实战指令", "content": content, "template": "html"}
    try:
        requests.post("https://www.pushplus.plus/send", json=payload, timeout=30)
    except: pass

if __name__ == "__main__":
    main()
