# encoding:utf-8
import os, json, requests, datetime
import pandas as pd

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
            if len(parts) > 8:
                name_code = parts[0]
                name = "".join([c for c in name_code if not c.isdigit()])
                code = "".join([c for c in name_code if c.isdigit()])
                price = float(parts[8]) if parts[8] else float(parts[4])
                pre_settle = float(parts[4]) if parts[4] else 1
                pct = round((price - pre_settle) / pre_settle * 100, 2) if pre_settle != 0 else 0
                color = "#b71c1c" if pct >= 0 else "#1b5e20"
                quotes.append({"name": name, "code": code, "price": price, "pct": pct, "color": color})
        return quotes
    except Exception as e:
        return []

# 获取历史K线并计算MACD、KDJ、均线 (使用腾讯接口)
def get_tech_analysis(name, code):
    # 腾讯期货代码，例如 MA2701
    symbol = f"{name}{code}"
    # 腾讯日K线接口
    url = f"https://web.ifzq.gtimg.cn/appstock/app/kline/kline?param={code},day,,,120"
    
    try:
        res = requests.get(url, timeout=10).json()
        klines = res['data'][code]['day']
        
        data = []
        for k in klines:
            # 腾讯格式: ["2023-10-24", "开盘", "收盘", "最高", "最低", "成交量"]
            data.append({
                'close': float(k[2]),
                'high': float(k[3]),
                'low': float(k[4])
            })
            
        df = pd.DataFrame(data)
        
        # 1. 计算均线 (MA20, MA60)
        df['MA20'] = df['close'].rolling(window=20).mean()
        df['MA60'] = df['close'].rolling(window=60).mean()
        
        # 2. 计算 MACD (12, 26, 9)
        exp1 = df['close'].ewm(span=12, adjust=False).mean()
        exp2 = df['close'].ewm(span=26, adjust=False).mean()
        df['DIFF'] = exp1 - exp2
        df['DEA'] = df['DIFF'].ewm(span=9, adjust=False).mean()
        df['MACD'] = (df['DIFF'] - df['DEA']) * 2
        
        # 3. 计算 KDJ (9, 3, 3)
        low_min = df['low'].rolling(window=9).min()
        high_max = df['high'].rolling(window=9).max()
        rsv = (df['close'] - low_min) / (high_max - low_min) * 100
        df['K'] = rsv.ewm(com=2, adjust=False).mean()
        df['D'] = df['K'].ewm(com=2, adjust=False).mean()
        df['J'] = 3 * df['K'] - 2 * df['D']

        last = df.iloc[-1]
        prev = df.iloc[-2]
        
        # ================= 大白话分析逻辑 =================
        if last['close'] > last['MA20'] and last['MA20'] > last['MA60']:
            trend_stage = "长线大牛市"
            trend_desc = "价格踩在所有均线上方，大方向坚决看涨，回踩就是机会。"
        elif last['close'] < last['MA20'] and last['MA20'] < last['MA60']:
            trend_stage = "长线大熊市"
            trend_desc = "价格被所有均线压着打，大方向坚决看跌，反弹就是诱多。"
        elif last['close'] > last['MA60']:
            trend_stage = "长线多头，短线洗盘"
            trend_desc = "大方向还在涨，但最近几天有点涨不动了，在回调休息。"
        else:
            trend_stage = "长线空头，短线反弹"
            trend_desc = "大方向还在跌，但最近几天跌不动了，空头在平仓撤退。"

        if last['MACD'] > 0 and prev['MACD'] <= 0:
            macd_momentum = "刚出红柱（金叉），资金开始进场，要涨。"
        elif last['MACD'] > 0 and last['MACD'] > prev['MACD']:
            macd_momentum = "红柱持续放大，资金在猛冲，多头很强。"
        elif last['MACD'] < 0 and prev['MACD'] >= 0:
            macd_momentum = "刚出绿柱（死叉），资金开始撤退，要跌。"
        elif last['MACD'] < 0 and last['MACD'] < prev['MACD']:
            macd_momentum = "绿柱持续放大，资金在狂砸，空头很强。"
        else:
            macd_momentum = "红绿柱在缩小，涨跌动能都在衰竭，快变盘了。"

        if last['J'] > 80:
            kdj_momentum = f"J值高达{last['J']:.0f}，短线严重超买，随时会大回调，千万别追。"
        elif last['J'] < 20:
            kdj_momentum = f"J值低至{last['J']:.0f}，短线严重超卖，随时会大反弹，别追空。"
        else:
            kdj_momentum = f"J值处于{last['J']:.0f}，短线情绪正常，跟着大方向做就行。"
            
        return trend_stage, trend_desc, macd_momentum, kdj_momentum
    except Exception as e:
        print(f"获取 {name} 数据失败: {e}")
        return "日内震荡", "历史数据暂不可用，纯看日内表现。", "动能未明", "短线温度未知"

def build_html():
    now = (datetime.datetime.utcnow() + datetime.timedelta(hours=8)).strftime('%m-%d %H:%M')
    quotes = get_realtime_quotes()

    html = f'<div style="font-family:-apple-system,sans-serif;max-width:600px;color:#000;font-size:14px;">'
    html += f'<div style="background:linear-gradient(135deg,#1a3c6e,#2b5aa0);color:#fff;text-align:center;padding:12px;border-radius:8px;font-size:16px;font-weight:bold;">期货深度盯盘（指标版）<br><span style="font-size:12px;">{now} | 权益:{CAPITAL:,}</span></div>'

    html += f'<div style="font-size:16px;font-weight:bold;margin:15px 0 10px 0;text-align:center;color:#000;">📌 核心速览（多红空绿）</div>'

    for q in quotes:
        stage, trend_desc, macd_desc, kdj_desc = get_tech_analysis(q["name"], q["code"])
        
        if q["pct"] > 0:
            bg_color, border_color = "#fff5f5", "#ff4d4f"
        elif q["pct"] < 0:
            bg_color, border_color = "#f6ffed", "#52c41a"
        else:
            bg_color, border_color = "#f5f5f5", "#d9d9d9"

        html += f'<div style="background:{bg_color}; border:2px solid {border_color}; border-radius:8px; padding:12px; margin-bottom:12px; box-shadow:0 2px 4px rgba(
