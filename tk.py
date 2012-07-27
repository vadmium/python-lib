from functools import partial
from functools import reduce
from operator import or_
from math import ceil
from . import event
from lib import Record
import tkinter
from tkinter.ttk import (Frame, Label, Scrollbar)
from tkinter.ttk import Treeview
from tkinter.font import nametofont
from math import ceil

class Form(object):
    def __init__(self, master):
        self.master = master
        self.master.columnconfigure(1, weight=1)
        en = font_size(nametofont("TkDefaultFont")["size"] / 2)
        self.master.columnconfigure(0, pad=en)
    
    def add_field(self, widget, multiline=False, **kw):
        label_sticky = [tkinter.EW]
        widget_sticky = [tkinter.EW]
        if multiline:
            label_sticky.append(tkinter.N)
            widget_sticky.append(tkinter.NS)
        
        label = Label(self.master, **kw)
        label.grid(column=0, sticky=label_sticky)
        row = label.grid_info()["row"]
        if multiline:
            self.master.rowconfigure(row, weight=1)
        widget.grid(row=row, column=1, sticky=widget_sticky)

class ScrolledTree(Frame):
    def __init__(self, master, columns=None, tree=True, headings=True):
        Frame.__init__(self, master)
        self.rowconfigure(0, weight=1)
        self.columnconfigure(0, weight=1)
        
        if columns is not None:
            self.nontree_columns = columns
        else:
            try:
                self.nontree_columns = len(headings)
            except TypeError:
                self.nontree_columns = 1
        
        show = list()
        self.tree_shown = tree
        if self.tree_shown:
            show.append("tree")
            self.nontree_columns -= 1
        if headings:
            show.append("headings")
        
        self.nontree_columns = range(self.nontree_columns)
        self.tree = Treeview(self, show=show,
            columns=tuple(self.nontree_columns))
        self.tree.grid(sticky=(tkinter.EW, tkinter.NS))
        
        scroll = Scrollbar(self, orient=tkinter.VERTICAL,
            command=self.tree.yview)
        scroll.grid(row=0, column=1, sticky=(tkinter.W, tkinter.NS))
        self.tree.configure(yscrollcommand=scroll.set)
        scroll = Scrollbar(self, orient=tkinter.HORIZONTAL,
            command=self.tree.xview)
        scroll.grid(row=1, column=0, sticky=(tkinter.N, tkinter.EW))
        self.tree.configure(xscrollcommand=scroll.set)
        
        if headings:
            try:
                headings = zip(self.columns(), headings)
            except TypeError:
                pass
            else:
                for (column, text) in headings:
                    self.tree.heading(column, text=text)
        
        self.heading_font = nametofont("TkHeadingFont")
        self.space = "\N{EN QUAD}"
        for column in self.columns():
            text = self.tree.heading(column, option="text")
            width = self.heading_font.measure(text + self.space)
            width = max(width, self.tree.column(column, option="minwidth"))
            self.tree.column(column, stretch=False, width=width)
        self.space_size = self.heading_font.measure(self.space)
        self.text_font = nametofont("TkTextFont")
    
    def columns(self):
        if self.tree_shown:
            yield "#0"
        for column in self.nontree_columns:
            yield column
    
    def add(self, parent="", *args, **kw):
        child = self.tree.insert(parent, "end", *args, **kw)
        if not self.tree.focus():
            self.tree.focus(child)
        
        width = 1
        while parent:
            width += 1
            parent = self.tree.parent(parent)
        em = font_size(self.text_font["size"])
        width *= self.tree.winfo_fpixels(em)
        
        try:
            text = kw["text"]
        except LookupError:
            pass
        else:
            width += self.text_font.measure(text) + self.space_size
        
        if width > self.tree.column("#0", option="width"):
            self.tree.column("#0", width=ceil(width))
        
        for (i, value) in enumerate(kw.get("values", ())):
            width = self.text_font.measure(value) + self.space_size
            if width > self.tree.column(i, option="width"):
                self.tree.column(i, width=width)
        
        return child
    
    def bind_select(self, *args, **kw):
        return self.tree.bind("<<TreeviewSelect>>", *args, **kw)
    def unbind_select(self, *args, **kw):
        return self.tree.unbind("<<TreeviewSelect>>", *args, **kw)

def font_size(size):
    if size < 0:
        return -size
    else:
        return "{size}p".format_map(locals())

# Another potential API implementation
if False:
    from types import MethodType
    class MethodClass(type):
        def __get__(self, obj, cls):
            if obj is None:
                return self
            return MethodType(self, obj)
    class EventDriver(object):
        def __init__(self, widget):
            self.widget = widget
        class FileEvent(..., metaclass=MethodClass):
            def __init__(self, parent, *_, **__):
                ...(parent.widget)
            ...
        ...

def EventDriver(widget):
    # Create subclasses with "widget" as a member that inherit from the
    # driver classes defined below
    return Record(
        FileEvent=type("EventDriver.FileEvent", (FileEvent,), locals()),
        Timer=type("EventDriver.Timer", (Timer,), locals()),
    )

class FileEvent(event.FileEvent):
    from tkinter import (READABLE as READ, WRITABLE as WRITE)
    
    def __init__(self, *args, **kw):
        self.tk = self.widget.tk
        event.FileEvent.__init__(self, *args, **kw)
    
    def watch(self, ops):
        self.ops = reduce(or_, ops)
    
    def arm(self, *args, **kw):
        event.FileEvent.arm(self, *args, **kw)
        self.tk.createfilehandler(self.fd, self.ops, self.handler)
    
    def close(self, *args, **kw):
        self.tk.deletefilehandler(self.fd)
        event.FileEvent.close(self, *args, **kw)
    
    def handler(self, fd, mask):
        if self.callback is not None:
            return self.callback((fd, set(op for op in
                (self.READ, self.WRITE) if mask & op)))

class Timer(event.Event):
    def __init__(self):
        event.Event.__init__(self)
        self.timer = None
    
    def start(self, timeout):
        self.timer = self.widget.after(ceil(timeout * 1000), self.handler)
    
    def stop(self):
        self.widget.after_cancel(self.timer)
    
    def handler(self):
        if self.callback is not None:
            return self.callback()
