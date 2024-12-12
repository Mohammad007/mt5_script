import MetaTrader5 as mt5
from colorama import Fore, Style, init
import logging
import pandas as pd
import numpy as np
import pandas_ta as ta
from tabulate import tabulate
import time

# Initialize colorama and logging
init()
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

class SniperBot:
    def __init__(self, symbols, account_number, password, server):
        self.symbols = symbols
        self.account_number = account_number
        self.password = password
        self.server = server
        self.open_positions = {}
        
    def initialize(self):
        """Initialize MT5 connection and login"""
        if not mt5.initialize():
            logging.error("MT5 initialization failed")
            return False
            
        if not mt5.login(self.account_number, password=self.password, server=self.server):
            logging.error(f"Login failed: {mt5.last_error()}")
            mt5.shutdown()
            return False
            
        # Get account info after successful login
        account_info = mt5.account_info()
        if account_info is not None:
            # Create login details table
            login_data = [
                ["Account Name", account_info.name],
                ["Account Number", self.account_number],
                ["Server", self.server],
                ["Balance", f"${account_info.balance:.2f}"]
            ]
            print("\nLogin Details:")
            print(tabulate(login_data, tablefmt="grid"))
            
        logging.info(f"Logged in successfully to account {self.account_number}")
        return True

    def has_open_position(self, symbol):
        """Check if there's already an open position for the symbol"""
        positions = mt5.positions_get(symbol=symbol)
        return positions is not None and len(positions) > 0

    def check_and_close_profitable_trades(self):
        """Check for profitable trades and close them if profit >= $10"""
        positions = mt5.positions_get()
        
        if positions is None:
            return
            
        for position in positions:
            current_price = mt5.symbol_info_tick(position.symbol).bid if position.type == mt5.ORDER_TYPE_BUY else mt5.symbol_info_tick(position.symbol).ask
            profit = position.profit
            
            if profit >= 10:  # $10 profit threshold
                close_request = {
                    "action": mt5.TRADE_ACTION_DEAL,
                    "symbol": position.symbol,
                    "volume": position.volume,
                    "type": mt5.ORDER_TYPE_SELL if position.type == mt5.ORDER_TYPE_BUY else mt5.ORDER_TYPE_BUY,
                    "position": position.ticket,
                    "price": current_price,
                    "magic": 234000,
                    "comment": "close_profit",
                    "type_time": mt5.ORDER_TIME_GTC,
                    "type_filling": mt5.ORDER_FILLING_IOC,
                }
                
                result = mt5.order_send(close_request)
                if result is None:
                    logging.error(f"Failed to close profitable trade - {mt5.last_error()}")
                    continue
                    
                if result.retcode != mt5.TRADE_RETCODE_DONE:
                    logging.error(f"Failed to close profitable trade: {result.comment}")
                else:
                    logging.info(f"{Fore.GREEN}Closed profitable trade for {position.symbol} with ${profit:.2f} profit{Style.RESET_ALL}")

    def check_and_close_stoploss_trades(self):
        """Check for trades in loss and close them if loss >= $30"""
        positions = mt5.positions_get()
        
        if positions is None:
            return
            
        for position in positions:
            current_price = mt5.symbol_info_tick(position.symbol).bid if position.type == mt5.ORDER_TYPE_BUY else mt5.symbol_info_tick(position.symbol).ask
            profit = position.profit
            
            if profit <= -30:  # $30 loss threshold
                close_request = {
                    "action": mt5.TRADE_ACTION_DEAL,
                    "symbol": position.symbol,
                    "volume": position.volume,
                    "type": mt5.ORDER_TYPE_SELL if position.type == mt5.ORDER_TYPE_BUY else mt5.ORDER_TYPE_BUY,
                    "position": position.ticket,
                    "price": current_price,
                    "magic": 234000,
                    "comment": "close_loss",
                    "type_time": mt5.ORDER_TIME_GTC,
                    "type_filling": mt5.ORDER_FILLING_IOC,
                }
                
                result = mt5.order_send(close_request)
                if result is None:
                    logging.error(f"Failed to close stoploss trade - {mt5.last_error()}")
                    continue
                    
                if result.retcode != mt5.TRADE_RETCODE_DONE:
                    logging.error(f"Failed to close stoploss trade: {result.comment}")
                else:
                    logging.error(f"{Fore.RED}Closed stoploss trade for {position.symbol} with ${profit:.2f} loss{Style.RESET_ALL}")

    def shutdown(self):
        """Cleanup and shutdown"""
        mt5.shutdown()

