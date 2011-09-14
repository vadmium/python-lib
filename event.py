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

def Routine(routine, group=None):
    """
    Runs an event-driven co-routine implemented as a generator. The generator
    can yield:
    + Event objects, which are waited on before continuing the co-routine
    + Generator sub-co-routines, which are executed to completion before the
    parent co-routine is continued
    """
    
    if group is None:
        group = Group()
    RoutineCls(routine, group)
    return group

class RoutineCls:
    def __init__(self, routine, group):
        self.routines = [routine]
        self.group = weakref.ref(group)
        self.group().set.add(self)
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
                try:
                    current = self.routines[-1]
                    if exc:
                        # Traceback from first parameter apparently ignored
                        obj = current.throw(*exc)
                    elif send is not None:
                        obj = current.send(send)
                    else:
                        obj = next(current)
                except BaseException as e:
                    self.routines.pop()
                    if isinstance(e, StopIteration):
                        exc = None
                        if e.args:
                            send = e.args[0]
                        else:
                            send = None
                    else:
                        # Saving exception creates circular reference
                        exc = exc_info()
                else:
                    if isinstance(obj, Event):
                        self.event = obj
                        self.event.arm(self.wakeup)
                        return
                    else:
                        self.routines.append(obj)
                        exc = None
                        send = None
            
            self.close()
            if exc:
                raise exc[1]
                
                #~ # Alternative for Python 2, to include traceback
                #~ raise exc[0], exc[1], exc[2]
            else:
                return send
        finally:
            # Break circular reference if traceback includes this function
            del exc
    
    def close(self):
        if self.routines:
            self.event.close()
            while self.routines:
                self.routines.pop().close()
        try:
            self.group().set.remove(self)
        except (ReferenceError, LookupError):
            pass
    
    __del__ = close
    
    def __repr__(self):
        return "<{} {:#x}>".format(type(self).__name__, id(self))

class Group:
    def __init__(self):
        self.set = set()
    def close(self):
        for i in list(self.set):
            i.close()

class Event:
    """
    Base class for events that a co-routine can wait on by yielding.
    Subclasses should provide an Event.arm(callback) method which registers
    an object to call when the event is triggered.
    """
    
    def close(self):
        pass

class constructor:
    """Decorator wrapper for classes whose __init__ method is a coroutine"""
    def __init__(self, cls):
        self.cls = cls
    def __call__(self, *args, **kw):
        o = self.cls.__new__(self.cls, *args, **kw)
        yield o.__init__(*args, **kw)
        raise StopIteration(o)

class Queue(Event):
    """
    An event that may be triggered before it is armed.
    """
    def __init__(self):
        self.callback = None
        self.queue = []
    
    def arm(self, callback):
        self.callback = callback
    
    def close(self):
        self.callback = None
    
    def put(self, value=None, exc=None):
        if self.callback is not None:
            print(value, exc)
            self.callback(send=value, exc=exc)
        else:
            if exc is None:
                exc = StopIteration(value)
            self.queue.append(exc)
    
    def get(self):
        """
        Sub-co-routine that will wait for the event to be triggered if there
        are no triggered events already pending.
        """
        try:
            exc = self.queue.pop(0)
        except IndexError:
            pass # Avoid yielding in exception handler
        else:
            raise exc
        raise StopIteration((yield self))

class EventSet(Event):
    """
    A composite event that is triggered by any sub-event in a set
    """
    
    def __init__(self, set=()):
        self.set = []
        for event in set:
            self.add(event)
    
    def add(self, event):
        self.set.append(Subevent(weakref.ref(self), event))
    
    def arm(self, callback):
        self.callback = callback
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
    
    def __repr__(self):
        return "<{}([{}])>".format(
            type(self).__name__, ", ".join(str(e.event) for e in self.set))

class Subevent:
    def __init__(self, set, event):
        self.set = set
        self.event = event
    
    @weakmethod
    def trigger(self, args):
        self.set().callback((self.event, args))
