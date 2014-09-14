from __future__ import print_function

import sys
from collections import Set
import inspect
from functions import setitem
from collections import OrderedDict

try:  # Python 3.3
    from inspect import signature, Parameter
except ImportError:  # Python < 3.3
    from collections import namedtuple
    
    try:  # Python 3
        from inspect import getfullargspec
    except ImportError:  # Python < 3
        from inspect import getargspec
        FullArgSpec = namedtuple("FullArgSpec", """
            args, varargs, varkw, defaults,
            kwonlyargs, kwonlydefaults, annotations""")
        def getfullargspec(*pos, **kw):
            argspec = getargspec(*pos, **kw)
            return FullArgSpec(*argspec,
                kwonlyargs=(), kwonlydefaults=None, annotations=None)
    
    class signature:
        def __init__(self, func):
            argspec = getfullargspec(func)
            self.parameters = OrderedDict()
            defaults_start = -len(argspec.defaults or ())
            for (i, name) in enumerate(argspec.args, -len(argspec.args)):
                if i < defaults_start:
                    default = Parameter.empty
                else:
                    default = argspec.defaults[i]
                self.parameters[name] = Parameter(name,
                    Parameter.POSITIONAL_OR_KEYWORD, default)
            if argspec.varargs is not None:
                self.parameters[argspec.varargs] = Parameter(argspec.varargs,
                    Parameter.VAR_POSITIONAL, None)
            for name in argspec.kwonlyargs:
                default = argspec.kwonlydefaults.get(name, Parameter.empty)
                self.parameters[name] = Parameter(name,
                    Parameter.KEYWORD_ONLY, default)
            if argspec.varkw is not None:
                self.parameters[argspec.varkw] = Parameter(argspec.varkw,
                    Parameter.VAR_KEYWORD, None)
            
            self.func = func  # Get signature.bind() partially working
        
        def bind(self, *pos, **kw):
            inspect.getcallargs(self.func, *pos, **kw)
    
    Parameter = namedtuple("Parameter", "name, kind, default")
    for name in (
        "POSITIONAL_ONLY", "POSITIONAL_OR_KEYWORD", "VAR_POSITIONAL",
        "KEYWORD_ONLY", "VAR_KEYWORD",
        "empty",
    ):
        setattr(Parameter, name, object())

try:  # Python 3.3
    from collections import ChainMap
except ImportError:  # Python < 3.3
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

def run(func=None, args=None, param_types=dict()):
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
    
    (func, sig, keywords, param_types) = prepare(func, param_types)
    varpos = param_kind(sig, Parameter.VAR_POSITIONAL)
    varkw = param_kind(sig, Parameter.VAR_KEYWORD)
    
    if args is None:
        args = sys.argv[1:]
    
    auto_help = varkw is None and "help" not in keywords
    if auto_help:
        param = Parameter("help", Parameter.KEYWORD_ONLY, default=False)
        keywords[param.name] = param
    
    pos_kinds = (Parameter.POSITIONAL_ONLY, Parameter.POSITIONAL_OR_KEYWORD)
    pos_iter = (param for
        param in sig.parameters.values() if param.kind in pos_kinds)
    
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
            param = keywords.get(opt)
            if not param:
                if varkw is None:
                    raise SystemExit("Unexpected option {opt!r}".
                        format(**locals()))
                param = varkw
            
            if param.kind != param.VAR_KEYWORD and noarg_param(param):
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
                
                arg = convert(param_types, param, arg)
                
                if param.kind != param.VAR_KEYWORD and multi_param(param):
                    opts.setdefault(opt, list()).append(arg)
                else:
                    opts[opt] = arg
        
        else:
            param = next(pos_iter, varpos)
            if param is not None:
                arg = convert(param_types, param, arg)
            positional.append(arg)
    
    if auto_help and opts.get("help", False):
        help(func, param_types=param_types)
        return
    
    try:
        sig.bind(*positional, **opts)
    except TypeError as err:
        raise SystemExit(err)
    
    return func(*positional, **opts)

def convert(types, param, arg):
    convert = types.get(param.name)
    if not convert:
        return arg
    try:
        return convert(arg)
    except ValueError as err:
        raise SystemExit("{!r} parameter: {}".format(param.name, err))

