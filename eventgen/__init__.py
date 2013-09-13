"""Support for event-driven generators

PEP 380 "Syntax for delegating to a subgenerator" ["yield from"]:
http://www.python.org/dev/peps/pep-0380

Similar generator wrapper implementation:
https://mail.python.org/pipermail/python-dev/2010-July/102320.html

"Weightless" looks rather up-to-date. It mentions PEP 380. But 0.6.0.1 apparently only compiles with Python 2.
http://www.weightless.io/
* Has a survey of other implementations
"""

import weakref
from functions import weakmethod
from sys import exc_info
import sys
from collections import deque
from functions import WrapperFunction
from functools import partial
from contextlib import contextmanager
from traceback import extract_stack
from warnings import warn

class Send(object):
    def __init__(self, value=None):
        self.value = value
    def result(self):
        return self.value
    def sendcall(self, gen):
        return partial(gen.send, self.value)
    def genresult(self):
        return StopIteration(self.value)
    def default(self):
        sys.displayhook(self.value)

class Throw(object):
    def __init__(self, *exc):
        try:
            (exc,) = exc
        except ValueError:
            self.exc = list(exc)
        else:
            self.exc = [type(exc), exc, getattr(exc, "__traceback__", None)]
    
    def with_traceback(self, tb):
        try:
            self.exc[1].with_traceback(tb)
        except AttributeError:
            pass
        self.exc[2] = tb
        return self
    
    def result(self):
        #~ # Hack to include traceback in Python 2:
        #~ raise self.exc[0], self.exc[1], self.exc[2]
        raise self.exc[1]
    def sendcall(self, gen):
        # Traceback from first parameter apparently ignored
        return partial(gen.throw, *self.exc)
    def genresult():
        #~ self.result()  # Python 2 hack
        return self.exc[1]
    def default(self):
        sys.excepthook(*self.exc)

class routine(WrapperFunction):
    """Decorator converting generator factory into Thread() factory"""
    def __call__(self, *args, **kw):
        return Thread(self.__wrapped__(*args, **kw))

class Thread(object):
    """Schedules the logical execution thread of an event-driven generator
    
    The generator can yield:
    * Event objects, which are waited on before continuing the coroutine
    * Generator sub-coroutines, which are executed to completion before the
    parent coroutine is continued
    """
    
    def __init__(self, routine, join=False):
        """
        join=True argument indicates that any exception raised or value
        returned from the coroutine should be saved and returned whenever the
        join() method is called. By default the result is passed to sys.
        excepthook() or sys.displayhook() instead.
        """
        
        self.result = join
        self.reapers = list()
        self.routines = [routine]
        with firedoor(self):
            self.trampoline(Send())
    
    @weakmethod
    def resume(self, result=Send()):
        self.event.close()
        self.trampoline(result)
    
    def trampoline(self, result):
        tb = None  # For seamless deletion at end
        self.event = None  # Create attribute and mark not active
        
        try:
            while self.routines:
                call = result.sendcall(self.routines[-1])
                try:
                    obj = call()
                except BaseException as e:
                    self.routines.pop()
                    if isinstance(e, StopIteration):
                        result = Send(*e.args)
                    else:
                        # Saving traceback creates circular reference
                        result = Throw(*exc_info())
                        
                        # Remove our throw or send call from traceback, but
                        # only if there is more traceback
                        tb = result.exc[2].tb_next
                        if tb:
                            result.with_traceback(tb)
                
                else:
                    if isinstance(obj, Event):
                        self.event = obj
                        self.event.block(self.resume)
                        return
                    elif isinstance(obj, Yield):
                        self.routines.pop()
                        result = Send(obj.send)
                    else:
                        self.routines.append(obj)
                        result = Send()
            
            if self.result:
                self.result = result
            else:
                result.default()
            for r in self.reapers:
                r()
        
        finally:
            # Break circular reference if traceback includes this function
            del tb
            del result
    
    def close(self):
        if self.event:
            self.event.close()
            self.event = None
        while self.routines:
            self.routines.pop().close()
    
    def __del__(self):
        if self.routines:
            warn(ResourceWarning("Thread {0!r} left running".format(self)))
            self.close()
    
    def join(self):
        if self.routines:
            r = Callback()
            self.reapers.append(r)
            yield r
        
        if self.result:
            raise self.result.genresult()
    
    def __repr__(self):
        return "<{0} {1:#x}>".format(type(self).__name__, id(self))
    
    def extract_stack(self, limit=None):
        stack = list()
        for routine in reversed(self.routines):
            new = extract_stack(routine.gi_frame, limit=limit)
            if limit is not None:
                limit -= len(new)
            stack = new + stack
            if limit is not None and not limit:
                break
        return stack

