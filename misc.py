import sys
from os.path import basename
import os
from functools import partial
from functions import Function, WrapperFunction

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
    
    @partial(fixups.__setitem__, "reprlib")
    def _(self, *pos, **kw):
        try:
            self.__wrapped__("reprlib", *pos, **kw)
        except ImportError:
            sys.modules["reprlib"] = self.__wrapped__("repr", *pos, **kw)
    
    @partial(fixups.__setitem__, "types")
    def _(self, *pos, **kw):
        types = self.__wrapped__("types", *pos, **kw)
        if not hasattr(types, "InstanceType"):
            types.InstanceType = object
        if not hasattr(types, "ClassType"):
            types.ClassType = type
    
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
