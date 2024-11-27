import yfinance as yf
import pandas as pd
from datetime import datetime, timedelta
from tabulate import tabulate
from colorama import init, Fore, Style
import plotly.graph_objects as go
from plotly.subplots import make_subplots

def analyze_indian_stocks(stock_list, days=30):
    """
    Analyze Indian stocks using EMA strategy to generate buy/sell signals with entry/exit prices
    
    Parameters:
    stock_list (list): List of stock symbols (NSE symbols with .NS suffix)
    days (int): Number of days to look back for analysis
    """
    # Calculate date range - get more historical data for EMA calculation
    end_date = datetime.now()
    start_date = end_date - timedelta(days=days)  # Extra days for EMA calculation
    
    results = {
        'buy_signals': [],
        'sell_signals': []
    }
    
    for symbol in stock_list:
        try:
            # Fetch stock data
            stock = yf.download(f"{symbol}.NS", start=start_date, end=end_date)
            
            if len(stock) == 0:
                print(f"No data found for {symbol}")
                continue
            
            # Calculate EMAs
            stock['EMA20'] = stock['Close'].ewm(span=20, adjust=False).mean()
            stock['EMA50'] = stock['Close'].ewm(span=50, adjust=False).mean()
            stock['EMA200'] = stock['Close'].ewm(span=200, adjust=False).mean()
            
            # Calculate RSI
            delta = stock['Close'].diff()
            gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
            rs = gain / loss
            stock['RSI'] = 100 - (100 / (1 + rs))
            
            # Calculate MACD
            exp1 = stock['Close'].ewm(span=12, adjust=False).mean()
            exp2 = stock['Close'].ewm(span=26, adjust=False).mean()
            stock['MACD'] = exp1 - exp2
            stock['Signal_Line'] = stock['MACD'].ewm(span=9, adjust=False).mean()
            
            # Get latest values
            current_price = stock['Close'].iloc[-1]
            current_ema20 = stock['EMA20'].iloc[-1]
            current_ema50 = stock['EMA50'].iloc[-1]
            current_ema200 = stock['EMA200'].iloc[-1]
            current_rsi = stock['RSI'].iloc[-1]
            current_macd = stock['MACD'].iloc[-1]
            current_signal = stock['Signal_Line'].iloc[-1]
            
            # Previous day values
            prev_ema20 = stock['EMA20'].iloc[-2]
            prev_ema50 = stock['EMA50'].iloc[-2]
            prev_macd = stock['MACD'].iloc[-2]
            prev_signal = stock['Signal_Line'].iloc[-2]
            
            # Calculate entry/exit prices based on EMAs
            entry_buffer = 0.002  # 0.2% buffer for entry
            exit_buffer = 0.002   # 0.2% buffer for exit
            
            # Generate signals based on multiple indicators
            # Buy signal: EMA20 crosses above EMA50 + confirming indicators
            if (prev_ema20 <= prev_ema50 and current_ema20 > current_ema50 and
                current_price > current_ema200 and  # Price above 200 EMA
                current_rsi > 40 and current_rsi < 70 and  # RSI not overbought
                prev_macd <= prev_signal and current_macd > current_signal):  # MACD crossover
                
                entry_price = current_price * (1 - entry_buffer)
                stop_loss = entry_price * 0.98  # 2% stop loss
                target = entry_price * 1.04  # 4% target
                
                results['buy_signals'].append({
                    'symbol': symbol,
                    'current_price': round(current_price, 2),
                    'entry_price': round(entry_price, 2),
                    'exit_price': round(stop_loss, 2),
                    'ema20': round(current_ema20, 2),
                    'ema50': round(current_ema50, 2),
                    'rsi': round(current_rsi, 2),
                    'macd': round(current_macd, 3),
                    'signal': f'{Fore.RED}SELL{Style.RESET_ALL}',
                    'data': stock
                })
            
            # Sell signal: EMA20 crosses below EMA50 + confirming indicators
            elif (prev_ema20 >= prev_ema50 and current_ema20 < current_ema50 and
                  current_price < current_ema200 and  # Price below 200 EMA
                  current_rsi < 60 and current_rsi > 30 and  # RSI not oversold
                  prev_macd >= prev_signal and current_macd < current_signal):  # MACD crossover
                
                entry_price = current_price * (1 + entry_buffer)
                stop_loss = entry_price * 1.02  # 2% stop loss
                target = entry_price * 0.96  # 4% target
                
                results['sell_signals'].append({
                    'symbol': symbol,
                    'current_price': round(current_price, 2),
                    'entry_price': round(entry_price, 2),
                    'exit_price': round(stop_loss, 2),
                    'ema20': round(current_ema20, 2),
                    'ema50': round(current_ema50, 2),
                    'rsi': round(current_rsi, 2),
                    'macd': round(current_macd, 3),
                    'signal': f'{Fore.GREEN}BUY{Style.RESET_ALL}',
                    'data': stock
                })
                
        except Exception as e:
            print(f"Error processing {symbol}: {str(e)}")
            
    return results

