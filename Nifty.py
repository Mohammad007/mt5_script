import pandas as pd
import numpy as np
from sklearn.linear_model import LinearRegression
import yfinance as yf
from colorama import Fore, Back, Style

# Download Indian market indices data
indices = ["^NSEI", "^NSEBANK"]  # NSEI is Nifty50, NSEBANK is Bank Nifty
data = yf.download(indices, period="5d")

# Check if there is enough data to perform analysis
if len(data) < 5:
    print("Error: Not enough historical data to perform analysis.")
    exit()

# Calculate basic statistics and market sentiment
print("\nIndian Market Analysis:")
overall_sentiment = 0

# FII and DII Data (Example data - in real implementation, this would be fetched from a data source)
fii_data = {
    'buy_value': 5000,  # in crores
    'sell_value': 4500,  # in crores
    'net_value': 500    # in crores
}

dii_data = {
    'buy_value': 4200,  # in crores
    'sell_value': 4400,  # in crores
    'net_value': -200   # in crores
}

# Print FII/DII Analysis
print("\nFII/DII Analysis (in Crores):")
print(f"FII Net Flow: ₹{fii_data['net_value']} crores")
print(f"DII Net Flow: ₹{dii_data['net_value']} crores")

# Institutional Activity Sentiment
inst_sentiment = 1 if (fii_data['net_value'] + dii_data['net_value']) > 0 else -1
print(f"\nInstitutional Activity: {Fore.GREEN + 'Positive' + Style.RESET_ALL if inst_sentiment > 0 else Fore.RED + 'Negative' + Style.RESET_ALL}")

index_names = {
    "^NSEI": "NIFTY 50",
    "^NSEBANK": "BANK NIFTY"
}

for index in indices:
    index_data = data['Close'][index]
    print(f"\n{index_names[index]}:")
    
    # Calculate today's value change and percentage
    today_close = index_data.iloc[-1]
    prev_close = index_data.iloc[-2]
    value_change = today_close - prev_close
    pct_change = (value_change / prev_close) * 100
    
    change_color = Fore.GREEN if value_change > 0 else Fore.RED
    print(f"Today's Close: {today_close:.2f}")
    print(f"Change: {change_color}{value_change:+.2f} ({pct_change:+.2f}%){Style.RESET_ALL}")
    
    # Calculate market breadth and strength
    total_volume = data['Volume'][index].iloc[-1]
    if total_volume == 0:
        breadth = 0
        strength = 0
    else:
        if value_change > 0:
            buyers = total_volume * 0.6
            sellers = total_volume * 0.4
        else:
            buyers = total_volume * 0.4
            sellers = total_volume * 0.6
            
        breadth = (buyers - sellers) / total_volume
        
        # Calculate market strength based on volume
        avg_volume = data['Volume'][index].rolling(window=5).mean().iloc[-1]
        strength = total_volume / avg_volume - 1
        
    print(f"Market Breadth: {breadth:.2%}")
    print(f"Volume Strength: {strength:.2%}")
    
    # Calculate technical indicators
    # RSI
    delta = data['Close'][index].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
    rs = gain / loss
    rsi = 100 - (100 / (1 + rs)).iloc[-1]
    
    # Moving Averages
    ma20 = data['Close'][index].rolling(window=20).mean().iloc[-1]
    ma50 = data['Close'][index].rolling(window=50).mean().iloc[-1]
    
    # print(f"RSI: {rsi:.2f}")
    # print(f"MA20: {ma20:.2f}")
    # print(f"MA50: {ma50:.2f}")
    
    # Prepare data for trend prediction
    X = np.arange(len(index_data)).reshape(-1, 1)
    y = index_data.values
    model = LinearRegression()
    model.fit(X, y)
    
    # Predict next day's trend
    next_day = len(index_data)
    predicted_value = model.predict([[next_day]])[0]
    pred_change = predicted_value - today_close
    pred_color = Fore.GREEN if pred_change > 0 else Fore.RED
    print(f"Tomorrow's Prediction: {pred_color}{predicted_value:.2f} ({pred_change:+.2f}){Style.RESET_ALL}")
    
    # Calculate fundamental score
    fundamental_score = 0
    
    # Add fundamental factors
    if rsi < 30:  # Oversold
        fundamental_score += 1
    elif rsi > 70:  # Overbought
        fundamental_score -= 1
        
    if today_close > ma50:  # Above long term trend
        fundamental_score += 1
    else:
        fundamental_score -= 1
        
    if strength > 0.2:  # Strong volume
        fundamental_score += 1
    elif strength < -0.2:  # Weak volume
        fundamental_score -= 1
    
    # Calculate sentiment score with more weight on fundamentals
    sentiment_score = 0
    sentiment_score += 1 if value_change > 0 else -1  # Price trend
    sentiment_score += 1 if breadth > 0 else -1       # Market breadth
    sentiment_score += 1 if pred_change > 0 else -1   # Prediction
    sentiment_score += inst_sentiment                 # Institutional activity
    sentiment_score += fundamental_score * 2          # Fundamental factors (double weight)
    
    overall_sentiment += sentiment_score
    
    # Print index sentiment with fundamental consideration
    sentiment_text = ""
    if sentiment_score > 2:
        sentiment_text = Back.GREEN + Fore.WHITE + "STRONGLY BULLISH" + Style.RESET_ALL
    elif sentiment_score > 0:
        sentiment_text = Fore.GREEN + "MODERATELY BULLISH" + Style.RESET_ALL
    elif sentiment_score < -2:
        sentiment_text = Back.RED + Fore.WHITE + "STRONGLY BEARISH" + Style.RESET_ALL
    elif sentiment_score < 0:
        sentiment_text = Fore.RED + "MODERATELY BEARISH" + Style.RESET_ALL
    else:
        sentiment_text = Fore.YELLOW + "NEUTRAL" + Style.RESET_ALL
        
    print(f"Index Sentiment (Including Fundamentals): {sentiment_text}")
    print(f"Fundamental Score: {fundamental_score}")

# Print overall Indian market sentiment with trading recommendations
print("\nOverall Indian Market Sentiment: ", end="")
if overall_sentiment > 4:
    print(f"{Back.GREEN}{Fore.WHITE}STRONGLY BULLISH - Good time to BUY with strong fundamentals{Style.RESET_ALL}")
elif overall_sentiment > 0:
    print(f"{Fore.GREEN}MODERATELY BULLISH - Consider selective BUYING of fundamentally strong stocks{Style.RESET_ALL}")
elif overall_sentiment < -4:
    print(f"{Back.RED}{Fore.WHITE}STRONGLY BEARISH - Consider SELLING weak fundamental positions{Style.RESET_ALL}")
elif overall_sentiment < 0:
    print(f"{Fore.RED}MODERATELY BEARISH - Be CAUTIOUS, focus on strong fundamentals{Style.RESET_ALL}")
else:
    print(f"{Fore.YELLOW}NEUTRAL - HOLD fundamentally strong positions{Style.RESET_ALL}")