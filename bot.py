import os
import time
import requests
import pandas as pd
from pybit.unified_trading import HTTP

print("🚀 Auto Trading Bot Starting...")

# =========================
# ENV VARIABLES (RAILWAY)
# =========================
API_KEY = os.getenv("API_KEY")
API_SECRET = os.getenv("API_SECRET")
BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")

if not all([API_KEY, API_SECRET, BOT_TOKEN, CHAT_ID]):
    print("❌ Missing environment variables")
    exit()

# =========================
# BYBIT CONNECTION
# =========================
session = HTTP(
    testnet=True,
    api_key=API_KEY,
    api_secret=API_SECRET
)

symbol = "XAUUSDT" or "BTCUSDT" # IMPORTANT: most stable Bybit format
running = True

# =========================
# TELEGRAM
# =========================
def send_msg(text):
    try:
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
        requests.post(url, data={"chat_id": CHAT_ID, "text": text})
    except Exception as e:
        print("Telegram error:", e)

send_msg("🚀 Auto Trading Bot ONLINE")

# =========================
# MARKET DATA
# =========================
def get_data():
    data = session.get_kline(
        category="linear",
        symbol=symbol,
        interval="5",
        limit=100
    )

    df = pd.DataFrame(data["result"]["list"])
    df = df.iloc[:, :5]
    df.columns = ["time", "open", "high", "low", "close"]
    df = df.astype(float)

    return df

# =========================
# INDICATORS (YOUR STRATEGY)
# =========================
def indicators(df):
    # Bollinger Bands
    df["mid"] = df["close"].rolling(20).mean()
    df["std"] = df["close"].rolling(20).std()
    df["upper"] = df["mid"] + 2 * df["std"]
    df["lower"] = df["mid"] - 2 * df["std"]

    # Stochastic
    low14 = df["low"].rolling(14).min()
    high14 = df["high"].rolling(14).max()
    df["stoch"] = 100 * (df["close"] - low14) / (high14 - low14)

    return df

# =========================
# SIGNAL LOGIC (YOUR RULES)
# =========================
def signal(df):
    last = df.iloc[-1]
    prev = df.iloc[-2]

    mid_lower = (last["lower"] + last["mid"]) / 2
    mid_upper = (last["upper"] + last["mid"]) / 2

    buy = (
        last["close"] > mid_lower and
        prev["stoch"] < 30 and
        last["stoch"] > prev["stoch"]
    )

    sell = (
        last["close"] < mid_upper and
        prev["stoch"] > 70 and
        last["stoch"] < prev["stoch"]
    )

    if buy:
        return "buy"
    if sell:
        return "sell"
    return "hold"

# =========================
# ORDER EXECUTION (REAL)
# =========================
def place_order(side, price):
    try:
        qty = 0.01  # simple fixed lot (we can upgrade later)

        if side == "Buy":
            sl = price * 0.98
            tp = price * 1.06
        else:
            sl = price * 1.02
            tp = price * 0.94

        print(f"🚨 PLACING ORDER: {side} @ {price}")

        order = session.place_order(
            category="linear",
            symbol=symbol,
            side=side,
            orderType="Market",
            qty=qty,
            takeProfit=tp,
            stopLoss=sl
        )

        print("ORDER RESPONSE:", order)

        send_msg(f"📊 TRADE EXECUTED\n{side}\nEntry: {price}\nTP: {tp}\nSL: {sl}")

    except Exception as e:
        print("ORDER FAILED:", e)
        send_msg(f"ORDER FAILED: {e}")

# =========================
# MAIN LOOP
# =========================
while True:
    try:
        df = get_data()
        df = indicators(df)

        sig = signal(df)
        price = df.iloc[-1]["close"]

        print("Signal:", sig)

        if sig == "buy":
            place_order("Buy", price)

        elif sig == "sell":
            place_order("Sell", price)
        

        print(
            f"Close={last['close']}, "
            f"Stoch={last['stoch']:.2f}, "
            f"Lower={last['lower']:.2f}, "
            f"Upper={last['upper']:.2f}"
)

         sig = signal(df)

print("Signal:", sig)

        time.sleep(300)

    except Exception as e:
        print("MAIN ERROR:", e)
        time.sleep(10)
