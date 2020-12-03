import pytest
from data_controller import DataController, UnknownSymbolException



_TEST_ACCOUNT_NAME = 'TestAcc'


@pytest.fixture()
def tmp_database_path(tmpdir):
  return str(tmpdir / 'test.db')


@pytest.fixture()
def data_controller(tmp_database_path):
  dc = DataController(tmp_database_path)
  test_accounts = [_TEST_ACCOUNT_NAME,
                   _TEST_ACCOUNT_NAME + '_2',
                   _TEST_ACCOUNT_NAME + '_3']
  for test_account in test_accounts:
    dc.create_account(test_account, 'USD')
  assert [account.name for account in dc.get_all_accounts()] == test_accounts
  return dc


def test_create(data_controller):
  with pytest.raises(ValueError):
    data_controller.create_account(_TEST_ACCOUNT_NAME, 'USD')


def test_account_categories(tmp_database_path):
  dc = DataController(tmp_database_path)
  accounts = list((i, _TEST_ACCOUNT_NAME + '_' + str(i))
                  for i in range(4))
  for i, account_name in accounts:
    dc.create_account(account_name, currency='USD', category=i)
  for i, account_name in accounts:
    accs = dc.get_all_accounts(category=i)
    assert [acc.name for acc in accs] == [account_name]


def test_add(data_controller):
  for account in data_controller.get_all_accounts():
    values = [12.0, -5, 27]
    assert data_controller.get_balance(account.name) == 0.
    for v in values:
      data_controller.add_transaction(account.name, value=v)
    assert data_controller.get_balance(account.name) == sum(values)


def test_second_last(data_controller):
  for account in data_controller.get_all_accounts():
    values = [12.0, -5, 27]
    balances = [0.]
    for v in values:
      data_controller.add_transaction(account.name, value=v)
      balances.append(v + balances[-1])
    for index in [-1, -2, -3]:
      assert data_controller.get_balance(account.name, index=index) == \
             balances[index], (balances, index)


def test_shares_buy_sell(data_controller):
  with pytest.raises(UnknownSymbolException):
    data_controller.add_share_transaction('TEST', quantity=10, proceeds=-100)

  data_controller.add_stock_symbol('TEST', 'USD')
  assert data_controller.get_currency_of_symbol('TEST') == 'USD'
  data_controller.add_share_transaction('TEST', quantity=10, proceeds=-100)
  data_controller.add_share_transaction('TEST', quantity=-10, proceeds=110)
  overview = data_controller.get_symbol_overview('TEST')
  assert overview.quantity == 0
  assert overview.proceeds_so_far == 10


def test_shares_two_buys(data_controller):
  data_controller.add_stock_symbol('TEST', 'USD')
  data_controller.add_share_transaction('TEST', quantity=10, proceeds=-100)
  data_controller.add_share_transaction('TEST', quantity=10, proceeds=-110)
  overview = data_controller.get_symbol_overview('TEST')
  assert overview.quantity == 20
  assert overview.proceeds_so_far == -210


def test_shares_get_all(data_controller):
  symbols = ['TST', 'TST2']
  for symbol in symbols:
    data_controller.add_stock_symbol(symbol, 'USD')
  assert [so.symbol
          for so in data_controller.get_all_symbol_overviews()] == symbols