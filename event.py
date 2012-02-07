# PEP 380 "Syntax for delegating to a subgenerator" [yield from]:
# http://www.python.org/dev/peps/pep-0380

# Similar generator wrapper implementation:
# http://mail.python.org/pipermail/python-dev/2010-July/102320.html

# "Weightless" looks rather up-to-date. It mentions PEP 380. But 0.6.0.1
# apparently only compiles with Python 2.
# http://www.weightless.io/

import weakref
from lib import weakmethod
from sys import exc_info
from lib import Record
from sys import (displayhook, excepthook)

class Routine(object):
    """
    Runs an event-driven co-routine implemented as a generator. The generator
    can yield:
    + Event objects, which are waited on before continuing the co-routine
    + Generator sub-co-routines, which are executed to completion before the
    parent co-routine is continued
    """
    
    def __init__(self, routine, result=False):
        self.result = result
        self.reapers = list()
        self.routines = [routine]
        try:
            self.bump()
        except:
            self.close()
            raise
    
    @weakmethod
    def wakeup(self, *args, **kw):
        self.event.close()
        self.bump(*args, **kw)
    
    def bump(self, send=None, exc=None):
        if exc is not None:
            try:
                tb = exc.__traceback__
            except AttributeError:
                tb = None
            exc = (type(exc), exc, tb)
        
        try:
            while self.routines:
                current = self.routines[-1]
                try:
                    if exc:
                        # Traceback from first parameter apparently ignored
                        obj = current.throw(*exc)
                    else:
                        obj = current.send(send)
                except BaseException as e:
                    self.routines.pop()
                    if isinstance(e, StopIteration):
                        exc = None
                        if e.args:
                            send = e.args[0]
                        else:
                            send = None
                    else:
                        # Saving traceback creates circular reference
                        # Remove our throw or send call from traceback
                        tb = exc_info()[2].tb_next
                        if hasattr(e, "__traceback__"):
                            e.__traceback__ = tb
                        exc = (type(e), e, tb)
                else:
                    if isinstance(obj, Event):
                        self.event = obj
                        self.event.arm(self.wakeup)
                        return
                    else:
                        self.routines.append(obj)
                        exc = None
                        send = None
            
            if not self.result:
                if exc:
                    excepthook(*exc)
                else:
                    displayhook(send)
            
            if exc:
                self.result = exc
            else:
                self.result = (None, StopIteration(send), None)
            
            for r in self.reapers:
                r()
        
        finally:
            # Break circular reference if traceback includes this function
            del exc
    
    def close(self):
        if self.routines:
            self.event.close()
            while self.routines:
                self.routines.pop().close()
    
    __del__ = close
    
    def join(self):
        if self.routines:
            r = Callback()
            self.reapers.append(r)
            yield r
        
        raise self.result[1]
        
        #~ # Alternative for Python 2, to include traceback
        #~ raise self.result[0], self.result[1], self.result[2]
    
    def __repr__(self):
        return "<{0} {1:#x}>".format(type(self).__name__, id(self))

class Group(object):
    def __init__(self):
        self.set = set()
    
    def add(self, routine):
        self.set.add(routine)
    
    def close(self):
        while self.set:
            self.set.pop().close()

class Event(object):
    """Base class for events that a co-routine can wait on by yielding"""
    def __init__(self):
        self.callback = None
    
    def arm(self, callback):
        """Registers an object to call when the event is triggered"""
        self.callback = callback
    
    def close(self):
        """Cancel the effect of the "arm" method call"""
        self.callback = None

class Callback(Event):
    """
    A simple event triggered by calling it.
    """
    def __call__(self, *args):
        """Any arguments passed to the callback are yielded from the event as
        a tuple
        """
        self.callback(args)

class Queue(Event):
    """
    An event that may be triggered before it is armed (message queue).
    """
    def __init__(self):
        Event.__init__(self)
        self.queue = list()
    
    def send(self, value=None):
        self.queue.append(Record(exc=None, ret=value))
        if self.callback is not None:
            self.callback()
    
    def throw(self, exc):
        self.queue.append(Record(exc=exc))
        if self.callback is not None:
            self.callback()
    
    def __call__(self, *args):
        return self.send(args)
    
    def __iter__(self):
        return self
    
    def __next__(self):
        try:
            item = self.queue.pop(0)
        except LookupError:
            raise StopIteration()
        
        if item.exc is None:
            return item.ret
        else:
            raise item.exc
    next = __next__
    
    def __len__(self):
        """Return the number of messages waiting in the queue"""
        return len(self.queue)

class Any(Event):
    """
    A composite event that is triggered by any sub-event in a set
    """
    
    def __init__(self, set=()):
        Event.__init__(self)
        self.set = []
        for event in set:
            self.add(event)
    
    def add(self, event):
        self.set.append(Subevent(weakref.ref(self), event))
    
    def arm(self, callback):
        Event.arm(self, callback)
        try:
            for e in self.set:
                e.event.arm(e.trigger)
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
        return "<{0}([{1}])>".format(
            type(self).__name__, ", ".join(str(e.event) for e in self.set))

class Subevent(object):
    def __init__(self, set, event):
        self.set = set
        self.event = event
    
    @weakmethod
    def trigger(self, send=None, exc=None):
        self.set().callback(send=(self.event, send), exc=exc)

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
