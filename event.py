class Routine:
    """
    Runs an event-driven co-routine implemented as a generator. The generator
    can yield:
    + Event objects, which are waited on before continuing the co-routine
    + Generator sub-co-routines, which are executed to completion before the
    parent co-routine is continued
    """
    
    def __init__(self, routine):
        #~ print(self, "*")
        self.routines = [routine]
        self.bump()
    
    def bump(self, *args):
        call = Send(*args)
        
        try:
            while self.routines:
                try:
                    obj = call(self.routines[-1])
                except StopIteration as stop:
                    self.routines.pop()
                    call = Send(*stop.args)
                except BaseException as e:
                    self.routines.pop()
                    call = Throw(e)
                else:
                    if isinstance(obj, Event):
                        obj.arm(self.bump)
                        return
                    else:
                        self.routines.append(obj)
                        call = Send()
            
            return call.close()
        finally:
            # Break circular reference if call references exception traceback
            del call

class Send:
    def __init__(self, arg=None):
        self.arg = arg
    def __call__(self, routine):
        return routine.send(self.arg)
    def close(self):
        return self.arg

class Throw:
    def __init__(self, exc):
        self.exc = exc
    def __call__(self, routine):
        # Traceback already in the exception object apparently ignored
        return routine.throw(self.exc, None, self.exc.__traceback__)
    def close(self):
        raise self.exc

class Event:
    """
    Base class for events that a co-routine can wait on by yielding.
    Subclasses should provide an Event.arm(callback) method which registers
    an object to call when the event is triggered.
    """
    pass

class Queue(Event):
    """
    An event that may be triggered before it is armed.
    """
    def __init__(self):
        self.callback = None
        self.queue = []
    
    def arm(self, callback):
        self.callback = callback
    
    def put(self, arg=None):
        callback = self.callback
        if callback:
            self.callback = None
            callback(arg)
        else:
            self.queue.append(arg)
    
    def get(self):
        """
        Sub-co-routine that will wait for the event to be triggered if there
        are no triggered events already pending.
        """
        try:
            raise StopIteration(self.queue.pop(0))
        except IndexError:
            raise StopIteration((yield self))

#~ class Callback(Event):
    #~ """
    #~ An Event object that is callable.
    #~ """
    #~ def arm(self, callback):
        #~ self.callback = callback
    #~ def __call__(self, *args, **kw):
        #~ self.callback(*args, **kw)
