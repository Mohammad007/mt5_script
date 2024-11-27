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
                    logging.info(f"Closed profitable trade for {position.symbol} with ${profit:.2f} profit")
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
            'level_0': high,  # 0% retracement
            'level_236': high - (diff * 0.236),  # 23.6% retracement
            'level_382': high - (diff * 0.382),  # 38.2% retracement
            'level_500': high - (diff * 0.500),  # 50.0% retracement
            'level_618': high - (diff * 0.618),  # 61.8% retracement
            'level_786': high - (diff * 0.786),  # 78.6% retracement
            'level_100': low    # 100% retracement
        }
        return levels

    def calculate_ema_signals(self, df, backcandles=15):
        """Calculate EMA signals"""
        EMAsignal = [0] * len(df)
        
        for row in range(backcandles, len(df)):
            upt = 1
            dnt = 1
            for i in range(row-backcandles, row+1):
                if max(df.open[i], df.close[i]) >= df.EMA[i]:
                    dnt = 0
                if min(df.open[i], df.close[i]) <= df.EMA[i]:
                    upt = 0
            if upt == 1 and dnt == 1:
                EMAsignal[row] = 3
            elif upt == 1:
                EMAsignal[row] = 2
            elif dnt == 1:
                EMAsignal[row] = 1
                
        return EMAsignal

    def generate_fib_signal(self, df, l, backcandles, gap, zone_threshold, price_diff_threshold):
        """Generate trading signals based on Fibonacci retracements"""
        max_price = df.high[l-backcandles:l-gap].max()
        min_price = df.low[l-backcandles:l-gap].min()
        index_max = df.high[l-backcandles:l-gap].idxmax()
        index_min = df.low[l-backcandles:l-gap].idxmin()
        price_diff = max_price - min_price

        # Calculate Fibonacci levels
        if index_min < index_max:  # Uptrend
            fib_levels = self.calculate_fib_levels(max_price, min_price)
            if df.EMASignal[l] == 2 and price_diff > price_diff_threshold:
                # Entry at 61.8% retracement
                entry = fib_levels['level_618']
                # SL at 38.2% retracement
                sl = fib_levels['level_382']
                # TP at previous high (0% retracement)
                tp = fib_levels['level_0']
                
                if abs(df.close[l] - entry) < zone_threshold and df.high[l-gap:l].min() > entry:
                    return (2, sl, tp, index_min, index_max)
                
        elif index_min > index_max:  # Downtrend
            fib_levels = self.calculate_fib_levels(min_price, max_price)
            if df.EMASignal[l] == 1 and price_diff > price_diff_threshold:
                # Entry at 61.8% retracement
                entry = min_price + (price_diff * 0.618)
                # SL at 38.2% retracement
                sl = min_price + (price_diff * 0.382)
                # TP at previous low (0% retracement)
                tp = min_price
                
                if abs(df.close[l] - entry) < zone_threshold and df.low[l-gap:l].max() < entry:
                    return (1, sl, tp, index_min, index_max)
        
        return (0, 0, 0, 0, 0)

    def place_fib_trade(self, symbol, order_type, volume=0.1):
        """Place a trade using Fibonacci levels for entry, SL, and TP"""
        if self.has_open_position(symbol):
            logging.info(f"Skipping {symbol} - Position already exists")
            return False

        # Get current market data
        symbol_data = mt5.symbol_info_tick(symbol)
        if symbol_data is None:
            logging.error(f"Failed to get market data for {symbol}")
            return False

        # Calculate entry price based on Fibonacci level (61.8%)
        price = symbol_data.ask if order_type == mt5.ORDER_TYPE_BUY else symbol_data.bid
        
        # Get recent price data for Fibonacci calculations
        rates = mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_M5, 0, 100)
        if rates is None:
            logging.error(f"Failed to get historical data for {symbol}")
            return False
            
        df = pd.DataFrame(rates)
        high = df['high'].max()
        low = df['low'].min()
        
        # Calculate Fibonacci levels
        fib_levels = self.calculate_fib_levels(high, low)
        
        if order_type == mt5.ORDER_TYPE_BUY:
            sl = fib_levels['level_382']  # 38.2% retracement as SL
            tp = fib_levels['level_0']    # 0% retracement as TP
        else:
            sl = fib_levels['level_382']  # 38.2% retracement as SL
            tp = fib_levels['level_100']  # 100% retracement as TP

        request = {
            "action": mt5.TRADE_ACTION_DEAL,
            "symbol": symbol,
            "volume": volume,
            "type": order_type,
            "price": price,
            "sl": sl,
            "tp": tp,
            "magic": 234000,
            "comment": "FibSniperBot Trade",
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
        
        logging.info(f"Order placed successfully: {symbol} Entry: {price:.5f} SL: {sl:.5f} TP: {tp:.5f}")
        return True

def process_dataframe(df):
    """Process dataframe with EMA and Fibonacci signals"""
    # Calculate EMA and RSI
    df['RSI'] = ta.rsi(df.close, length=12)
    df['EMA'] = ta.ema(df.close, length=150)
    
    # Create bot instance for signal generation
    bot = FibSniperBot([], None, None, None)
    
    # Calculate EMA signals
    df['EMASignal'] = bot.calculate_ema_signals(df)
    
    # Initialize Fibonacci signal arrays
    gap_candles = 5
    backcandles = 40
    signal = [0 for i in range(len(df))]
    TP = [0 for i in range(len(df))]
    SL = [0 for i in range(len(df))]
    MinSwing = [0 for i in range(len(df))]
    MaxSwing = [0 for i in range(len(df))]
    
    # Generate signals
    for row in range(backcandles, len(df)):
        gen_sig = bot.generate_fib_signal(
            df, row, 
            backcandles=backcandles, 
            gap=gap_candles, 
            zone_threshold=0.001, 
            price_diff_threshold=0.01
        )
        signal[row] = gen_sig[0]
        SL[row] = gen_sig[1]
        TP[row] = gen_sig[2]
        MinSwing[row] = gen_sig[3]
        MaxSwing[row] = gen_sig[4]
    
    # Add signals to dataframe
    df['signal'] = signal
    df['SL'] = SL
    df['TP'] = TP
    df['MinSwing'] = MinSwing
    df['MaxSwing'] = MaxSwing
    
    return df

# Usage example
if __name__ == "__main__":
    # Your account details
    SYMBOLS = ["EURUSD", "GBPUSD", "USDJPY", "USDCHF", "USDCAD", "EURGBP", "EURJPY", "GBPJPY"]
    ACCOUNT = 79431322  # Replace with your account number
    PASSWORD = "Bilal@8477"
    SERVER = "Exness-MT5Trial8"
    
    # Create and run bot
    bot = FibSniperBot(SYMBOLS, ACCOUNT, PASSWORD, SERVER)
    
    try:
        if bot.initialize():
            print(f"{Fore.GREEN}Account initialized successfully{Style.RESET_ALL}")
            # Place trades using Fibonacci levels
            for symbol in SYMBOLS:
                volume = 1.0  # Adjust based on your risk management
                bot.place_fib_trade(symbol, mt5.ORDER_TYPE_BUY, volume)
                
            # Continuously monitor trades
            while True:
                # bot.check_and_close_profitable_trades()
                time.sleep(2)  # Check every 2 seconds
                
    except KeyboardInterrupt:
        print(f"{Fore.YELLOW}Bot stopping...{Style.RESET_ALL}")
    finally:
        bot.shutdown()
