import tkinter as tk
from tkinter import ttk
import webbrowser
import datetime
import random
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import matplotlib.dates as mdates
from matplotlib.dates import DateFormatter
from mplfinance.original_flavor import candlestick_ohlc
from re import search
import threading



# ========== INTERACTIVE BROKERS API ADDITIONS (BEGIN) ==========
from threading import Thread
from ibapi.client import EClient
from ibapi.wrapper import EWrapper
from ibapi.contract import Contract
from ibapi.order import Order
from ibapi.execution import ExecutionFilter




class IBApiClient(EWrapper, EClient):
  def __init__(self, gui_callback):
      EClient.__init__(self, self)
      self.nextOrderId = None
      self.gui_callback = gui_callback

      self.positions = {}
      self.trades = []
      self.market_data = {}


  def connect_async(self, host="127.0.0.1", port=7497, client_id=100):
      Thread(target=self.connect, args=(host, port, client_id), daemon=True).start()


  def nextValidId(self, orderId: int):
      self.nextOrderId = orderId
      if self.gui_callback:
          self.gui_callback('next_order_id',orderId)


  def error(self, reqId, errorCode, errorString, advancedOrderRejectJson=None):
      print(f"IB Error {errorCode} (req {reqId}): {errorString}")


  def orderStatus(self, orderId, status, filled, remaining, avgFillPrice,
                  permId, parentId, lastFillPrice, clientId, whyHeld, mktCapPrice):
      print(f"OrderStatus. ID: {orderId}, Status: {status}, Filled: {filled}, Remaining: {remaining}, AvgFillPrice: {avgFillPrice}")



  def execDetails(self, reqId, contract, execution):
      trade = {
          'symbol': contract.symbol,
          'qty': execution.shares,
          'price': execution.price,
          'side': execution.side,
          'time': execution.time,
          'exchange': execution.exchange
      }
      self.trades.append(trade)
      if self.gui_callback:
          self.gui_callback('trade_update', trade)


  def position(self, account, contract, position, avgCost):
      self.positions[contract.symbol] = position
      if self.gui_callback:
          self.gui_callback('positions_update', dict(self.positions))


  def positionEnd(self):
      print("Position data complete")


  def tickPrice(self, reqId, tickType, price, attrib):
      print(f"tickPrice received: reqId={reqId}, tickType={tickType}, price={price}")
      if reqId not in self.market_data:
          self.market_data[reqId] = {}
      if tickType == 1:
          self.market_data[reqId]['bid'] = price
      elif tickType == 2:
          self.market_data[reqId]['ask'] = price
      elif tickType == 4:
          self.market_data[reqId]['last'] = price
      if self.gui_callback:
          self.gui_callback('market_data_update', (reqId, self.market_data[reqId]))


  def request_positions(self):
      self.reqPositions()


  def request_executions(self):
      filt = ExecutionFilter()
      self.reqExecutions(1, filt)


  def request_market_data(self, symbol, reqId):
      contract = Contract()
      contract.symbol = symbol
      contract.secType = "STK"
      contract.exchange = "SMART"
      contract.currency = "USD"
      self.reqMktData(reqId, contract, "", False, False, [])


  def place_order(self, symbol, action, qty, order_type="LMT", lmt_price=None, tif="GTC"):
   if self.nextOrderId is None:
       print("Waiting for next valid order ID from IB...")
       return False


   contract = Contract()
   contract.symbol = symbol
   contract.secType = "STK"
   contract.exchange = "SMART"
   contract.currency = "USD"


   order = Order()
   order.action = action
   order.totalQuantity = qty


   # Fix order_type string for IB API: convert "MID PRICE" to "MIDPRICE"
   if order_type.upper().replace(" ", "") == "MIDPRICE":
       order.orderType = "MIDPRICE"
   elif order_type.upper() == "MKT":
       order.orderType = "MKT"
   else:
       order.orderType = "LMT"


   order.tif = tif


   # Clear deprecated attributes to prevent IB Error 10268
   order.eTradeOnly = ""
   order.firmQuoteOnly = ""
   order.nbboPriceCap = ""


   if order.orderType == "LMT" and lmt_price is not None:
       try:
           order.lmtPrice = float(lmt_price)
       except ValueError:
           print("Invalid limit price.")
           return False


   print(f"Placing order #{self.nextOrderId}: {action} {qty} {symbol} {order.orderType} at {lmt_price}")
   self.placeOrder(self.nextOrderId, contract, order)
   self.nextOrderId += 1
   return True


  def request_account_summary(self):
      self.reqAccountSummary(9001, "All", "NetLiquidation,TotalCashValue,AvailableFunds")



  def accountSummary(self, reqId, account, tag, value, currency):
      if self.gui_callback:
          self.gui_callback('account_summary_update', {'tag': tag, 'value': value, 'currency': currency})


  def accountSummaryEnd(self, reqId):
      print("Account Summary End")


