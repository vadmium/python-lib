from functools import reduce
from operator import or_
from math import ceil
from . import (FileEvent as BaseFileEvent, Event)
from . import Send
from functions import weakmethod
from warnings import warn
from asyncio.base_events import BaseEventLoop
from traceback import format_exception
import tkinter
from tkwrap import scroll
from functools import partial

class EventLoop(BaseEventLoop):
    def base_init(self):
        BaseEventLoop.__init__(self)
        self.callbacks = None
    
    def call_soon(self, callback, *pos, **kw):
        if not self.callbacks:
            self.callbacks = list()
            self.new_callbacks()
        self.callbacks.append(partial(callback, *pos, **kw))
    call_soon_threadsafe = call_soon
    
    def invoke_callbacks(self):
        callbacks = self.callbacks
        self.callbacks = None
        for callback in callbacks:
            callback()
    
    def __init__(self, widget):
        self.base_init()
        self._widget = widget
    
    def run_forever(self):
        self._widget.mainloop()
    
    def new_callbacks(self):
        self._widget.after_idle(self.invoke_callbacks)
    
    def default_exception_handler(self, context):
        BaseEventLoop.default_exception_handler(self, context)
        
        lines = list()
        lines.append(context.pop("message"))
        exc = context.pop("exception")
        for item in sorted(context.items()):
            lines.append("{}={!r}".format(*item))
        exc = "".join(format_exception(type(exc), exc, exc.__traceback__))
        lines.append(exc.rstrip())
        
        window = tkinter.Toplevel(self._widget)
        window.title("Exception")
        text = tkinter.Text(window, wrap="word")
        scroll(text)
        text.focus_set()
        text.insert(tkinter.END, "\n".join(lines))
        text.see(tkinter.END)
        text["state"] = tkinter.DISABLED

class FileEvent(BaseFileEvent):
    READ = tkinter.READABLE
    WRITE = tkinter.WRITABLE
    
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
