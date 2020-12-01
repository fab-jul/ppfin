import argparse
import contextlib
import dataclasses
import json
import sqlite3
import os


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
      print('Commiting...')
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
        (id INTEGER PRIMARY KEY, name text, currency text)""")
      c.execute("""
        CREATE TABLE transactions
        (id INTEGER PRIMARY KEY, 
        accountID INTEGER,
        value real,
        balance_after real)""")

  def create_account(self, name):
    with self.connect() as c:
      existing = set(c.execute('SELECT * FROM accounts WHERE name=?', (name,)))
      if existing:
        raise ValueError('Account with name exists: {name}')
      c.execute('INSERT INTO accounts (name, currency) VALUES (?, ?)',
                (name, 'USD'))

  def get_all_accounts(self):
    with self.connect() as c:
      return [Account(self, name, currency)
              for name, currency
              in c.execute('SELECT name, currency FROM accounts')]

  def add_transaction(self, account_name: str, value: float):
    with self.connect() as c:
      last_balance, accountID = self._get_last_balance(c, account_name)
      new_balance = last_balance + value
      c.execute('INSERT INTO transactions (accountID, value, balance_after) '
                'VALUES (?, ?, ?)',
                (accountID, value, new_balance))
      return new_balance

  def get_balance(self, account_name: str) -> float:
    with self.connect() as c:
      last_balance, _ = self._get_last_balance(c, account_name)
      return last_balance

  @staticmethod
  def _get_last_balance(c: sqlite3.Cursor, account_name):
    c.execute('SELECT id FROM accounts WHERE name=?', (account_name,))
    accountID, = c.fetchone()
    c.execute(
      'SELECT balance_after FROM transactions '
      'WHERE accountID=? '
      'ORDER BY id DESC LIMIT 1 ',
      (accountID,))
    last_balance, = c.fetchone() or (0.,)
    return last_balance, accountID


@dataclasses.dataclass
class Account:
  dc: DataController
  name: str
  currency: str
  _balance: float = None

  def get_formatted_balance(self):
    return format_balance(self.get_balance())

  def get_balance(self):
    return self._lazy('_balance', lambda: self.dc.get_balance(self.name))

  def _lazy(self, field_name, fn):
    if not getattr(self, field_name):
      setattr(self, field_name, fn())
    return getattr(self, field_name)


def format_balance(balance: float) -> str:
  return f'{balance:.2f}' if balance else '0.00'


def create_db_from_json(json_p):
  out_p = json_p.replace('.json', '.db')
  if os.path.isfile(out_p):
    os.rename(out_p, out_p + '.bak')

  with open(json_p, 'r') as f:
    accounts = json.load(f)
    dc = DataController(out_p)
    with dc.connect():
      for account_name, balance in accounts.items():
        dc.create_account(account_name)
        dc.add_transaction(account_name, balance)


def main():
  p = argparse.ArgumentParser()
  p.add_argument('--create_db_from_json', '-c')
  flags = p.parse_args()
  if flags.create_db_from_json:
    create_db_from_json(flags.create_db_from_json)


if __name__ == '__main__':
  main()