def plot_stock_chart(stock_data, symbol, signal_type):
    fig = make_subplots(rows=4, cols=1, shared_xaxes=True,
                        vertical_spacing=0.03,
                        subplot_titles=(f'{symbol} Price Chart', 'Volume', 'RSI', 'MACD'),
                        row_heights=[0.4, 0.2, 0.2, 0.2])

    # Candlestick chart
    fig.add_trace(go.Candlestick(x=stock_data.index,
                                open=stock_data['Open'],
                                high=stock_data['High'],
                                low=stock_data['Low'],
                                close=stock_data['Close'],
                                name='OHLC'), row=1, col=1)

    # Add EMAs
    fig.add_trace(go.Scatter(x=stock_data.index, y=stock_data['EMA20'],
                            line=dict(color='orange', width=1),
                            name='EMA20'), row=1, col=1)
    fig.add_trace(go.Scatter(x=stock_data.index, y=stock_data['EMA50'],
                            line=dict(color='blue', width=1),
                            name='EMA50'), row=1, col=1)
    fig.add_trace(go.Scatter(x=stock_data.index, y=stock_data['EMA200'],
                            line=dict(color='purple', width=1),
                            name='EMA200'), row=1, col=1)

    # Volume
    fig.add_trace(go.Bar(x=stock_data.index, y=stock_data['Volume'],
                        name='Volume'), row=2, col=1)

    # RSI
    fig.add_trace(go.Scatter(x=stock_data.index, y=stock_data['RSI'],
                            line=dict(color='red', width=1),
                            name='RSI'), row=3, col=1)
    
    # Add RSI levels
    fig.add_hline(y=70, line_dash="dash", line_color="red", row=3, col=1)
    fig.add_hline(y=30, line_dash="dash", line_color="green", row=3, col=1)

    # MACD
    fig.add_trace(go.Scatter(x=stock_data.index, y=stock_data['MACD'],
                            line=dict(color='blue', width=1),
                            name='MACD'), row=4, col=1)
    fig.add_trace(go.Scatter(x=stock_data.index, y=stock_data['Signal_Line'],
                            line=dict(color='orange', width=1),
                            name='Signal Line'), row=4, col=1)

    # Update layout
    fig.update_layout(
        title=f'{symbol} - {signal_type} Signal',
        yaxis_title='Price',
        yaxis2_title='Volume',
        yaxis3_title='RSI',
        yaxis4_title='MACD',
        xaxis_rangeslider_visible=False,
        height=1000
    )

    fig.show()

