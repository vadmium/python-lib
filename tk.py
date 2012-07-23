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

def add_field(window, label, widget, multiline=False, **kw):
    label_sticky = [tkinter.EW]
    widget_sticky = [tkinter.EW]
    if multiline:
        label_sticky.append(tkinter.N)
        widget_sticky.append(tkinter.NS)
    
    label = Label(window, text=label)
    label.grid(column=0, sticky=label_sticky, **kw)
    row = label.grid_info()["row"]
    if multiline:
        window.rowconfigure(row, weight=1)
    widget.grid(row=row, column=1, sticky=widget_sticky, **kw)

class ScrolledTree(Frame):
    def __init__(self, master, columns=1):
        Frame.__init__(self, master)
        self.rowconfigure(0, weight=1)
        self.columnconfigure(0, weight=1)
        
        kw = dict()
        try:
            count = len(columns)
        except TypeError:
            count = columns
            kw.update(show=("tree",))
        self.tree = Treeview(self, columns=tuple(range(count - 1)), **kw)
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
        for i in range(count):
            if i:
                column = i - 1
            else:
                column = "#0"
            
            try:
                text = columns[i]
            except TypeError:
                width = 0
            else:
                self.tree.heading(column, text=text)
                width = self.heading_font.measure(text)
            
            width = max(width, self.tree.column(column, option="minwidth"))
            self.tree.column(column, stretch=False, width=width)
        
        self.text_font = nametofont("TkTextFont")
    
    def add(self, values, parent="", *args, **kw):
        child = self.tree.insert(parent, "end", *args,
            text=values[0], values=values[1:], **kw)
        if not self.tree.focus():
            self.tree.focus(child)
        
        for (i, value) in enumerate(values):
            if i:
                i = i - 1
            else:
                i = "#0"
            width = self.text_font.measure(value)
            if width > self.tree.column(i, option="width"):
                self.tree.column(i, width=width)
        
        return child
    
    def bind_select(self, *args, **kw):
        return self.tree.bind("<<TreeviewSelect>>", *args, **kw)
    def unbind_select(self, *args, **kw):
        return self.tree.unbind("<<TreeviewSelect>>", *args, **kw)

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
