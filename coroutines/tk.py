from functools import reduce
import operator
from math import ceil
from . import Event
from functions import weakmethod
from warnings import warn
from . import EventLoop as _EventLoop
from traceback import format_exception
import tkinter
from tkwrap import scroll
from functools import partial

class EventLoop(_EventLoop):
    def __init__(self, widget):
        super().__init__()
        self._widget = widget
        self._filehandlers = dict()
    
    def run_forever(self):
        self._widget.mainloop()
    
    def new_callbacks(self):
        self._widget.after_idle(self.invoke_callbacks)
    
    def stop(self):
        self._widget.quit()
    
    def default_exception_handler(self, context):
        super().default_exception_handler(context)
        
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
    
    def add_reader(self, *pos, **kw):
        return self._add_filehandler(tkinter.READABLE, *pos, **kw)
    def add_writer(self, *pos, **kw):
        return self._add_filehandler(tkinter.WRITABLE, *pos, **kw)
    def _add_filehandler(self, mask, fd, callback, *pos, **kw):
        callbacks = self._filehandlers.setdefault(fd, dict())
        if callbacks:
            self._widget.tk.deletefilehandler(fd)
        callbacks[mask] = partial(callback, *pos, **kw)
        mask = reduce(operator.or_, callbacks.keys())
        self._widget.tk.createfilehandler(fd, mask, self._filehandler)
    
    def remove_reader(self, *pos, **kw):
        return self._remove_filehandler(tkinter.READABLE, *pos, **kw)
    def remove_writer(self, *pos, **kw):
        return self._remove_filehandler(tkinter.WRITABLE, *pos, **kw)
    def _remove_filehandler(self, mask, fd):
        callbacks = self._filehandlers[fd]
        del callbacks[mask]
        if not callbacks:
            self._widget.tk.deletefilehandler(fd)
            del self._filehandlers[fd]
    
    def _filehandler(self, fd, mask):
        self._widget.tk.deletefilehandler(fd)
        callbacks = self._filehandlers.pop(fd)
        for (cbmask, callback) in callbacks.items():
            if mask & cbmask:
                callback()

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
            warn(ResourceWarning("Timer {!r} left running".format(self)),
                stacklevel=2)
            self.stop()
