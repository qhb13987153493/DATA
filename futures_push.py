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

# 获取实时期货价格 (保持新浪)
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

# 获取历史K线并计算指标 (使用腾讯接口)
def get_tech_analysis(name, code):
    # 腾讯期货代码映射
    prefix_map = {"甲醇": "MA", "PVC": "V", "白糖": "SR"}
    symbol = f"{prefix_map.get(name, '')}{code}"
    url = f"https://web.ifzq.gtimg.cn/appstock/app/kline/kline?param={symbol},day,,,120"
    
    headers = {"User-Agent": "Mozilla/5.0"}
    
    try:
        res = requests.get(url, headers=headers, timeout=10).json()
        data_dict = res.get('data', {})
        
        # 腾讯的返回结构比较深，需要层层提取
        if not data_dict or symbol not in data_dict or 'day' not in data_dict[symbol]:
            raise ValueError("腾讯接口未返回该品种的K线")
            
        klines = data_dict[symbol]['day']
        
        data = []
        for k in klines:
            # 腾讯格式: [日期, 开, 收, 高, 低, 量]
            data.append({
                'close': float(k[2]),
                'high': float(k[3]),
                'low': float(k[4])
            })
            
        df = pd.DataFrame(data)
        
        # 计算均线
        df['MA20'] = df['close'].rolling(window=20).mean()
        df['MA60'] = df['close'].rolling(window=60).mean()
        
        # 计算 MACD
        exp1 = df['close'].ewm(span=12, adjust=False).mean()
        exp2 = df['close'].ewm(span=26, adjust=False).mean()
        df['DIFF'] = exp1 - exp2
        df['DEA'] = df['DIFF'].ewm(span=9, adjust=False).mean()
        df['MACD'] = (df['DIFF'] - df['DEA']) * 2
        
        # 计算 KDJ
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
        print(f"解析 {name} 数据失败: {e}")
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

        html += f'<div style="background:{bg_color}; border:2px solid {border_color}; border-radius:8px; padding:12px; margin-bottom:12px; box-shadow:0 2px 4px rgba(0,0,0,0.05);">'
        
        html += f'<div style="font-size:16px; font-weight:bold; color:#000; margin-bottom:8px; border-bottom:1px dashed #ccc; padding-bottom:6px;">'
        html += f'{q["name"]} {q["code"]}：<span style="color:{q["color"]}; font-size:20px;">{q["price"]}</span> <span style="color:{q["color"]}; font-size:14px;">({q["pct"]:+.2f}%)</span>'
        html += f'</div>'
        
        html += f'<div style="color:#000; font-size:14px; line-height:1.7;">'
        html += f'👉 <b>当前阶段：</b><span style="font-size:16px; font-weight:bold;">{stage}</span><br>'
        html += f'💬 <b>大白话趋势：</b>{trend_desc}<br>'
        html += f'🔥 <b>资金动能：</b>{macd_desc}<br>'
        html += f'🌡️ <b>短线温度：</b>{kdj_desc}'
        html += f'</div></div>'

    html += f'<div style="background:#fff3e0;border-left:4px solid #f57c00;border-radius:6px;padding:12px;margin:15px 0 10px 0;">'
    html += f'<div style="font-size:16px;font-weight:bold;margin-bottom:8px;color:#000;">💰 资金阶梯分配表</div>'
    for q in quotes:
        m = MULTIPLIER.get(q["name"], 10)
        margin = round(q["price"] * m * 0.10)
        first = max(int(CAPITAL * 0.20 / margin), 1)
        add_lot = max(int(CAPITAL * 0.30 / margin), 1)
        cap = max(int(CAPITAL * 0.60 / margin), 1)
        html += f'<div style="font-size:13px;line-height:1.6;margin-bottom:6px;color:#000;">'
        html += f'<b>{q["name"]}</b>：首仓买 <b>{first}手</b> → 加仓到 {first+add_lot}手 → 最多不超过 <b>{cap}手</b>'
        html += f'</div>'
    html += f'<div style="font-size:12px;color:#000;margin-top:6px;font-weight:bold;">⚠️ 注意：上限是“最多能买这么多”，不是让你全买满！</div>'
    html += f'</div>'

    if POSITIONS:
        html += f'<div style="background:#ffebee;border-left:4px solid #d32f2f;border-radius:6px;padding:12px;margin:10px 0;">'
        html += f'<div style="font-size:16px;font-weight:bold;margin-bottom:8px;color:#000;">🚨 持仓急救（总亏 {TOTAL_PNL:,} 元）</div>'
        for p in POSITIONS:
            html += f'<div style="font-size:13px;line-height:1.6;margin-bottom:4px;color:#000;">{p["name"]} <b>{p["dir"]}{p["lots"]}手</b> (均价{p["avg"]}) | 盈亏: {p["pnl"]:+}元</div>'
        html += f'<div style="font-size:13px;color:#000;background:#fff;padding:8px;border-radius:4px;margin-top:8px;border:1px solid #ffcdd2;">'
        html += f'<b>大白话建议：</b>你手里拿的是空单，如果上面的分析显示目前是“大牛市”或者“资金动能强”，赶紧逢高减仓，别死扛了！千万别逆着大趋势加仓。'
        html += f'</div></div>'

    html += f'<div style="color:#666;font-size:12px;text-align:center;margin-top:15px;">数据来源：新浪财经 & 腾讯财经 | 指标依据：MA、MACD、KDJ 综合判定</div>'
    return html

def main():
    token = os.environ.get("PUSHPLUS_TOKEN")
    if not token:
        print("❌ 未在Secrets中配置PUSHPLUS_TOKEN")
        return
    content = build_html()
    payload = {"token": token, "title": "期货深度盯盘（指标版）", "content": content, "template": "html"}
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
