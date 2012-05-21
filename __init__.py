import sys
import weakref
from os.path import basename
from sys import modules
from sys import argv
import os
from types import MethodType
from functools import partial

try:
    from urllib.parse import (urlsplit, urlunsplit)
except ImportError:
    from urlparse import (urlsplit, urlunsplit)

try:
    import builtins
except ImportError:
    import __builtin__ as builtins

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

class deco_factory(Function):
    """Decorator to create a decorator factory given a function taking the
    factory input and the object to be decorated"""
    def __init__(self, d):
        self.d = d
        self.__name__ = d.__name__
        self.__doc__ = d.__doc__
    def __call__(self, *args, **kw):
        return partial(self.d, *args, **kw)

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

class Record(object):
    def __init__(self, *args, **kw):
        self.__dict__.update(*args, **kw)
    def __repr__(self):
        return "{0}({1})".format(type(self).__name__,
            ", ".join("{0}={1!r}".format(name, value)
            for (name, value) in self.__dict__.items()))

def assimilate(name, fromlist):
    module = __import__(name, fromlist=fromlist)
    for name in fromlist:
        setattr(builtins, name, getattr(module, name))

def run_main(module):
    if module != "__main__":
        return
    main = modules[module].main
    try:
        alias_opts = main.alias_opts
    except AttributeError:
        alias_opts = dict()
    try:
        arg_types = main.arg_types
    except AttributeError:
        arg_types = dict()
    
    try:
        ann = main.__annotations__
    except AttributeError:
        pass
    else:
        arg_types.update(ann)
    
    args = list()
    opts = dict()
    cmd_args = iter(argv[1:])
    while True:
        try:
            arg = next(cmd_args)
        except StopIteration:
            break
        if arg == "--":
            args.extend(cmd_args)
            break
        if arg.startswith("-"):
            opt = arg[len("-"):]
            try:
                opt = alias_opts[opt]
            except LookupError:
                opt = opt.replace("-", "_")
            
            convert = arg_types.get(opt)
            if convert is True:
                arg = convert
            else:
                arg = next(cmd_args)
                if opt in arg_types:
                    arg = convert(arg)
            opts[opt] = arg
        else:
            args.append(arg)
    
    for i in range(len(args)):
        try:
            convert = arg_types[i]
        except LookupError:
            pass
        else:
            args[i] = convert(args[i])
    
    main(*args, **opts)

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

def strip(s, start="", end=""):
    if not s.startswith(start):
        raise ValueError("Expected {0!r} starting string".format(start))
    if not s.endswith(end):
        raise ValueError("Expected {0!r} ending string".format(end))
    if len(s) < len(start) + len(end):
        raise ValueError(
            "String not enclosed by {0!r} and {1!r}".format(start, end))
    return s[len(start):len(s) - len(end)]

def url_port(url, scheme, ports):
    """Raises "ValueError" if the URL is not valid"""
    
    parsed = urlsplit(url, scheme=scheme)
    if not parsed.hostname:
        parsed = urlsplit("//" + url, scheme=scheme)
    if not parsed.hostname:
        raise ValueError("No host name specified: {0}".format(url))
    
    try:
        def_port = ports[parsed.scheme]
    except LookupError:
        raise ValueError("Unhandled scheme: {0}".format(parsed.scheme))
    port = parsed.port
    if port is None:
        port = def_port
    path = urlunsplit(("", "", parsed.path, parsed.query, parsed.fragment))
    return Record(scheme=parsed.scheme, hostname=parsed.hostname, port=port,
        path=path, username=parsed.username, password=parsed.password)

@deco_factory
def fields(f, *args, **kw):
    "Decorator factory to add arbitrary fields to function object"
    f.__dict__.update(*args, **kw)
    return f
