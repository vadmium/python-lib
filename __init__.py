import sys
import weakref
from os.path import basename
import __main__
import os
from types import MethodType
from functools import partial
from collections import namedtuple
from collections import Set
from inspect import getcallargs
from inspect import getdoc
from inspect import getfullargspec
from sys import stderr

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

def command(func=None, args=None, *, param_types=dict()):
    """Invokes a function using CLI arguments
    
    func: Defaults to __main__.main
    args: Defaults to sys.argv[1:]. If specified, the command name shown in
        help is taken from func.__name__; otherwise, from sys.argv[0].
    param_types:  This mapping extends and overrides any "param_types"
        attribute of "func". The parameter and attribute both map parameter
        keywords to functions taking an argument string and returning the
        parameter's data type. By default, arguments are passed to "func" as
        unconverted strings. The special keywords "*" and "**" apply to any
        excess positional and keyword arguments.
    
    The command option names are the parameter keywords, and hyphenated (-)
    option names are interpreted as using underscores (_) instead. Options
    may be prefixed with either a single (-) or a double (--) dash. An
    option's argument may be separated by an equals sign (=) or may be in a
    separate argument word.
    
    For parameters that default to "False", the command option does not take
    an argument and sets the corresponding "func" argument to "True". For
    parameters that default to an empty list, tuple or set, the command
    option may be given multiple times and are combined into a sequence.
    
    Raises SystemExit() when the function was not actually run [TODO: when
    appropriate]
    """
    
    """Similar implementations:
    https://pypi.python.org/pypi/clize: adapts the function in two steps
    http://dev.kylealanhale.com/wiki/projects/quicli: very decorator-happy, with much "argparse" API and little automatic introspection
    """
    # return value could be str or int -> System exit
    
    if func is None:
        func = __main__.main
    if args is None:
        args = sys.argv[1:]
    
    argspec = getfullargspec(func)
    
    if argspec.defaults is None:
        defaults = dict()
    else:
        defaults = len(argspec.args) - len(argspec.defaults)
        defaults = dict(zip(argspec.args[defaults:], argspec.defaults))
    if argspec.kwonlydefaults is not None:
        defaults.update(argspec.kwonlydefaults)
    
    # Infer parameter modes from default values
    def noarg_default(default):
        return default is False
    def multi_default(default):
        return isinstance(default, (tuple, list, Set))
    
    params = set().union(argspec.args, argspec.kwonlyargs)
    
    for (param, type) in getattr(func, "param_types", dict()):
        param_types.setdefault(param, type)
    
    help = (argspec.varkw is None and "help" not in params)
    if help:
        params.add("help")
        defaults["help"] = False
    
    positional = list()
    opts = dict()
    args = iter(args)
    while True:
        try:
            arg = next(args)
        except StopIteration:
            break
        if arg == "--":
            positional.extend(args)
            break
        
        if arg.startswith("-") and arg != "-":
            # Allow options to be preceded by two dashes
            if arg.startswith("--"):
                opt = arg[2:]
            else:
                opt = arg[1:]
            
            # Allow argument to be separated by equals sign
            try:
                (opt, arg) = opt.split("=")
            except ValueError:
                arg = None
            
            opt = opt.replace("-", "_")
            if opt in params:
                key = opt
            else:
                key = "**"
            
            if noarg_default(defaults.get(key)):
                if arg is not None:
                    raise SystemExit("Option {opt!r} takes no argument".
                        format_map(locals()))
                opts[opt] = True
            
            else:
                if arg is None:
                    try:
                        arg = next(args)
                    except StopIteration:
                        raise SystemExit("Option {opt!r} requires an "
                            "argument".format_map(locals()))
                
                try:
                    convert = param_types[key]
                except LookupError:
                    pass
                else:
                    arg = convert(arg)
                
                if multi_default(defaults.get(key)):
                    opts.setdefault(opt, list()).append(arg)
                else:
                    opts[opt] = arg
        
        else:
            try:
                key = argspec.args[len(positional)]
            except LookupError:
                key = "*"
            
            try:
                convert = param_types[key]
            except LookupError:
                pass
            else:
                arg = convert(arg)
            
            positional.append(arg)
    
    if help and opts.get("help", False):
        params = (params.difference(("help",)) or
            argspec.varargs is not None or argspec.varkw is not None)
        if params:
            stderr.write("Parameters:")
            for param in argspec.args:
                try:
                    default = defaults[param]
                except LookupError:
                    format = " [--{}=]X"
                else:
                    if noarg_default(defaults.get(param)):
                        format = " [--{} | X]"
                    elif multi_default(defaults.get(param)):
                        format = " [--{} . . . | X]"
                    else:
                        format = " [[--{}=]X]"
                stderr.write(format.format(param.replace("_", "-")))
            if argspec.varargs is not None:
                stderr.write(
                    " [{argspec.varargs}  . . .]".format_map(locals()))
            for param in argspec.kwonlyargs:
                try:
                    default = defaults[param]
                except LookupError:
                    format = " --{}=X"
                else:
                    if noarg_default(default):
                        format = " [--{}]"
                    elif multi_default(default):
                        format = " [--{}=X . . .]"
                    else:
                        format = " [--{}=X]"
                stderr.write(format.format(param.replace("_", "-")))
            print(file=stderr)
        
        doc = getdoc(func)
        if doc is not None:
            if params:
                print(file=stderr)
            print(doc, file=stderr)
        
        return
    
    try:
        getcallargs(func, *positional, **opts)
    except TypeError as err:
        raise SystemExit(err)
    
    return func(*positional, **opts)

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
    if start and not s.startswith(start):
        raise ValueError("Expected {0!r} starting string".format(start))
    if end and not s.endswith(end):
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
        raise ValueError("No host name specified: {0!r}".format(url))
    
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

class Cleanup:
    def __init__(self):
        self.exits = []
    
    def __enter__(self):
        return self
    
    def __exit__(self, *exc):
        while self.exits:
            if self.exits.pop()(*exc):
                exc = (None, None, None)
        return exc == (None, None, None)
    
    def __call__(self, context):
        exit = context.__exit__
        enter = context.__enter__
        add_exit = self.exits.append
        
        res = enter()
        add_exit(exit)
        
        return res

def nop(*args, **kw):
    pass

FieldType = namedtuple("Field", "key, value")
def Field(**kw):
    (field,) = kw.items()
    return FieldType(*field)
