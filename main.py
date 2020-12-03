import logging

logger = logging.getLogger()
logger.setLevel(logging.DEBUG)

fh = logging.FileHandler('otp.log')
fh.setLevel(logging.DEBUG)
logger.addHandler(fh)

import argparse
import urwid

import data_controller
import symbol_values


_BACKGROUND = urwid.SolidFill(u'\N{MEDIUM SHADE}')
_BASE_CURRENCY = 'CHF'


_main_event_loop = urwid.AsyncioEventLoop()


_PALETTE = [
  ('brand', 'bold,underline,dark blue', ''),
  ('underline', 'underline', ''),
  ('bold', 'bold', ''),
  ('err', 'dark red,bold', ''),
  ('reversed', 'standout', ''),
  ('up', 'dark green', ''),
  ('upbold', 'dark green,bold', ''),
  ('neutral', '', ''),
  ('neutralbold', 'bold', ''),
  ('down', 'dark red', ''),
  ('downbold', 'dark red,bold', ''),
]

_STYLES = {palette_entry[0] for palette_entry in _PALETTE}

_BOLD_MAP = {key: key + 'bold'
             for key in _STYLES if key in _STYLES and key + 'bold' in _STYLES}


class Controller:
  def __init__(self):
    self.stack = [_BACKGROUND]
    self.view = urwid.Padding(self.stack[-1], left=1, right=1)

  def unhandled_input(self, key):
    try:
      self.stack[-1].unhandled_input(key)
    except AttributeError:
      pass

  def _update(self):
    self.view.original_widget = self.stack[-1]

  def push(self, w):
    self.stack.append(w)
    self._update()

  def pop(self):
    self.stack.pop()
    try:
      self.stack[-1].refresh()
    except AttributeError:
      pass
    self._update()



def make_button(title, callback_fn):
  button = urwid.Button(title)
  urwid.connect_signal(button, 'click', callback_fn)
  return urwid.AttrMap(button, None, focus_map='reversed')


def boldify(w):
  return urwid.AttrMap(w, attr_map=_BOLD_MAP)


def on_main(fn):
  def callback():
    _main_event_loop.alarm(0, lambda: fn())
  return callback


class Header(urwid.WidgetWrap):
  _ALIGNS = {'l': 'left', 'r': 'right'}

  def __init__(self, *titles, aligns=None):
    titles = [('underline', title) if not isinstance(title, tuple) else title
              for title in titles]
    if not aligns:
      aligns = ''.join('l' for _ in titles)
    aligns = [Header._ALIGNS[align] for align in aligns]
    if len(aligns) != len(titles):
      raise ValueError
    super().__init__(
      urwid.Columns([urwid.Text(title, align=align)
                     for title, align in zip(titles, aligns)]))


