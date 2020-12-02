import symbol_values
import time


def test_cache():
  aapl = symbol_values.Ticker('AAPL')
  assert aapl.queried is None
  aapl.current_value()
  last_queried = aapl.queried
  assert last_queried is not None
  time.sleep(0.1)
  aapl.current_value()
  # Make sure we are using the cache!
  assert aapl.queried == last_queried


def test_global_cache():
  while symbol_values._tickers:
    symbol_values._tickers.popitem()
  aapl = symbol_values.Ticker.make('AAPL')
  assert aapl.queried is None
  aapl.current_value()
  last_queried = aapl.queried
  assert last_queried is not None
  aapl = symbol_values.Ticker.make('AAPL')
  time.sleep(0.1)
  aapl.current_value()
  # Make sure we are using the cache!
  assert aapl.queried == last_queried

