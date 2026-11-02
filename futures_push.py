# encoding:utf-8
import os, json, requests, datetime
import pandas as pd
import numpy as np

# ================= 你的账户核心数据 =================
CAPITAL = 289485
RISK_PER_TRADE = round(CAPITAL * 0.01) # 单笔风控上限：约 2895 元
POSITIONS = [
    {"name": "甲醇", "code": "2701", "dir": "空", "lots": 7, "avg": 2889.43},
    {"name": "甲醇", "code": "2701", "dir": "多", "lots": 2, "avg": 3051.50},
    {"name": "PVC", "code": "2701", "dir": "空", "lots": 13, "avg": 5096.46},
]
MULTIPLIER = {"甲醇": 10, "PVC": 5, "白糖": 10}
DATA_FILE = "kline_data.json"
# ====================================================

def get_realtime_quotes():
    # 加入了 原油 和 焦煤 作为宏观风向标
    symbols = {"甲醇": "nf_MA2701", "PVC": "nf_V2701", "白糖": "nf_SR2701", "焦煤": "nf_JM2701", "原油": "nf_SC2701"}
    url = "http://hq.sinajs.cn/list=" + ",".join(symbols.values())
    headers = {"Referer": "http://finance.sina.com.cn"}
    try:
        data = requests.get(url, headers=headers, timeout=10).text
        quotes = []
        for line in data.strip().split('\n'):
            if '"' not in line: continue
            parts = line.split('"')[1].split(',')
            if len(parts) > 14:
                name_code = parts[0]
                name = "".join([c for c in name_code if not c.isdigit()])
                code = "".join([c for c in name_code if c.isdigit()])
                price = float(parts[8]) if parts[8] else float(parts[4])
                pre_settle = float(parts[4]) if parts[4] else 1
                pct = round((price - pre_settle) / pre_settle * 100, 2) if pre_settle != 0 else 0
                oi = float(parts[13]) if len(parts)>13 and parts[13] else 0 
                quotes.append({
                    "name": name, "code": code, "price": price, "pct": pct,
                    "open": float(parts[1]) if parts[1] else 0, 
                    "high": max(float(parts[2]), float(parts[3])), 
                    "low": min(float(parts[2]), float(parts[3])),
                    "pre_settle": pre_settle, "oi": oi
                })
        return quotes
    except: return []

def update_history(name, code, price, high, low, oi):
    try:
        if os.path.exists(DATA_FILE):
            with open(DATA_FILE, "r") as f: history = json.load(f)
        else: history = {}
    except:
        history = {}
        
    key = f"{name}_{code}"
    if key not in history: history[key] = []
    today = datetime.datetime.now().strftime("%Y-%m-%d")
    updated = False
    for row in history[key]:
        if row["date"] == today:
            row["close"] = price; row["high"] = max(row.get("high", price), high); row["low"] = min(row.get("low", price), low); row["oi"] = oi
            updated = True; break
    if not updated: history[key].append({"date": today, "close": price, "high": high, "low": low, "oi": oi})
    
    try:
        with open(DATA_FILE, "w") as f: json.dump(history, f)
    except: pass
    return history[key]

def fetch_kline_data(name, code, period="day"):
    prefix = {"甲醇": "MA", "PVC": "V", "白糖": "SR", "原油": "SC", "焦煤": "JM"}.get(name, "")
    symbol_tx = f"{prefix}{code}"
    headers = {"User-Agent": "Mozilla/5.0"}
    try:
        url_tx = f"https://web.ifzq.gtimg.cn/appstock/app/kline/kline?param={symbol_tx},{period},,,120"
        res = requests.get(url_tx, headers=headers, timeout=5).json()
        return [{'close': float(k[2]), 'high': float(k[3]), 'low': float(k[4])} for k in res['data'][symbol_tx][period]]
    except: return None

