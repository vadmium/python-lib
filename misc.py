import sys
import weakref
from os.path import basename
import os
from types import MethodType
from functools import partial
from contextlib import closing

try:
    from urllib.parse import (urlsplit, urlunsplit)
except ImportError:
    from urlparse import (urlsplit, urlunsplit)

try:
    from io import SEEK_CUR
except ImportError:
    SEEK_CUR = 1

class Function(object):
    def __init__(self):
        # By default, name the function after its class
        self.__name__ = type(self).__name__
    def __get__(self, obj, cls):
        if obj is None:
            return self
        return MethodType(self, obj)

class WrapperFunction(Function):
    from functools import (update_wrapper, WRAPPER_ASSIGNMENTS)
    def __init__(self, wrapped, assigned=WRAPPER_ASSIGNMENTS, *args, **kw):
        self.update_wrapper(wrapped, assigned, *args, **kw)
        if not hasattr(self, "__wrapped__"):  # Python 2 does not add this
            self.__wrapped__ = wrapped
        
        # Python 2 cannot assign these unless they are guaranteed to exist
        for name in {"__defaults__", "__code__"}.difference(assigned):
            try:
                value = getattr(wrapped, name)
            except AttributeError:
                continue
            setattr(self, name, value)
        
        try:
            self.__kwdefaults__ = wrapped.__kwdefaults__
        except AttributeError:
            pass

class deco_factory(WrapperFunction):
    """Decorator to create a decorator factory given a function taking the
    factory input and the object to be decorated"""
    def __call__(self, *args, **kw):
        return partial(self.__wrapped__, *args, **kw)

class exc_sink(Function):
    """Decorator wrapper to trap all exceptions raised from a function to the
    default exception hook"""
    def __init__(self, inner):
        self.inner = inner
    def __call__(self, *args, **kw):
        try:
            return self.inner(*args, **kw)
        except BaseException as e:
            sys.excepthook(type(e), e, e.__traceback__)

class weakmethod(object):
    """Decorator wrapper for methods that binds to objects using a weak
    reference"""
    def __init__(self, func):
        self.func = func
    def __get__(self, obj, cls):
        if obj is None:
            return self
        return WeakBinding(self.func, obj)
class WeakBinding(Function):
    def __init__(self, func, obj):
        self.func = func
        self.ref = weakref.ref(obj)
    def __call__(self, *args, **kw):
        obj = self.ref()
        if obj is None:
            raise ReferenceError("dead weakly-bound method {0} called".
                format(self.func))
        return self.func.__get__(obj, type(obj))(*args, **kw)
    def __repr__(self):
        return "<{0} of {1} to {2}>".format(
            type(self).__name__, self.func, self.ref())

def gen_repr(gi):
    f = gi.gi_frame
    if f:
        return "<{0} {1:#x}, {2}:{3}>".format(f.f_code.co_name, id(gi),
            basename(f.f_code.co_filename), f.f_lineno)
    else:
        return "<{0} {1:#x} (inactive)>".format(gi.gi_code.co_name,
            id(gi))

def transplant(path, old="/", new=""):
    path_dirs = path_split(path)
    for root_dir in path_split(old):
        try:
            path_dir = next(path_dirs)
        except StopIteration:
            if not path and root_dir == "/":
                raise ValueError("Null path not relative to {0}".format(old))
            else:
                raise ValueError(
                    "{0} is an ancestor of {1}".format(path, old))
        if path_dir != root_dir:
            raise ValueError("{0} is not relative to {1}".format(path, old))
    
    return os.path.join(new, "/".join(path_dirs))

def path_split(path):
    if os.path.isabs(path):
        yield "/"
    
    for component in path.split("/"):
        if component:
            yield component

def url_port(url, scheme, ports):
    """Raises "ValueError" if the URL is not valid"""
    
    parsed = urlsplit(url, scheme=scheme)
    if not parsed.hostname:
        parsed = urlsplit("//" + url, scheme=scheme)
    if not parsed.hostname:
        raise ValueError("No host name specified: {0!r}".format(url))
    
    try:
        def_port = ports[parsed.scheme]
    except LookupError:
        raise ValueError("Unhandled scheme: {0}".format(parsed.scheme))
    port = parsed.port
    if port is None:
        port = def_port
    path = urlunsplit(("", "", parsed.path, parsed.query, parsed.fragment))
    return dict(scheme=parsed.scheme, hostname=parsed.hostname, port=port,
        path=path, username=parsed.username, password=parsed.password)

class Context(object):
    def __enter__(self):
        return self
    def __exit__(self, *exc):
        return False

class CloseAll(closing):
    def __init__(self):
        closing.__init__(self, self)
        self.set = []
    
    def close(self, *exc):
        while self.set:
            self.set.pop().close()
    
    def add(self, handle):
        self.set.append(handle)