class FibSniperBot(SniperBot):
    def __init__(self, symbols, account_number, password, server):
        super().__init__(symbols, account_number, password, server)
        
    def calculate_fib_levels(self, high, low):
        """Calculate Fibonacci retracement levels"""
        diff = high - low
        levels = {
            'level_2618': high + (diff * 2.618),  # 261.8% extension
            'level_1618': high + (diff * 1.618),  # 161.8% extension
            'level_1414': high + (diff * 1.414),  # 141.4% extension
            'level_1000': high,                   # 100% retracement
            'level_0786': high - (diff * 0.786),  # 78.6% retracement
            'level_0618': high - (diff * 0.618),  # 61.8% retracement
            'level_0500': high - (diff * 0.500),  # 50% retracement
            'level_0382': high - (diff * 0.382),  # 38.2% retracement
            'level_0236': high - (diff * 0.236),  # 23.6% retracement
            'level_0000': low                     # 0% retracement
        }
        return levels

    def detect_structure_break(self, df, lookback=10):
        """Detect break of market structure"""
        highs = df['high'].rolling(window=lookback).max()
        lows = df['low'].rolling(window=lookback).min()
        
        # Bullish break - price closes above recent high
        bullish_break = df['close'] > highs.shift(1)
        
        # Bearish break - price closes below recent low  
        bearish_break = df['close'] < lows.shift(1)
        
        return bullish_break, bearish_break

    def place_fib_trade(self, symbol, order_type, volume=0.1):
        """Place trade on structure break and apply Fibonacci levels after entry"""
        if self.has_open_position(symbol):
            logging.info(f"Skipping {symbol} - Position already exists")
            return False

        # Get current market data
        symbol_data = mt5.symbol_info_tick(symbol)
        if symbol_data is None:
            logging.error(f"Failed to get market data for {symbol}")
            return False

        # Get 5 min timeframe data
        rates = mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_M5, 0, 100)
        if rates is None:
            logging.error(f"Failed to get historical data for {symbol}")
            return False
            
        df = pd.DataFrame(rates)
        
        # Check for structure break
        bullish_break, bearish_break = self.detect_structure_break(df)
        
        # Only enter if we have structure break
        if not (bullish_break.iloc[-1] or bearish_break.iloc[-1]):
            return False
            
        # Calculate Fibonacci levels after structure break
        if bullish_break.iloc[-1]:
            # Use recent swing low to high for Fib levels
            low = df['low'].rolling(window=20).min().iloc[-1]
            high = df['close'].iloc[-1]  # Current price as high
            order_type = mt5.ORDER_TYPE_BUY
        else:
            # Use recent swing high to low for Fib levels
            high = df['high'].rolling(window=20).max().iloc[-1] 
            low = df['close'].iloc[-1]  # Current price as low
            order_type = mt5.ORDER_TYPE_SELL

        fib_levels = self.calculate_fib_levels(high, low)
        
        if order_type == mt5.ORDER_TYPE_BUY:
            price = symbol_data.ask
            sl = fib_levels['level_0618']  # SL at 61.8% retracement
            tp = fib_levels['level_1618']  # TP at 161.8% extension
        else:
            price = symbol_data.bid
            sl = fib_levels['level_0618']  # SL at 61.8% retracement  
            tp = fib_levels['level_0000']  # TP at 0% level

        # Get symbol info to check stops
        symbol_info = mt5.symbol_info(symbol)
        if symbol_info is None:
            logging.error(f"Failed to get symbol info for {symbol}")
            return False

        # Enable symbol for trading if needed
        if not symbol_info.visible:
            if not mt5.symbol_select(symbol, True):
                logging.error(f"Failed to enable {symbol} for trading")
                return False

        request = {
            "action": mt5.TRADE_ACTION_DEAL,
            "symbol": symbol,
            "volume": volume,
            "type": order_type,
            "price": price,
            "sl": sl,
            "tp": tp,
            "magic": 234000,
            "comment": "fib_trade",
            "type_time": mt5.ORDER_TIME_GTC,
            "type_filling": mt5.ORDER_FILLING_IOC,
            "deviation": 20  # Allow price deviation in points
        }
        
        result = mt5.order_send(request)
        if result is None:
            logging.error(f"Order failed - {mt5.last_error()}")
            return False
            
        if result.retcode != mt5.TRADE_RETCODE_DONE:
            logging.error(f"Order failed: {result.comment}")
            return False
        
        self.open_positions[result.order] = {
            "symbol": symbol,
            "entry_price": price,
            "sl": sl,
            "tp": tp
        }
        
        logging.info(f"{Fore.YELLOW}Structure break order placed: {symbol} Entry: {price:.5f} SL: {sl:.5f} TP: {tp:.5f}{Style.RESET_ALL}")
        return True

def process_dataframe(df):
    """Process dataframe with structure break detection and Fibonacci levels"""
    # Calculate technical indicators
    df['RSI'] = ta.rsi(df.close, length=12)
    df['EMA'] = ta.ema(df.close, length=150)
    
    # Create bot instance
    bot = FibSniperBot([], None, None, None)
    
    # Detect structure breaks
    bullish_break, bearish_break = bot.detect_structure_break(df)
    df['bullish_break'] = bullish_break
    df['bearish_break'] = bearish_break
    
    return df

# Usage example
if __name__ == "__main__":
    # Your account details
    SYMBOLS = ["EURUSD", "GBPUSD", "USDJPY", "USDCHF", "USDCAD", "EURGBP", "EURJPY", "GBPJPY", "AUDUSD", "NZDUSD", "AUDCHF", "AUDNZD", "EURAUD", "EURCAD", "EURCHF", "EURNZD", "GBPAUD", "GBPCAD", "GBPCHF", "GBPNZD", "NZDCAD", "NZDCHF", "NZDJPY"]
    ACCOUNT = 79431322  # Replace with your account number
    PASSWORD = "Bilal@8477"
    SERVER = "Exness-MT5Trial8"
    
    # Create and run bot
    bot = FibSniperBot(SYMBOLS, ACCOUNT, PASSWORD, SERVER)
    
    try:
        if bot.initialize():
            print(f"{Fore.GREEN}Account initialized successfully{Style.RESET_ALL}")
            
            while True:
                # Check for structure breaks and place trades
                for symbol in SYMBOLS:
                    volume = 0.1  # Adjust based on risk management
                    bot.place_fib_trade(symbol, None, volume)
                
                # Check open positions
                # bot.check_and_close_profitable_trades()
                # bot.check_and_close_stoploss_trades()
                
                # Wait before next iteration
                time.sleep(1)
                
    except KeyboardInterrupt:
        print(f"{Fore.YELLOW}Bot stopping...{Style.RESET_ALL}")
    finally:
        bot.shutdown()
