import sys
import random
import json
import os
from datetime import datetime, timedelta
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.dates import DateFormatter, DayLocator
from mplfinance.original_flavor import candlestick_ohlc
from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
                            QLabel, QLineEdit, QPushButton, QTableWidget, QTableWidgetItem,
                            QComboBox, QTabWidget, QSplitter, QFormLayout, QSpinBox,
                            QDoubleSpinBox, QMessageBox, QHeaderView, QTextEdit, QCheckBox)
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QColor
import requests
from dateutil.relativedelta import relativedelta

class Stock:
    def __init__(self, symbol, name, initial_price, volatility):
        self.symbol = symbol
        self.name = name
        self.price_history = [initial_price]
        self.volatility = volatility
        self.last_update = datetime.now()
        self.volume_history = [0]
        self.ohlc_data = []
        self.indicators = {
            'MA20': [],
            'MA50': [],
            'RSI': []
        }
        self.load_historical_data()
        
    def load_historical_data(self):
        try:
            end_date = datetime.now()
            start_date = end_date - relativedelta(months=3)
            
            url = f"https://query1.finance.yahoo.com/v8/finance/chart/{self.symbol}?interval=1d&period1={int(start_date.timestamp())}&period2={int(end_date.timestamp())}"
            headers = {'User-Agent': 'Mozilla/5.0'}
            response = requests.get(url, headers=headers)
            data = response.json()
            
            timestamps = data['chart']['result'][0]['timestamp']
            closes = data['chart']['result'][0]['indicators']['quote'][0]['close']
            opens = data['chart']['result'][0]['indicators']['quote'][0]['open']
            highs = data['chart']['result'][0]['indicators']['quote'][0]['high']
            lows = data['chart']['result'][0]['indicators']['quote'][0]['low']
            volumes = data['chart']['result'][0]['indicators']['quote'][0]['volume']
            
            self.ohlc_data = []
            for i in range(len(timestamps)):
                date = datetime.fromtimestamp(timestamps[i])
                self.ohlc_data.append([
                    date.date().toordinal(),
                    opens[i], highs[i], lows[i], closes[i],
                    volumes[i]
                ])
                
            if closes:
                self.price_history = closes
        except Exception as e:
            print(f"Fehler beim Laden historischer Daten für {self.symbol}: {str(e)}")
            self.generate_fake_historical_data()
    
    def generate_fake_historical_data(self):
        base_price = random.uniform(50, 500)
        self.ohlc_data = []
        for i in range(60):
            date = (datetime.now() - timedelta(days=60-i)).date()
            open_price = base_price * (1 + random.uniform(-0.02, 0.02))
            close_price = open_price * (1 + random.uniform(-0.03, 0.03))
            high_price = max(open_price, close_price) * (1 + random.uniform(0, 0.02))
            low_price = min(open_price, close_price) * (1 - random.uniform(0, 0.02))
            volume = random.randint(1000000, 5000000)
            
            self.ohlc_data.append([
                date.toordinal(),
                open_price, high_price, low_price, close_price,
                volume
            ])
            base_price = close_price
        
    def update_price(self, volume_impact=0):
        now = datetime.now()
        if (now - self.last_update).seconds >= 1:
            change_percent = self.volatility * (random.random() - 0.5)
            volume_impact_factor = volume_impact * 0.0001
            change_percent += volume_impact_factor
            
            new_price = self.price_history[-1] * (1 + change_percent)
            new_price = max(0.01, new_price)
            self.price_history.append(new_price)
            self.volume_history.append(volume_impact)
            self.last_update = now
            
            if len(self.ohlc_data) > 0:
                last_day = self.ohlc_data[-1]
                current_date = datetime.now().date()
                if current_date.toordinal() == last_day[0]:
                    last_day[2] = max(last_day[2], new_price)
                    last_day[3] = min(last_day[3], new_price)
                    last_day[4] = new_price
                    last_day[5] += volume_impact
                else:
                    self.ohlc_data.append([
                        current_date.toordinal(),
                        new_price, new_price, new_price, new_price,
                        volume_impact
                    ])
            
            self.update_indicators()
            return True
        return False
    
    def update_indicators(self):
        closes = [day[4] for day in self.ohlc_data]
        if not closes:
            return
            
        prices = pd.Series(closes)
        
        if len(prices) >= 20:
            self.indicators['MA20'] = prices.rolling(window=20).mean().tolist()
        if len(prices) >= 50:
            self.indicators['MA50'] = prices.rolling(window=50).mean().tolist()
        if len(prices) >= 14:
            delta = prices.diff()
            gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
            rs = gain / loss
            rsi = 100 - (100 / (1 + rs))
            self.indicators['RSI'] = rsi.tolist()
    
    def get_current_price(self):
        return self.price_history[-1] if self.price_history else 0
    
    def get_ohlc_data(self, days=30):
        return self.ohlc_data[-days:] if self.ohlc_data else []
    
    def get_volume_data(self, days=30):
        return [day[5] for day in self.ohlc_data[-days:]] if self.ohlc_data else []