class SummaryView(urwid.WidgetWrap):
  def __init__(self, dc: data_controller.DataController, controller: Controller):
    self.dc = dc
    self.controller = controller
    self.focus_walker = None
    self._last_focus = None
    symbol_values.Ticker.register_callback(
      'SummaryView',
      on_main(self.refresh))
      # lambda: controller.main_loop.event_loop.alarm(0, lambda *_: self.refresh()))
    with self.dc.connect():
      super(SummaryView, self).__init__(self._get_menu())

  def unhandled_input(self, key):
    if key == 'r':
      self.refresh()

  def refresh(self):
    logger.info('***\nREFRESH\n***')
    with self.dc.connect():
      self._set_w(self._get_menu())

  def __del__(self):
    symbol_values.Ticker.remove_callback('SummaryView')

  def _get_menu(self):
    body = [urwid.Text(('brand', 'ppfin')), urwid.Divider()]

    # Accounts
    accs = self.dc.get_all_accounts()
    if not accs:
      body += [urwid.Text('No Accounts!')]
    else:
      body += [Header('Account', 'Diff', 'Balance', aligns='lrr')]
      for acc in accs:
        body.append(urwid.Columns([
          make_button(acc.name, lambda _:...),
          urwid.Text(acc.get_diff_to_last().attr_str(), align='right'),
          urwid.Text(str(acc.get_balance()), align='right')]))
      total_diff = sum(acc.get_diff_to_last() for acc in accs).attr_str()
      total = str(sum(acc.get_balance() for acc in accs))
      body += [urwid.Columns([
        urwid.Text(('bold', 'Total')),
        boldify(urwid.Text(total_diff, align='right')),
        urwid.Text(('bold', total), align='right')])]
    body += [urwid.Divider(),
             make_button('Update Balances', self._update_balances),
             make_button('Add Account', self._add_account),
             urwid.Divider()]

    # Shares
    symbol_overviews = self.dc.get_all_symbol_overviews()
    if not symbol_overviews:
      body += [urwid.Text('No Shares!')]
    else:
      body += [Header('Symbol', 'Shares', 'Gain', 'Possession', aligns='lrrr')]
      for so in symbol_overviews:
        body.append(urwid.Columns([
          make_button(so.symbol, self._update_share),
          urwid.Text(str(so.quantity), align='right'),
          urwid.Text(so.get_current_total_gain().attr_str(),
                     align='right'),
          urwid.Text(str(so.get_current_total_value()),
                     align='right')]))

      total_gain = sum(
        so.get_current_total_gain(currency=_BASE_CURRENCY)
        for so in symbol_overviews)
      total_share_value = sum(
        so.get_current_total_value(currency=_BASE_CURRENCY)
        for so in symbol_overviews)

      body += [
        urwid.Columns([
          urwid.Text(('bold', 'Total')),
          urwid.Text(''),
          urwid.Text(('bold', str(total_gain)), align='right'),
          urwid.Text(('bold', str(total_share_value)), align='right'),
        ])
      ]
    body += [urwid.Divider(),
             make_button('Update Shares', self._update_shares),
             make_button('Add Share', self._add_share),
             urwid.Divider()]

    self.focus_walker = urwid.SimpleFocusListWalker(body)
    urwid.connect_signal(self.focus_walker, 'modified',
                         lambda: self._cache_focus_value())
    if self._last_focus is not None:
      self.focus_walker.set_focus(self._last_focus)
    return urwid.ListBox(self.focus_walker)

  def _cache_focus_value(self):
    self._last_focus = self.focus_walker.focus

  def _update_share(self, k):
    raise ValueError(k.get_label())

  def _update_shares(self, _):
    pass

  def _add_share(self, _):
    def done(_):
      name = name_edit.get_edit_text()
      currency = cur_edit.get_edit_text()
      try:
        self.dc.add_stock_symbol(name, currency)
      except data_controller.SymbolExistsException:
        pass  # TODO: maybe handle
      self.controller.pop()

    header = urwid.Text('Add Share')
    name_edit = urwid.Edit("Symbol: ")
    cur_edit = urwid.Edit("Currency: ")
    widget = urwid.Pile([
      header,
      name_edit,
      cur_edit,
      make_button('Done', done),
      make_button('Cancel', lambda _: self.controller.pop()),
    ])
    self.controller.push(urwid.Filler(widget, 'top'))

  def _update_balances(self, _):
    self.controller.push(UpdateView(self.dc, self.controller))

  def _add_account(self, _):
    def done(_):
      name, _ = name_edit.get_text()
      name = name.replace('Name: ', '')
      self.dc.create_account(name, _BASE_CURRENCY)  # TODO
      self.controller.pop()

    name_edit = urwid.Edit("Name: ")
    header = urwid.Text('Add Account')
    widget = urwid.Pile([
      header,
      name_edit,
      make_button('Done', done),
      make_button('Cancel', lambda _: self.controller.pop()),
    ])
    self.controller.push(urwid.Filler(widget, 'top'))


