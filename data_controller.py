import argparse
import collections
import csv
import contextlib
import dataclasses
import json
import sqlite3
import os
from datetime import datetime

from helpers import OptionalFloat, OptionalBalance
import symbol_values


import logging

logger = logging.getLogger()


class UnknownSymbolException(Exception):
  pass


class SymbolExistsException(Exception):
  pass


class DataController(object):
  def __init__(self, db_path):
    self.db_path = db_path
    self.conn = None
    self.num_conns = 0
    self.setup()

  @contextlib.contextmanager
  def connect(self) -> sqlite3.Cursor:
    if not self.conn:
      self.conn = sqlite3.connect(self.db_path)
    self.num_conns += 1
    yield self.conn.cursor()
    self.num_conns -= 1
    if self.num_conns == 0:
      logger.info('Commiting...')
      self.conn.commit()
      self.conn.close()
      self.conn = None

  def setup(self):
    if os.path.isfile(self.db_path):
      return
    print('Creating db...')
    with self.connect() as c:
      c.execute("""
        CREATE TABLE accounts
        (id INTEGER PRIMARY KEY, 
         category INTEGER,
         name text,
         currency text)""")
      c.execute("""
        CREATE TABLE transactions
        (id INTEGER PRIMARY KEY, 
        accountID INTEGER,
        date text,
        info text,
        value real,
        balance_after real)""")
      c.execute("""
        CREATE TABLE stocks
        (id INTEGER PRIMARY KEY,
         symbol text,
         currency text)
        """)
      c.execute("""
        CREATE TABLE shareTransactions
        (id INTEGER PRIMARY KEY,
        symbolID INTEGER,
        date text,
        quantity int,   -- How many bought/sold
        proceeds real,   
        quantity_after int,
        proceeds_after real)
        """)

  def add_stock_symbol(self, symbol, currency):
    with self.connect() as c:
      existing = set(c.execute('SELECT * FROM stocks WHERE symbol=?', (symbol,)))
      if existing:
        raise SymbolExistsException(f'Symbol exists: {symbol}')
      c.execute('INSERT INTO stocks (symbol, currency) VALUES (?, ?)',
                (symbol, currency))

  def add_share_transaction(self, symbol, quantity, proceeds, date=None):
    with self.connect() as c:
      if not date:
        date = datetime.now().strftime('%Y-%m-%d, %H:%M:%S')
      quantity_so_far, proceeds_so_far, symbolID = self._fetch_symbol(symbol)
      quantity_after = quantity_so_far + quantity
      proceeds_after = proceeds_so_far + proceeds
      c.execute('INSERT INTO shareTransactions ('
                'symbolID, date, quantity, proceeds, quantity_after, proceeds_after) '
                'VALUES (?, ?, ?, ?, ?, ?)',
                (symbolID, date, quantity, proceeds,
                 quantity_after, proceeds_after))

  def get_all_symbol_overviews(self):
    with self.connect() as c:
      return [self.get_symbol_overview(res[0])
              for res in c.execute('SELECT symbol FROM stocks')]

  def get_symbol_overview(self, symbol) -> 'SymbolOverview':
    quantity_so_far, proceeds_so_far, _ = self._fetch_symbol(symbol)
    return SymbolOverview(
      self, symbol, quantity_so_far, proceeds_so_far)

  def get_currency_of_symbol(self, symbol):
    with self.connect() as c:
      c.execute('SELECT currency FROM stocks WHERE symbol=?', (symbol,))
      return c.fetchone()[0]

  def _fetch_symbol(self, symbol):
    with self.connect() as c:
      c.execute('SELECT id FROM stocks WHERE symbol=?', (symbol,))
      symbolID = c.fetchone()
      if symbolID is None:
        raise UnknownSymbolException(symbol)
      symbolID, = symbolID  # Unpack 1-tuple
      c.execute('SELECT quantity_after, proceeds_after FROM shareTransactions '
                'WHERE symbolID=? '
                'ORDER BY id DESC LIMIT 1', (symbolID,))
      quantity_after, proceeds_after = c.fetchone() or (0, 0.)
      return quantity_after, proceeds_after, symbolID

  def create_account(self, name, currency, category=0):
    with self.connect() as c:
      existing = set(c.execute('SELECT * FROM accounts WHERE name=?', (name,)))
      if existing:
        raise ValueError(f'Account with name exists: {name}')
      c.execute('INSERT INTO accounts (name, currency, category) VALUES (?, ?, ?)',
                (name, currency, category))

  def get_all_accounts(self, category=None):
    with self.connect() as c:
      if category is None:
        results = c.execute('SELECT name, currency FROM accounts')
      else:
        results = c.execute('SELECT name, currency FROM accounts '
                            'WHERE category=?', (category,))
      return [Account(self, name, currency) for name, currency in results]

  def get_account_transactions(self, account_name):
    with self.connect() as c:
      c.execute('SELECT id, currency FROM accounts WHERE name=?', (account_name,))
      accountID, currency = c.fetchone()
      return [AccountTransaction(date, info, OptionalBalance(value, currency))
              for date, info, value
              in c.execute('SELECT date, info, value FROM transactions '
                           'WHERE accountID=?', (accountID,))]

  def add_transaction(self,
                      account_name: str,
                      value: float,
                      date: str = None,
                      info: str = ''):
    if not date:
      # TODO: Validate!
      date = datetime.now().strftime('%Y-%m-%d, %H:%M:%S')
    with self.connect() as c:
      last_balance, accountID = self._get_last_balance(account_name)
      new_balance = last_balance + value
      c.execute('INSERT INTO transactions '
                '(accountID, date, info, value, balance_after) '
                'VALUES '
                '(?, ?, ?, ?, ?)',
                (accountID, date, info, value, new_balance))
      return new_balance

  def get_balance(self, account_name: str, index=-1) -> float:
    with self.connect() as c:
      last_balance, _ = self._get_last_balance(account_name, index)
      return last_balance

  def _get_last_balance(self, account_name, index=-1):
    if index >= 0:
      raise NotImplementedError(index)
    with self.connect() as c:
      c.execute('SELECT id FROM accounts WHERE name=?', (account_name,))
      accountID, = c.fetchone()
      c.execute(
        'SELECT balance_after FROM transactions '
        'WHERE accountID=? '
        f'ORDER BY id DESC LIMIT {abs(index)} ',
        (accountID,))
      res = c.fetchall()
      if not res:
        last_balance = 0.
      else:
        last_balance, = res[-1]
      return last_balance, accountID


