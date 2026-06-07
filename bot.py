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

symbol = "BTCUSDT" # IMPORTANT: most stable Bybit format
running = True

last_update_id = 0

def get_balance():
    try:
        balance = session.get_wallet_balance(category="linear")

        print("BAL RAW:", balance)

        usdt = balance["result"]["list"][0]["totalEquity"]

        return float(usdt)

    except Exception as e:
        print("BAL ERROR:", e)
        return None

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


def check_commands():
    global running, last_update_id

    try:
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/getUpdates"
        res = requests.get(url).json()

        for update in res.get("result", []):

            update_id = update.get("update_id")

            if update_id is None or update_id <= last_update_id:
                continue

            last_update_id = update_id

            # ✅ SAFE MESSAGE ACCESS
            message = update.get("message", {})
            msg = message.get("text", "")
            
            print("DEBUG MSG:", msg)

            if not msg:
                continue

            msg = msg.strip().lower()

            print("COMMAND RECEIVED:", msg)

            # STOP
            if msg == "stop":
                running = False
                send_msg("⛔ Bot STOPPED")

            # START
            elif msg == "start":
                running = True
                send_msg("✅ Bot STARTED")

            # BALANCE
            elif msg == "balance":
                bal = get_balance()

                if bal is not None:
                    send_msg(f"💰 Balance: {bal} USDT")
                else:
                    send_msg("❌ Could not fetch balance")

    except Exception as e:
        print("CMD ERROR:", e)

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
        check_commands()

        if not running:
            time.sleep(5)
            continue

        df = get_data()
        df = indicators(df)

        ticker = session.get_tickers(
            category="linear",
            symbol="BTCUSDT"
        )

        live_price = ticker["result"]["list"][0]["lastPrice"]
        print("LIVE BTC PRICE:", live_price)

        sig = signal(df)

trend = "up" if df["close"].iloc[-1] > df["close"].rolling(50).mean().iloc[-1] else "down"
volatility = df["close"].pct_change().std()

print(f"Trend: {trend} | Volatility: {volatility}")

        last = df.iloc[-1]

        print(
            f"Close={last['close']}, "
            f"Stoch={last['stoch']:.2f}, "
            f"Lower={last['lower']:.2f}, "
            f"Upper={last['upper']:.2f}"
        )

        print("Signal:", sig)

        price = df.iloc[-1]["close"]

        if sig == "buy" and trend == "up" and volatility < 0.02:
    place_order("Buy", price)

elif sig == "sell" and trend == "down" and volatility < 0.02:
    place_order("Sell", price)
            place_order("Buy", price)


        time.sleep(300)

    except Exception as e:
        print("MAIN ERROR:", e)
        time.sleep(10)
