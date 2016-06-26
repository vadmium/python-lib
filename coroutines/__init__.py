"""Framework for driving async coroutine tasks"""

import weakref
from functions import weakmethod
from collections import deque
from functions import WrapperFunction
from contextlib import contextmanager
from traceback import extract_stack
from warnings import warn
from .results import ReturnResult, RaiseResult, call_result
import asyncio
from asyncio.base_events import BaseEventLoop
from functools import partial

class EventLoop(BaseEventLoop):
    def __init__(self, *pos, **kw):
        super().__init__(*pos, **kw)
        self.callbacks = dict()  # {None: [callbacks]}
    
    def call_soon(self, callback, *pos, **kw):
        # Cannot call back immediately because some call sites assume the
        # callback is not yet invoked when this function returns
        new = list()
        queue = self.callbacks.setdefault(None, new)
        queue.append(partial(callback, *pos, **kw))
        if queue is new:
            self.new_callbacks()
    def call_soon_threadsafe(self, *pos, **kw):
        return self.call_soon(*pos, **kw)
    
    def invoke_callbacks(self):
        callbacks = self.callbacks.pop(None)
        for callback in callbacks:
            callback()
    
    def run_until_complete(self, future):
        future = asyncio.ensure_future(future, loop=self)
        future.add_done_callback(self._stop_callback)
        self.run_forever()
        return future.result()
    
    def _stop_callback(self, future):
        return self.stop()

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
            self.trampoline(_startresult)
    
    @weakmethod
    def resume(self, result=ReturnResult()):
        self.event.close()
        self.trampoline(result)
    
    def trampoline(self, result):
        while self.routines:
            call = result.resume_call(self.routines[-1])
            result = Result.from_call(call)
            
            if isinstance(result, RaiseResult):
                self.routines.pop()
                if isinstance(result.exception(), StopIteration):
                    result = ReturnResult(*result.exception().args)
            
            elif isinstance(result, ReturnResult):
                if isinstance(result.result(), Event):
                    self.event = result.result()
                    self.event.block(self.resume)
                    return
                else:
                    self.routines.append(result.result())
                    result = _startresult
        
        if self.result:
            self.result = result
        else:
            result.display()
        self.close()
    
    def close(self):
        if self.routines:
            self.event.close()
            while self.routines:
                self.routines.pop().close()
        while self.reapers:
            self.reapers.pop()()
    
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
            raise self.result.exit_generator()
    
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

# Imitation Result object to start a generator by invoking send(None)
_startresult = ReturnResult(None)

class MainTask(asyncio.Task):
    """Task that is not expected to return a value or exception"""
    
    def __init__(self, *pos, loop, **kw):
        asyncio.Task.__init__(self, *pos, loop=loop, **kw)
        self.loop = loop
        self.add_done_callback(type(self)._on_done)
    
    def _on_done(self):
        exc = self.exception()
        if exc:
            self.loop.call_exception_handler(dict(
                message="Exception in {!r}".format(self),
                exception=exc,
            ))

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

class AsyncioGenerator:
    def next(self, generator):
        self.yielding = False
        for result in generator:
            if self.yielding:
                return result
            yield result
    
    def generate(self, value=None):
        self.yielding = True
        yield value

class Callback(Event):
    """A simple event triggered by calling it
    """
    def __call__(self, *args):
        """
        Positional arguments passed to the callback are yielded from the
        event as a tuple
        """
        self.callback(ReturnResult(args))

class Queue(Event):
    """An event that may be triggered before it is armed (message queue)
    """
    def __init__(self):
        Event.__init__(self)
        self.queue = deque()
    
    def send(self, value=None):
        self.queue.append(ReturnResult(value))
        if self.callback is not None:
            self.callback()
    
    def throw(self, exc):
        self.queue.append(RaiseResult(exc))
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
        return item.result()
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
            for (i, e) in enumerate(self.set):
                e.event.block(e.trigger)
        except:
            for e in self.set[:i]:
                e.event.close()
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
    def trigger(self, result=ReturnResult()):
        if isinstance(result, ReturnResult):
            result = ReturnResult((self.event, result.result()))
        self.set().callback(result)

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
