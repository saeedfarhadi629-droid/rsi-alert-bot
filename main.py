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

SYMBOLS = ["SOLUSDT", "ETHUSDT", "DOGEUSDT", "ADAUSDT", "AAVEUSDT"]
INTERVAL = "5m"
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
    url = "https://api.binance.com/api/v3/klines"
    params = {"symbol": symbol, "interval": interval, "limit": limit}
    try:
        r = requests.get(url, params=params, timeout=10)
        data = r.json()
        if not isinstance(data, list):
            print(f"Data error {symbol}: {data}")
            return None
        df = pd.DataFrame(data, columns=[
            'open_time', 'open', 'high', 'low', 'close', 'volume',
            'close_time', 'quote_asset_volume', 'number_of_trades',
            'taker_buy_base_asset_volume', 'taker_buy_quote_asset_volume', 'ignore'
        ])
        df['close'] = df['close'].astype(float)
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
    print("Golden RSI bot started...")
    send_telegram_message("🤖 *Golden RSI bot activated*\n\nWatching 5m timeframe...")

    last_alert = {}

    while True:
        for symbol in SYMBOLS:
            try:
                df = get_klines(symbol, INTERVAL)
                if df is None:
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
                           f"⏱ *TF:* {INTERVAL}\n"
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
