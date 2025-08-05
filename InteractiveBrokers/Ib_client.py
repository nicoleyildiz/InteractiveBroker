from flask import jsonify, request
from ib_insync import *
from threading import Thread
import datetime
import re
from ib_insync import IB


DEFAULT_CLIENT_ID = 20


class IBClient:
   def __init__(self, client_id=DEFAULT_CLIENT_ID):
       self.ib = IB()
       self.client_id = client_id
       self.news_bulletins = []  # store live news items
       self.trade_updates = []  # store trade updates


   def connect(self, host='127.0.0.1', port=7497, client_id=None):
       self.ib.connect(host, port, clientId=client_id or self.client_id)
       self.ib.reqNewsBulletins(allMessages=True)
       self.ib.newsBulletinEvent += self._on_news_bulletin
       Thread(target=self.ib.run, daemon=True).start()


   def disconnect(self):
       self.ib.disconnect()


   def _on_news_bulletin(self, msgId, msgType, message, origExchange):
       now = datetime.datetime.now()
       symbol = None


       match = re.search(r"\[([A-Z]+)\]", message)
       if match:
           symbol = match.group(1)
       else:
           for part in message.split():
               if part.isupper() and len(part) <= 5:
                   symbol = part
                   break


       self.news_bulletins.append({
           'datetime': now.isoformat(),
           'source': origExchange,
           'symbol': symbol or "",
           'headline': message,
           'url': f"https://www.google.com/search?q={message.replace(' ', '+')}"
       })


       if len(self.news_bulletins) > 50:
           self.news_bulletins.pop(0)


   def get_real_time_news(self):
       return self.news_bulletins


   def get_account_summary(self):
       return self.ib.accountSummary()
  
   def get_portfolio(self):
       return self.ib.portfolio()
  
   def place_order(self, symbol, action, quantity, order_type='MKT'):
       contract = Stock(symbol, 'SMART', 'USD')
       self.ib.qualifyContracts(contract)
       order = MarketOrder(action, quantity) if order_type == 'MKT' else LimitOrder(action, quantity, 100)
       trade = self.ib.placeOrder(contract, order)
       return trade
  
   def cancel_order(self, order_id):
       for o in self.ib.openOrders():
           if o.order.orderId == order_id:
               self.ib.cancelOrder(o.order)
           return True
       return False
  
   def subscribe_price(self, symbol):
       contract = Stock(symbol, 'SMART', 'USD')
       self.ib.qualifyContracts(contract)
       ticker = self.ib.reqMktData(contract, '', False, False)
       return ticker
  
   def subscribe_real_time_bars(self, symbol):
       contract = Stock(symbol, 'SMART', 'USD')
       bars = self.ib.reqRealTimeBars(contract, 5, "TRADES", False)
       return bars
  
   def get_news_provider(self):
       return self.ib.newsProviders()
  
   def get_news_headlines(self, provider_code='BRFG', num_articles=10):
       contract = Stock('AAPL', 'SMART', 'USD')
       return self.ib.reqHistoricalNews(
           conId=self.ib.qualifyContracts(contract)[0].conId,
           providerCode=provider_code,
           startDateTime='',
           totalResults=num_articles,
           options=[]
       )
  
   def get_news_article(self, article_id):
       return self.ib.reqNewsArticle(providerCode='BRFG', articleId=article_id)
  
   def get_news(self, symbol):
       provider = request.args.get('provider', 'BRFG')
       headlines = self.ib.get_news_headlines(provider_code=provider)
       return jsonify([{
           'headline': h.headline,
           'articleId': h.articleId,
           'time': h.time
       } for h in headlines])
  
   def get_historical_bars(self, symbol, bar_size_seconds, duration_str='2 D'):
       contract = Stock(symbol, 'SMART', 'USD')
       self.ib.qualifyContracts(contract)
       bar_size_str = f"{bar_size_seconds} secs"
       bars = self.ib.reqHistoricalData(
           contract,
           endDateTime='',
           durationStr=duration_str,
           barSizeSetting=bar_size_str,
           whatToShow='TRADES',
           useRTH=True,
           formatDate=1
       )
       return bars
  
   def get_contract(self, symbol):
       contract = Contract()
       contract.symbol = symbol
       contract.secType = "STK"
       contract.exchange = "SMART"
       contract.currency = "USD"
       return contract


   def subscribe_news(self, callback):
       self.ib.newsBulletinEvent += callback


   def on_news_article(self, msgId, msgType, message, origExchange):
       print(f"News [{msgId}] Type {msgType} from {origExchange}: {message}")


   def req_market_data(self, contract, callback):
       self.ib.qualifyContracts(contract)
       bars = self.ib.reqRealTimeBars(contract, 5, "TRADES", False)


       def update_loop():
           last_time = None
           while True:
               self.ib.sleep(1)
               if bars:
                   bar = bars[-1]
                   if last_time != bar.time:
                       tick = {
                           'time': bar.time,
                           'open': bar.open,
                           'high': bar.high,
                           'low': bar.low,
                           'close': bar.close,
                           'volume': bar.volume
                       }
                       callback(tick)
                       last_time = bar.time


       Thread(target=update_loop, daemon=True).start()