@dataclasses.dataclass
class Account:
  dc: DataController
  name: str
  currency: str
  _balance: float = None
  _last_balance: float = None

  def get_diff_to_last(self) -> OptionalBalance:
    return OptionalBalance(
      self.get_balance() - _lazy(self, '_last_balance',
                                 lambda: self.dc.get_balance(self.name, -2)),
      self.currency)

  def get_balance(self) -> OptionalBalance:
    return OptionalBalance(
      _lazy(self, '_balance', lambda: self.dc.get_balance(self.name)),
      self.currency)


@dataclasses.dataclass
class AccountTransaction:
  date: str
  info: str
  value: OptionalBalance


def _lazy(obj, field_name, fn):
  if not getattr(obj, field_name):
    setattr(obj, field_name, fn())
  return getattr(obj, field_name)


@dataclasses.dataclass
class SymbolOverview:
  dc: DataController
  symbol: str
  quantity: int
  proceeds_so_far: float
  _currency: str = None

  def __str__(self):
    return f'Symbol({self.symbol} / quant={self.quantity} / ' \
           f'proceeds={self.proceeds_so_far:,.2f} / ' \
           f'gain={self.get_current_total_gain():,.2f})'

  def get_current_total_gain(self, currency=None) -> OptionalBalance:
    return self.get_current_total_value(currency) + self.proceeds_so_far

  # TODO: Optionals?
  def get_current_total_value(self, currency=None) -> OptionalBalance:
    t = symbol_values.Ticker.make(self.symbol)
    current_value = OptionalBalance(t.get_current_value(), self.get_currency())
    value_in_native_currency = current_value * self.quantity
    if currency:
      return symbol_values.convert_currency(value_in_native_currency,
                                            self.get_currency(), currency)
    return value_in_native_currency

  def get_currency(self) -> str:
    return _lazy(self, '_currency',
                 lambda: self.dc.get_currency_of_symbol(self.symbol))


def create_db_from_files(accounts_json_p, stocks_ibkr_csv_p):
  out_p = accounts_json_p.replace('.json', '.db')

  if os.path.isfile(out_p):
    os.rename(out_p, out_p + '.bak')

  dc = DataController(out_p)
  _parse_accounts_json_into_db(accounts_json_p, dc)
  _parse_stocks_ibkr_csv(stocks_ibkr_csv_p, dc)