def help(func=None, file=sys.stderr, param_types=dict()):
    (func, sig, keywords, param_types) = prepare(func, param_types)
    
    (summary, body) = splitdoc(inspect.getdoc(func))
    if summary:
        print(summary, file=file)
    
    if sig.parameters:
        if summary:
            print(file=file)
        file.write("parameters:")
        
        for param in sig.parameters.values():
            param = format_kind[param.kind](param, param_types)
            file.writelines((" ", param))
        
        first = True
        # TODO: Include positional-only parameters
        for param in keywords.values():
            if (param.default in (Parameter.empty, None) or
            noarg_param(param) or multi_param(param)):
                continue
            
            if first:
                file.write("\n" "defaults:")
                first = False
            file.write(" {}={!s}".format(option(param.name), param.default))
        
        print(file=file)
    
    if body is not None:
        if summary or sig.parameters:
            print(file=file)
        print(body, file=file)
    
    if not summary and not sig.parameters and not body:
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

format_kind = dict()

@setitem(format_kind, Parameter.POSITIONAL_ONLY)
def format_pos(param, types):
    res = format_pos_single(param, types)
    if param.default is not param.empty:
        res = "[" + res + "]"
    return res

@setitem(format_kind, Parameter.VAR_POSITIONAL)
def format_varpos(param, types):
    return "[" + format_pos_single(param, types) + " . . .]"

def format_pos_single(param, types):
    try:
        res = "{}: {}".format(param.name, types[param.name].__name__)
    except (LookupError, AttributeError):
        res = param.name
    return "<" + res + ">"

@setitem(format_kind, Parameter.POSITIONAL_OR_KEYWORD)
def format_pos_kw(param, types):
    return format_kw_infer(param, types, "[{param}] <{value}>", "{param}")

@setitem(format_kind, Parameter.KEYWORD_ONLY)
def format_kw(param, types):
    return format_kw_infer(param, types, "{param}=<{value}>", "{param}")

@setitem(format_kind, Parameter.VAR_KEYWORD)
def format_varkw(param, types):
    return format_kw_format(param, types, "[{param}=<{value}> . . .]")

def format_kw_infer(param, types, format, noarg):
    if param.default is not param.empty:
        if noarg_param(param):
            format = noarg
        if multi_param(param):
            format = "{format} . . .".format(**locals())
        format = "[{format}]".format(**locals())
    return format_kw_format(param, types, format)

def format_kw_format(param, types, format):
    value = types.get(param.name, str).__name__
    param = option(param.name)
    return format.format(param=param, value=value)

def option(param):
    param = param.replace("_", "-")
    if param.startswith("-"):
        return "--" + param
    else:
        return "-" + param

def prepare(func=None, param_types=dict()):
    if func is None:
        from __main__ import main as func
    
    sig = signature(func)
    
    keyword_kinds = (Parameter.POSITIONAL_OR_KEYWORD, Parameter.KEYWORD_ONLY)
    keywords = OrderedDict((param.name, param) for
        param in sig.parameters.values() if param.kind in keyword_kinds)
    
    param_types = ChainMap(param_types, getattr(func, "param_types", dict()))
    for param in param_types:
        if param not in sig.parameters:
            raise TypeError("{func.__name__}() does not have "
                "a parameter called {param!r}".format(**locals()))
    
    return (func, sig, keywords, param_types)

def param_kind(sig, kind):
    return next(iter(param for
        param in sig.parameters.values() if param.kind == kind), None)

# Infer parameter modes from default values
def noarg_param(param):
    return param.default is False
def multi_param(param):
    return (isinstance(param.default, (tuple, list, Set)) and
        not param.default)

def main():
    import importlib
    from types import ModuleType
    
    if len(sys.argv) < 2 or sys.argv[1] in {"-help", "--help", "-h"}:
        print("""\
Calls a function from a Python module

parameters: <module>[.function] [arguments | -help]

If the function name is omitted, the main() function is called.""")
        return
    
    name = sys.argv[1]
    
    (module, sep, attr) = name.rpartition(".")
    try:
        if sep:
            func = getattr(importlib.import_module(module), attr, None)
        else:
            func = None
        if func is None:
            func = importlib.import_module(name)
    except ImportError as err:
        raise SystemExit(err)
    
    if isinstance(func, ModuleType):
        func = getattr(func, "main", None)
        if func is None:
            raise SystemExit("Module {} has no main() function".format(name))
    
    return run(func, sys.argv[2:])

if __name__ == "__main__":
    raise SystemExit(main())
