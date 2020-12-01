import argparse

import urwid

import data_controller


_BACKGROUND = urwid.SolidFill(u'\N{MEDIUM SHADE}')


_PALETTE = [
  ('bold', 'bold', ''),
  ('err', 'dark red,bold', ''),
  ('reversed', 'standout', ''),
]


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


class AccountsView(urwid.WidgetWrap):
  def __init__(self, dc: data_controller.DataController, controller: Controller):
    self.dc = dc
    self.controller = controller
    super(AccountsView, self).__init__(self._get_menu())

  def refresh(self):
    self._set_w(self._get_menu())

  def _get_menu(self):
    body = [urwid.Text('ppfin'), urwid.Divider()]
    accs = self.dc.get_all_accounts()
    if not accs:
      body += [urwid.Text('No Accounts!')]
    else:
      for acc in accs:
        body.append(urwid.Columns([
          make_button(acc.name, lambda _:...),
          urwid.Text(acc.get_formatted_balance(), align='right')]))
      body += [urwid.Divider(),
               urwid.Text(data_controller.format_balance(
                 sum(a.get_balance() for a in accs)), align='right')]
    body += [urwid.Divider(),
             make_button('Update Balances', self._update),
             make_button('Add Account', self._add_account),
             ]
    focus_walker = urwid.SimpleFocusListWalker(body)
    return urwid.ListBox(focus_walker)

  def _update(self, _):
    self.controller.push(UpdateView(self.dc, self.controller))

  def _add_account(self, _):
    def done(_):
      name, _ = name_edit.get_text()
      name = name.replace('Name: ', '')
      self.dc.create_account(name)
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
    self.controller.push(AccountsView(dc, self.controller))
    self.main_loop = None

  def make_main_loop(self):
    self.main_loop = urwid.MainLoop(self.draw(),
                                    palette=_PALETTE,
                                    unhandled_input=self.controller.unhandled_input)
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

