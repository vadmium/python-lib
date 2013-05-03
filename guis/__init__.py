from misc import Function
from misc import deco_factory

@deco_factory
def stash(stash, *args, **kw):
    stash(*args, **kw)
    return args[-1]

def probe():
    try:
        from .win import Win
    except ImportError:
        from .tk import Ttk
        return Ttk()
    return Win()

class Window:
    def __init__(self, gui, *pos, **kw):
        self.gui = gui
        self.gui.new_window(self, *pos, **kw)
    def close(self):
        return self.gui.close_window(self)

class Labelled:
    def __init__(self, label, access=None):
        self.label = label
        self.access = access
    
    def label_key(self):
        if self.access:
            return "{0.label} (&{0.access})".format(self)
        else:
            return self.label

class Control:
    def place(self, gui):
        self.gui = gui

class Entry(Control):
    expand = True
    def __init__(self, value=None):
        self.value = value
    def get(self):
        return self.gui.controls[type(self)].get(self.gui, self)
    def set(self, text):
        return self.gui.controls[type(self)].set(self.gui, self, text)

class Button(Labelled):
    def __init__(self, label, command=None, access=None,
    default=False, close=False):
        Labelled.__init__(self, label, access)
        self.command = command
        self.default = default
        self.close = close
    
    def default(self, window):
        if window.command:
            window.command()
    def close(self, window):
        window.close()

class TreeBase(Control):
    multiline = True
    expand = True
    def __init__(self, columns=1, selected=None, opened=None):
        """
        columns: Sequence of dict() objects for each column, or column
            headings. Keys can be "text" and "width". Width is measured
            in digits (U+2007 "Figure space"). Default: single unnamed
            column"""
        self.columns = columns
        self.selected = selected
        self.opened = opened
    def add(self, *pos, **kw):
        return self.gui.controls[type(self)].add(self.gui, self, *pos, **kw)
    def selection(self):
        return self.gui.controls[type(self)].selection(self.gui, self)
    def remove(self, item):
        return self.gui.controls[type(self)].remove(self.gui, self, item)
    def __iter__(self):
        return self.gui.controls[type(self)].iter(self.gui, self)
    def clear(self):
        return self.gui.controls[type(self)].clear(self.gui, self)

class List(TreeBase):
    def get(self, item):
        return self.gui.controls[type(self)].get(self.gui, self, item)

class Tree(TreeBase):
    def children(self, parent):
        return self.gui.controls[type(self)].children(self.gui, self, parent)
    def set(self, item, text):
        return self.gui.controls[type(self)].set(self.gui, self, item, text)

class MenuEntry:
    expand = True
    def __init__(self, menu, value):
        self.menu = menu
        self.value = value
    def get(self):
        return self.gui.controls[type(self)].get(self.gui, self)

class Inline:
    expand = True
    def __init__(self, *cells):
        self.cells = cells

class Form:
    def __init__(self, *fields):
        self.fields = fields
        self.depth = self.get_depth(self.fields)
    
    def get_depth(self, fields):
        depth = 0
        for field in fields:
            if isinstance(field, Section):
                depth = max(depth, 1 + self.get_depth(field.fields))
        return depth

class Section(Labelled):
    def __init__(self, label, *fields, access=None):
        Labelled.__init__(self, label, access)
        self.fields = fields
class Field(Labelled):
    def __init__(self, label, field, access=None):
        Labelled.__init__(self, label, access)
        self.field = field