class IBClient:
 def __init__(self, gui_callback):
     self.news_list = []
     self.news_urls = []
     self.ibapi = IBApiClient(gui_callback)
     self.ibapi.connect_async()
     self.current_symbol = "AAPL"
     self.reqId_counter = 1
     self.symbol_reqId_map = {}
     self.trade_activities = []
     self.last_prices = {}


 def start(self):
     threading.Timer(3, self.ibapi.run).start()
     threading.Timer(5, self.initial_request).start()


 def initial_request(self):
  self.ibapi.request_positions()
  self.ibapi.request_executions()
  self.subscribe_market_data(self.current_symbol)
  self.ibapi.request_account_summary()

 def subscribe_market_data(self, symbol):
      if symbol in self.symbol_reqId_map:
          return self.symbol_reqId_map[symbol]
      reqId = self.reqId_counter
      self.reqId_counter += 1
      self.symbol_reqId_map[symbol] = reqId
      self.ibapi.request_market_data(symbol, reqId)
      return reqId

 def get_account_summary(self):
     return [
         {'tag': 'NetLiquidation', 'value': '1.0M'},
     ]


 def place_order(self, symbol, action, qty, order_type="LMT", lmt_price=None, tif="GTC"):
      return self.ibapi.place_order(symbol, action, qty, order_type, lmt_price, tif)


 def on_news(self, bulletin):
      now = datetime.datetime.now()
      symbol = None
      match = search(r"\[([A-Z]+)\]", bulletin['message'])
      if match:
          symbol = match.group(1)
      else:
          parts = bulletin['message'].split()
          for part in parts:
              if part.isupper() and len(part) <= 5:
                  symbol = part
                  break
      source = bulletin.get('exchange', '') or bulletin.get('origExchange', '')
      headline = bulletin['message']
      if not any(news['headline'] == headline for news in self.news_list):
          self.news_list.append({
              'datetime': now,
              'source': source,
              'symbol': symbol if symbol else "",
              'headline': headline,
              'url': bulletin.get('url', f"https://www.google.com/search?q={headline.replace(' ', '+')}")
          })
          if len(self.news_list) > 20:
              self.news_list.pop(0)



 def get_real_time_news(self):
      return list(self.news_list)


 def add_trade_activity(self, trade):
     self.trade_activities.append(trade)
     if len(self.trade_activities) > 50:
         self.trade_activities.pop(0)



 def get_trade_activities(self):
     return list(self.trade_activities)
 
 def get_bid_mid_ask(self, symbol):
  import random
  bid = round(random.uniform(100, 110), 2)
  ask = round(bid + random.uniform(0.1, 0.5), 2)
  mid = round((bid + ask) / 2, 2)
  self.last_prices[symbol] = mid
  return {'bid': bid, 'mid': mid, 'ask': ask}




