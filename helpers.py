import functools


@functools.total_ordering
class OptionalFloat(object):
  def __init__(self, value=None):
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


def make_func(func_name_):
  def func(self_, *args):
    if self_.value is None:
      return OptionalFloat(None)
    args = [(OptionalFloat(arg) if not isinstance(arg, OptionalFloat) else arg)
            for arg in args]
    if not all(arg.filled() for arg in args):
      return OptionalFloat(None)
    args_as_float = [arg.get() for arg in args]
    return OptionalFloat(getattr(self_.value, func_name_)(*args_as_float))
  return func


for func_name in [#"__lt__", "__le__", "__eq__", "__ne__", "__gt__", "__ge__",
                  "__add__", "__radd__", "__sub__", "__rsub__", "__mul__",
                  "__rmul__", "__mod__", "__rmod__", "__divmod__",
                  "__rdivmod__", "__pow__", "__rpow__", "__neg__", "__pos__",
                  "__abs__", "__floordiv__", "__rfloordiv__", "__truediv__",
                  "__rtruediv__", "__round__"]:
  setattr(OptionalFloat, func_name, make_func(func_name))
