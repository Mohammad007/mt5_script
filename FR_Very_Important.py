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
        """Check for profitable trades and close them if profit >= $10, then reopen"""
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
                    "comment": "Close profitable trade",
                    "type_time": mt5.ORDER_TIME_GTC,
                    "type_filling": mt5.ORDER_FILLING_IOC,
                }
                
                result = mt5.order_send(close_request)
                if result.retcode != mt5.TRADE_RETCODE_DONE:
                    logging.error(f"Failed to close profitable trade: {result.comment}")
                else:
                    logging.info(f"{Fore.GREEN}Closed profitable trade for {position.symbol} with ${profit:.2f} profit{Style.RESET_ALL}")
                    # Reopen the position with the same parameters
                    time.sleep(1)  # Small delay before reopening
                    self.place_fib_trade(position.symbol, position.type, position.volume)

    def check_and_close_stoploss_trades(self):
        """Check for profitable trades and close them if profit >= $10, then reopen"""
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
                    "comment": "Close stoploss trade",
                    "type_time": mt5.ORDER_TIME_GTC,
                    "type_filling": mt5.ORDER_FILLING_IOC,
                }
                
                result = mt5.order_send(close_request)
                if result.retcode != mt5.TRADE_RETCODE_DONE:
                    logging.error(f"Failed to close stoploss trade: {result.comment}")
                else:
                    logging.info(f"{Fore.RED}Closed stoploss trade for {position.symbol} with ${profit:.2f} loss{Style.RESET_ALL}")
                    # Reopen the position with the same parameters
                    time.sleep(1)  # Small delay before reopening
                    self.place_fib_trade(position.symbol, position.type, position.volume)

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
            '1.000': low + (diff * 1.000),  # 100% (Full retracement)
            '0.786': low + (diff * 0.786),  # 78.6% retracement
            '0.618': low + (diff * 0.618),  # 61.8% retracement
            '0.500': low + (diff * 0.500),  # 50% retracement
            '0.382': low + (diff * 0.382),  # 38.2% retracement
            '0.236': low + (diff * 0.236),  # 23.6% retracement
            '0.000': low + (diff * 0.000),  # 0% (No retracement)
            '-0.272': low + (diff * -0.272), # -27.2% extension
            '-0.618': low + (diff * -0.618), # -61.8% extension
            '-1.000': low + (diff * -1.000)  # -100% extension
        }
        return levels

    def detect_structure_break(self, df):
        """Detect break of structure"""
        # Calculate recent highs and lows
        df['prev_high'] = df['high'].shift(1)
        df['prev_low'] = df['low'].shift(1)
        df['prev_close'] = df['close'].shift(1)
        
        # Detect break of structure
        df['bos_buy'] = (df['close'] > df['prev_high']) & (df['prev_close'] < df['prev_high'])
        df['bos_sell'] = (df['close'] < df['prev_low']) & (df['prev_close'] > df['prev_low'])
        
        return df

    def place_fib_trade(self, symbol, order_type, volume=0.1):
        """Place a trade using Break of Structure and Fibonacci levels"""
        if self.has_open_position(symbol):
            logging.info(f"Skipping {symbol} - Position already exists")
            return False

        # Get current market data
        symbol_data = mt5.symbol_info_tick(symbol)
        if symbol_data is None:
            logging.error(f"Failed to get market data for {symbol}")
            return False

        # Get recent price data
        rates = mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_M5, 0, 100)
        if rates is None:
            logging.error(f"Failed to get historical data for {symbol}")
            return False
            
        df = pd.DataFrame(rates)
        df = self.detect_structure_break(df)
        
        # Check for break of structure
        if order_type == mt5.ORDER_TYPE_BUY and not df['bos_buy'].iloc[-1]:
            logging.info(f"No buy break of structure detected for {symbol}")
            return False
        elif order_type == mt5.ORDER_TYPE_SELL and not df['bos_sell'].iloc[-1]:
            logging.info(f"No sell break of structure detected for {symbol}")
            return False

        # Calculate Fibonacci levels based on the structure break
        if order_type == mt5.ORDER_TYPE_BUY:
            # For buy, use low to high
            low = df['low'].min()
            high = df['high'].max()
        else:
            # For sell, use high to low
            high = df['high'].max()
            low = df['low'].min()
            
        fib_levels = self.calculate_fib_levels(high, low)
        price = symbol_data.ask if order_type == mt5.ORDER_TYPE_BUY else symbol_data.bid
        
        # Wait for price to touch 0.618 Fibonacci level
        entry = fib_levels['0.618']
        if order_type == mt5.ORDER_TYPE_BUY:
            if price > entry:
                logging.info(f"Price above 0.618 Fib level for {symbol}, waiting for pullback")
                return False
        else:
            if price < entry:
                logging.info(f"Price below 0.618 Fib level for {symbol}, waiting for pullback")
                return False

        # Set SL and TP levels
        if order_type == mt5.ORDER_TYPE_BUY:
            sl = fib_levels['1.000']     # SL at 100%
            tp = fib_levels['-1.000']    # TP at -100% extension
        else:
            sl = fib_levels['0.000']     # SL at 0%
            tp = fib_levels['-1.000']    # TP at -100% extension

        request = {
            "action": mt5.TRADE_ACTION_DEAL,
            "symbol": symbol,
            "volume": volume,
            "type": order_type,
            "price": price,
            "sl": sl,
            "tp": tp,
            "magic": 234000,
            "comment": "FibSniperBot BOS Trade",
            "type_time": mt5.ORDER_TIME_GTC,
            "type_filling": mt5.ORDER_FILLING_IOC,
        }
        
        result = mt5.order_send(request)
        if result.retcode != mt5.TRADE_RETCODE_DONE:
            logging.error(f"Order failed: {result.comment}")
            return False
        
        self.open_positions[result.order] = {
            "symbol": symbol,
            "entry_price": price,
            "sl": sl,
            "tp": tp
        }
        
        logging.info(f"BOS Order placed successfully: {symbol} Entry: {price:.5f} SL: {sl:.5f} TP: {tp:.5f}")
        return True

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
                # Place trades using Break of Structure and Fibonacci levels
                for symbol in SYMBOLS:
                    volume = 1.0  # Adjust based on your risk management
                    bot.place_fib_trade(symbol, mt5.ORDER_TYPE_BUY, volume)
                    bot.place_fib_trade(symbol, mt5.ORDER_TYPE_SELL, volume)
                
                # Wait 2 seconds before next trade search
                time.sleep(2)
                
    except KeyboardInterrupt:
        print(f"{Fore.YELLOW}Bot stopping...{Style.RESET_ALL}")
    finally:
        bot.shutdown()