def get_tech_analysis(q):
    try:
        name, code = q["name"], q["code"]
        price, high, low, open_p, pre_settle, oi = q["price"], q["high"], q["low"], q["open"], q["pre_settle"], q["oi"]
        
        data_d = fetch_kline_data(name, code, "day")
        data_60 = fetch_kline_data(name, code, "m60")
        
        stop_loss, action_plan, order_type = 0, "", "观望"
        source_label = "历史数据"
        diff = (high - low) if high > low else price * 0.01
        atr = diff / 2

        # 量仓诊断
        if price > open_p and oi > 0: vol_price_state = "增仓上涨"
        elif price < open_p and oi > 0: vol_price_state = "增仓下跌"
        elif price > open_p and oi == 0: vol_price_state = "减仓上涨"
        else: vol_price_state = "减仓下跌"

        # 放宽跳空阈值到 3.0%
        gap_pct = abs(open_p - pre_settle) / pre_settle * 100 if pre_settle > 0 else 0
        
        if not data_d:
            history_list = update_history(name, code, price, high, low, oi)
            if len(history_list) < 20:
                source_label = f"自建库({len(history_list)}/20)"
                if gap_pct > 3.0:
                    return "极端跳空", "开盘偏离昨结超3%，情绪异常。", vol_price_state, "未知", source_label, "🛑 情绪盘，停止挂单。", "观望", price, 0
                elif price >= low + diff * 0.7 and price > open_p: 
                    stage, desc = "多头中期(日内)", "日内多头占优。"; order_type = "做多"; stop_loss = low - (atr * 0.3)
                    action_plan = f"🛑 轻仓试多：现价 <b>{price}</b>。<br>🚫 止损：<b>{stop_loss:.0f}</b>。"
                elif price <= low + diff * 0.3 and price < open_p: 
                    stage, desc = "空头中期(日内)", "日内空头占优。"; order_type = "做空"; stop_loss = high + (atr * 0.3)
                    action_plan = f"🛑 轻仓试空：现价 <b>{price}</b>。<br>🚫 止损：<b>{stop_loss:.0f}</b>。"
                else: 
                    stage, desc, order_type, stop_loss = "观望", "卡在中间。", "观望", 0
                    action_plan = f"🛑 多看少动。"
                return stage, desc, vol_price_state, "日内波动", source_label, action_plan, order_type, price, stop_loss
            else:
                data_d = history_list; source_label = "自建库"

        df = pd.DataFrame(data_d)
        df['MA20'] = df['close'].rolling(window=20).mean(); df['MA60'] = df['close'].rolling(window=60).mean()
        df['std'] = df['close'].rolling(window=20).std()
        df['upper'] = df['MA20'] + (df['std'] * 2); df['lower'] = df['MA20'] - (df['std'] * 2)
        exp1 = df['close'].ewm(span=12, adjust=False).mean(); exp2 = df['close'].ewm(span=26, adjust=False).mean()
        df['DIFF'] = exp1 - exp2; df['DEA'] = df['DIFF'].ewm(span=9, adjust=False).mean(); df['MACD'] = (df['DIFF'] - df['DEA']) * 2
        df['TR'] = np.maximum(df['high'] - df['low'], np.maximum(abs(df['high'] - df['close'].shift()), abs(df['low'] - df['close'].shift())))
        atr_val = df['TR'].rolling(window=14).mean().iloc[-1]
        atr = atr_val if not pd.isna(atr_val) else atr
        
        low_min = df['low'].rolling(window=9).min(); high_max = df['high'].rolling(window=9).max()
        rsv = (df['close'] - low_min) / (high_max - low_min) * 100
        df['K'] = rsv.ewm(com=2, adjust=False).mean(); df['D'] = df['K'].ewm(com=2, adjust=False).mean(); df['J'] = 3 * df['K'] - 2 * df['D']

        last, prev = df.iloc[-1], df.iloc[-2]
        ma20, ma60 = last['MA20'] if not pd.isna(last['MA20']) else price, last['MA60'] if not pd.isna(last['MA60']) else price
        upper, lower = last['upper'] if not pd.isna(last['upper']) else price*2, last['lower'] if not pd.isna(last['lower']) else price*0.5
        filter_band = atr * 0.3

        # 60分钟共振过滤
        m60_overbought = False
        if data_60:
            try:
                df60 = pd.DataFrame(data_60)
                low60 = df60['low'].rolling(window=9).min(); high60 = df60['high'].rolling(window=9).max()
                rsv60 = (df60['close'] - low60) / (high60 - low60) * 100
                k60 = rsv60.ewm(com=2, adjust=False).mean(); d60 = k60.ewm(com=2, adjust=False).mean()
                j60 = (3 * k60 - 2 * d60).iloc[-1]
                if j60 > 90: m60_overbought = True
            except: pass

        if gap_pct > 3.0:
            stage, desc, order_type, stop_loss = "极端跳空", "开盘跳空超3%，原指标失效。", "观望", 0
            action_plan = f"🛑 等待缺口回补，或站稳均线（{ma20:.0f}）再操作。"
        elif last['close'] > ma20 and ma20 > ma60:
            if vol_price_state == "减仓上涨":
                stage, desc, order_type, stop_loss = "多头陷阱", "价格在涨，但持仓量在减！虚涨，严禁追多！", "观望", 0
                action_plan = f"🚫 严禁追多：主力在撤退，多单赶紧落袋。"
            elif last['close'] >= upper: 
                stage, desc, order_type, stop_loss = "多头极值(超买)", "顶破布林带上轨，防暴跌。", "观望", 0
                action_plan = f"🚫 严禁追多，获利了结。"
            elif last['J'] > 80 or (last['MACD'] > 0 and last['MACD'] < prev['MACD']): 
                stage, desc, order_type, stop_loss = "多头后期", "动能衰竭，等跌破MA20再反手。", "观望", 0
                action_plan = f"🛡️ 只平多不开空。"
            elif m60_overbought:
                stage, desc, order_type, stop_loss = "日线多头", "⚠️但60分钟严重超买，短线有回调需求。", "观望", 0
                action_plan = f"👀 等60分钟回调企稳，或等回踩 <b>{ma20:.0f}</b> 再进多。"
            else:
                stage, desc, order_type = "多头中期", "增仓上涨/红柱放大，趋势正猛。", "做多"
                stop_loss = ma20 - (atr * 1.0)
                buy_point = max(ma20 + filter_band, price)
                action_plan = f"🚀 顺势做多：站稳 <b>{buy_point:.0f}</b> 加 1 手多。<br>🚫 止损：<b>{stop_loss:.0f}</b>。"
        elif last['close'] < ma20 and ma20 < ma60:
            if vol_price_state == "减仓下跌":
                stage, desc, order_type, stop_loss = "空头陷阱", "价格在跌，但持仓量在减！虚跌，严禁追空！", "观望", 0
                action_plan = f"🚫 严禁追空：空单赶紧落袋。"
            elif last['close'] <= lower: 
                stage, desc, order_type, stop_loss = "空头极值(超卖)", "跌破布林带下轨，防反弹。", "观望", 0
                action_plan = f"🚫 严禁追空，获利了结。"
            elif last['J'] < 20 or (last['MACD'] < 0 and last['MACD'] > prev['MACD']): 
                stage, desc, order_type, stop_loss = "空头后期", "动能衰竭，等突破MA20再反手。", "观望", 0
                action_plan = f"🛡️ 只平空不开多。"
            else:
                stage, desc, order_type = "空头中期", "增仓下跌/绿柱放大，趋势极弱。", "做空"
                stop_loss = ma20 + (atr * 1.0)
                sell_point = min(ma20 - filter_band, price)
                action_plan = f"🔪 顺势做空：跌破 <b>{sell_point:.0f}</b> 加 1 手空。<br>🚫 止损：<b>{stop_loss:.0f}</b>。"
        else:
            stage, desc, order_type, stop_loss = "观望", "均线纠缠，方向不明。", "观望", 0
            action_plan = "🛑 多看少动。"

        mom = "红柱放大，多头动能强。" if last['MACD']>0 and last['MACD']>prev['MACD'] else ("绿柱放大，空头动能强。" if last['MACD']<0 and last['MACD']<prev['MACD'] else "动能交替，面临变盘。")
        kdj = f"J值{last['J']:.0f}，" + ("严重超买。" if last['J']>80 else ("严重超卖。" if last['J']<20 else "情绪正常。"))
        
        action_plan += f"<br>🏃 <b>加仓与保本：</b>盈利超1倍ATR({atr*1.0:.0f}点)，推保本；盈利超2倍ATR，推移动止损。"
        return stage, desc, vol_price_state, kdj, source_label, action_plan, order_type, price, stop_loss
    except Exception as e:
        print(f"Error analyzing {q.get('name')}: {e}")
        return "观望", "解析异常。", "未知", "未知", "报错", "观望为主。", "观望", q.get("price", 0), 0

