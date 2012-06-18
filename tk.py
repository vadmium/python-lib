from functools import partial
from functools import reduce
from operator import or_
from math import ceil
from . import event
from lib import Record
import tkinter
from tkinter.ttk import Label

def add_field(window, row, label, widget):
    Label(window, text=label).grid(
        row=row, column=0, sticky=tkinter.E + tkinter.W)
    widget.grid(row=row, column=1, sticky=tkinter.E + tkinter.W)

def treeview_add(tree, item, *args, **kw):
    return tree.insert(item, "end", *args, **kw)

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
