from __future__ import print_function

import sys
import inspect
from functions import setitem
from collections import OrderedDict

try:  # Python 3.3
    from collections.abc import Set
    from inspect import signature, Parameter
except ImportError:  # Python < 3.3
    from collections import Set
    from collections import namedtuple
    from inspect import getargspec
    
    class signature:
        def __init__(self, func):
            argspec = getargspec(func)
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
            if argspec.keywords is not None:
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

try:  # Python 3.3
    from contextlib import ExitStack
except ImportError:  # Python < 3.3
    from misc import Context
    class ExitStack(Context):
        def __init__(self):
            self.exit = None
        
        def enter_context(self, context):
            self.exit = context.__exit__
            return context.__enter__()
        
        def __exit__(self, *exc):
            if self.exit:
                return self.exit(*exc)

def public(api):
    sys.modules[api.__module__].__all__.append(api.__name__)
    return api
__all__ = list()

@public
def run(func=None, args=None, param_types=dict(), cli_result=False):
    """Invokes a function using CLI arguments
    
    func: Defaults to __main__.main
    args: Defaults to sys.argv[1:]
    param_types:  This mapping extends and overrides any "param_types"
        attribute of "func". The parameter and attribute both map parameter
        keywords to functions taking an argument string and returning the
        parameter's data type. By default, arguments are passed to "func" as
        unconverted strings. The special keywords "*" and "**" apply to any
        excess positional and keyword arguments.
    cli_result: If true, the function or context manager result will be
        displayed, or will have a method invoked as a subcommand. A
        subcommand is invoked by passing an extra positional argument.
    
    If the function has a "cli_context" attribute set to True, the return
    value is entered as a context manager. Any further return value handling
    uses the result returned when entering the context manager.
    
    If the function has the "subcommand_class" attribute set, a subcommand
    will be expected, and will invoke a method listed in the class on the
    function or context manager result.
    
    The CLI option names are the parameter keywords, and hyphenated (-)
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
    http://dev.kylealanhale.com/wiki/projects/quicli: very decorator-happy,
        with much "argparse" API and little automatic introspection
    """
    
    [func, sig, keywords, param_types] = prepare(func, param_types)
    varpos = param_kind(sig, Parameter.VAR_POSITIONAL)
    varkw = param_kind(sig, Parameter.VAR_KEYWORD)
    
    if args is None:
        args = sys.argv[1:]
    
    auto_help = list()
    if varkw is None:
        for opt in ("help", "h"):
            if opt not in keywords:
                auto_help.append(opt)
                param = Parameter(opt, Parameter.KEYWORD_ONLY, default=False)
                keywords[opt] = param
    
    if sig:
        pos_kinds = (
            Parameter.POSITIONAL_ONLY, Parameter.POSITIONAL_OR_KEYWORD)
        pos_iter = (param for
            param in sig.parameters.values() if param.kind in pos_kinds)
    else:
        pos_iter = iter(())
    
    positional = list()
    opts = dict()
    args = iter(args)
    endopts = False
    while True:
        arg = next(args, None)
        if arg is None:
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
                [opt, arg] = opt.split("=")
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
                        if sig:
                            msg = "Option {!r} requires an argument"
                            msg = msg.format(opt)
                        else:
                            msg = "Keyword options require arguments"
                        raise SystemExit(msg)
                
                arg = convert(param_types, param, arg)
                
                if param.kind != param.VAR_KEYWORD and multi_param(param):
                    opts.setdefault(opt, list()).append(arg)
                else:
                    opts[opt] = arg
        
        else:
            param = next(pos_iter, varpos)
            if (cli_result or hasattr(func, "subcommand_class")) and (
            param is varpos or param.default is not Parameter.empty):
                break
            if param is not None:
                arg = convert(param_types, param, arg)
            positional.append(arg)
    
    if any(opts.get(help, False) for help in auto_help):
        help(func, param_types=param_types)
        return
    
    if sig:
        try:
            sig.bind(*positional, **opts)
        except TypeError as err:
            raise SystemExit(err)
    
    result = func(*positional, **opts)
    with ExitStack() as cleanup:
        if getattr(func, "cli_context", False):
            result = cleanup.enter_context(result)
        if not cli_result and not hasattr(func, "subcommand_class"):
            return result
        if arg is None:
            sys.displayhook(result)
            return
        
        if arg is None:
            all = getattr(result, "__all__", None)
            if all is None:
                funcs = dir(result)
            else:
                funcs = all
            heading = False
            for name in funcs:
                if all is None and name.startswith("_"):
                    continue
                func = getattr(result, name)
                if not callable(func):
                    continue
                if not heading:
                    sys.stderr.write("public subcommands:\n")
                    heading = True
                sys.stderr.write(name)
                [summary, _] = splitdoc(inspect.getdoc(func))
                if summary:
                    sys.stderr.writelines((": ", summary))
                sys.stderr.write("\n")
            if not heading:
                sys.stderr.write("no public subcommands found\n")
        else:
            try:
                func = getattr(result, arg)
            except AttributeError as err:
                err = "Invalid subcommand {!r}: {}".format(arg, err)
                raise SystemExit(err)
            return run(func, args, cli_result=cli_result)