class Event(object):
    """Base class that a thread can yield to wait for an event
    
    The default implementation has a "callback" attribute which can be called
    to resume the thread. It is set to None when the event is not active."""
    
    def __init__(self):
        self.callback = None
    
    def block(self, callback):
        """Registers a callback to resume the thread
        
        The callback may be invoked from the context of another thread, but
        this involves recursive calls on the subroutine stack, so it should
        be limited."""
        
        self.callback = callback
    
    def close(self):
        """Cancel the effect of the block() call
        
        This is automatically called whenever the thread is resumed, or if
        the thread is closed without being resumed."""
        
        self.callback = None

class Yield(object):
    def __init__(self, send):
        self.send = send

class Callback(Event):
    """A simple event triggered by calling it
    """
    def __call__(self, *args):
        """
        Positional arguments passed to the callback are yielded from the
        event as a tuple
        """
        self.callback(Send(args))

class Queue(Event):
    """An event that may be triggered before it is armed (message queue)
    """
    def __init__(self):
        Event.__init__(self)
        self.queue = deque()
    
    def send(self, value=None):
        self.queue.append(dict(ret=value))
        if self.callback is not None:
            self.callback()
    
    def throw(self, exc):
        self.queue.append(dict(exc=exc))
        if self.callback is not None:
            self.callback()
    
    def __call__(self, *args):
        return self.send(args)
    
    def __iter__(self):
        return self
    
    def __next__(self):
        try:
            item = self.queue.popleft()
        except LookupError:
            raise StopIteration()
        
        try:
            exc = item["exc"]
        except LookupError:
            return item["ret"]
        else:
            raise exc
    next = __next__
    
    def __len__(self):
        """Return the number of messages waiting in the queue"""
        return len(self.queue)

class Select(Event):
    """An event triggered by any of a set of alternatives"""
    
    def __init__(self, set=()):
        Event.__init__(self)
        self.set = []
        for event in set:
            self.add(event)
    
    def add(self, event):
        self.set.append(Subevent(weakref.ref(self), event))
    
    def block(self, callback):
        Event.block(self, callback)
        try:
            for e in self.set:
                e.event.block(e.trigger)
        except:
            i = iter(self.set)
            while True:
                ee = next(i)
                if ee is e:
                    break
                ee.close()
            raise
    
    def close(self):
        for e in self.set:
            e.event.close()
        Event.close(self)
    
    def __repr__(self):
        return "{0}({1})".format(
            type(self).__name__, repr(self.set))

class Subevent(object):
    def __init__(self, set, event):
        self.set = set
        self.event = event
    
    @weakmethod
    def trigger(self, result=Send()):
        if not isinstance(result, Throw):
            result = Send((self.event, result.result()))
        self.set().callback(result)

class FileEvent(Event):
    def __init__(self, fd):
        Event.__init__(self)
        self.fd = fd
    def writable(self):
        self.watch((self.WRITE,))
        return self
    def readable(self):
        self.watch((self.READ,))
        return self

class constructor(object):
    """Decorator wrapper for classes whose __init__ method is a coroutine"""
    def __init__(self, cls):
        self.cls = cls
    def __call__(self, *args, **kw):
        o = self.cls.__new__(self.cls, *args, **kw)
        yield o.__init__(*args, **kw)
        raise StopIteration(o)

class Lock(object):
    def __init__(self):
        self.locked = False
        self.waiting = []
    def __call__(self):
        cascade = LockContext(self).cascade()
        
        if self.locked:
            our_turn = Callback()
            self.waiting.append(our_turn)
            yield our_turn
        with cascade:
            self.locked = True

class LockContext(object):
    def __init__(self, lock):
        self.lock = lock
    def  __enter__(self):
        pass
    def __exit__(self, *exc):
        try:
            next_turn = self.lock.waiting.pop()
        except LookupError:
            self.lock.locked = False
        else:
            next_turn()
    
    def cascade(self):
        """Return context manager that releases lock on exception, otherwise
        returns the context via StopIteration"""
        return LockCascade(self)

class LockCascade(object):
    def __init__(self, context):
        self.context = context
    def __enter__(self):
        pass
    def __exit__(self, *exc):
        if exc != (None, None, None):
            if not self.context.__exit__(*exc):
                return False
        raise StopIteration(self.context)

@contextmanager
def firedoor(handle):
    try:
        yield
    except:
        handle.close()
        raise
