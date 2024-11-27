import yfinance as yf
import pandas as pd
from datetime import datetime, timedelta
from tabulate import tabulate
from colorama import init, Fore, Style

def calculate_pivots(high, low, close):
    pivot = (high + low + close) / 3
    r1 = (2 * pivot) - low
    r2 = pivot + (high - low)
    r3 = high + 2 * (pivot - low)
    s1 = (2 * pivot) - high
    s2 = pivot - (high - low)
    s3 = low - 2 * (high - pivot)
    return pivot, r1, r2, r3, s1, s2, s3

def analyze_indian_stocks(stock_list, days=30):
    """
    Analyze Indian stocks using Pivot Points strategy
    """
    end_date = datetime.now()
    start_date = end_date - timedelta(days=days)
    
    results = {
        'buy_signals': [],
        'sell_signals': []
    }
    
    for symbol in stock_list:
        try:
            stock = yf.download(f"{symbol}.NS", start=start_date, end=end_date)
            
            if len(stock) == 0:
                print(f"No data found for {symbol}")
                continue
            
            # Get latest price
            current_price = stock['Close'].iloc[-1]
            
            # Skip if price not in 100-1000 range
            if current_price < 100 or current_price > 1000:
                continue
                
            # Calculate Pivot Points using data from 2 days ago
            pivot, r1, r2, r3, s1, s2, s3 = calculate_pivots(
                stock['High'].iloc[-3],
                stock['Low'].iloc[-3], 
                stock['Close'].iloc[-3]
            )
            stock['Pivot'] = pivot
            stock['R1'] = r1
            stock['R2'] = r2
            stock['R3'] = r3
            stock['S1'] = s1
            stock['S2'] = s2
            stock['S3'] = s3
            
            # Generate signals based on price action around pivot level
            # Buy signal: Price closes above pivot
            if current_price > pivot:
                
                entry_price = current_price
                stop_loss = pivot * 0.99  # Just below pivot
                target1 = r1  # First target at R1
                target2 = r2  # Second target at R2
                
                results['buy_signals'].append({
                    'symbol': symbol,
                    'current_price': round(current_price, 2),
                    'entry_price': round(entry_price, 2),
                    'exit_price': round(stop_loss, 2),
                    'target1': round(target1, 2),
                    'target2': round(target2, 2),
                    'pivot': round(pivot, 2),
                    'r1': round(r1, 2),
                    'r2': round(r2, 2),
                    'r3': round(r3, 2),
                    's1': round(s1, 2),
                    's2': round(s2, 2),
                    's3': round(s3, 2),
                    'signal': f'{Fore.GREEN}BUY{Style.RESET_ALL}',
                    'data': stock
                })
            
            # Sell signal: Price closes below pivot
            elif current_price < pivot:
                
                entry_price = current_price
                stop_loss = pivot * 1.01  # Just above pivot
                target1 = s1  # First target at S1
                target2 = s2  # Second target at S2
                
                results['sell_signals'].append({
                    'symbol': symbol,
                    'current_price': round(current_price, 2),
                    'entry_price': round(entry_price, 2),
                    'exit_price': round(stop_loss, 2),
                    'target1': round(target1, 2),
                    'target2': round(target2, 2),
                    'pivot': round(pivot, 2),
                    'r1': round(r1, 2),
                    'r2': round(r2, 2),
                    'r3': round(r3, 2),
                    's1': round(s1, 2),
                    's2': round(s2, 2),
                    's3': round(s3, 2),
                    'signal': f'{Fore.RED}SELL{Style.RESET_ALL}',
                    'data': stock
                })
                
        except Exception as e:
            print(f"Error processing {symbol}: {str(e)}")
            
    return results

# Example usage
if __name__ == "__main__":
    # Initialize colorama
    init()
    
    # List of some major Indian stocks (add .NS suffix for NSE)
    indian_stocks = [
            'ONGC'
        ]
    # indian_stocks = [
    #         'RELIANCE', 'TCS', 'HDFCBANK', 'INFY', 'ICICIBANK',
    #         'HINDUNILVR', 'SBIN', 'BHARTIARTL', 'ITC', 'KOTAKBANK',
    #         'LT', 'AXISBANK', 'MARUTI', 'ASIANPAINT', 'WIPRO',
    #         'ULTRACEMCO', 'TITAN', 'BAJFINANCE', 'TECHM', 'SUNPHARMA',
    #         'TATASTEEL', 'HCLTECH', 'ADANIENT', 'JSWSTEEL', 'NTPC', 'BAJAJFINSV'
    #     ]
    
    # Analyze stocks
    results = analyze_indian_stocks(indian_stocks)
    
    # Get today's date
    today = datetime.now().strftime("%Y-%m-%d")
    
    # Prepare data for tables
    headers = ["Symbol", "Current Price (₹)", "Entry Price (₹)", "Stop Loss (₹)", 
              "Target 1 (₹)", "Target 2 (₹)", "PP", "Signal"]
    
    data_buy = [[stock['symbol'], stock['current_price'], stock['entry_price'], 
                 stock['exit_price'], stock['target1'], stock['target2'],
                 stock['pivot'], stock['signal']]
                for stock in results['buy_signals']]
                
    data_sell = [[stock['symbol'], stock['current_price'], stock['entry_price'],
                  stock['exit_price'], stock['target1'], stock['target2'],
                  stock['pivot'], stock['signal']]
                 for stock in results['sell_signals']]
    
    # Print date
    print(f"\nStock Analysis for {today}")
    
    # Print buy signals
    print(f"\n{Fore.GREEN}Stocks with Buy Signals (Pivot Points):{Style.RESET_ALL}")
    print(tabulate(data_buy, headers=headers, tablefmt="grid"))
    
    # Print sell signals
    print(f"\n{Fore.RED}Stocks with Sell Signals (Pivot Points):{Style.RESET_ALL}")
    print(tabulate(data_sell, headers=headers, tablefmt="grid"))