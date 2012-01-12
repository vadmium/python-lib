from functools import partial
from functools import reduce
from operator import or_
from math import ceil
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

class FileWatcher(object):
    def __init__(self, widget, fd, callback):
        self.widget = widget
        self.fd = fd
        self.callback = callback
    
    def watch(self, ops):
        self.widget.tk.createfilehandler(self.fd, reduce(or_, ops),
            self.handler)
    
    def destroy(self):
        self.widget.tk.deletefilehandler(self.fd)
    
    def handler(self, fd, mask):
        self.callback(fd, mask)

class Timer(object):
    def __init__(self, widget, callback):
        self.widget = widget
        self.callback = callback
    
    def start(self, timeout):
        self.timer = self.widget.after(ceil(timeout * 1000), self.callback)
    
    def stop(self):
        self.widget.after_cancel(self.timer)
