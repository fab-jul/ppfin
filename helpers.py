import functools
from typing import Union


@functools.total_ordering
class OptionalFloat(object):
  def __init__(self, value=None):
    if isinstance(value, OptionalFloat):
      value = value.value
    if value is not None:
      value = float(value)
    self.value = value

  def __str__(self):
    return f'OptionalFloat({self.value})'

  def filled(self):
    return self.value is not None

  def format(self, fmt_str='{:.2f}', empty_text='?') -> str:
    return fmt_str.format(self.value) if self.filled() else empty_text

  def get(self):
    if self.value is None:
      raise ValueError
    return self.value

  def __format__(self, format_spec):
    if self.value is None:
      return 'NONE!!!'
    return self.value.__format__(format_spec)

  def __eq__(self, other):
    if not isinstance(other, OptionalFloat):
      other = OptionalFloat(other)
    return other.value == self.value

  def __lt__(self, other):
    if not isinstance(other, OptionalFloat):
      other = OptionalFloat(other)
    if not (self.filled() and other.filled()):
      raise NotImplemented
    return self.value < other.value


class OptionalBalance(OptionalFloat):
  def __init__(self,
               value: Union[float, None],
               currency: str,
               placeholder: str = '...'):
    self.currency = currency
    self.placeholder = placeholder
    super().__init__(value)

  def attr_str(self):
    col = 'neutral'
    if self.filled():
      col = 'up' if self.get() >= 0 else 'down'
    return (col, str(self))

  def __str__(self):
    if self.filled():
      return f'{self.currency} {self.get():,.2f}'
    return self.placeholder


def format_balance(balance: float) -> str:
  return f'{balance:,.2f}' if balance else '0.00'


def _make_func(cls, func_name, checker=None, get_init_kwargs=None):
  """
  :param cls: Class to create.
  :param func_name: Name of the function to implement.
  :param checker: Function that takes a list of instances of `cls` and
      returns a boolean indicating whether they are all conformant.
  :param get_init_kwargs: Function that takes a single instance of `cls` and
      returns a dictionary with the kwargs needed to instantiate new elements
      of `cls`.
  """
  def func(self, *args):
    init_kwargs = get_init_kwargs(self) if get_init_kwargs else {}
    if self.value is None:
      return cls(None, **init_kwargs)
    args = [(cls(arg, **init_kwargs) if not isinstance(arg, cls) else arg)
            for arg in args]
    if checker and not checker([self] + args):
      raise NotImplemented(args)
    if not all(arg.filled() for arg in args):
      return cls(None, **init_kwargs)
    args_as_float = [arg.get() for arg in args]
    return cls(getattr(self.value, func_name)(*args_as_float),
               **init_kwargs)
  return func

def _finalize_classes():
  all_funcs = ["__add__", "__radd__", "__sub__", "__rsub__", "__mul__",
               "__rmul__", "__mod__", "__rmod__", "__divmod__",
               "__rdivmod__", "__pow__", "__rpow__", "__neg__", "__pos__",
               "__abs__", "__floordiv__", "__rfloordiv__", "__truediv__",
               "__rtruediv__", "__round__"]

  for func_name in all_funcs:
    setattr(OptionalFloat, func_name, _make_func(OptionalFloat, func_name))

  # Tests
  assert OptionalFloat(4.) * OptionalFloat(1.) == OptionalFloat(4.)
  assert OptionalFloat(4.) * OptionalFloat(None) == OptionalFloat(None)

  for func_name in all_funcs:
    setattr(OptionalBalance, func_name,
            _make_func(
              OptionalBalance, func_name,
              # Make sure all have the same currency
              checker=lambda args: len(set(arg.currency for arg in args)) == 1,
              get_init_kwargs=lambda arg: dict(currency=arg.currency,
                                               placeholder=arg.placeholder)))

  assert OptionalBalance(4., 'USD') * OptionalBalance(1., 'USD') == \
         OptionalBalance(4., 'USD')


_finalize_classes()