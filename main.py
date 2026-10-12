import os
import requests
import pandas as pd
import time
from datetime import datetime

BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")

if not BOT_TOKEN or not CHAT_ID:
    print("Error: BOT_TOKEN and CHAT_ID env vars not set!")
    exit(1)

SYMBOLS = [
    "BTC_USDT", "ETH_USDT", "BNB_USDT", "XRP_USDT", "SOL_USDT",
    "TRX_USDT", "DOGE_USDT", "ADA_USDT", "LINK_USDT", "XLM_USDT",
    "BCH_USDT", "LTC_USDT", "AVAX_USDT", "DOT_USDT", "MATIC_USDT",
    "SHIB_USDT", "UNI_USDT", "ATOM_USDT", "ETC_USDT", "FIL_USDT",
    "APT_USDT", "ARB_USDT", "OP_USDT", "NEAR_USDT", "INJ_USDT",
    "SUI_USDT", "SEI_USDT", "TIA_USDT", "AAVE_USDT", "MKR_USDT",
    "COMP_USDT", "CRV_USDT", "SNX_USDT", "SAND_USDT", "MANA_USDT",
    "AXS_USDT", "GALA_USDT", "APE_USDT", "CHZ_USDT", "ENJ_USDT",
    "ZIL_USDT", "ONE_USDT", "ALGO_USDT", "VET_USDT", "ICP_USDT",
    "FTM_USDT", "EGLD_USDT", "THETA_USDT", "FLOW_USDT", "PEPE_USDT"
]
INTERVAL = "Min5"
RSI_PERIOD = 14


def send_telegram_message(message):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": CHAT_ID,
        "text": message,
        "parse_mode": "Markdown",
        "disable_web_page_preview": True
    }
    try:
        requests.post(url, json=payload, timeout=10)
        print(f"Sent: {message[:50]}...")
    except Exception as e:
        print(f"Send error: {e}")


def get_klines(symbol, interval, limit=100):
    """دریافت کندل‌ها از KCEX API (ساختار ستونی)"""
    url = f"https://www.kcex.com/fapi/v1/contract/kline/{symbol}"
    
    end_time = int(time.time())
    start_time = end_time - (limit * 5 * 60)
    
    params = {
        "symbol": symbol,
        "interval": interval,
        "start": start_time,
        "end": end_time
    }
    
    try:
        r = requests.get(url, params=params, timeout=15)
        data = r.json()
        
        if not isinstance(data, dict) or not data.get("success"):
            print(f"KCEX error {symbol}: {str(data)[:200]}")
            return None
        
        candles = data.get("data", {})
        if not candles or "close" not in candles:
            print(f"No candle data for {symbol}")
            return None
        
        # KCEX داده رو ستونی برمی‌گردونه، تبدیل به DataFrame
        df = pd.DataFrame({
            'open_time': candles.get('time', []),
            'open': candles.get('open', []),
            'high': candles.get('high', []),
            'low': candles.get('low', []),
            'close': candles.get('close', []),
            'volume': candles.get('vol', [])
        })
        
        # تبدیل به عدد
        for col in ['open', 'high', 'low', 'close', 'volume']:
            df[col] = pd.to_numeric(df[col], errors='coerce')
        
        # حذف ردیف‌های خالی و مرتب‌سازی بر اساس زمان (قدیمی به جدید)
        df = df.dropna().sort_values('open_time').reset_index(drop=True)
        
        return df
    except Exception as e:
        print(f"Fetch error {symbol}: {e}")
        return None


def calculate_rsi(series, period=14):
    delta = series.diff()
    gain = delta.where(delta > 0, 0.0)
    loss = -delta.where(delta < 0, 0.0)
    avg_gain = gain.ewm(alpha=1/period, min_periods=period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1/period, min_periods=period, adjust=False).mean()
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))


def check_divergence(symbol, df):
    if df is None or len(df) < RSI_PERIOD + 5:
        return None
    rsi_series = calculate_rsi(df['close'], RSI_PERIOD)
    recent = df.tail(4).copy()
    recent['rsi'] = rsi_series.tail(4)
    if recent['rsi'].isna().any():
        return None

    price_ll = recent['close'].iloc[-1] < recent['close'].iloc[-3] and recent['close'].iloc[-2] < recent['close'].iloc[-4]
    rsi_hl = recent['rsi'].iloc[-1] > recent['rsi'].iloc[-3] and recent['rsi'].iloc[-2] > recent['rsi'].iloc[-4]
    price_hh = recent['close'].iloc[-1] > recent['close'].iloc[-3] and recent['close'].iloc[-2] > recent['close'].iloc[-4]
    rsi_lh = recent['rsi'].iloc[-1] < recent['rsi'].iloc[-3] and recent['rsi'].iloc[-2] < recent['rsi'].iloc[-4]

    if price_ll and rsi_hl:
        return "BULLISH"
    elif price_hh and rsi_lh:
        return "BEARISH"
    return None


def main():
    print("Golden RSI bot started on KCEX...")
    send_telegram_message("🤖 *Golden RSI bot activated*\n\nExchange: *KCEX*\nWatching 5m timeframe...")

    last_alert = {}

    while True:
        for symbol in SYMBOLS:
            try:
                df = get_klines(symbol, INTERVAL)
                if df is None or len(df) < RSI_PERIOD + 5:
                    continue
                signal = check_divergence(symbol, df)
                current_time = time.time()

                if signal and (symbol not in last_alert or current_time - last_alert.get(symbol, 0) > 600):
                    price = df['close'].iloc[-1]
                    rsi_val = calculate_rsi(df['close']).iloc[-1]

                    if signal == "BULLISH":
                        emoji = "🟢📈"
                        title = "Bullish Divergence"
                    else:
                        emoji = "🔴📉"
                        title = "Bearish Divergence"

                    msg = (f"{emoji} *{title}*\n"
                           f"━━━━━━━━━━━━━━━\n"
                           f"💱 *Symbol:* {symbol}\n"
                           f"⏱ *TF:* 5m\n"
                           f"💰 *Price:* {price:.4f}\n"
                           f"📊 *RSI:* {rsi_val:.1f}\n"
                           f"🕒 {datetime.now().strftime('%H:%M:%S')}")

                    send_telegram_message(msg)
                    last_alert[symbol] = current_time

            except Exception as e:
                print(f"Process error {symbol}: {e}")

        time.sleep(60)


if __name__ == "__main__":
    main()
