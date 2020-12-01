import pytest
from data_controller import DataController



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
    dc.create_account(test_account)
  assert [account.name for account in dc.get_all_accounts()] == test_accounts
  return dc


def test_create(data_controller):
  with pytest.raises(ValueError):
    data_controller.create_account(_TEST_ACCOUNT_NAME)


def test_add(data_controller):
  for account in data_controller.get_all_accounts():
    values = [12.0, -5, 27]
    assert data_controller.get_balance(account.name) == 0.
    for v in values:
      data_controller.add_transaction(account.name, value=v)
    assert data_controller.get_balance(account.name) == sum(values)

