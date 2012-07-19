from functools import partial
from functools import reduce
from operator import or_
from math import ceil
from . import event
from lib import Record
import tkinter
from tkinter.ttk import Label

def add_field(window, label, widget, multiline=False, **kw):
    label_sticky = [tkinter.E, tkinter.W]
    widget_sticky = [tkinter.E, tkinter.W]
    if multiline:
        label_sticky.append(tkinter.N)
        widget_sticky.extend((tkinter.N, tkinter.S))
    
    label = Label(window, text=label)
    label.grid(column=0, sticky=label_sticky, **kw)
    row = label.grid_info()["row"]
    if multiline:
        window.rowconfigure(row, weight=1)
    widget.grid(row=row, column=1, sticky=widget_sticky, **kw)

def treeview_add(tree, parent="", *args, **kw):
    child = tree.insert(parent, "end", *args, **kw)
    if not tree.focus():
        tree.focus(child)
    return child

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
