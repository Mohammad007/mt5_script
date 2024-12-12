from pybit.unified_trading import HTTP
import pandas as pd
import numpy as np
import time
from colorama import Fore, Style
import pandas_ta as ta

API_KEY = "J1OgMqNv77Y58f5A36"
API_SECRET = "p2mpFwCgTQk93xo5AOcUJ05GQdQsxrHV5hSm"

# Initialize session with an increased recv_window and timeout
session = HTTP(
    demo=True,
    api_key=API_KEY,
    api_secret=API_SECRET
)

# Trading parameters
LEVERAGE = 12  # Fixed leverage for all trades
TAKE_PROFIT = 1  # Take profit target in USDT
STOP_LOSS = 10  # Stop loss target in USDT
WALLET_PERCENTAGE = 0.40  # Risk per trade
COINS = ["TRXUSDT", "XRPUSDT", "DOGEUSDT", "ADAUSDT", "DOTUSDT", "ONTUSDT", "QTUMUSDT", "MEMEUSDT", "THEUSDT", "ZRCUSDT", "OLUSDT", "BANUSDT", "TAIUSDT", "ACTUSDT", "ALGOUSDT", "FTMUSDT", "GOATUSDT", "GALAUSDT", "EOSUSDT", "ENAUSDT", "CRVUSDT"]

def get_wallet_balance():
    """Get current wallet balance"""
    try:
        wallet = session.get_wallet_balance(accountType="UNIFIED")
        return float(wallet["result"]["list"][0]["totalEquity"])
    except Exception as e:
        print(f"Error getting wallet balance: {e}")
        return 0

def get_min_trading_qty(symbol):
    """Get minimum trading quantity and quantity step for a symbol"""
    try:
        instruments = session.get_instruments_info(
            category="linear",
            symbol=symbol
        )
        instrument = instruments["result"]["list"][0]
        return float(instrument["lotSizeFilter"]["minOrderQty"]), float(instrument["lotSizeFilter"]["qtyStep"])
    except Exception as e:
        print(f"Error getting trading rules for {symbol}: {e}")
        return 0, 0

def calculate_ma(data, length=30, ma_type='HMA'):
    """Calculate Moving Average based on type"""
    if ma_type == 'SMA':
        return ta.sma(data, length=length)
    elif ma_type == 'EMA':
        return ta.ema(data, length=length)
    elif ma_type == 'WMA':
        return ta.wma(data, length=length)
    elif ma_type == 'HMA':
        return ta.hma(data, length=length)
    elif ma_type == 'RMA':
        return ta.rma(data, length=length)
    return ta.sma(data, length=length)

def get_trading_signal(df):
    """Check for BOS (Break of Structure) signals"""
    ma = calculate_ma(df['close'], length=30, ma_type='HMA')
    df['ma'] = ma
    
    # Calculate crossovers
    df['ma_co'] = (df['close'] > df['ma']) & (df['close'].shift(1) <= df['ma'].shift(1))
    df['ma_cu'] = (df['close'] < df['ma']) & (df['close'].shift(1) >= df['ma'].shift(1))
    
    # Check for BOS conditions
    last_row = df.iloc[-1]
    
    if last_row['ma_co']:  # Potential buy signal
        # Check if price breaks above recent high after crossing above MA
        recent_high = df['high'].rolling(window=5).max().iloc[-2]
        if last_row['close'] > recent_high:
            return "LONG"
            
    elif last_row['ma_cu']:  # Potential sell signal
        # Check if price breaks below recent low after crossing below MA
        recent_low = df['low'].rolling(window=5).min().iloc[-2]
        if last_row['close'] < recent_low:
            return "SHORT"
            
    return "NEUTRAL"

def calculate_fib_levels(high, low):
    """Calculate Fibonacci retracement levels"""
    diff = high - low
    return {
        '0.000': high,
        '0.236': high - (diff * 0.236),
        '0.382': high - (diff * 0.382),
        '0.500': high - (diff * 0.500),
        '0.618': high - (diff * 0.618),
        '0.786': high - (diff * 0.786),
        '1.000': low,
        '-0.236': high + (diff * 0.236),
        '-0.618': high + (diff * 0.618),
        '-1.000': high + diff
    }

