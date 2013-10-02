from __future__ import print_function

import sys
from collections import Set
import inspect
from sys import stderr
from itertools import chain

try:
    from inspect import getfullargspec
except ImportError:
    from inspect import getargspec
    from collections import namedtuple
    FullArgSpec = namedtuple("FullArgSpec", """
        args, varargs, varkw, defaults,
        kwonlyargs, kwonlydefaults, annotations""")
    def getfullargspec(*pos, **kw):
        argspec = getargspec(*pos, **kw)
        return FullArgSpec(*argspec,
            kwonlyargs=(), kwonlydefaults=None, annotations=None)

try:
    from collections import ChainMap
except ImportError:
    from collections import Mapping
    class ChainMap(Mapping):
        def __init__(self, *maps):
            self.maps = maps
        
        def __getitem__(self, key):
            for map in self.maps:
                try:
                    return map.__getitem__(key)
                except LookupError:
                    continue
            else:
                raise KeyError(key)
        
        def __iter__(self):
            keys = set()
            for map in self.maps:
                for key in map:
                    if key not in keys:
                        keys.add(key)
                        yield key
        
        def __len__(self):
            return len(frozenset().union(*self.maps))

def command(func=None, args=None, param_types=dict()):
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
    
    (func, argspec, params, param_types, defaults) = prepare(
        func, param_types)
    
    if args is None:
        args = sys.argv[1:]
    
    auto_help = (argspec.varkw is None and "help" not in params)
    if auto_help:
        params.add("help")
        defaults["help"] = False
    
    positional = list()
    opts = dict()
    args = iter(args)
    endopts = False
    while True:
        try:
            arg = next(args)
        except StopIteration:
            break
        if arg == "--":
            endopts = True
            continue
        
        if not endopts and arg.startswith("-") and arg != "-":
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
                if argspec.varkw is None:
                    raise SystemExit("Unexpected option {opt!r}".
                        format(**locals()))
                key = "**"
            
            if noarg_default(defaults.get(key)):
                if arg is not None:
                    raise SystemExit("Option {opt!r} takes no argument".
                        format(**locals()))
                opts[opt] = True
            
            else:
                if arg is None:
                    try:
                        arg = next(args)
                    except StopIteration:
                        raise SystemExit("Option {opt!r} requires an "
                            "argument".format(**locals()))
                
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
    
    if auto_help and opts.get("help", False):
        help(func, param_types=param_types)
        return
    
    try:
        inspect.getcallargs(func, *positional, **opts)
    except TypeError as err:
        raise SystemExit(err)
    
    return func(*positional, **opts)

def help(func=None, file=stderr, param_types=dict()):
    (func, argspec, params, param_types, defaults) = prepare(
        func, param_types)
    
    (summary, body) = splitdoc(inspect.getdoc(func))
    if summary:
        print(summary, file=file)
    
    params = (params or
        argspec.varargs is not None or argspec.varkw is not None)
    
    if params:
        if summary:
            print(file=file)
        file.write("parameters:")
        print_params(argspec.args, file, defaults, param_types,
            normal="[{param}] <{value}>",
            noarg="{param}",
        )
        if argspec.varargs is not None:
            value = argspec.varargs
            try:
                type = param_types["*"]
            except LookupError:
                pass
            else:
                value = "{value}: {type.__name__}".format(**locals())
            file.write(" [<{value}> . . .]".format(**locals()))
        print_params(argspec.kwonlyargs, file, defaults, param_types,
            normal="{param}=<{value}>",
            noarg="{param}",
        )
        if argspec.varkw is not None:
            type = param_types.get("**", str).__name__
            file.write(" [{}=<{}> . . .]".format(
                option(argspec.varkw), type))
        
        first = True
        for param in chain(argspec.args, argspec.kwonlyargs):
            try:
                default = defaults[param]
            except LookupError:
                continue
            if (default is None or
            noarg_default(default) or multi_default(default)):
                continue
            
            if first:
                file.write("\n" "defaults:")
                first = False
            file.write(" {}={!s}".format(option(param), default))
        
        print(file=file)
    
    if body is not None:
        if summary or params:
            print(file=file)
        print(body, file=file)
    
    if not summary and not params and not body:
        print("no parameters", file=file)

def splitdoc(doc):
    """Returns a tuple (summary, body) for a docstring
    
    The summary corresponds to the first line. Either item may be None if not
    present."""
    
    if doc is None:
        return (None, None)
    
    lines = doc.split("\n", 2)
    if len(lines) > 1 and lines[1]:  # Second line exists but is not blank
        return (None, doc)
    
    if len(lines) < 3:
        return (lines[0], None)
    return (lines[0], lines[2])

def print_params(params, file, defaults, types, normal, noarg):
    for param in params:
        value = types.get(param, str).__name__
        try:
            default = defaults[param]
        except LookupError:
            format = normal
        else:
            if noarg_default(default):
                format = noarg
            else:
                format = normal
            if multi_default(default):
                format = "{format} . . .".format(**locals())
            format = "[{format}]".format(**locals())
        
        param = option(param)
        file.writelines((" ", format.format(param=param, value=value)))

def option(param):
    param = param.replace("_", "-")
    if param.startswith("-"):
        return "--" + param
    else:
        return "-" + param

def prepare(func=None, param_types=dict()):
    if func is None:
        from __main__ import main as func
    
    argspec = getfullargspec(func)
    
    if argspec.defaults is None:
        defaults = dict()
    else:
        defaults = len(argspec.args) - len(argspec.defaults)
        defaults = dict(zip(argspec.args[defaults:], argspec.defaults))
    if argspec.kwonlydefaults is not None:
        defaults.update(argspec.kwonlydefaults)
    
    param_types = ChainMap(param_types, getattr(func, "param_types", dict()))
    
    params = set().union(argspec.args, argspec.kwonlyargs)
    for param in param_types:
        if param == "*":
            if argspec.varargs is None:
                raise TypeError("{func.__name__}() does not take "
                    "variable positional arguments (*)".format(**locals()))
        elif param == "**":
            if argspec.varkw is None:
                raise TypeError("{func.__name__}() does not take "
                    "variable keyword arguments (**)".format(**locals()))
        else:
            if param not in params:
                raise TypeError("{func.__name__}() does not have "
                    "a parameter called {param!r}".format(**locals()))
    
    return (func, argspec, params, param_types, defaults)

# Infer parameter modes from default values
def noarg_default(default):
    return default is False
def multi_default(default):
    return isinstance(default, (tuple, list, Set)) and not default
