# InteractiveBroker
This is an app designed to connect with the Interactive Brokers API with real-time data 

#Overview
Trader Workstation (TWS) is a desktop GUI application written in Python using Tkinter. It offers a friendly, interactive interface to:

1. View and manage trading accounts

2. Execute buy/sell/liquidate orders

3. Visualize price charts

4. Track portfolios and trading activity

5. View news feeds linked to stocks

The app integrates with the Interactive Brokers API to provide real-time data and order execution. It also contains simulated data and mock news for demonstration.

#Features- 
Account Summary: View net liquidation, margin, SMA, daily/unrealized/realized P&L.

Portfolio Table: Real-time position tracking for each symbol.

Trading Actions: Execute Buy, Sell, and Liquidate actions with quantity, order type, price, and TIF.

Charting: Interactive price chart with selectable time intervals and symbols; rendered using matplotlib.

Activity Log: Table of all trading activities, including executed trades.

Market Data: Displays bid, mid, and ask prices for current symbol.

News Feed: Linked news headlines for tracked stocks, with popup previews and direct links in your browser.

#Requirements
Python 3.7+

Interactive Brokers API (ibapi)

matplotlib

mplfinance

Install dependencies: 
pip install ibapi matplotlib mplfinance

#Quick Start
Connect TWS

1. Start your Interactive Brokers TWS or IB Gateway with API access enabled (default port 7497).
2. Run the app using python app.py
3. GUI Usage

Account: Check balances and margin values.

Portfolio: See and manage positions.

Buy/Sell: Enter symbol, qty, order type, and submit.

Chart: Select symbol and interval; view candlestick OHLC chart.

Activity: Track trades in real time.

News: Select headline for a full preview; open the article in a browser.

Main Files & Structure
app.py: Main application file (the provided code).

IBApiClient: Handles all API communication with Interactive Brokers.

IBClient: Business logic and data handling.

IBDashboard: Tkinter main window, builds UI and binds logic.

No other scripts required.

#Customization
Symbols: Default symbols (AAPL, TSLA, MSFT, AMZN, NVDA) can be changed in code.

News: Sample news is fed automatically for demo purposes. Connect to a real news source for live data.


Known Limitations:
Live trading requires a funded and correctly configured Interactive Brokers account.

Chart displays simulated OHLC data for demo purposes. Integrate IB historical data for live charts.

Demo news is simulated and is replaced with real feeds for live updates.

How to run the code: Run main code using the app.py script 

#License
This code is provided for educational and non-commercial use. Use caution and test thoroughly before real-money trading.

#Credits
Python Tkinter
Interactive Brokers API (ibapi)
matplotlib & mplfinance