def convert(types, param, arg):
    convert = types.get(param.name)
    if not convert:
        return arg
    try:
        return convert(arg)
    except ValueError as err:
        raise SystemExit("{!r} parameter: {}".format(param.name, err))

@public
def help(func=None, file=sys.stderr, param_types=dict()):
    [func, sig, keywords, param_types] = prepare(func, param_types)
    
    [summary, body] = splitdoc(inspect.getdoc(func))
    if summary:
        file.writelines((summary, "\n"))
    
    if not sig:
        if summary:
            file.write("\n")
        file.write("syntax: [-keyword=argument . . .] [positional . . .]\n")
    elif sig.parameters:
        if summary:
            file.write("\n")
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
        
        file.write("\n")
    
    if body is not None:
        if summary or not sig or sig.parameters:
            file.write("\n")
        file.writelines((body, "\n"))
    
    if not summary and sig and not sig.parameters and not body:
        file.write("no parameters\n")

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
    param_types = ChainMap(param_types, getattr(func, "param_types", dict()))
    
    try:
        sig = signature(func)
    except (ValueError, TypeError):
        return (func, None, dict(), param_types)
    
    keyword_kinds = (Parameter.POSITIONAL_OR_KEYWORD, Parameter.KEYWORD_ONLY)
    keywords = OrderedDict((param.name, param) for
        param in sig.parameters.values() if param.kind in keyword_kinds)
    
    # Explicit set() construction to work around Python 2's keys() lists
    missing = set(param_types.keys()).difference(sig.parameters.keys())
    if missing:
        missing = ", ".join(map(repr, missing))
        msg = "{}() missing parameters: {}".format(func.__name__, missing)
        raise TypeError(msg)
    
    return (func, sig, keywords, param_types)

def param_kind(sig, kind):
    if sig:
        return next(iter(param for
            param in sig.parameters.values() if param.kind == kind), None)
    else:
        name = {
            Parameter.VAR_POSITIONAL: "positional",
            Parameter.VAR_KEYWORD: "keywords",
        }[kind]
        return Parameter(name, kind, default=Parameter.empty)

# Infer parameter modes from default values
def noarg_param(param):
    return param.default is False
def multi_param(param):
    return (isinstance(param.default, (tuple, list, Set)) and
        not param.default)

@public
def import_module(module):
    """Calls a function from a Python module"""
    
    import importlib
    
    try:
        return importlib.import_module(module)
    except ImportError as err:
        if getattr(err, "name", module) != module:  # Python 3.3
            raise
        raise SystemExit(err)

if __name__ == "__main__":
    try:
        run(import_module, cli_result=True)
    except (KeyboardInterrupt, BrokenPipeError):
        raise SystemExit(1)
