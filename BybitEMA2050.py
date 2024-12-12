from pybit.unified_trading import HTTP
import pandas as pd
import numpy as np
import time
from colorama import Fore, Style

API_KEY = "J1OgMqNv77Y58f5A36"
API_SECRET = "p2mpFwCgTQk93xo5AOcUJ05GQdQsxrHV5hSm"

# Initialize session with an increased recv_window
session = HTTP(
    demo=True,
    api_key=API_KEY,
    api_secret=API_SECRET
)

# Trading parameters
LEVERAGE = 20  # Fixed leverage for all trades
TAKE_PROFIT = 2  # Take profit in USDT
STOP_LOSS = 20  # Increased stop loss target (in percentage)
WALLET_PERCENTAGE = 0.40  # Reduced risk per trade
COINS = ["NEOUSDT", "QNTUSDT","ARUSDT", "INJUSDT", "ATOMUSDT", "OMUSDT", "AAVEUSDT", "SOLUSDT", "AVAXUSDT", "LINKUSDT", "LTCUSDT", "UNIUSDT", "XMRUSDT", "INJUSDT", "NEOUSDT","HNTUSDT", "TRXUSDT", "XRPUSDT", "DOGEUSDT", "ADAUSDT", "DOTUSDT", "ONTUSDT", "QTUMUSDT", "MEMEUSDT", "THEUSDT", "ZRCUSDT", "OLUSDT", "BANUSDT", "TAIUSDT", "ACTUSDT", "ALGOUSDT", "FTMUSDT", "GOATUSDT", "GALAUSDT", "EOSUSDT", "ENAUSDT", "CRVUSDT"]

def analyze_trend(closes, opens):
    """
    Analyze price trend using 20 and 50 EMA crossover strategy with confirmation candle
    Returns:
    - "LONG": When 20 EMA crosses above 50 EMA and next candle is green
    - "SHORT": When 20 EMA crosses below 50 EMA and next candle is red
    - "NEUTRAL": When no clear signal is present
    """
    # Calculate EMAs with 10 period offset
    ema_20 = pd.Series(closes).ewm(span=20, adjust=False).mean()
    ema_50 = pd.Series(closes).ewm(span=50, adjust=False).mean().shift(10)
    
    # Get the last values for EMAs
    ema20_current = ema_20.iloc[-1]
    ema20_prev = ema_20.iloc[-2]
    ema50_current = ema_50.iloc[-1]
    ema50_prev = ema_50.iloc[-2]
    
    # Get last two candles
    current_close = closes[-1]
    current_open = opens[-1]
    prev_close = closes[-2]
    prev_open = opens[-2]
    
    # Check if current candle is green/red
    is_current_green = current_close > current_open
    is_current_red = current_close < current_open
    
    # Check for crossover conditions with confirmation candle
    if ema20_prev < ema50_prev and ema20_current > ema50_current and is_current_green:
        print(Fore.GREEN + f"LONG Signal: EMA20 ({ema20_current:.4f}) crossed above EMA50 ({ema50_current:.4f}) with green confirmation" + Style.RESET_ALL)
        return "LONG"
    elif ema20_prev > ema50_prev and ema20_current < ema50_current and is_current_red:
        print(Fore.RED + f"SHORT Signal: EMA20 ({ema20_current:.4f}) crossed below EMA50 ({ema50_current:.4f}) with red confirmation" + Style.RESET_ALL)
        return "SHORT"
    
    print(f"Current EMAs - EMA20: {ema20_current:.4f}, EMA50: {ema50_current:.4f}")
    return "NEUTRAL"

def get_wallet_balance():
    try:
        wallet = session.get_wallet_balance(
            accountType="UNIFIED",
            coin="USDT"
        )
        
        balance = float(wallet['result']['list'][0]['coin'][0]['availableToWithdraw'])
        print(Fore.YELLOW + f"Balance: {balance} USDT" + Style.RESET_ALL)
        return balance
    except Exception as e:
        print(f"Error getting wallet balance: {e}")
        return 0

def has_open_position(symbol):
    try:
        positions = session.get_positions(
            category="linear",
            symbol=symbol
        )
        position_size = float(positions["result"]["list"][0]["size"])
        if position_size == 0:
            return False
            
        # Check if take profit reached
        entry_price = float(positions["result"]["list"][0]["avgPrice"])
        current_price = float(positions["result"]["list"][0]["markPrice"])
        position_side = positions["result"]["list"][0]["side"]
        
        profit = 0
        if position_side == "Buy":
            profit = (current_price - entry_price) * position_size
        else:  # Sell
            profit = (entry_price - current_price) * position_size
            
        if profit >= TAKE_PROFIT:
            # Close position at market price
            close_side = "Sell" if position_side == "Buy" else "Buy"
            session.place_order(
                category="linear",
                symbol=symbol,
                side=close_side,
                orderType="Market",
                qty=str(position_size),
                reduceOnly=True
            )
            print(Fore.GREEN + f"Closed position for {symbol} with {profit:.2f} USDT profit" + Style.RESET_ALL)
            return False
            
        return True
    except Exception as e:
        print(f"Error checking position: {e}")
        return False

def get_trading_info(symbol):
    try:
        instruments = session.get_instruments_info(
            category="linear",
            symbol=symbol
        )
        min_qty = float(instruments["result"]["list"][0]["lotSizeFilter"]["minOrderQty"])
        qty_step = float(instruments["result"]["list"][0]["lotSizeFilter"]["qtyStep"])
        tick_size = float(instruments["result"]["list"][0]["priceFilter"]["tickSize"])
        return min_qty, qty_step, tick_size
    except Exception as e:
        print(f"Error getting trading info for {symbol}: {e}")
        return 1, 1, 0.01  # Default values

