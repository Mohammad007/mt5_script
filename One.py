import yfinance as yf
import numpy as np
import pandas as pd

class IndianStockAlgoTrader:
    def __init__(self, stocks, capital=100000):
        """
        Initialize the algorithmic trader for Indian stocks
        
        :param stocks: List of stock tickers (NSE format)
        :param capital: Initial trading capital
        """
        self.stocks = [f"{stock}.NS" for stock in stocks]  # Convert to NSE format
        self.capital = capital
        self.portfolio = {}
    
    def fetch_historical_data(self, period='5d'):
        """
        Fetch historical stock data
        
        :param period: Time period for historical data
        :return: Dictionary of stock dataframes
        """
        historical_data = {}
        for stock in self.stocks:
            try:
                df = yf.download(stock, period=period)
                
                # Check if dataframe is not empty
                if len(df) > 0:
                    df['Returns'] = df['Close'].pct_change()
                    
                    # Use a smaller window for 1-week data
                    df['Momentum'] = df['Returns'].rolling(window=min(5, len(df))).mean()
                    historical_data[stock] = df
                else:
                    print(f"No data available for {stock}")
            except Exception as e:
                print(f"Error fetching data for {stock}: {e}")
        return historical_data
    
    def generate_trading_signals(self, historical_data):
        """
        Generate buy/sell signals based on momentum strategy
        
        :param historical_data: Dictionary of stock dataframes
        :return: Trading signals
        """
        signals = {}
        for stock, df in historical_data.items():
            # Safely get the most recent momentum
            if len(df['Momentum'].dropna()) > 0:
                recent_momentum = df['Momentum'].dropna().iloc[-1]
                signals[stock] = {
                    'buy': recent_momentum > 0.02,  # Buy if momentum > 2%
                    'sell': recent_momentum < -0.02  # Sell if momentum < -2%
                }
            else:
                signals[stock] = {'buy': False, 'sell': False}
        return signals
    
    def execute_trades(self, signals, historical_data):
        """
        Execute trades based on generated signals
        
        :param signals: Trading signals
        :param historical_data: Historical stock data
        """
        for stock, signal in signals.items():
            # Ensure historical data exists and has entries
            if stock in historical_data and len(historical_data[stock]) > 0:
                latest_price = historical_data[stock]['Close'].iloc[-1]
                
                # Buy logic
                if signal['buy'] and self.capital > latest_price:
                    shares_to_buy = int(self.capital * 0.1 / latest_price)
                    trade_cost = shares_to_buy * latest_price
                    
                    self.portfolio[stock] = {
                        'shares': shares_to_buy,
                        'purchase_price': latest_price
                    }
                    self.capital -= trade_cost
                
                # Sell logic
                elif signal['sell'] and stock in self.portfolio:
                    shares_to_sell = self.portfolio[stock]['shares']
                    sell_value = shares_to_sell * latest_price
                    
                    self.capital += sell_value
                    del self.portfolio[stock]
    
    def run_strategy(self):
        """
        Execute complete trading strategy
        """
        historical_data = self.fetch_historical_data(period='5d')
        signals = self.generate_trading_signals(historical_data)
        self.execute_trades(signals, historical_data)
        
        # Performance reporting
        print("Trading Strategy Results:")
        print(f"Remaining Capital: ₹{self.capital:.2f}")
        print("Current Portfolio:")
        for stock, details in self.portfolio.items():
            print(f"{stock}: {details['shares']} shares at ₹{details['purchase_price']:.2f}")

# Example usage
if __name__ == "__main__":
    indian_stocks = ['INFY', 'ABB', 'TCS', 'LT']
    trader = IndianStockAlgoTrader(indian_stocks)
    trader.run_strategy()


# import yfinance as yf
# import pandas as pd
# import numpy as np

# class IndianStockOptionsTrader:
#     def __init__(self, stocks, capital=100000):
#         """
#         Initialize options trading strategy
#         """
#         self.stocks = stocks
#         self.capital = capital
#         self.portfolio = {}
    
#     def fetch_options_data(self, stock):
#         """
#         Fetch options data for a single stock
        
#         :param stock: Stock ticker
#         :return: Options data or None
#         """
#         try:
#             ticker = yf.Ticker(f"{stock}.NS")
            
#             # Get nearest expiration date
#             expirations = ticker.options
#             if not expirations:
#                 print(f"No options available for {stock}")
#                 return None
            
#             # Get options for the nearest expiration
#             options = ticker.option_chain(expirations[0])
            
#             # Check if options exist
#             if options.calls.empty or options.puts.empty:
#                 print(f"No call or put options for {stock}")
#                 return None
            
#             return options
#         except Exception as e:
#             print(f"Error fetching options for {stock}: {e}")
#             return None
    
#     def select_options(self, options, current_price):
#         """
#         Select ATM options
        
#         :param options: Options chain
#         :param current_price: Current stock price
#         :return: Selected call and put options
#         """
#         # Find options closest to current price
#         calls = options.calls
#         puts = options.puts
        
#         # Sort by absolute difference from current price
#         call_option = calls.loc[(calls['strike'] - current_price).abs().idxmin()]
#         put_option = puts.loc[(puts['strike'] - current_price).abs().idxmin()]
        
#         return call_option, put_option
    
#     def run_strategy(self):
#         """
#         Execute options trading strategy
#         """
#         print("Options Trading Strategy Results:")
        
#         for stock in self.stocks:
#             try:
#                 # Fetch current stock price
#                 stock_ticker = f"{stock}.NS"
#                 current_price = yf.download(stock_ticker, period='5d')['Close'].iloc[-1]
                
#                 # Fetch options data
#                 options = self.fetch_options_data(stock)
#                 if options is None:
#                     continue
                
#                 # Select options
#                 call_option, put_option = self.select_options(options, current_price)
                
#                 # Calculate trade amounts
#                 call_trade_amount = self.capital * 0.25
#                 put_trade_amount = self.capital * 0.25
                
#                 # Calculate option shares
#                 call_shares = int(call_trade_amount / call_option['lastPrice'])
#                 put_shares = int(put_trade_amount / put_option['lastPrice'])
                
#                 # Update portfolio
#                 self.portfolio[stock] = {
#                     'call': {
#                         'strike': call_option['strike'],
#                         'expiry': call_option['expiry'],
#                         'shares': call_shares,
#                         'price': call_option['lastPrice']
#                     },
#                     'put': {
#                         'strike': put_option['strike'],
#                         'expiry': put_option['expiry'],
#                         'shares': put_shares,
#                         'price': put_option['lastPrice']
#                     }
#                 }
                
#                 # Deduct trade costs
#                 trade_cost = (call_shares * call_option['lastPrice'] + 
#                               put_shares * put_option['lastPrice'])
#                 self.capital -= trade_cost
                
#                 # Print trade details
#                 print(f"\n{stock} Options:")
#                 print(f"Call - Strike: ₹{call_option['strike']}, Shares: {call_shares}")
#                 print(f"Put  - Strike: ₹{put_option['strike']}, Shares: {put_shares}")
            
#             except Exception as e:
#                 print(f"Error processing {stock}: {e}")
        
#         # Final capital
#         print(f"\nRemaining Capital: ₹{self.capital:.2f}")

# # Example usage
# if __name__ == "__main__":
#     indian_stocks = ['INFY', 'ABB', 'TCS', 'LT', 'TECHM', 'SIEMENS', 'BAJAJFINSV', 'HCLTECH', 'ULTRACEMCO', 'TITAN', 'HAL', 'MARUTI']
#     trader = IndianStockOptionsTrader(indian_stocks)
#     trader.run_strategy()