class UpdateView(urwid.WidgetWrap):
  def __init__(self, dc: data_controller.DataController,
               controller: Controller):
    self.dc = dc
    self.controller = controller
    self.done_button: urwid.AttrMap = None
    self.focus_walker: urwid.SimpleFocusListWalker = None
    self.accs = None
    super(UpdateView, self).__init__(self._get_menu())

  def refresh(self):
    self._set_w(self._get_menu())

  def unhandled_input(self, key):
    if key == 'enter':
      # is_ok = self._validate()
      current_idx = self.focus_walker.focus
      # current_widget = self.focus_walker[current_idx]
      next_position = self.focus_walker.next_position(current_idx)
      if isinstance(self.focus_walker[next_position], urwid.Divider):
        next_position += 1
      # if not isinstance(current_widget, urwid.Edit):
      #   return
      self.focus_walker.set_focus(next_position)

  def _get_menu(self):
    body = [urwid.Text('Update'), urwid.Divider()]
    self.accs = self.dc.get_all_accounts()
    if not self.accs:
      raise NotImplemented
    indent = max(len(acc.name) for acc in self.accs) + 5
    for acc in self.accs:
      label = acc.name + ':'
      indent_acc = (indent - len(label)) * ' '
      body.append(urwid.Edit(f"{label}{indent_acc}"))
        # make_button(acc.name, lambda _:...),
        # urwid.Text(acc.get_formatted_balance(), align='right')]))

    def done(_):
      all_ok = self._validate()
      if all_ok:
        self._commit()
        self.controller.pop()

    self.done_button = make_button('Done', done)
    body += [urwid.Divider(),
             self.done_button,
             make_button('Cancel', lambda _: self.controller.pop()),
             ]
    self.focus_walker = urwid.SimpleFocusListWalker(body)
    urwid.connect_signal(self.focus_walker, 'modified',
                         lambda: self._validate())
    return urwid.ListBox(self.focus_walker)

  def _commit(self):
    edit_fields = [e for e in self.focus_walker
                   if isinstance(e, urwid.Edit)]
    assert len(edit_fields) == len(self.accs)
    with self.dc.connect():
      for e, acc in zip(edit_fields, self.accs):
        assert acc.name in e.caption
        value = e.get_edit_text()
        if not value:
          continue
        value = float(value)
        diff = value - acc.get_balance()
        self.dc.add_transaction(acc.name, diff)


  def _validate(self):
    all_ok = True
    for i, e in enumerate(self.focus_walker):
      if not isinstance(e, urwid.Edit):
        continue
      value = e.get_edit_text()
      if not value:
        continue
      try:
        float(value)
        is_ok = True
      except ValueError:
        is_ok = False
      caption = e.caption
      if is_ok and '!' in caption:
        caption = caption.replace('!', ':')
        e.set_caption(caption)
      if not is_ok and '!' not in caption:
        caption = caption.replace(':', '!')
        e.set_caption(('err', caption))
      all_ok = all_ok and is_ok
    if not all_ok:
      self.done_button.set_attr_map({None: 'err'})
      self.done_button.original_widget.set_label(
        'Errors: All values must be floats!')
    else:
      self.done_button.set_attr_map({None: None})
      self.done_button.original_widget.set_label(
        'Done')
    return all_ok


class MainWindow:
  def __init__(self, dc: data_controller.DataController):
    self.dc = dc
    self.controller = Controller()
    self.controller.push(SummaryView(dc, self.controller))
    self.main_loop = None

  def make_main_loop(self):
    self.main_loop = urwid.MainLoop(self.draw(),
                                    palette=_PALETTE,
                                    unhandled_input=self.controller.unhandled_input,
                                    event_loop=_main_event_loop)
    return self.main_loop

  def draw(self):
    top = urwid.Overlay(self.controller.view, _BACKGROUND,
                        align='center', width=('relative', 80),
                        valign='middle', height=('relative', 80),
                        min_width=20, min_height=9)
    return top


def item_chosen(button, choice):
  raise urwid.ExitMainLoop()
  response = urwid.Text([u'You chose ', choice, u'\n'])
  done = urwid.Button(u'Ok')
  urwid.connect_signal(done, 'click', exit_program)
  main.original_widget = urwid.Filler(urwid.Pile([response,
                                                  urwid.AttrMap(done, None, focus_map='reversed')]))

def exit_program(button):
  raise urwid.ExitMainLoop()


def main():
  p = argparse.ArgumentParser()
  p.add_argument('--database', '-db', required=True)
  flags = p.parse_args()
  dc = data_controller.DataController(flags.database)
  mw = MainWindow(dc)
  loop = mw.make_main_loop()
  loop.run()



if __name__ == '__main__':
  main()

