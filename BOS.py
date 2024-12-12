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
            
            if profit >= 10:  # $15 profit threshold
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
                    self.place_bos_trade(position.symbol, position.type, position.volume)

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
                    self.place_bos_trade(position.symbol, position.type, position.volume)

    def shutdown(self):
        """Cleanup and shutdown"""
        mt5.shutdown()

class BOSSniperBot(SniperBot):
    def __init__(self, symbols, account_number, password, server):
        super().__init__(symbols, account_number, password, server)
        
    def calculate_ma(self, data, length=30, ma_type='HMA'):
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

    def calculate_fib_levels(self, high, low):
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

    def check_bos_signal(self, df):
        """Check for BOS (Break of Structure) signals"""
        ma = self.calculate_ma(df['close'], length=30, ma_type='HMA')
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
                return 'BUY'
                
        elif last_row['ma_cu']:  # Potential sell signal
            # Check if price breaks below recent low after crossing below MA
            recent_low = df['low'].rolling(window=5).min().iloc[-2]
            if last_row['close'] < recent_low:
                return 'SELL'
                
        return None

    def place_bos_trade(self, symbol, order_type, volume=0.1):
        """Place a trade based on BOS strategy with Fibonacci levels"""
        if self.has_open_position(symbol):
            logging.info(f"Skipping {symbol} - Position already exists")
            return False

        # Get recent price data for 5-minute timeframe
        rates = mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_M5, 0, 100)
        if rates is None:
            logging.error(f"Failed to get historical data for {symbol}")
            return False
            
        df = pd.DataFrame(rates)
        signal = self.check_bos_signal(df)
        
        if signal is None:
            return False
            
        symbol_info = mt5.symbol_info_tick(symbol)
        if symbol_info is None:
            logging.error(f"Failed to get symbol info for {symbol}")
            return False

        # Calculate Fibonacci levels after BOS
        high = df['high'].max()
        low = df['low'].min()
        fib_levels = self.calculate_fib_levels(high, low)

        if signal == 'BUY':
            price = symbol_info.ask
            entry = fib_levels['0.618']  # Entry at 61.8% retracement
            sl = fib_levels['1.000']     # Stop loss at 100% retracement
            tp = fib_levels['-1.000']    # Take profit at -100% extension
            order_type = mt5.ORDER_TYPE_BUY
        else:  # SELL
            price = symbol_info.bid
            entry = fib_levels['0.618']  # Entry at 61.8% retracement
            sl = fib_levels['0.000']     # Stop loss at 0% retracement
            tp = fib_levels['-1.000']     # Take profit at -100% extension
            order_type = mt5.ORDER_TYPE_SELL

        request = {
            "action": mt5.TRADE_ACTION_DEAL,
            "symbol": symbol,
            "volume": volume,
            "type": order_type,
            "price": price,
            "sl": sl,
            "tp": tp,
            "magic": 234000,
            "comment": "BOSSniperBot Fib Trade",
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
        
        logging.info(f"BOS {signal} Order placed successfully with Fib levels: {symbol} Entry: {price:.5f} SL: {sl:.5f} TP: {tp:.5f}")
        return True

# Usage example
if __name__ == "__main__":
    # Your account details
    SYMBOLS = ["EURUSD", "GBPUSD", "USDJPY", "USDCHF", "USDCAD", "EURGBP", "EURJPY", "GBPJPY", "AUDUSD", "NZDUSD", "AUDCHF", "AUDNZD", "EURAUD", "EURCAD", "EURCHF", "EURNZD", "GBPAUD", "GBPCAD", "GBPCHF", "GBPNZD", "NZDCAD", "NZDCHF", "NZDJPY"]
    ACCOUNT = 79504013  # Replace with your account number
    PASSWORD = "Bilal@8477"
    SERVER = "Exness-MT5Trial8"
    
    # Create and run bot
    bot = BOSSniperBot(SYMBOLS, ACCOUNT, PASSWORD, SERVER)
    
    try:
        if bot.initialize():
            print(f"{Fore.GREEN}Account initialized successfully{Style.RESET_ALL}")
            
            while True:
                # Place trades using BOS strategy with Fibonacci levels
                for symbol in SYMBOLS:
                    volume = 0.20  # Adjust based on your risk management
                    bot.place_bos_trade(symbol, mt5.ORDER_TYPE_BUY, volume)
                    bot.place_bos_trade(symbol, mt5.ORDER_TYPE_SELL, volume)
                
                # Check and manage open positions
                bot.check_and_close_profitable_trades()
                # bot.check_and_close_stoploss_trades()
                
                # Wait before next iteration
                print(f"{Fore.YELLOW}Waiting for 2 seconds before next iteration...{Style.RESET_ALL}")
                time.sleep(2)
                
    except KeyboardInterrupt:
        print(f"{Fore.YELLOW}Bot stopping...{Style.RESET_ALL}")
    finally:
        bot.shutdown()
