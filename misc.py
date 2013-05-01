import sys
import weakref
from os.path import basename
import os
from types import MethodType
from functools import partial

class Function(object):
    def __init__(self, name=None):
        # By default, name the function after its class
        self.__name__ = name or type(self).__name__
    def __get__(self, obj, cls=None):
        if obj is None:
            return self
        return MethodType(self, obj)

class WrapperFunction(Function):
    from functools import (update_wrapper, WRAPPER_ASSIGNMENTS)
    def __init__(self, wrapped, assigned=WRAPPER_ASSIGNMENTS, *args, **kw):
        self.update_wrapper(wrapped, assigned, *args, **kw)
        
        # Python 2 does not add this, and Python 3 overwrites it with
        # wrapped.__wrapped__ when updating self.__dict__
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
    
    def __get__(self, *pos, **kw):
        binding = self.__wrapped__.__get__(*pos, **kw)
        # Avoid Python 2's unbound methods, with __self__ = None
        if binding is self.__wrapped__ or binding.__self__ is None:
            return self
        else:
            return type(binding)(self, binding.__self__)

def wrap_import():
    global installed_wrapper
    if installed_wrapper:
        return
    wrapper = ImportWrapper(__import__)
    wrapper("builtins").__import__ = wrapper
    installed_wrapper = wrapper

installed_wrapper = None

class ImportWrapper(WrapperFunction):
    fixups = dict()
    
    def __init__(self, *pos, **kw):
        WrapperFunction.__init__(self, *pos, **kw)
        self.interested = set(self.fixups.keys())
    
    def __call__(self, name, globals={}, locals={}, fromlist=None,
    level=None):
        if level is None or level <= 0:
            path = name.split(".")
            for i in range(len(path)):
                self.fix(".".join(path[:i + 1]), globals, locals, level=0)
            
            for attr in fromlist or ():
                attr = "{}.{}".format(name, attr)
                self.fix(attr, globals, locals, level=0)
        
        # Actual default value of "level" changed in Python 3
        if level is None:
            return self.__wrapped__(name, globals, locals, fromlist)
        else:
            return self.__wrapped__(name, globals, locals, fromlist, level)
    
    def fix(self, name, *pos, **kw):
        if name not in self.interested:
            return
        self.interested.remove(name)
        self.fixups[name](self, *pos, **kw)
    
    @partial(fixups.__setitem__, "builtins")
    def _(self, *pos, **kw):
        try:
            self.__wrapped__("builtins", *pos, **kw)
        except ImportError:
            builtin = self.__wrapped__("__builtin__", *pos, **kw)
            sys.modules["builtins"] = builtin
    
    @partial(fixups.__setitem__, "io")
    def _(self, *pos, **kw):
        io = self.__wrapped__("io", *pos, **kw)
        if not hasattr(io, "SEEK_CUR"):
            io.SEEK_CUR = self.__wrapped__("os", *pos, **kw).SEEK_CUR
    
    @partial(fixups.__setitem__, "urllib.parse")
    def _(self, *pos, **kw):
        try:
            urllib = self.__wrapped__("urllib.parse", *pos, **kw)
        except ImportError:
            urlparse = self.__wrapped__("urlparse", *pos, **kw)
            sys.modules["urllib"].parse = urlparse
            sys.modules["urllib.parse"] = urlparse

wrap_import()

from urllib.parse import (urlsplit, urlunsplit)

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

class WeakBinding(object):
    def __init__(self, func, obj):
        self.__func__ = func
        self.ref = weakref.ref(obj)
    
    @property
    def __self__(self):
        obj = self.ref()
        if obj is None:
            raise ReferenceError("weakly bound instance to method {0!r} "
                "no longer exists".format(self.__func__))
        return obj
    
    def __call__(self, *args, **kw):
        obj = self.__self__
        return self.__func__.__get__(obj, type(obj))(*args, **kw)
    
    def __repr__(self):
        return "<{0} of {1} to {2}>".format(
            type(self).__name__, self.__func__, self.ref())

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
        self.close()

class CloseAll(Context):
    def __init__(self):
        self.set = []
    
    def close(self):
        while self.set:
            self.set.pop().close()
    
    def add(self, handle):
        self.set.append(handle)
