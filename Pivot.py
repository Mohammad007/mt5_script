import MetaTrader5 as mt5
from colorama import Fore, Style, init
import logging
import pandas as pd
import numpy as np
import pandas_ta as ta
from tabulate import tabulate
import time
from datetime import datetime, timedelta

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
            
            if profit >= 3:  # $3 profit threshold
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
                    self.place_trade(position.symbol, position.volume)

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
                    self.place_trade(position.symbol, position.volume)

    def shutdown(self):
        """Cleanup and shutdown"""
        mt5.shutdown()

class SniperBot(SniperBot):
    def __init__(self, symbols, account_number, password, server):
        super().__init__(symbols, account_number, password, server)

    def calculate_pivot_points(self, df):
        """Calculate classic pivot points"""
        df['PP'] = (df['high'].shift(1) + df['low'].shift(1) + df['close'].shift(1)) / 3
        df['R1'] = 2 * df['PP'] - df['low'].shift(1)
        df['S1'] = 2 * df['PP'] - df['high'].shift(1)
        df['R2'] = df['PP'] + (df['high'].shift(1) - df['low'].shift(1))
        df['S2'] = df['PP'] - (df['high'].shift(1) - df['low'].shift(1))
        return df

    def determine_trend(self, df):
        """Determine trend using multiple indicators"""
        # Calculate EMAs
        df['EMA20'] = ta.ema(df['close'], length=20)
        df['EMA50'] = ta.ema(df['close'], length=50)
        
        # Calculate RSI
        df['RSI'] = ta.rsi(df['close'], length=14)
        
        # Get current values
        current_price = df['close'].iloc[-1]
        current_ema20 = df['EMA20'].iloc[-1]
        current_ema50 = df['EMA50'].iloc[-1]
        current_rsi = df['RSI'].iloc[-1]
        
        # Determine trend based on multiple conditions
        trend = 'neutral'
        
        if (current_price > current_ema20 > current_ema50) and (current_rsi > 50):
            trend = 'bullish'
        elif (current_price < current_ema20 < current_ema50) and (current_rsi < 50):
            trend = 'bearish'
            
        return trend

    def find_entry_points(self, df):
        """Find entry points based on pivot points and price action"""
        df = self.calculate_pivot_points(df)
        trend = self.determine_trend(df)
        
        current_price = df['close'].iloc[-1]
        pp = df['PP'].iloc[-1]
        r1 = df['R1'].iloc[-1]
        s1 = df['S1'].iloc[-1]
        
        signal = 'none'
        entry = 0
        sl = 0
        tp = 0
        
        if trend == 'bullish':
            # Buy near S1 in bullish trend
            if current_price > s1 and current_price < pp:
                signal = 'buy'
                entry = current_price
                sl = s1 - 0.00100  # 100 pips below S1
                tp = r1  # Target R1
                
        elif trend == 'bearish':
            # Sell near R1 in bearish trend
            if current_price < r1 and current_price > pp:
                signal = 'sell'
                entry = current_price
                sl = r1 + 0.00100  # 100 pips above R1
                tp = s1  # Target S1
                
        return signal, entry, sl, tp

    def place_trade(self, symbol, volume=0.1):
        """Place trades based on pivot points and trend analysis"""            
        if self.has_open_position(symbol):
            return False
            
        # Get market data
        rates = mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_M15, 0, 100)
        if rates is None:
            return False
            
        df = pd.DataFrame(rates)
        signal, entry, sl, tp = self.find_entry_points(df)
        
        if signal == 'none':
            return False
            
        order_type = mt5.ORDER_TYPE_BUY if signal == 'buy' else mt5.ORDER_TYPE_SELL
        
        request = {
            "action": mt5.TRADE_ACTION_DEAL,
            "symbol": symbol,
            "volume": volume,
            "type": order_type,
            "price": entry,
            # "sl": sl,
            "tp": tp,
            "magic": 234000,
            "comment": "Pivot Trade",
            "type_time": mt5.ORDER_TIME_GTC,
            "type_filling": mt5.ORDER_FILLING_IOC,
        }
        
        result = mt5.order_send(request)
        if result.retcode != mt5.TRADE_RETCODE_DONE:
            logging.error(f"Order failed: {result.comment}")
            return False
            
        logging.info(f"{Fore.BLUE}New {signal} position opened for {symbol} at {entry:.5f}{Style.RESET_ALL}")
        return True

# Usage example
if __name__ == "__main__":
    # Your account details
    SYMBOLS = ["EURUSD", "GBPUSD", "USDJPY", "USDCHF", "USDCAD", "EURGBP", "EURJPY", "GBPJPY", "AUDUSD", "NZDUSD", "AUDCHF", "AUDNZD", "EURAUD", "EURCAD", "EURCHF", "EURNZD", "GBPAUD", "GBPCAD", "GBPCHF", "GBPNZD", "NZDCAD", "NZDCHF", "NZDJPY"]
    ACCOUNT = 79431322  # Replace with your account number
    PASSWORD = "Bilal@8477"
    SERVER = "Exness-MT5Trial8"
    
    # Create and run bot
    bot = SniperBot(SYMBOLS, ACCOUNT, PASSWORD, SERVER)
    
    try:
        if bot.initialize():
            print(f"{Fore.GREEN}Account initialized successfully{Style.RESET_ALL}")
            
            while True:
                for symbol in SYMBOLS:
                    volume = 0.1  # Adjust based on risk management
                    bot.place_trade(symbol, volume)
                
                bot.check_and_close_profitable_trades()
                # bot.check_and_close_stoploss_trades()
                
                time.sleep(1)  # Check every 1 seconds
                
    except KeyboardInterrupt:
        print(f"{Fore.YELLOW}Bot stopping...{Style.RESET_ALL}")
    finally:
        bot.shutdown()