def place_order(symbol, side, current_price):
    try:
        min_qty, qty_step, tick_size = get_trading_info(symbol)
        
        # Set leverage first
        try:
            response = session.set_leverage(
                category="linear",
                symbol=symbol,
                buyLeverage=str(LEVERAGE),
                sellLeverage=str(LEVERAGE)
            )
            if response.get("retMsg") != "OK":
                print(Fore.RED + f"Error setting leverage for {symbol}: {response.get('retMsg')}" + Style.RESET_ALL)
        except Exception as e:
            print(Fore.RED + f"Error setting leverage for {symbol}: {e}" + Style.RESET_ALL)
    
        available_balance = get_wallet_balance() * WALLET_PERCENTAGE
        print(Fore.YELLOW + f"Available balance: {available_balance} USDT" + Style.RESET_ALL)
        
        max_position_value = available_balance * LEVERAGE
        qty = max_position_value / current_price
        
        qty = max(min_qty, qty)
        qty = np.floor(qty / qty_step) * qty_step  # Ensuring qty step compliance
        
        while (qty * current_price) > max_position_value and qty >= min_qty:
            qty -= qty_step
            
        if qty < min_qty:
            print(Fore.RED + f"Calculated quantity {qty} is below minimum {min_qty} for {symbol}" + Style.RESET_ALL)
            return 0
        
        # Calculate Take Profit and Stop Loss prices
        if side == "Buy":
            take_profit_price = current_price + TAKE_PROFIT
            stop_loss_price = current_price * (1 - STOP_LOSS / 100)
        else:  # Sell
            take_profit_price = current_price - TAKE_PROFIT
            stop_loss_price = current_price * (1 + STOP_LOSS / 100)
        
        # Round prices according to tick size
        take_profit_price = round(take_profit_price / tick_size) * tick_size
        stop_loss_price = round(stop_loss_price / tick_size) * tick_size
        
        # Ensure Take Profit and Stop Loss are logical
        if side == "Sell" and take_profit_price >= current_price:
            take_profit_price = current_price - tick_size
            print(Fore.YELLOW + f"Adjusted Take Profit for Sell position to {take_profit_price}" + Style.RESET_ALL)
        if side == "Buy" and take_profit_price <= current_price:
            take_profit_price = current_price + tick_size
            print(Fore.YELLOW + f"Adjusted Take Profit for Buy position to {take_profit_price}" + Style.RESET_ALL)
        
        # Place main order with Take Profit and Stop Loss
        order = session.place_order(
            category="linear",
            symbol=symbol,
            side=side,
            orderType="Market",
            qty=str(qty),
            leverage=str(LEVERAGE),  # Leverage as string
            closeOnTrigger=False,
            stopLoss=str(stop_loss_price)
        )

        if order.get("retMsg") != "OK":
            print(Fore.RED + f"Failed to place order for {symbol}: {order.get('retMsg')}" + Style.RESET_ALL)
            return 0

        print(Fore.YELLOW + f"Placed {side} order for {symbol} with quantity {qty}" + Style.RESET_ALL)
        print(Fore.RED + f"Stop Loss set at {stop_loss_price} USDT" + Style.RESET_ALL)
        return qty
            
    except Exception as e:
        print(f"Error placing order: {e}")
        return 0  # Ensure a numerical return value

def main():
    position_info = {}
    
    while True:
        for coin in COINS:
            try:
                if has_open_position(coin):
                    print(f"Skipping {coin} - position already exists")
                    continue
                
                # Get more historical data for better EMA calculation
                klines = session.get_kline(
                    category="linear",
                    symbol=coin,
                    interval="3",
                    limit=300  # Increased for better EMA calculation
                )
                
                closes = [float(candle[4]) for candle in klines["result"]["list"]]
                opens = [float(candle[1]) for candle in klines["result"]["list"]]
                closes.reverse()  # Important: Reverse to get chronological order
                opens.reverse()
                
                ticker = session.get_tickers(
                    category="linear",
                    symbol=coin
                )
                if not ticker.get("result") or not ticker["result"]["list"]:
                    print(Fore.RED + f"No ticker data available for {coin}" + Style.RESET_ALL)
                    continue
                
                current_price = float(ticker["result"]["list"][0]["lastPrice"])
                
                print(f"\nAnalyzing {coin} at price {current_price}")
                signal = analyze_trend(closes, opens)

                if signal == "LONG":
                    print(Fore.GREEN + f"Taking LONG position for {coin}" + Style.RESET_ALL)
                    qty = place_order(coin, "Sell", current_price)
                    if qty > 0:
                        position_info[coin] = {
                            "entry_price": current_price,
                            "side": "Sell",
                            "stop_loss": current_price * (1 - STOP_LOSS / 100)
                        }
                elif signal == "SHORT":
                    print(Fore.RED + f"Taking SHORT position for {coin}" + Style.RESET_ALL)
                    qty = place_order(coin, "Buy", current_price)
                    if qty > 0:
                        position_info[coin] = {
                            "entry_price": current_price,
                            "side": "Buy",
                            "stop_loss": current_price * (1 + STOP_LOSS / 100)
                        }
                
            except Exception as e:
                print(Fore.RED + f"Error processing {coin}: {e}" + Style.RESET_ALL)
                continue
                
        time.sleep(1)

if __name__ == "__main__":
    main()