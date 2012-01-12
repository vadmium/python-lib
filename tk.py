from functools import partial
from functools import reduce
from operator import or_
from math import ceil
from . import event
import tkinter
from tkinter.ttk import Label

def add_field(window, row, label, widget):
    Label(window, text=label).grid(
        row=row, column=0, sticky=tkinter.E + tkinter.W)
    widget.grid(row=row, column=1, sticky=tkinter.E + tkinter.W)

class EventDriver(object):
    from tkinter import (READABLE as READ, WRITABLE as WRITE)
    
    def __init__(self, tk):
        self.tk = tk
    
    def FileWatcher(self, *args, **kw):
        return FileWatcher(self.tk, *args, **kw)
    
    def Timer(self, *args, **kw):
        return Timer(self.tk, *args, **kw)

class FileWatcher(event.Event):
    def __init__(self, widget, fd):
        self.tk = widget.tk
        self.fd = fd
        event.Event.__init__(self)
    
    def watch(self, ops):
        self.ops = reduce(or_, ops)
    
    def arm(self, *args, **kw):
        event.Event.arm(self, *args, **kw)
        self.tk.createfilehandler(self.fd, self.ops, self.handler)
    
    def close(self, *args, **kw):
        self.tk.deletefilehandler(self.fd)
        event.Event.close(self, *args, **kw)
    
    def handler(self, fd, mask):
        if self.callback is not None:
            return self.callback((fd, set(op for op in
                (EventDriver.READ, EventDriver.WRITE) if mask & op)))

class Timer(event.Event):
    def __init__(self, widget):
        self.widget = widget
        event.Event.__init__(self)
        self.timer = None
    
    def start(self, timeout):
        self.timer = self.widget.after(ceil(timeout * 1000), self.handler)
    
    def stop(self):
        self.widget.after_cancel(self.timer)
    
    def handler(self):
        if self.callback is not None:
            return self.callback()
