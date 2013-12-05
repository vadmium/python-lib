from functools import reduce
from operator import or_
from math import ceil
from . import (FileEvent as BaseFileEvent, Event)
from . import Send
from functions import weakmethod
from warnings import warn
from asyncio.base_events import BaseEventLoop

class EventLoop(BaseEventLoop):
    def call_soon(self, callback, *pos, **kw):
        return callback(*pos, **kw)
    
    def __init__(self, widget):
        BaseEventLoop.__init__(self)
        self._widget = widget
    
    def run_forever(self):
        self._widget.mainloop()

class FileEvent(BaseFileEvent):
    from tkinter import (READABLE as READ, WRITABLE as WRITE)
    
    def __init__(self, *args, **kw):
        self.tk = self.widget.tk
        BaseFileEvent.__init__(self, *args, **kw)
    
    def watch(self, ops):
        self.ops = reduce(or_, ops)
    
    def block(self, *args, **kw):
        BaseFileEvent.block(self, *args, **kw)
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
