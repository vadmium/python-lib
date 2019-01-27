import sys
from functools import partial

class Result:
    """Base class for abstracting function call and expression results
    
    Abstract methods:
    
    result(): Returns an ordinary return value or raises an exception. Usage:
            return result.result()
    resume_call(generator): Returns callable that resumes a generator.
        Separating the final call allows finer-grained exception handling,
        and can reduce the size of tracebacks. Usage:
            call = result.resume_call(generator)
            call()
    exit_generator(): Returns or raises an exception to exit a generator
        with. Usage:
            raise result.exit_generator()
        Equivalent Python 3.3 code:
            return result.result()
    display(): Reports the result as for interactive sessions.
    """
    
    def send_to(self, generator):
        """Resumes generator with result and returns next yielded value"""
        call = self.resume_call(generator)
        return call()

class ReturnResult(Result):
    """Normal function call or expression return value"""
    def __init__(self, value=None):
        self.value = value
    def result(self):
        return self.value
    def resume_call(self, generator):
        return partial(generator.send, self.value)
    def exit_generator(self):
        return StopIteration(self.value)
    def display(self):
        return sys.displayhook(self.value)
    def __repr__(self):
        return "{}({!r})".format(type(self).__name__, self.value)

class RaiseResult(Result):
    """Exception result of function call or expression"""
    
    def __init__(self, exc):
        self._exc = exc
        
        # Traceback attribute available since Python 3
        self._traceback = getattr(self.exception, "__traceback__", None)
    
    @classmethod
    def from_exc_info(cls):
        (_, value, traceback) = sys.exc_info()
        result = cls(value)
        result.traceback = traceback
        return result
    
    def exception(self):
        return self._exc
    def triple(self):
        return (type(self.exception()), self.exception(), self.traceback)
    
    @property
    def traceback(self):
        return self._traceback
    @traceback.setter
    def traceback(self, traceback):
        try:
            self._exc.with_traceback(traceback)
        except AttributeError:
            pass
        self._traceback = traceback
    
    if hasattr(BaseException, "__traceback__"):  # Python 3
        def result(self):
            raise self.exception()
        def exit_generator(self):
            return self.exception()
    else:  # Python < 3
        # Multi-argument raise syntax not allowed in Python 3
        exec("""\
def result(self):
    raise self._exc, None, self._traceback
def exit_generator(self):
    # Raise directly so that traceback is included
    raise self._exc, None, self._traceback
""")
    
    def resume_call(self, generator):
        return partial(generator.throw, *self.triple())
    def display(self):
        return sys.excepthook(*self.triple())
    def __repr__(self):
        return "{}({!r})".format(type(self).__name__, self.exception())
    
    def generator_result(self):
        if isinstance(self.exception(), StopIteration):
            return ReturnResult(*self.exception().args)
        else:
            return self

def call_result(call, *pos, **kw):
    exception = kw.pop("exception", BaseException)
    try:
        value = call(*pos, **kw)
    except exception:
        result = None
        try:
            result = RaiseResult.from_exc_info()
            
            # Remove our call from traceback if there are others
            traceback = result.traceback.tb_next
            if traceback:
                result.traceback = traceback
            
            return result
        finally:
            del result  # Traceback may reference this frame
    else:
        return ReturnResult(value)