def _parse_accounts_json_into_db(accounts_json_p, dc: DataController):
  with open(accounts_json_p, 'r') as f:
    accounts = json.load(f)
    # TODO: Should be more granular.
    currency = accounts["currency"]
    with dc.connect():
      for account_name, balance in accounts["last"].items():
        dc.create_account(account_name, currency)
        dc.add_transaction(account_name, balance,
                           info='Initial')
      for account_name, balance in accounts["now"].items():
        last_balance = dc.get_balance(account_name)
        dc.add_transaction(account_name, balance - last_balance,
                           info='Last Update')
      # Non liquits
      for cat1_acc, transactions in accounts["cat1"].items():
        dc.create_account(cat1_acc, currency, category=1)
        for info, date, value in transactions:
          dc.add_transaction('Non-Liquids', value, date=date, info=info)



_StockTrade = collections.namedtuple(
  '_StockTrade',
  ['symbol', 'currency', 'date', 'quantity', 'proceeds'])


class _StockTradeMaker(object):
  def __init__(self, header_row, symbols_yf):
    """
    :param header_row:
    :param symbols_yf:  Maps symbol names to YF names (e.g. 'IMAE': 'IMAE.AS')
    """
    self.mapping = {key: i for i, key in enumerate(header_row)}
    self.symbols_yf = symbols_yf

  def make(self, trade_row) -> _StockTrade:
    symbol = trade_row[self['Symbol']]
    return _StockTrade(symbol=self.symbols_yf.get(symbol, symbol),
                       currency=trade_row[self['Currency']],
                       date=trade_row[self['Date/Time']],
                       quantity=float(trade_row[self['Quantity']]),
                       proceeds=float(trade_row[self['Proceeds']]))

  def __getitem__(self, item):
    return self.mapping[item]


_EXCH_TO_YF = {
  'EBS': 'SW',
  'AEB': 'AS',
  'LSEETF': 'L',
}

_AMERICAN_EXCH = {'ARCA', 'NASDAQ'}


def _get_stock_yfinance_names(stocks_ibkr_csv_p):
  """Convert IBKR short names to YF names and check if actually valid."""
  with open(stocks_ibkr_csv_p, 'r') as f:
    r = csv.reader(f)
    symbol_col = exch_col = None
    symbols_yf = {}
    for row in r:
      if not row or row[0] != 'Financial Instrument Information':
        continue
      if row[1] == 'Header':
        symbol_col = row.index('Symbol')
        exch_col = row.index('Listing Exch')
        continue
      symbol, exch = row[symbol_col], row[exch_col]
      if exch in _EXCH_TO_YF:
        symbol_yf = symbol + '.' + _EXCH_TO_YF[exch]
      elif exch in _AMERICAN_EXCH:
        symbol_yf = symbol
      else:
        raise ValueError(f'Unknown: {symbol} / {exch}')
      print(f'{symbol} -> {symbol_yf}')
      symbols_yf[symbol] = symbol_yf
  if not symbols_yf:
    raise ValueError('No symbols found!')
  symbol_values.check_symbols(symbols_yf.values())
  return symbols_yf



def _parse_stocks_ibkr_csv(stocks_ibkr_csv_p, dc: DataController):
  # First get the stocks and exchanges.
  symbols_yf = _get_stock_yfinance_names(stocks_ibkr_csv_p)
  # Now parse our trades.
  print('-' * 20, 'Parsing trades...', sep='\n')
  with open(stocks_ibkr_csv_p, 'r') as f, dc.connect():
    r = csv.reader(f)
    symbols = set()
    stm = None
    for row in r:
      if not row or row[0] != 'Trades':
        continue
      if row[1] == 'Header':
        if stm is not None:  # Second Header for Forex trades
          break
        stm = _StockTradeMaker(row, symbols_yf)
        continue
      if row[1] != 'Data':
        continue
      st: _StockTrade = stm.make(row)
      # Add symbols to db. Do it here because here we know the currency!
      if st.symbol not in symbols:
        dc.add_stock_symbol(st.symbol, st.currency)
        symbols.add(st.symbol)
      dc.add_share_transaction(st.symbol, st.quantity, st.proceeds, st.date)
    print('\n'.join(map(str, dc.get_all_symbol_overviews())))


def main():
  p = argparse.ArgumentParser()
  p.add_argument('--accounts_from_json', '-a')
  p.add_argument('--stocks_from_ibkr', '-s')
  flags = p.parse_args()
  if flags.accounts_from_json:
    create_db_from_files(flags.accounts_from_json,
                         flags.stocks_from_ibkr)


if __name__ == '__main__':
  main()


