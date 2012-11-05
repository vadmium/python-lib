from functools import reduce
from operator import or_
from math import ceil
from . import (FileEvent as BaseFileEvent, Event)
from collections import namedtuple
from . import Send
from misc import weakmethod
from warnings import warn

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

def Driver(widget):
    # Create subclasses with "widget" as a member that inherit from the
    # driver classes defined below
    return DriverType(
        FileEvent=type(FileEvent.__name__, (FileEvent,), locals()),
        Timer=type(Timer.__name__, (Timer,), locals()),
    )
DriverType = namedtuple(Driver.__name__, "FileEvent, Timer")

class FileEvent(BaseFileEvent):
    from tkinter import (READABLE as READ, WRITABLE as WRITE)
    
    def __init__(self, *args, **kw):
        self.tk = self.widget.tk
        BaseFileEvent.__init__(self, *args, **kw)
    
    def watch(self, ops):
        self.ops = reduce(or_, ops)
    
    def arm(self, *args, **kw):
        BaseFileEvent.arm(self, *args, **kw)
        self.tk.createfilehandler(self.fd, self.ops, self.handler)
    
    def close(self, *args, **kw):
        self.tk.deletefilehandler(self.fd)
        BaseFileEvent.close(self, *args, **kw)
    
    def handler(self, fd, mask):
        trigger = set(op for op in (self.READ, self.WRITE) if mask & op)
        return self.callback(Send((fd, trigger)))

class Timer(Event):
    def __init__(self):
        Event.__init__(self)
        self.timer = None
    
    def start(self, timeout):
        self.timer = self.widget.after(ceil(timeout * 1000), self.handler)
    
    def stop(self):
        self.widget.after_cancel(self.timer)
        self.timer = None
    
    @weakmethod
    def handler(self):
        return self.callback()
    
    def __del__(self):
        if self.timer:
            warn(ResourceWarning("Timer {0!r} left running".format(self)),
                stacklevel=2)
            self.stop()