class StockChart(FigureCanvas):
    def __init__(self, parent=None, width=8, height=6, dpi=100):
        self.fig, (self.ax1, self.ax2) = plt.subplots(2, 1, figsize=(width, height), dpi=dpi, 
                                                     gridspec_kw={'height_ratios': [3, 1]})
        super().__init__(self.fig)
        self.setParent(parent)
        self.ax1.set_ylabel('Preis ($)')
        self.ax2.set_ylabel('Volumen')
        self.ax1.grid(True)
        self.ax2.grid(True)
        
    def plot_candlestick(self, ohlc_data, indicators, title, show_ma20, show_ma50):
        self.ax1.clear()
        self.ax2.clear()
        
        if not ohlc_data:
            return
            
        candlestick_ohlc(self.ax1, ohlc_data, width=0.6, colorup='g', colordown='r')
        
        self.ax1.xaxis.set_major_formatter(DateFormatter('%Y-%m-%d'))
        self.ax1.xaxis.set_major_locator(DayLocator(interval=max(1, len(ohlc_data)//5)))
        
        dates = [day[0] for day in ohlc_data]
        if show_ma20 and 'MA20' in indicators and len(indicators['MA20']) >= len(dates):
            self.ax1.plot(dates, indicators['MA20'][-len(dates):], label='MA20', color='orange', alpha=0.7)
        if show_ma50 and 'MA50' in indicators and len(indicators['MA50']) >= len(dates):
            self.ax1.plot(dates, indicators['MA50'][-len(dates):], label='MA50', color='blue', alpha=0.7)
        
        self.ax1.set_title(title)
        self.ax1.legend(loc='upper left')
        self.ax1.grid(True)
        
        volumes = [day[5] for day in ohlc_data]
        colors = ['g' if ohlc_data[i][4] >= ohlc_data[i][1] else 'r' for i in range(len(ohlc_data))]
        self.ax2.bar(dates, volumes, color=colors, width=0.6)
        self.ax2.xaxis.set_major_formatter(DateFormatter('%Y-%m-%d'))
        self.ax2.xaxis.set_major_locator(DayLocator(interval=max(1, len(ohlc_data)//5)))
        
        self.fig.autofmt_xdate()
        self.draw()

class Portfolio:
    def __init__(self, initial_cash=100000.0):
        self.cash = initial_cash
        self.holdings = {}
        self.transaction_history = []
        self.pending_orders = []
        
    def place_order(self, order_type, symbol, shares, price, order_kind='market'):
        order = {
            'type': order_type,
            'symbol': symbol,
            'shares': shares,
            'price': price,
            'kind': order_kind,
            'time': datetime.now(),
            'filled': 0,
            'status': 'pending'
        }
        self.pending_orders.append(order)
        return order
        
    def execute_market_order(self, order):
        symbol = order['symbol']
        shares = order['shares']
        price = order['price']
        
        if order['type'] == 'buy':
            return self.buy_stock(symbol, shares, price)
        else:
            return self.sell_stock(symbol, shares, price)
    
    def check_limit_orders(self, stock_prices):
        for order in self.pending_orders[:]:
            if order['kind'] == 'limit' and order['status'] == 'pending':
                current_price = stock_prices[order['symbol']]
                if order['type'] == 'buy' and current_price <= order['price']:
                    self.execute_market_order(order)
                    order['status'] = 'filled'
                elif order['type'] == 'sell' and current_price >= order['price']:
                    self.execute_market_order(order)
                    order['status'] = 'filled'
    
    def buy_stock(self, symbol, shares, price):
        total_cost = shares * price
        if total_cost > self.cash:
            return False, "Nicht genug Geld für diesen Kauf"
        
        self.cash -= total_cost
        if symbol in self.holdings:
            self.holdings[symbol] += shares
        else:
            self.holdings[symbol] = shares
            
        self.transaction_history.append({
            'type': 'buy',
            'symbol': symbol,
            'shares': shares,
            'price': price,
            'total': total_cost,
            'time': datetime.now(),
            'order_type': 'market'
        })
        return True, "Kauf erfolgreich"
    
    def sell_stock(self, symbol, shares, price):
        if symbol not in self.holdings or self.holdings[symbol] < shares:
            return False, "Nicht genug Anteile zum Verkauf"
        
        total_value = shares * price
        self.cash += total_value
        self.holdings[symbol] -= shares
        
        if self.holdings[symbol] == 0:
            del self.holdings[symbol]
            
        self.transaction_history.append({
            'type': 'sell',
            'symbol': symbol,
            'shares': shares,
            'price': price,
            'total': total_value,
            'time': datetime.now(),
            'order_type': 'market'
        })
        return True, "Verkauf erfolgreich"
    
    def get_portfolio_value(self, stock_prices):
        stock_value = sum(shares * stock_prices.get(symbol, 0) 
                       for symbol, shares in self.holdings.items())
        return self.cash + stock_value
    
    def get_holdings_table_data(self, stock_prices):
        data = []
        for symbol, shares in self.holdings.items():
            current_price = stock_prices.get(symbol, 0)
            value = shares * current_price
            change = (current_price - self.get_average_buy_price(symbol)) / self.get_average_buy_price(symbol) * 100
            data.append([symbol, shares, current_price, value, f"{change:.2f}%"])
        return data
    
    def get_average_buy_price(self, symbol):
        buys = [t for t in self.transaction_history 
                if t['type'] == 'buy' and t['symbol'] == symbol]
        total_shares = sum(t['shares'] for t in buys)
        total_cost = sum(t['total'] for t in buys)
        return total_cost / total_shares if total_shares > 0 else 0
    
    def save_to_file(self, filename):
        data = {
            'cash': self.cash,
            'holdings': self.holdings,
            'transaction_history': [
                {**t, 'time': t['time'].isoformat()} 
                for t in self.transaction_history
            ],
            'pending_orders': [
                {**o, 'time': o['time'].isoformat()} 
                for o in self.pending_orders
            ]
        }
        with open(filename, 'w') as f:
            json.dump(data, f)
    
    def load_from_file(self, filename):
        if not os.path.exists(filename):
            return
            
        with open(filename, 'r') as f:
            data = json.load(f)
        
        self.cash = data['cash']
        self.holdings = data['holdings']
        self.transaction_history = [
            {**t, 'time': datetime.fromisoformat(t['time'])} 
            for t in data['transaction_history']
        ]
        self.pending_orders = [
            {**o, 'time': datetime.fromisoformat(o['time'])} 
            for o in data.get('pending_orders', [])
        ]

class StockAPI:
    @staticmethod
    def get_current_price(symbol):
        try:
            url = f'https://query1.finance.yahoo.com/v8/finance/chart/{symbol}'
            headers = {'User-Agent': 'Mozilla/5.0'}
            response = requests.get(url, headers=headers, timeout=5)
            data = response.json()
            return data['chart']['result'][0]['meta']['regularMarketPrice']
        except Exception as e:
            print(f"Fehler beim Abrufen des Kurses für {symbol}: {str(e)}")
            return None

class TradingWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Professionelle Aktienhandelsplattform")
        self.setGeometry(100, 100, 1400, 900)
        
        self.stocks = self.initialize_stocks()
        self.portfolio = Portfolio()
        self.load_portfolio()
        self.current_stock = 'AAPL'
        
        self.show_ma20 = True
        self.show_ma50 = True
        self.show_rsi = True
        
        self.use_api = True
        self.api_fetch_interval = 300
        
        self.init_ui()
        self.setup_timer()
        self.fetch_initial_prices()
        
    def initialize_stocks(self):
        stock_definitions = [
            ('AAPL', 'Apple Inc.', 0.02),
            ('MSFT', 'Microsoft Corp.', 0.015),
            ('GOOGL', 'Alphabet Inc.', 0.025),
            ('AMZN', 'Amazon.com Inc.', 0.03),
            ('TSLA', 'Tesla Inc.', 0.04),
            ('META', 'Meta Platforms Inc.', 0.035),
            ('NVDA', 'NVIDIA Corp.', 0.045),
            ('JPM', 'JPMorgan Chase & Co.', 0.025),
            ('V', 'Visa Inc.', 0.02),
            ('WMT', 'Walmart Inc.', 0.015)
        ]
        
        stocks = {}
        for symbol, name, volatility in stock_definitions:
            initial_price = StockAPI.get_current_price(symbol) or random.uniform(50, 500)
            stocks[symbol] = Stock(symbol, name, initial_price, volatility)
        
        return stocks
        
    def fetch_initial_prices(self):
        if not self.use_api:
            return
            
        for symbol, stock in self.stocks.items():
            real_price = StockAPI.get_current_price(symbol)
            if real_price is not None:
                current_price = stock.get_current_price()
                adjustment_factor = 0.1
                new_price = current_price * (1 - adjustment_factor) + real_price * adjustment_factor
                stock.price_history[-1] = new_price
                
        QTimer.singleShot(self.api_fetch_interval * 1000, self.fetch_initial_prices)
        
    def init_ui(self):
        main_widget = QWidget()
        main_layout = QHBoxLayout()
        
        left_panel = QVBoxLayout()
        
        self.stock_combo = QComboBox()
        for symbol in self.stocks:
            self.stock_combo.addItem(f"{symbol} - {self.stocks[symbol].name}", symbol)
        self.stock_combo.currentIndexChanged.connect(self.on_stock_changed)
        left_panel.addWidget(self.stock_combo)
        
        self.stock_info = QLabel()
        left_panel.addWidget(self.stock_info)
        
        indicator_group = QWidget()
        indicator_layout = QHBoxLayout()
        
        self.ma20_check = QCheckBox("MA20 anzeigen")
        self.ma20_check.setChecked(True)
        self.ma20_check.stateChanged.connect(self.toggle_ma20)
        
        self.ma50_check = QCheckBox("MA50 anzeigen")
        self.ma50_check.setChecked(True)
        self.ma50_check.stateChanged.connect(self.toggle_ma50)
        
        self.rsi_check = QCheckBox("RSI anzeigen")
        self.rsi_check.setChecked(True)
        self.rsi_check.stateChanged.connect(self.toggle_rsi)
        
        indicator_layout.addWidget(self.ma20_check)
        indicator_layout.addWidget(self.ma50_check)
        indicator_layout.addWidget(self.rsi_check)
        indicator_group.setLayout(indicator_layout)
        left_panel.addWidget(indicator_group)
        
        self.chart = StockChart(self)
        left_panel.addWidget(self.chart)
        
        trade_group = QWidget()
        trade_layout = QFormLayout()
        
        self.trade_action = QComboBox()
        self.trade_action.addItems(["Kaufen", "Verkaufen"])
        trade_layout.addRow("Aktion:", self.trade_action)
        
        self.order_type = QComboBox()
        self.order_type.addItems(["Market Order", "Limit Order"])
        trade_layout.addRow("Order Typ:", self.order_type)
        
        self.shares_input = QSpinBox()
        self.shares_input.setMinimum(1)
        self.shares_input.setMaximum(10000)
        trade_layout.addRow("Anzahl:", self.shares_input)
        
        self.price_input = QDoubleSpinBox()
        self.price_input.setMinimum(0.01)
        self.price_input.setMaximum(100000)
        self.price_input.setDecimals(2)
        trade_layout.addRow("Preis:", self.price_input)
        
        self.execute_button = QPushButton("Order platzieren")
        self.execute_button.clicked.connect(self.execute_trade)
        trade_layout.addRow(self.execute_button)
        
        self.news_display = QTextEdit()
        self.news_display.setReadOnly(True)
        self.news_display.setMaximumHeight(100)
        left_panel.addWidget(self.news_display)
        
        trade_group.setLayout(trade_layout)
        left_panel.addWidget(trade_group)
        
        right_panel = QTabWidget()
        
        portfolio_tab = QWidget()
        portfolio_layout = QVBoxLayout()
        
        self.portfolio_value = QLabel()
        portfolio_layout.addWidget(self.portfolio_value)
        
        self.cash_label = QLabel()
        portfolio_layout.addWidget(self.cash_label)
        
        self.holdings_table = QTableWidget()
        self.holdings_table.setColumnCount(5)
        self.holdings_table.setHorizontalHeaderLabels(["Symbol", "Anteile", "Preis", "Wert", "Änderung"])
        self.holdings_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        portfolio_layout.addWidget(self.holdings_table)
        
        portfolio_tab.setLayout(portfolio_layout)
        right_panel.addTab(portfolio_tab, "Portfolio")
        
        transactions_tab = QWidget()
        transactions_layout = QVBoxLayout()
        
        self.transactions_table = QTableWidget()
        self.transactions_table.setColumnCount(7)
        self.transactions_table.setHorizontalHeaderLabels(["Zeit", "Typ", "Symbol", "Anteile", "Preis", "Total", "Order Typ"])
        self.transactions_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        transactions_layout.addWidget(self.transactions_table)
        
        transactions_tab.setLayout(transactions_layout)
        right_panel.addTab(transactions_tab, "Transaktionen")
        
        orders_tab = QWidget()
        orders_layout = QVBoxLayout()
        
        self.orders_table = QTableWidget()
        self.orders_table.setColumnCount(7)
        self.orders_table.setHorizontalHeaderLabels(["Zeit", "Typ", "Symbol", "Anteile", "Preis", "Status", "Order Typ"])
        self.orders_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        orders_layout.addWidget(self.orders_table)
        
        cancel_button = QPushButton("Ausgewählte Order stornieren")
        cancel_button.clicked.connect(self.cancel_order)
        orders_layout.addWidget(cancel_button)
        
        orders_tab.setLayout(orders_layout)
        right_panel.addTab(orders_tab, "Offene Orders")
        
        analysis_tab = QWidget()
        analysis_layout = QVBoxLayout()
        
        self.analysis_text = QTextEdit()
        self.analysis_text.setReadOnly(True)
        analysis_layout.addWidget(self.analysis_text)
        
        update_analysis_button = QPushButton("Analyse aktualisieren")
        update_analysis_button.clicked.connect(self.update_analysis)
        analysis_layout.addWidget(update_analysis_button)
        
        analysis_tab.setLayout(analysis_layout)
        right_panel.addTab(analysis_tab, "Technische Analyse")
        
        settings_tab = QWidget()
        settings_layout = QFormLayout()
        
        self.api_check = QCheckBox("Echtzeit-Kursdaten von Yahoo Finance verwenden")
        self.api_check.setChecked(True)
        self.api_check.stateChanged.connect(self.toggle_api)
        settings_layout.addRow(self.api_check)
        
        self.api_interval_input = QSpinBox()
        self.api_interval_input.setMinimum(1)
        self.api_interval_input.setMaximum(60)
        self.api_interval_input.setValue(5)
        self.api_interval_input.setSuffix(" Minuten")
        self.api_interval_input.valueChanged.connect(self.update_api_interval)
        settings_layout.addRow("API-Abfrageintervall:", self.api_interval_input)
        
        self.volatility_slider = QDoubleSpinBox()
        self.volatility_slider.setMinimum(0.01)
        self.volatility_slider.setMaximum(0.5)
        self.volatility_slider.setSingleStep(0.01)
        self.volatility_slider.setValue(0.02)
        settings_layout.addRow("Marktvolatilität:", self.volatility_slider)
        
        self.market_impact_slider = QDoubleSpinBox()
        self.market_impact_slider.setMinimum(0.0)
        self.market_impact_slider.setMaximum(1.0)
        self.market_impact_slider.setSingleStep(0.1)
        self.market_impact_slider.setValue(0.5)
        settings_layout.addRow("Handelsvolumen-Einfluss:", self.market_impact_slider)
        
        self.reset_button = QPushButton("Portfolio zurücksetzen")
        self.reset_button.clicked.connect(self.reset_portfolio)
        settings_layout.addRow(self.reset_button)
        
        self.save_button = QPushButton("Daten speichern")
        self.save_button.clicked.connect(self.save_data)
        settings_layout.addRow(self.save_button)
        
        settings_tab.setLayout(settings_layout)
        right_panel.addTab(settings_tab, "Einstellungen")
        
        splitter = QSplitter(Qt.Horizontal)
        left_widget = QWidget()
        left_widget.setLayout(left_panel)
        splitter.addWidget(left_widget)
        splitter.addWidget(right_panel)
        splitter.setSizes([800, 600])
        
        main_layout.addWidget(splitter)
        main_widget.setLayout(main_layout)
        self.setCentralWidget(main_widget)
        
        self.update_display()
        self.generate_news()
        
    def setup_timer(self):
        self.timer = QTimer()
        self.timer.timeout.connect(self.update_prices)
        self.timer.start(1000)
        
    def update_prices(self):
        stock_prices = {symbol: stock.get_current_price() for symbol, stock in self.stocks.items()}
        self.portfolio.check_limit_orders(stock_prices)
        
        for stock in self.stocks.values():
            if stock.symbol not in [o['symbol'] for o in self.portfolio.pending_orders if o['status'] == 'pending']:
                if stock.update_price():
                    self.update_display()
        
    def on_stock_changed(self, index):
        self.current_stock = self.stock_combo.itemData(index)
        self.update_display()
        
    def update_display(self):
        stock = self.stocks[self.current_stock]
        self.stock_info.setText(
            f"<b>{stock.name} ({stock.symbol})</b><br>"
            f"Aktueller Preis: ${stock.get_current_price():.2f}<br>"
            f"Tagesvolatilität: {stock.volatility*100:.1f}%<br>"
            f"Heutiges Volumen: {stock.volume_history[-1]:,}"
        )
        
        ohlc_data = stock.get_ohlc_data(30)
        self.chart.plot_candlestick(ohlc_data, stock.indicators, f"{stock.symbol} Candlestick Chart", 
                                   self.show_ma20, self.show_ma50)
        
        stock_prices = {symbol: s.get_current_price() for symbol, s in self.stocks.items()}
        portfolio_value = self.portfolio.get_portfolio_value(stock_prices)
        self.portfolio_value.setText(
            f"<b>Portfoliowert:</b> ${portfolio_value:,.2f}"
        )
        self.cash_label.setText(
            f"<b>Verfügbares Guthaben:</b> ${self.portfolio.cash:,.2f}"
        )
        
        holdings_data = self.portfolio.get_holdings_table_data(stock_prices)
        self.holdings_table.setRowCount(len(holdings_data))
        for row, data in enumerate(holdings_data):
            for col, value in enumerate(data):
                item = QTableWidgetItem(str(value))
                if col == 4:
                    change = float(value.strip('%'))
                    if change > 0:
                        item.setForeground(QColor(0, 200, 0))
                    elif change < 0:
                        item.setForeground(QColor(200, 0, 0))
                self.holdings_table.setItem(row, col, item)
        
        transactions = self.portfolio.transaction_history[-20:]
        self.transactions_table.setRowCount(len(transactions))
        for row, trans in enumerate(reversed(transactions)):
            self.transactions_table.setItem(row, 0, QTableWidgetItem(trans['time'].strftime("%H:%M:%S")))
            self.transactions_table.setItem(row, 1, QTableWidgetItem(trans['type'].upper()))
            self.transactions_table.setItem(row, 2, QTableWidgetItem(trans['symbol']))
            self.transactions_table.setItem(row, 3, QTableWidgetItem(str(trans['shares'])))
            self.transactions_table.setItem(row, 4, QTableWidgetItem(f"${trans['price']:.2f}"))
            self.transactions_table.setItem(row, 5, QTableWidgetItem(f"${trans['total']:.2f}"))
            self.transactions_table.setItem(row, 6, QTableWidgetItem(trans.get('order_type', 'market')))
            
            for col in range(7):
                if trans['type'] == 'buy':
                    self.transactions_table.item(row, col).setForeground(QColor(0, 150, 0))
                else:
                    self.transactions_table.item(row, col).setForeground(QColor(150, 0, 0))
        
        self.orders_table.setRowCount(len(self.portfolio.pending_orders))
        for row, order in enumerate(self.portfolio.pending_orders):
            self.orders_table.setItem(row, 0, QTableWidgetItem(order['time'].strftime("%H:%M:%S")))
            self.orders_table.setItem(row, 1, QTableWidgetItem(order['type'].upper()))
            self.orders_table.setItem(row, 2, QTableWidgetItem(order['symbol']))
            self.orders_table.setItem(row, 3, QTableWidgetItem(str(order['shares'])))
            self.orders_table.setItem(row, 4, QTableWidgetItem(f"${order['price']:.2f}"))
            self.orders_table.setItem(row, 5, QTableWidgetItem(order['status']))
            self.orders_table.setItem(row, 6, QTableWidgetItem(order['kind']))
            
            for col in range(7):
                if order['type'] == 'buy':
                    self.orders_table.item(row, col).setForeground(QColor(0, 100, 0))
                else:
                    self.orders_table.item(row, col).setForeground(QColor(100, 0, 0))
        
        self.price_input.setValue(stock.get_current_price())
        
    def execute_trade(self):
        action = self.trade_action.currentText().lower()
        order_kind = 'market' if self.order_type.currentText() == 'Market Order' else 'limit'
        shares = self.shares_input.value()
        price = self.price_input.value()
        symbol = self.current_stock
        
        if order_kind == 'market':
            market_impact_factor = self.market_impact_slider.value()
            volume_impact = shares * market_impact_factor
            self.stocks[symbol].update_price(volume_impact)
            
            if action == 'kaufen':
                success, message = self.portfolio.buy_stock(symbol, shares, price)
            else:
                success, message = self.portfolio.sell_stock(symbol, shares, price)
                
            if success:
                QMessageBox.information(self, "Erfolg", message)
            else:
                QMessageBox.warning(self, "Fehler", message)
        else:
            order = self.portfolio.place_order(action, symbol, shares, price, 'limit')
            QMessageBox.information(
                self, 
                "Limit Order platziert", 
                f"Limit {order['type']} Order für {shares} {symbol} zu ${price:.2f} platziert"
            )
        
        self.update_display()
        
    def cancel_order(self):
        selected_row = self.orders_table.currentRow()
        if 0 <= selected_row < len(self.portfolio.pending_orders):
            order = self.portfolio.pending_orders[selected_row]
            if order['status'] == 'pending':
                self.portfolio.pending_orders.pop(selected_row)
                QMessageBox.information(self, "Erfolg", "Order wurde storniert")
                self.update_display()
            else:
                QMessageBox.warning(self, "Fehler", "Diese Order kann nicht storniert werden")
        else:
            QMessageBox.warning(self, "Fehler", "Keine Order ausgewählt")
            
    def update_analysis(self):
        stock = self.stocks[self.current_stock]
        analysis = f"Technische Analyse für {stock.symbol}:\n\n"
        
        prices = [day[4] for day in stock.ohlc_data]  # Close prices
        if len(prices) >= 2:
            change = (prices[-1] - prices[-2]) / prices[-2] * 100
            analysis += f"Aktuelle Preisänderung: {change:.2f}%\n"
        
        if len(stock.indicators['MA20']) >= 1 and len(stock.indicators['MA50']) >= 1:
            ma20 = stock.indicators['MA20'][-1]
            ma50 = stock.indicators['MA50'][-1]
            current_price = stock.get_current_price()
            
            analysis += f"\nMoving Averages:\n"
            analysis += f"MA20: {ma20:.2f} ({'über' if current_price > ma20 else 'unter'} Preis)\n"
            analysis += f"MA50: {ma50:.2f} ({'über' if current_price > ma50 else 'unter'} Preis)\n"
            
            if ma20 > ma50 and current_price > ma20:
                analysis += "Bullish Trend (MA20 > MA50 und Preis > MA20)\n"
            elif ma20 < ma50 and current_price < ma20:
                analysis += "Bearish Trend (MA20 < MA50 und Preis < MA20)\n"
        
        if len(stock.indicators['RSI']) >= 1:
            rsi = stock.indicators['RSI'][-1]
            analysis += f"\nRSI: {rsi:.2f} - "
            if rsi > 70:
                analysis += "Überkauft (mögliche Verkaufschance)"
            elif rsi < 30:
                analysis += "Überverkauft (mögliche Kaufchance)"
            else:
                analysis += "Neutraler Bereich"
        
        self.analysis_text.setPlainText(analysis)
        
    def generate_news(self):
        news_items = [
            "Apple kündigt neues iPhone Modell an - Aktie steigt",
            "Microsoft gewinnt großen Cloud-Vertrag",
            "Amazon expandiert in neuen Markt",
            "Tesla verfehlt Lieferziele - Aktie fällt",
            "Meta kündigt neue VR-Plattform an",
            "Tech-Sektor zeigt gemischte Ergebnisse heute",
            "Wirtschaftsdaten besser als erwartet - Märkte reagieren positiv",
            "Zentralbank signalisiert mögliche Zinserhöhungen"
        ]
        
        selected_news = random.sample(news_items, 3)
        news_text = "Marktnachrichten:\n\n" + "\n\n".join(selected_news)
        self.news_display.setPlainText(news_text)
        
        QTimer.singleShot(random.randint(60000, 300000), self.generate_news)
        
    def reset_portfolio(self):
        reply = QMessageBox.question(
            self, 'Bestätigung', 
            'Möchten Sie wirklich Ihr Portfolio zurücksetzen? Alle Daten gehen verloren.',
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            self.portfolio = Portfolio()
            self.update_display()
            
    def save_data(self):
        self.portfolio.save_to_file('portfolio.json')
        
        stock_data = {
            symbol: {
                'name': stock.name,
                'volatility': stock.volatility,
                'price_history': stock.price_history,
                'volume_history': stock.volume_history,
                'ohlc_data': stock.ohlc_data
            }
            for symbol, stock in self.stocks.items()
        }
        with open('stocks.json', 'w') as f:
            json.dump(stock_data, f)
            
        QMessageBox.information(self, "Erfolg", "Daten erfolgreich gespeichert")
    
    def load_portfolio(self):
        if os.path.exists('portfolio.json'):
            try:
                self.portfolio.load_from_file('portfolio.json')
            except:
                pass
    
    def toggle_ma20(self, state):
        self.show_ma20 = state == Qt.Checked
        self.update_display()
        
    def toggle_ma50(self, state):
        self.show_ma50 = state == Qt.Checked
        self.update_display()
        
    def toggle_rsi(self, state):
        self.show_rsi = state == Qt.Checked
        self.update_display()
        
    def toggle_api(self, state):
        self.use_api = state == Qt.Checked
        if self.use_api:
            self.fetch_initial_prices()
            
    def update_api_interval(self, minutes):
        self.api_fetch_interval = minutes * 60

    def closeEvent(self, event):
        self.timer.stop()
        self.save_data()
        event.accept()

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = TradingWindow()
    window.show()
    sys.exit(app.exec_())
