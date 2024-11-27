import MetaTrader5 as mt5
from colorama import Fore, Style, init
import logging
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

    def place_trade(self, symbol, order_type, volume=0.1):
        """Place a trade with SL and TP"""
        if self.has_open_position(symbol):
            logging.info(f"Skipping {symbol} - Position already exists")
            return False

        point = mt5.symbol_info(symbol).point
        price = mt5.symbol_info_tick(symbol).ask if order_type == mt5.ORDER_TYPE_BUY else mt5.symbol_info_tick(symbol).bid
        
        # Calculate SL and TP based on current price
        sl = price * 0.9 if order_type == mt5.ORDER_TYPE_BUY else price * 1.1  # 10% SL
        tp = price * 1.5 if order_type == mt5.ORDER_TYPE_BUY else price * 0.5  # 50% TP
        
        request = {
            "action": mt5.TRADE_ACTION_DEAL,
            "symbol": symbol,
            "volume": volume,
            "type": order_type,
            "price": price,
            "sl": sl,
            "tp": tp,
            "magic": 234000,
            "comment": "SniperBot Trade",
            "type_time": mt5.ORDER_TIME_GTC,
            "type_filling": mt5.ORDER_FILLING_IOC,
        }
        
        result = mt5.order_send(request)
        if result.retcode != mt5.TRADE_RETCODE_DONE:
            logging.error(f"Order failed: {result.comment}")
            return False
        
        self.open_positions[result.order] = {"symbol": symbol, "entry_price": price}
        logging.info(f"Order placed successfully: {symbol}")
        return True

    def check_and_close_profitable_trades(self):
        """Check for profitable trades and close them if profit >= $20, then reopen"""
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
                    self.place_trade(position.symbol, position.type, position.volume)

    def shutdown(self):
        """Cleanup and shutdown"""
        mt5.shutdown()

if __name__ == "__main__":
    # Your account details
    SYMBOLS = ["EURUSD", "GBPUSD", "USDJPY", "USDCHF", "USDCAD", "EURGBP", "EURJPY", "GBPJPY"]
    ACCOUNT = 79431322
    PASSWORD = "Bilal@8477"
    SERVER = "Exness-MT5Trial8"
    
    # Create and run bot
    bot = SniperBot(SYMBOLS, ACCOUNT, PASSWORD, SERVER)
    
    try:
        if bot.initialize():
            print(f"{Fore.GREEN}Account initialized successfully{Style.RESET_ALL}")
            # Place a buy trade with $1000
            for symbol in SYMBOLS:
                volume = 1.0  # $1000 worth (adjust based on your broker's lot size)
                bot.place_trade(symbol, mt5.ORDER_TYPE_BUY, volume)
                
            # Continuously monitor trades
            while True:
                bot.check_and_close_profitable_trades()
                time.sleep(2)  # Check every 2 seconds
                
    except KeyboardInterrupt:
        print(f"{Fore.YELLOW}Account stopping...{Style.RESET_ALL}")
    finally:
        bot.shutdown()