# Example usage
if __name__ == "__main__":
    # Initialize colorama
    init()
    
    # List of some major Indian stocks (add .NS suffix for NSE)
    indian_stocks = [
            'AARTIIND', 'ABB', 'ABBOTINDIA', 'ABCAPITAL', 'ABFRL', 'ACC', 'ADANIPORTS', 
            'ALKEM', 'AMBUJACEM', 'APOLLOHOSP', 'APOLLOTYRE', 'ASHOKLEY', 'ASIANPAINT', 
            'ASTRAL', 'ATUL', 'AUBANK', 'AUROPHARMA', 'AXISBANK', 'BAJAJ-AUTO', 'BAJAJFINSV', 
            'BAJFINANCE', 'BALKRISIND', 'BALRAMCHIN', 'BANDHANBNK', 'BANKBARODA', 'BATAINDIA',
            'BEL', 'BERGEPAINT', 'BHARATFORG', 'BHARTIARTL', 'BHEL', 'BIOCON', 'BOSCHLTD',
            'BPCL', 'BRITANNIA', 'BSOFT', 'CANBK', 'CANFINHOME', 'CHAMBLFERT', 'CHOLAFIN',
            'CIPLA', 'COALINDIA', 'COFORGE', 'COLPAL', 'CONCOR', 'COROMANDEL', 'CROMPTON',
            'CUB', 'DABUR', 'DALBHARAT', 'DEEPAKNTR', 'DELTACORP', 'DIVISLAB', 'DIXON',
            'DLF', 'DRREDDY', 'EICHERMOT', 'ESCORTS', 'GLENMARK', 'GMRINFRA', 'GODREJCP',
            'GODREJPROP', 'GRANULES', 'GRASIM', 'GSPL', 'GUJGASLTD', 'HAL', 'HAVELLS',
            'HCLTECH', 'HDFCAMC', 'HDFCBANK', 'HDFCLIFE', 'HINDALCO', 'HINDCOPPER',
            'HINDPETRO', 'HINDUNILVR', 'HONAUT', 'ICICIBANK', 'ICICIGI',
            'ICICIPRULI', 'IDEA', 'IDFCFIRSTB', 'IEX', 'IGL', 'INDHOTEL', 'INDIACEM',
            'INDIAMART', 'INDIGO', 'INDUSINDBK', 'INDUSTOWER', 'INFY', 'IOC', 'IRCTC', 'ITC',
            'JINDALSTEL', 'JKCEMENT', 'JSWSTEEL', 'JUBLFOOD', 'KOTAKBANK', 'LALPATHLAB',
            'LAURUSLABS', 'LICHSGFIN', 'LT', 'LTTS', 'LUPIN', 'M&M', 'M&MFIN',
            'MANAPPURAM', 'MARICO', 'MARUTI', 'MCX', 'METROPOLIS', 'MFSL',
            'MGL', 'MOTHERSON', 'MPHASIS', 'MRF', 'MUTHOOTFIN', 'NATIONALUM',
            'NAUKRI', 'NAVINFLUOR', 'NESTLEIND', 'NMDC', 'OBEROIRLTY', 'OFSS', 'ONGC',
            'PAGEIND', 'PEL', 'PERSISTENT', 'PETRONET', 'PFC', 'PIDILITIND', 'PIIND',
            'PNB', 'POLYCAB', 'POWERGRID', 'RAMCOCEM', 'RBLBANK', 'RECLTD',
            'RELIANCE', 'SAIL', 'SBICARD', 'SBILIFE', 'SBIN', 'SHREECEM', 'SIEMENS',
            'SRF', 'SUNPHARMA', 'SUNTV', 'SYNGENE', 'TATACHEM', 'TATACOMM',
            'TATACONSUM', 'TATAMOTORS', 'TATAPOWER', 'TATASTEEL', 'TCS', 'TECHM', 'TITAN',
            'TORNTPHARM', 'TORNTPOWER', 'TRENT', 'TVSMOTOR', 'UBL', 'ULTRACEMCO', 'UPL',
            'VEDL', 'VOLTAS', 'WHIRLPOOL', 'WIPRO', 'ZEEL', 'ZYDUSLIFE'
        ]
    
    # Analyze stocks
    results = analyze_indian_stocks(indian_stocks)
    
    # Prepare data for tables
    headers = ["Symbol", "Current Price (₹)", "Entry Price (₹)", "Exit Price (₹)", "EMA20", "EMA50", "RSI", "MACD", "Signal"]
    
    data_buy = [[stock['symbol'], stock['current_price'], stock['entry_price'], stock['exit_price'],
                 stock['ema20'], stock['ema50'], stock['rsi'], stock['macd'], stock['signal']]
                for stock in results['buy_signals']]
    data_sell = [[stock['symbol'], stock['current_price'], stock['entry_price'], stock['exit_price'],
                  stock['ema20'], stock['ema50'], stock['rsi'], stock['macd'], stock['signal']]
                 for stock in results['sell_signals']]
    
    # Print buy signals
    print(f"\n{Fore.RED}Stocks with Buy Signals (Multiple Indicator Confirmation):{Style.RESET_ALL}")
    print(tabulate(data_buy, headers=headers, tablefmt="grid"))
    
    # Print sell signals
    print(f"\n{Fore.GREEN}Stocks with Sell Signals (Multiple Indicator Confirmation):{Style.RESET_ALL}")
    print(tabulate(data_sell, headers=headers, tablefmt="grid"))

    # Plot charts for stocks with signals
    for stock in results['buy_signals']:
        plot_stock_chart(stock['data'], stock['symbol'], 'Buy')
    
    for stock in results['sell_signals']:
        plot_stock_chart(stock['data'], stock['symbol'], 'Sell')