import concurrent.futures
import urllib.error
from typing import Optional

import yfinance as yf
import time

import helpers

import logging

logger = logging.getLogger()

_tickers = {}
_callbacks = {}
_executor = concurrent.futures.ThreadPoolExecutor(max_workers=8)


class Ticker(object):
  @staticmethod
  def make(symbol_name) -> 'Ticker':
    if symbol_name not in _tickers:
      _tickers[symbol_name] = Ticker(symbol_name)
    return _tickers[symbol_name]

  @staticmethod
  def register_callback(name, callback_fn):
    logger.info(f'**REG{name}')
    _callbacks[name] = callback_fn

  @staticmethod
  def remove_callback(name):
    del _callbacks[name]

  def __init__(self, symbol_name):
    if symbol_name in _tickers:
      raise ValueError(symbol_name)
    logger.info(f'*** Create Ticker for {symbol_name}')
    self.symbol_name = symbol_name
    self.queried = None  # Time of query
    self.info_cache = None
    self.query_cache_timeout_s = 5 * 60  # 5 minutes.
    self._current_value = helpers.OptionalFloat(None)
    self.waiting = False

  def get_current_value(self) -> helpers.OptionalFloat:
    self.lazy_update()
    return self._current_value

  def lazy_update(self, force=None) -> Optional[concurrent.futures.Future]:
    if force or self._should_update():
      return self._schedule_update()
    return None

  def _schedule_update(self) -> concurrent.futures.Future:
    self.queried = time.time()
    self.waiting = True

    def _get_info(retry=5):
      try:
        return yf.Ticker(self.symbol_name).info
      except urllib.error.HTTPError as e:
        if retry:
          logger.info(f'*** Caught {e} for {self.symbol_name}, retry={retry}')
          return _get_info(retry-1)
        raise e

    def _done(fut_):
      logger.info(f'DONE {self.symbol_name} {_callbacks.keys()}')
      self.info_cache = fut_.result()
      try:
        self._current_value = helpers.OptionalFloat(
          self.info_cache['regularMarketOpen'])
        logger.info(f' --> {self.symbol_name} {self._current_value}')
      except KeyError:
        import pprint
        pprint.pprint(self.info_cache)
        raise ValueError(self.symbol_name)
      self.waiting = False
      for callback in _callbacks.values():
        callback()

    fut = _executor.submit(lambda: _get_info())
    logger.info(f'*** Pending: {_executor._work_queue.qsize()} jobs')
    fut.add_done_callback(_done)
    return fut

  def _should_update(self):
    if not self.queried:
      return True
    if self.waiting:
      return False
    passed = time.time() - self.queried
    if passed > self.query_cache_timeout_s:
      return True
    return False


def main():
  for _ in range(10):
    print(convert_currency(1, 'USD', 'CHF'))
    time.sleep(1)


def convert_currency(amount, from_cur, to_cur) -> helpers.OptionalBalance:
  if from_cur == to_cur:
    return amount
  base_amount = Ticker.make(f'{from_cur}{to_cur}=X').get_current_value()
  logger.info(f'CONVERTING {amount} {from_cur} -> {to_cur} -> {base_amount}')
  return helpers.OptionalBalance(base_amount * amount, to_cur)


def check_symbols(symbols):
  futs = [Ticker.make(symbol_name).lazy_update(force=True)
          for symbol_name in symbols]
  for fut in concurrent.futures.as_completed(futs):
    info = fut.result()
    print('Checked:', info['shortName'])
  return True


if __name__ == '__main__':
    main()