def get_position_advice(pos, current_price):
    try:
        dir_str = pos['dir']
        mult = MULTIPLIER.get(pos['name'], 10)
        pnl = (current_price - pos['avg']) * pos['lots'] * mult if dir_str == "多" else (pos['avg'] - current_price) * pos['lots'] * mult
        
        slip_pt = 3
        if pnl < 0:
            if dir_str == "空":
                cut_price = current_price + (pos['avg'] - current_price) * 0.5 
                return f"⚠️ 浮亏 {int(pnl)}元。反弹到 <b>{cut_price:.0f}</b> 附近必须减半仓。条件单止损多填 <b>{slip_pt}</b> 个点防扫损。"
            else:
                cut_price = current_price - (current_price - pos['avg']) * 0.5
                return f"⚠️ 浮亏 {int(pnl)}元。跌破 <b>{cut_price:.0f}</b> 附近必须减半仓。条件单止损多填 <b>{slip_pt}</b> 个点防扫损。"
        else:
            return f"✅ 浮盈 {int(pnl)}元。**保本铁律**：立刻将止损推到开仓价 {pos['avg']}（加 {slip_pt} 个点缓冲）。"
    except: return "计算异常"

def build_html():
    now = (datetime.datetime.utcnow() + datetime.timedelta(hours=8)).strftime('%m-%d %H:%M')
    quotes = get_realtime_quotes()
    
    oil_quote = next((q for q in quotes if q["name"] == "原油"), None)
    coking_coal = next((q for q in quotes if q["name"] == "焦煤"), None)
    
    main_quotes = [q for q in quotes if q["name"] not in ["原油", "焦煤"]]
    price_dict = {q["name"]: q["price"] for q in main_quotes}

    html = f'<div style="font-family:-apple-system,sans-serif;max-width:600px;color:#000;font-size:14px;">'
    html += f'<div style="background:linear-gradient(135deg,#1a3c6e,#2b5aa0);color:#fff;text-align:center;padding:12px;border-radius:8px;font-size:16px;font-weight:bold;">顶级期货实战指令<br><span style="font-size:12px;">{now} | 权益:{CAPITAL:,}</span></div>'

    month = datetime.datetime.now().month
    if month in [11, 12]:
        html += f'<div style="background:#ffebee;border:2px solid #d32f2f;border-radius:6px;padding:10px;margin:10px 0;font-size:14px;text-align:center;color:#b71c1c;font-weight:bold;">'
        html += f'🚨 <b>时间警报：01 合约即将交割！</b><br>主力正在移仓换月，流动性骤降，极易假突破，严禁开新仓！'
        html += f'</div>'

    html += f'<div style="background:#f5f7fa;border:1px solid #d9d9d9;border-radius:6px;padding:8px;margin:10px 0;font-size:13px;text-align:center;color:#000;">'
    if oil_quote:
        oil_color = "#b71c1c" if oil_quote["pct"] > 0 else "#1b5e20"
        html += f'🛢️ <b>原油：</b><span style="color:{oil_color};font-weight:bold;">{oil_quote["pct"]:+.2f}%</span>'
    if coking_coal:
        coal_color = "#b71c1c" if coking_coal["pct"] > 0 else "#1b5e20"
        html += f' ｜ ⛏️ <b>焦煤：</b><span style="color:{coal_color};font-weight:bold;">{coking_coal["pct"]:+.2f}%</span>'
    if oil_quote and (oil_quote["pct"] > 2.0 or oil_quote["pct"] < -2.0):
        html += f'<br><span style="color:#d32f2f;font-weight:bold;font-size:12px;"> ⚠️ 原油异动剧烈，化工品风险放大！</span>'
    html += f'</div>'

    analysis_results = []
    for q in main_quotes:
        stage, trend_desc, macd_desc, kdj_desc, source_label, action_plan, order_type, buy_price, stop_loss = get_tech_analysis(q)
        analysis_results.append({"q": q, "order_type": order_type, "buy": buy_price, "stop": stop_loss})
        
        color_map = {"空头": ("#f6ffed", "#52c41a"), "多头": ("#fff5f5", "#ff4d4f"), "跳空": ("#fff8e1", "#f57c00"), "陷阱": ("#fff8e1", "#f57c00")}
        bg_color, border_color = "#f5f5f5", "#d9d9d9"
        for k, v in color_map.items():
            if k in stage: bg_color, border_color = v; break

        html += f'<div style="background:{bg_color}; border:2px solid {border_color}; border-radius:8px; padding:12px; margin-bottom:12px;">'
        html += f'<div style="font-size:16px; font-weight:bold; margin-bottom:8px; border-bottom:1px dashed #ccc; padding-bottom:6px;">'
        html += f'{q["name"]} {q["code"]}：<span style="font-size:20px;">{q["price"]}</span> ({q["pct"]:+.2f}%)<span style="font-size:10px; color:#888; float:right;">{source_label}</span></div>'
        
        if abs(q["pct"]) > 6.0:  
            html += f'<div style="background:#d32f2f;color:#fff;padding:6px;border-radius:4px;margin-bottom:8px;font-size:12px;font-weight:bold;">🚨 极端行情：涨跌幅超 6%！禁止追单！</div>'

        html += f'<div style="font-size:14px; line-height:1.7;">👉 <b>阶段：</b>{stage}<br>💬 <b>趋势：</b>{trend_desc}<br>🔥 <b>动能/量仓：</b>{macd_desc}<br>🌡️ <b>温度：</b>{kdj_desc}<br>'
        html += f'<div style="background:#fff; border:2px solid {border_color}; padding:10px; border-radius:6px; margin-top:10px;"><div style="font-weight:bold; color:{border_color};">🎯 指令：</div>{action_plan}</div></div></div>'

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

    if POSITIONS:
        html += f'<div style="background:#ffebee;border-left:4px solid #d32f2f;border-radius:6px;padding:12px;margin:10px 0;">'
        html += f'<div style="font-size:16px;font-weight:bold;margin-bottom:8px;color:#000;">🚨 持仓真实急救</div>'
        for p in POSITIONS:
            cur_price = price_dict.get(p['name'], 0)
            if cur_price > 0:
                advice = get_position_advice(p, cur_price)
                html += f'<div style="font-size:13px;line-height:1.6;margin-bottom:6px;background:#fff;padding:6px;border-radius:4px;border:1px solid #ffcdd2;">'
                html += f'<b>{p["name"]} {p["dir"]}{p["lots"]}手</b>：{advice}</div>'
        
        html += f'<div style="font-size:12px;color:#b71c1c;background:#fff3f3;padding:8px;border-radius:4px;margin-top:8px;border:1px solid #ffcdd2;line-height:1.5;">'
        html += f'🔍 <b>敞口诊断：</b>当前持仓高度集中在【能化板块】。面临板块单边双杀风险，切忌同向开仓！'
        html += f'</div></div>'

    html += f'<div style="border-top:1px dashed #999; margin-top:15px; padding-top:10px; font-size:12px; color:#555; line-height:1.5;">'
    html += f'💡 <b>情绪熔断：</b>如果近三天累计亏损超 {int(CAPITAL * 0.03):,} 元，强制空仓休息一天，严禁报复性交易！'
    html += f'</div></div>'
    
    return html

def main():
    token = os.environ.get("PUSHPLUS_TOKEN")
    if not token: 
        print("❌ 未在Secrets中配置PUSHPLUS_TOKEN")
        return
    
    content = build_html()
    payload = {"token": token, "title": "顶级期货实战指令", "content": content, "template": "html"}
    try:
        resp = requests.post("https://www.pushplus.plus/send", json=payload, timeout=30)
        if resp.json().get("code") == 200:
            print("✅ 推送成功")
        else:
            print(f"❌ 推送失败: {resp.json().get('msg')}")
    except Exception as e:
        print(f"❌ 网络错误: {e}")

if __name__ == "__main__":
    main()
