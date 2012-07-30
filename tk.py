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
    def __init__(self, master, column=0):
        self.master = master
        self.column = column
        self.master.columnconfigure(column + 1, weight=1)
        en = font_size(nametofont("TkDefaultFont")["size"] / 2)
        self.master.columnconfigure(column + 0, pad=en)
    
    def add_field(self, widget, multiline=False, **kw):
        label_sticky = [tkinter.EW]
        widget_sticky = [tkinter.EW]
        if multiline:
            label_sticky.append(tkinter.N)
            widget_sticky.append(tkinter.NS)
        
        label = Label(self.master, **kw)
        label.grid(column=self.column + 0, sticky=label_sticky)
        row = label.grid_info()["row"]
        if multiline:
            self.master.rowconfigure(row, weight=1)
        widget.grid(row=row, column=self.column + 1, sticky=widget_sticky)

class ScrolledTree(Frame):
    def __init__(self, master, columns=1, tree=True, headings=True):
        Frame.__init__(self, master)
        self.rowconfigure(0, weight=1)
        self.columnconfigure(0, weight=1)
        
        try:
            self.nontree_columns = len(columns)
        except TypeError:
            self.nontree_columns = columns
        
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
        
        self.heading_font = nametofont("TkHeadingFont")
        self.heading_space = "\N{EN QUAD}"
        self.space_size = self.heading_font.measure(self.heading_space)
        self.text_font = nametofont("TkTextFont")
        
        self.auto_width = list()
        for (key, value) in zip(self.columns(), columns):
            if isinstance(value, str):
                value = Record(heading=value)
            
            if headings:
                try:
                    heading = value.heading
                except AttributeError:
                    pass
                else:
                    self.tree.heading(key, text=heading)
            
            try:
                width = value.width
            except AttributeError:
                auto = True
                
                if headings:
                    text = self.tree.heading(key, option="text")
                    text += self.heading_space
                    width = self.heading_font.measure(text)
            
            else:
                auto = False
                
                try:
                    (width, unit) = width
                except TypeError:
                    unit = self.EM
                width *= self.text_font.measure(unit)
                width += self.space_size
            
            self.auto_width.append(auto)
            width = max(width, self.tree.column(key, option="minwidth"))
            self.tree.column(key, stretch=False, width=width)
    EM = "\N{EM SPACE}"
    FIGURE = "\N{FIGURE SPACE}"
    
    def columns(self):
        if self.tree_shown:
            yield "#0"
        for column in self.nontree_columns:
            yield column
    
    def add(self, parent="", *args, **kw):
        child = self.tree.insert(parent, "end", *args, **kw)
        if not self.tree.focus():
            self.tree.focus(child)
        
        auto = iter(self.auto_width)
        if self.tree_shown and next(auto):
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
            if not next(auto):
                continue
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