def place_order(symbol, side, current_price):
    try:
        # Set leverage
        session.set_leverage(
            category="linear",
            symbol=symbol,
            buyLeverage=str(LEVERAGE),
            sellLeverage=str(LEVERAGE)
        )
    except Exception as e:
        if "leverage not modified" in str(e) or "110043" in str(e):
            pass
        else:
            print(f"Error setting leverage for {symbol}: {e}")
            pass

    available_balance = get_wallet_balance() * WALLET_PERCENTAGE
    max_position_value = available_balance * LEVERAGE
    qty = max_position_value / current_price
    
    min_qty, qty_step = get_min_trading_qty(symbol)
    qty = max(min_qty, qty)
    qty = round(qty / qty_step) * qty_step
    
    while (qty * current_price) > max_position_value:
        qty -= qty_step
        
    if qty < min_qty:
        print(Fore.RED + f"Not enough balance for {symbol}" + Style.RESET_ALL)
        return 0

    try:
        # Get recent high/low for Fibonacci levels
        klines = session.get_kline(
            category="linear",
            symbol=symbol,
            interval="3",
            limit=70
        )
        
        df = pd.DataFrame(klines["result"]["list"])
        high = float(df[2].max())  # Column 2 is high
        low = float(df[3].min())   # Column 3 is low
        fib_levels = calculate_fib_levels(high, low)

        # Calculate entry, sl and tp based on Fibonacci levels
        if side == "Buy":
            entry = current_price
            sl = fib_levels['1.000']     # Stop loss at 100% retracement
            tp = fib_levels['-1.000']    # Take profit at -100% extension
        else:
            entry = current_price
            sl = fib_levels['0.000']     # Stop loss at 0% retracement
            tp = fib_levels['-1.000']    # Take profit at -100% extension

        # Place the main order
        order = session.place_order(
            category="linear",
            symbol=symbol,
            side=side,
            orderType="Market",
            qty=str(qty)
        )

        # Place take profit order
        session.place_order(
            category="linear",
            symbol=symbol,
            side="Sell" if side == "Buy" else "Buy",
            orderType="Limit",
            qty=str(qty),
            price=str(tp),
            reduceOnly=True,
            timeInForce="PostOnly"
        )

        # Place stop loss order
        session.place_order(
            category="linear", 
            symbol=symbol,
            side="Sell" if side == "Buy" else "Buy",
            orderType="Limit",
            qty=str(qty),
            price=str(sl),
            reduceOnly=True,
            timeInForce="PostOnly"
        )

        print(Fore.GREEN + f"Placed {side} order for {symbol} with quantity {qty}, Entry: {entry}, TP: {tp}" + Style.RESET_ALL)
        return qty
    except Exception as e:
        print(Fore.RED + f"Error placing order for {symbol}: {e}" + Style.RESET_ALL)
        return 0

def main():
    position_info = {}
    
    while True:
        try:
            for coin in COINS:
                klines = session.get_kline(
                    category="linear",
                    symbol=coin,
                    interval="5",
                    limit=70
                )
                
                # Create DataFrame for BOS strategy
                df = pd.DataFrame(klines["result"]["list"])
                df.columns = ['time', 'open', 'high', 'low', 'close', 'volume', 'turnover']
                for col in ['open', 'high', 'low', 'close', 'volume', 'turnover']:
                    df[col] = df[col].astype(float)
                df = df.iloc[::-1]  # Reverse to get chronological order
                
                current_price = float(session.get_tickers(
                    category="linear",
                    symbol=coin
                )["result"]["list"][0]["lastPrice"])
                
                signal = get_trading_signal(df)
                
                positions = session.get_positions(
                    category="linear",
                    symbol=coin
                )["result"]["list"]
                
                if positions and float(positions[0]["size"]) > 0:
                    if coin in position_info:
                        entry_price = position_info[coin]["entry_price"]
                        side = position_info[coin]["side"]
                        position_size = float(positions[0]["size"])
                        
                        profit = 0
                        if side == "Buy":
                            profit = current_price - entry_price
                        else:
                            profit = entry_price - current_price
                            
                        profit_usdt = profit * position_size
                        
                        if profit_usdt >= TAKE_PROFIT or profit_usdt <= -STOP_LOSS:
                            close_side = "Sell" if side == "Buy" else "Buy"
                            session.place_order(
                                category="linear",
                                symbol=coin,
                                side=close_side,
                                orderType="Market",
                                qty=str(position_size)
                            )
                            del position_info[coin]
                            if profit_usdt >= TAKE_PROFIT:
                                print(Fore.GREEN + f"Closed position for {coin} with profit {profit_usdt} USDT" + Style.RESET_ALL)
                            else:
                                print(Fore.RED + f"Closed position for {coin} with loss {profit_usdt} USDT" + Style.RESET_ALL)
                
                elif signal in ["SHORT", "LONG"]:
                    side = "Sell" if signal == "SHORT" else "Buy"
                    qty = place_order(coin, side, current_price)
                    if qty > 0:
                        position_info[coin] = {
                            "entry_price": current_price,
                            "side": side
                        }
            print(Fore.YELLOW + "Waiting for 5 seconds before next iteration..." + Style.RESET_ALL)
            time.sleep(5)
            
        except Exception as e:
            print(f"Error in main loop: {e}")
            time.sleep(5)  # Increased sleep time on error
            continue

if __name__ == "__main__":
    main()