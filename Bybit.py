from pybit.unified_trading import HTTP

API_KEY = "J1OgMqNv77Y58f5A36"
API_SECRET = "p2mpFwCgTQk93xo5AOcUJ05GQdQsxrHV5hSm"

# Initialize session with an increased recv_window
session = HTTP(
    demo=True,
    api_key=API_KEY,
    api_secret=API_SECRET,
    recv_window=10000  # Increased recv_window to handle timestamp differences
)

# Request wallet balance
response = session.get_wallet_balance(
    accountType="UNIFIED",
    coin="USDT"
)

print(response)
