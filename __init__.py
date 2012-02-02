import sys
import weakref
from os.path import basename
from sys import modules
from sys import argv
import os

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
        self.__name__ = type(self).__name__
    def __get__(self, obj, cls):
        if obj is None:
            return self
        return Binding(self, obj)
class Binding:
    def __init__(self, func, obj):
        self.func = func
        self.obj = obj
    def __call__(self, *args, **kw):
        return self.func(self.obj, *args, **kw)

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
        arg_opts = main.arg_opts
    except AttributeError:
        arg_opts = ()
    
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
            
            if opt in arg_opts:
                opts[opt] = next(cmd_args)
            else:
                opts[opt] = True
        else:
            args.append(arg)
    
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