class IBDashboard(tk.Tk):
 def __init__(self):
     super().__init__()
     self.title("Trader Workstation")
     self.geometry("1300x750")
     self.account_summary_data = {}
     self.news_urls = []


     self.ib_client = IBClient(gui_callback=self.handle_ib_event)
     self.ib_client.start()


     self.grid_columnconfigure(0, weight=3)
     self.grid_columnconfigure(1, weight=2)
     self.grid_rowconfigure(0, weight=0)
     self.grid_rowconfigure(1, weight=3)
     self.grid_rowconfigure(2, weight=1)



     self.build_ui()
     self.running = True
     self.protocol("WM_DELETE_WINDOW", self.on_close)


 def on_close(self):
       self.running = False
       self.destroy()




 def build_ui(self):
     # --- Account Summary ---
     account_frame = tk.Frame(self, bd=2, relief=tk.SUNKEN)
     account_frame.grid(row=0, column=0, columnspan=2, sticky="nsew", padx=5, pady=5)
     account_frame.grid_columnconfigure(0, weight=1)
     tk.Label(account_frame, text="Account Summary", font=("Arial", 14)).grid(row=0, column=0, sticky="w", padx=5, pady=5)
     self.account_text = tk.Text(account_frame, height=6)
     self.account_text.grid(row=1, column=0, sticky="nsew", padx=5, pady=5)


     #-- buy/sell buttons
     button_frame = tk.Frame(account_frame)
     button_frame.grid(row=0, column=1, sticky="e", padx=(0, 10), pady=(5, 10))
     buy_button = tk.Button(button_frame, text="Buy", command=self.buy_action)
     buy_button.pack(side=tk.LEFT, padx=(0, 5))



     sell_button = tk.Button(button_frame, text="Sell", command=self.sell_action)
     sell_button.pack(side=tk.LEFT)


     liquidate_button = tk.Button(button_frame, text="Liquidate", command=self.liquidate_position_action)
     liquidate_button.pack(side=tk.LEFT, padx=(0, 5))


     #--- Quantity, limit, limit price, day
     fields_frame = tk.Frame(account_frame)
     fields_frame.grid(row=1, column=1, sticky="nsew", padx=5, pady=2)

     tk.Label(fields_frame, text="Qty").grid(row=0, column=0, padx=2)
     self.qty_entry = tk.StringVar(value="100")
     tk.Entry(fields_frame, textvariable=self.qty_entry, width=7).grid(row=0, column=1, padx=2)


     #tk.Label(fields_frame, text="Limit:").grid(row=0, column=2, padx=2)
     self.limit_var = tk.StringVar(value="LMT")
     self.limit_dropdown = ttk.Combobox(fields_frame, textvariable=self.limit_var, width=7, state="readonly")
     self.limit_dropdown['values'] = ("LMT", "MID PRICE", "MKT")
     self.limit_dropdown.grid(row=0, column=3, padx=2)


     tk.Label(fields_frame, text="Limit Price:").grid(row=0, column=4, padx=2)
     self.limit_price_var = tk.StringVar(value="0.00")
     tk.Entry(fields_frame, textvariable=self.limit_price_var, width=8).grid(row=0, column=5, padx=2)


     #tk.Label(fields_frame, text="Day:").grid(row=0, column=6, padx=2)
     self.day_var = tk.StringVar(value="Day")
     self.day_dropdown = ttk.Combobox(fields_frame, textvariable=self.day_var, width=7, state="readonly")
     self.day_dropdown['values'] = ("Day", "GTC")
     self.day_dropdown.grid(row=0, column=7, padx=2)


     # --- Chart Frame ---
     chart_frame = tk.Frame(self, bd=2, relief=tk.SUNKEN)
     chart_frame.grid(row=1, column=0, sticky="nsew", padx=5, pady=5)
     chart_frame.grid_rowconfigure(1, weight=3)
     chart_frame.grid_rowconfigure(2, weight=1)
     chart_frame.grid_columnconfigure(0, weight=1)


     self.fig, self.ax_price = plt.subplots(1, 1, figsize=(4, 2.5))
     self.canvas = FigureCanvasTkAgg(self.fig, master=chart_frame)
     self.canvas.get_tk_widget().grid(row=1, column=0, sticky="nsew", padx=5, pady=5)

     # Chart Symbol Selector
     selector_frame = tk.Frame(chart_frame)
     selector_frame.grid(row=0, column=0, sticky="ew", pady=(5, 0))
     tk.Label(selector_frame, text="Chart Symbol:").pack(side=tk.LEFT, padx=(5, 2))
     self.symbol_var = tk.StringVar(value="AAPL")
     symbol_dropdown = ttk.Combobox(selector_frame, textvariable=self.symbol_var,
                                    values=["AAPL", "TSLA", "MSFT", "AMZN", "NVDA"],
                                    state="normal", width=10)
     symbol_dropdown.pack(side=tk.LEFT)
     symbol_dropdown.bind("<<ComboboxSelected>>", self.on_symbol_change)
     symbol_dropdown.bind("<Return>", self.on_symbol_change)
     symbol_dropdown.bind("<FocusOut>", self.on_symbol_change)

     # Chart (matplotlib)
     self.fig, self.ax_price = plt.subplots(1, 1, figsize=(4, 2.5))
     self.canvas = FigureCanvasTkAgg(self.fig, master=chart_frame)
     self.canvas.get_tk_widget().grid(row=1, column=0, sticky="nsew", padx=5, pady=5)

     # Interval Selector
     self.interval_var = tk.StringVar(value="5 min")
     interval_dropdown = ttk.Combobox(selector_frame, textvariable=self.interval_var,
                                     values=["1 min","3 min" ,"5 min", "10 min", "15 min", "30 min", "1 hour","4 hours" ,"1 day", "1 week", "1 month"],
                                     state="readonly", width=7)
     interval_dropdown.pack(side=tk.LEFT, padx=(10, 0))
     interval_dropdown.bind("<<ComboboxSelected>>", self.on_interval_change)


     # --- Activity Section below chart ---
     activity_frame = tk.Frame(self, bd=2, relief=tk.SUNKEN)
     activity_frame.grid(row=2, column=0, sticky="nsew", padx=5, pady=5)
     activity_frame.grid_columnconfigure(0, weight=1)
     tk.Label(activity_frame, text="Activity (Trades)", font=("Arial", 14)).grid(row=0, column=0, sticky="w", padx=5, pady=5)


     columns = ("PlusMinus", "Time", "Symbol", "Action", "Qty", "Price", "Exchange")
     self.activity_tree = ttk.Treeview(activity_frame, columns=columns, show="headings", height=9)
     for col in columns:
         self.activity_tree.heading(col, text=col)
         self.activity_tree.column(col, width=80, anchor="center")
     self.activity_tree.grid(row=1, column=0, sticky="nsew", padx=5, pady=(0, 5))

     # --- Portfolio/Profile Frame (TWS Style) ---
     portfolio_frame = tk.Frame(self, bd=2, relief=tk.SUNKEN)
     portfolio_frame.grid(row=1, column=1, sticky="nsew", padx=5, pady=5)
     portfolio_frame.grid_rowconfigure(2, weight=1)
     portfolio_frame.grid_columnconfigure(0, weight=1)
     tk.Label(portfolio_frame, text="Portfolio", font=("Arial", 14)).grid(row=0, column=0, sticky="w", padx=5, pady=(5, 10))

     summary_frame = tk.Frame(portfolio_frame)
     summary_frame.grid(row=1, column=0, sticky="ew", padx=5, pady=(5, 0))

     pnl_frame = tk.Frame(summary_frame)
     pnl_frame.pack(side=tk.LEFT, anchor="nw", padx=(0, 40))
     tk.Label(pnl_frame, text="P&L", font=("Arial", 11, "bold")).grid(row=0, column=0, sticky="w")
     tk.Label(pnl_frame, text="DAILY", font=("Arial", 9, "bold")).grid(row=1, column=0, sticky="w")
     tk.Label(pnl_frame, text="Since prior Close", font=("Arial", 9, "bold")).grid(row=2, column=0, sticky="w")
     self.unrealized_label = tk.Label(pnl_frame, text="Unrealized", font=("Arial", 11, "bold"))
     self.unrealized_label.grid(row=1, column=1, sticky="w", padx=(20,0))
     self.unrealized_value = tk.Label(pnl_frame, text="0", font=("Arial", 11))
     self.unrealized_value.grid(row=1, column=2, sticky="w")
     self.realized_label = tk.Label(pnl_frame, text="Realized", font=("Arial", 11, "bold"))
     self.realized_label.grid(row=2, column=1, sticky="w", padx=(20,0))
     self.realized_value = tk.Label(pnl_frame, text="0", font=("Arial", 11))
     self.realized_value.grid(row=2, column=2, sticky="w")
     # Right: Margin
     margin_frame = tk.Frame(summary_frame)
     margin_frame.pack(side=tk.LEFT, anchor="nw")
     tk.Label(margin_frame, text="Margin", font=("Arial", 11, "bold")).grid(row=0, column=0, sticky="w")
     tk.Label(margin_frame, text="Net Liquidity", font=("Arial", 10, "bold")).grid(row=1, column=0, sticky="w")
     self.netliq_value = tk.Label(margin_frame, text="1.0M", font=("Arial", 11))
     self.netliq_value.grid(row=1, column=1, sticky="w")
     tk.Label(margin_frame, text="Excess Liq", font=("Arial", 10, "bold")).grid(row=1, column=2, sticky="w", padx=(20,0))
     self.excessliq_value = tk.Label(margin_frame, text="1.0M", font=("Arial", 11))
     self.excessliq_value.grid(row=1, column=3, sticky="w")
     tk.Label(margin_frame, text="Maintenance", font=("Arial", 10, "bold")).grid(row=2, column=0, sticky="w")
     self.maint_value = tk.Label(margin_frame, text="0", font=("Arial", 11))
     self.maint_value.grid(row=2, column=1, sticky="w")
     tk.Label(margin_frame, text="SMA", font=("Arial", 10, "bold")).grid(row=2, column=2, sticky="w", padx=(20,0))
     self.sma_value = tk.Label(margin_frame, text="1.0M", font=("Arial", 11))
     self.sma_value.grid(row=2, column=3, sticky="w")


     # --- Portfolio Table (DLY ... FIN INSTR etc) ---
     table_frame = tk.Frame(portfolio_frame)
     table_frame.grid(row=2, column=0, sticky="nsew", padx=5, pady=(10,5))
     columns = ("DLY", "FIN INSTR", "POS", "MKT VAL")
     self.portfolio_tree = ttk.Treeview(table_frame, columns=columns, show="headings", height=15)
     for col in columns:
         self.portfolio_tree.heading(col, text=col, anchor="center")
         self.portfolio_tree.column(col, width=120 if col=="FIN INSTR" else 80, anchor="center")
     self.portfolio_tree.grid(row=0, column=0, sticky="nsew")


     # --- News Frame ---
     news_frame = tk.Frame(self, bd=2, relief=tk.SUNKEN)
     news_frame.grid(row=2, column=1, sticky="nsew", padx=5, pady=5)
     news_frame.grid_rowconfigure(1, weight=1)
     news_frame.grid_columnconfigure(0, weight=1)
     tk.Label(news_frame, text="News", font=("Arial", 14)).grid(row=0, column=0, sticky="w", padx=5, pady=5)
     self.news_listbox = tk.Listbox(news_frame, height=12)
     self.news_listbox.grid(row=1, column=0, sticky="nsew", padx=5, pady=5)
     self.news_listbox.bind('<<ListboxSelect>>', self.open_news_link)

     #News tab
     self.notebook = ttk.Notebook(self)
     self.notebook.grid(row=3, column=0, columnspan=2, sticky="nsew", padx=5, pady=5)
     self.notebook_tabs = {}
     self.news_listbox.bind('<<ListboxSelect>>', self.open_news_popup)


     self.on_ordertype_change()
     self.refresh_data()
     self.refresh_news()
     self.update_chart()
     self.sample_bulletins = [
         {
             'message': "Breaking News: [AAPL] hits all time high!",
             'exchange': "APPL",
             'url': "https://www.barrons.com/articles/apple-stock-wwdc-ai-iphone-521dee2a"
         },
         {
             'message': "Breaking News: [TSLA] Stock is rising",
             'exchange': "TSLA",
             'url': "https://www.barrons.com/articles/tesla-stock-price-robotaxi-musk-b725a2ce"
         },
         {
             'message': "Update: [MSFT] Hits an all-time high",
             'exchange': "MSFT",
             'url': "https://www.fool.com/investing/2025/06/13/microsoft-all-time-high-buy-meta-platforms-nvidia/"
         },
         {
             'message': "Market Update: [AMZN] Stock Could Rise 35%",
             'exchange': "AMZN",
             'url': "https://watcher.guru/news/amazon-stock-amzn-could-rise-35-to-290-as-84-plan-to-shop-prime-day"
         },
         {
             'message': "Market Update: [NVDA] Stock is on the rise",
             'exchange': "NVSA",
             'url': "https://www.barrons.com/articles/nvidia-stock-price-ai-chips-e2a8c497"
         },
         {
             'message': "Why Is Telomir Pharmaceuticals Stock (TELO) Up 150% Today?",
             'exchange': "TELO",
             'url': "https://www.tipranks.com/news/why-is-telomir-pharmaceuticals-stock-telo-up-150-today"
         },
         {
             'message': "Incannex Healthcare (IXHL) Soars 64.82 percent on Cannabis Industry Growth",
             'exchange': "IXHL",
             'url': "https://www.ainvest.com/news/incannex-healthcare-ixhl-soars-64-82-cannabis-industry-growth-2507/"
         },
         {
             'message': "CYCLACEL PHARMACEUTICALS COMMENTS ON RECENT STOCK PRICE VOLATILITY",
             'exchange': "CYCC",
             'url': "https://www.stocktitan.net/news/CYCC/cyclacel-pharmaceuticals-comments-on-recent-stock-price-owny8ncywd2t.html"
         },
         {
             'message': "Blaize Secures Contract to Deliver Scalable Hybrid AI Infrastructure Across Asia",
             'exchange': "BZAI",
             'url': "https://www.stocktitan.net/news/BZAI/blaize-secures-contract-to-deliver-scalable-hybrid-ai-infrastructure-6ncsr9t4pwu0.html"
         },
         {
             'message': "Expion360 to Host First Quarter 2025 Financial Results Conference Call",
             'exchange': "XPON",
             'url': "https://www.stocktitan.net/news/XPON/expion360-to-host-first-quarter-2025-financial-results-conference-wnlfx6lkkvdi.html"
         },
         {
             'message': "$STEM stock is up 17% today. Here's what we see in our data.",
             'exchange': "STEM",
             'url': "https://www.nasdaq.com/articles/stem-stock-17-today-heres-what-we-see-our-data"
         },
         {
             'message': "Carver Bancorp, Inc. Rings Nasdaq Opening Bell Celebrating Juneteenth, Elevating the Role of Community Banks in Serving Main Street",
             'exchange': "CARV",
             'url': "https://www.stocktitan.net/news/CARV/carver-bancorp-inc-rings-nasdaq-opening-bell-celebrating-juneteenth-ci2sgrla1ozd.html"
         },
         {
             'message': "Solid Power(SLDP) Shares Soar 4.40% on Battery Tech Advancements",
             'exchange': "SLDP",
             'url': "https://www.ainvest.com/news/solid-power-sldp-shares-soar-4-40-battery-tech-advancements-2507/"
         }
     ]
     self.news_index = 0
     self.simulate_news_feed()
     self.update_chart()
     self.refresh_data()
     self.refresh_news()




 def handle_ib_event(self, event_type, data):
  if not self.running:
       return
  if event_type == 'positions_update':
      self.after(0, lambda: self.refresh_portfolio(data))
  elif event_type == 'trade_update':
      self.after(0, lambda: self.add_trade_activity(data))
  elif event_type == 'market_data_update':
      reqId, market_data = data
      # Update last_prices mid price
      for sym, r_id in self.ib_client.symbol_reqId_map.items():
          if r_id == reqId:
              bid = market_data.get('bid')
              ask = market_data.get('ask')
              if bid is not None and ask is not None:
                  mid = (bid + ask) / 2
                  self.ib_client.last_prices[sym] = mid
              break
      self.after(0, self.refresh_account_text)
  elif event_type == 'account_summary_update':
      self.after(0, lambda: self.update_account_summary(data))
  elif event_type == 'next_order_id':
      pass



 def refresh_portfolio(self, positions):
      self.portfolio_tree.delete(*self.portfolio_tree.get_children())
      for symbol, pos in positions.items():
          self.portfolio_tree.insert("", tk.END, values=(symbol, pos))


 def add_trade_activity(self, trade):
      plus_minus = '+' if trade['side'].upper() == 'BUY' else '-'
      time = trade['time'] if 'time' in trade else datetime.datetime.now().strftime("%H:%M:%S")
      self.activity_tree.insert("", 0, values=(
          plus_minus,
          time,
          trade.get('symbol', ''),
          trade.get('side', ''),
          trade.get('qty', ''),
          f"{trade.get('price', 0):.2f}",
          trade.get('exchange', '')
      ))



 def update_market_data(self, reqId, md):
      for sym, r_id in self.ib_client.symbol_reqId_map.items():
          if r_id == reqId:
              text = f"{sym} Market Data:\n"
              if 'bid' in md:
                  text += f"Bid: {md['bid']}\n"
              if 'ask' in md:
                  text += f"Ask: {md['ask']}\n"
              if 'last' in md:
                  text += f"Last: {md['last']}\n"
              self.account_text.delete(1.0, tk.END)
              self.account_text.insert(tk.END, text)
              break


 def buy_action(self):
  symbol = self.symbol_var.get()
  try:
      qty = int(self.qty_entry.get())
  except ValueError:
      print("Invalid quantity")
      return


  prices = self.ib_client.get_bid_mid_ask(symbol)
  mid = prices['mid']
  if mid is None:
      print("Market data unavailable, cannot place buy order")
      return
 

  order_type = self.limit_var.get()
  lmt_price = self.limit_price_var.get() if order_type == "LMT" else None
  tif = self.day_var.get()
  placed = self.ib_client.place_order(symbol, "BUY", qty, order_type, lmt_price, tif)
  if placed:
      print(f"Buy order placed for {qty} {symbol} at approx {mid:.2f}")
      self.ib_client.last_prices[symbol] = mid  # Update after trade
  else:
      print("Order not placed - waiting for IB connection")



 def sell_action(self):
  symbol = self.symbol_var.get()
  try:
      qty = int(self.qty_entry.get())
  except ValueError:
      print("Invalid quantity")
      return



  prices = self.ib_client.get_bid_mid_ask(symbol)
  mid = prices['mid']
  if mid is None:
      print("Market data unavailable, cannot place sell order")
      return



  position = self.ib_client.ibapi.positions.get(symbol, 0)
  if position < qty:
      print(f"Sell blocked: Not enough shares in position ({position}) < ({qty})")
      return



  order_type = self.limit_var.get()
  lmt_price = self.limit_price_var.get() if order_type == "LMT" else None
  tif = self.day_var.get()
  placed = self.ib_client.place_order(symbol, "SELL", qty, order_type, lmt_price, tif)
  if placed:
      print(f"Sell order placed for {qty} {symbol} at approx {mid:.2f}")
      self.ib_client.last_prices[symbol] = mid
  else:
      print("Order not placed - waiting for IB connection or insufficient position")

 def liquidate_position_action(self):
      symbol = self.symbol_var.get()
      position = self.ib_client.ibapi.positions.get(symbol, 0)
      if position > 0:
          self.ib_client.place_order(symbol, "SELL", position, "MKT", None, "GTC")
      elif position < 0:
          self.ib_client.place_order(symbol, "BUY", -position, "MKT", None, "GTC")
      else:
          print("No position to liquidate.")


 def open_news_link(self, event):
      selection = event.widget.curselection()
      if selection:
          index = selection[0]
          if 0 <= index < len(self.ib_client.news_list):
              url = self.ib_client.news_list[index].get('url')
              if url:
                  webbrowser.open(url)


 def on_symbol_change(self, event=None):
  new_symbol = self.symbol_var.get()
  old_symbol = self.ib_client.current_symbol


  if new_symbol and new_symbol != old_symbol:
      if old_symbol in self.ib_client.symbol_reqId_map:
          old_reqId = self.ib_client.symbol_reqId_map[old_symbol]
          self.ib_client.ibapi.cancelMktData(old_reqId)
          del self.ib_client.symbol_reqId_map[old_symbol]




      self.ib_client.current_symbol = new_symbol
      self.ib_client.subscribe_market_data(new_symbol)


      self.update_chart()
      self.refresh_account_text()


 def refresh_data(self):
      self.after(5000, self.refresh_data)


 def refresh_news(self):
      news = self.ib_client.get_real_time_news()
      self.news_listbox.delete(0, tk.END)
      for item in news:
          time_str = item['datetime'].strftime("%H:%M")
          line = f"{time_str} [{item['source']}] {item['symbol']} - {item['headline']}"
          self.news_listbox.insert(tk.END, line)
      self.after(5000, self.refresh_news)


 def update_chart(self):
      self.ax_price.clear()
      interval_min = self.get_interval_minutes()
      symbol = self.symbol_var.get()
      now = datetime.datetime.now()
      num_points = 20
      dates = [now - datetime.timedelta(minutes=interval_min * x) for x in reversed(range(num_points))]
      ohlc = []
      price = 100.0
      for d in dates:
          open_p = price + random.uniform(-1, 1)
          high_p = open_p + random.uniform(0, 2)
          low_p = open_p - random.uniform(0, 2)
          close_p = low_p + random.uniform(0, high_p - low_p)
          volume = random.randint(1000, 5000)
          ohlc.append((mdates.date2num(d), open_p, high_p, low_p, close_p, volume))
          price = close_p
      candlestick_ohlc(self.ax_price, ohlc, width=0.0005 * interval_min, colorup='g', colordown='r')
      self.ax_price.set_title(f"{symbol} Price Chart ({self.interval_var.get()})")
      self.ax_price.grid(True)
      if interval_min >= 60:
          self.ax_price.xaxis.set_major_formatter(DateFormatter('%m-%d %H:%M'))
      elif interval_min >= 1:
          self.ax_price.xaxis.set_major_formatter(DateFormatter('%H:%M'))
      else:
          self.ax_price.xaxis.set_major_formatter(DateFormatter('%H:%M:%S'))
      self.fig.autofmt_xdate()
      self.canvas.draw()




 def on_interval_change(self, event):
      self.update_chart()


 def get_interval_minutes(self):
      try:
          return int(self.interval_var.get().split()[0])
      except Exception:
          return 5



 def on_ordertype_change(self, event=None):
  pass
 
 
 def simulate_news_feed(self):
  bulletin = self.sample_bulletins[self.news_index % len(self.sample_bulletins)]
  self.news_index += 1
  self.ib_client.on_news(bulletin)
  self.after(15000, self.simulate_news_feed)




 def update_account_summary(self, data):
      tag = data['tag']
      value = data['value']
      currency = data['currency']
      self.account_summary_data[tag] = f"{value} {currency}"
      self.refresh_account_text()



 def refresh_account_text(self):
  symbol = self.symbol_var.get()
  prices = self.ib_client.get_bid_mid_ask(symbol)
  bid = prices['bid']
  mid = prices['mid']
  ask = prices['ask']


  bid_str = f"{bid:.2f}"
  mid_str = f"{mid:.2f}"
  ask_str = f"{ask:.2f}"


  netliq = self.account_summary_data.get('NetLiquidation', 'N/A')


  self.account_text.delete(1.0, tk.END)
  self.account_text.insert(tk.END, f"Net Liquidation: {netliq}\n\n")
  self.account_text.insert(tk.END, f"{symbol} Prices:\n")
  self.account_text.insert(tk.END, f"Bid: {bid_str}\n")
  self.account_text.insert(tk.END, f"Mid: {mid_str}\n")
  self.account_text.insert(tk.END, f"Ask: {ask_str}\n")


 def update_market_data(self, reqId, md):
   self.refresh_account_text()


 def schedule_account_summary_refresh(self):
      self.ib_client.ibapi.request_account_summary()
      self.after(180000, self.schedule_account_summary_refresh)


 def open_news_popup(self, event):
  selection = event.widget.curselection()
  if selection:
      index = selection[0]
      if 0 <= index < len(self.ib_client.news_list):
          news_item = self.ib_client.news_list[index]
          # Create new toplevel window
          popup = tk.Toplevel(self)
          popup.title(news_item['headline'][:60])  # Show first 60 chars in title
          popup.geometry('700x350')
        
          # Headline
          tk.Label(popup, text=news_item['headline'], font=("Arial", 16, "bold"), wraplength=650).pack(anchor="w", padx=20, pady=(20, 5))
          # Metadata
          info = f"Date: {news_item['datetime'].strftime('%Y-%m-%d %H:%M')} | Source: {news_item['source']} | Symbol: {news_item['symbol']}"
          tk.Label(popup, text=info, font=("Arial", 9), fg="gray").pack(anchor="w", padx=20, pady=(0, 10))
          # Long headline/message (could be replaced with article if available)
          tk.Message(popup, text=news_item['headline'], width=650, font=("Arial", 12)).pack(anchor="w", padx=20, pady=5)
          # Open in browser button
          tk.Button(popup, text="Open in Browser", command=lambda: webbrowser.open(news_item['url'])).pack(anchor="e", padx=20, pady=10)



if __name__ == "__main__":
 app = IBDashboard()
 app.mainloop()


