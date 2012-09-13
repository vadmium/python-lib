import sys
from collections import Set
from inspect import getcallargs
from inspect import getdoc
from inspect import getfullargspec
from sys import stderr
from itertools import chain

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
    
    (func, argspec, param_types, defaults) = inspect(func, param_types)
    if args is None:
        args = sys.argv[1:]
    
    params = set().union(argspec.args, argspec.kwonlyargs)
    
    auto_help = (argspec.varkw is None and "help" not in params)
    if auto_help:
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
                if argspec.varkw is None:
                    raise SystemExit("Unexpected option {opt!r}".
                        format_map(locals()))
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
    
    if auto_help and opts.get("help", False):
        help(func, param_types=param_types)
        return
    
    try:
        getcallargs(func, *positional, **opts)
    except TypeError as err:
        raise SystemExit(err)
    
    return func(*positional, **opts)

def help(func=None, file=stderr, *, param_types=dict()):
    (func, argspec, param_types, defaults) = inspect(func, param_types)
    params = (argspec.args or argspec.varargs is not None or
        argspec.kwonlyargs or argspec.varkw is not None)
    if params:
        file.write("Parameters:")
        print_params(argspec.args, file, defaults, param_types,
            normal="[-{param}] <{value}>",
            noarg="-{param} | <{value}>",
        )
        if argspec.varargs is not None:
            value = argspec.varargs
            try:
                type = param_types["*"]
            except LookupError:
                pass
            else:
                value = "{value}: {type.__name__}".format_map(locals())
            file.write(" [<{value}> . . .]".format_map(locals()))
        print_params(argspec.kwonlyargs, file, defaults, param_types,
            normal="-{param}=<{value}>",
            noarg="-{param}",
        )
        if argspec.varkw is not None:
            type = param_types.get("**", str).__name__
            file.write(
                " [-{argspec.varkw}=<{type}> . . .]".format_map(locals()))
        
        first = True
        for param in chain(argspec.args, argspec.kwonlyargs):
            try:
                default = defaults[param]
            except LookupError:
                continue
            if default is None or noarg_default(default):
                continue
            
            if first:
                file.write("\n" "Defaults:")
                first = False
            param = param.replace("_", "-")
            file.write(" -{param}={default!s}".format_map(locals()))
        
        print(file=file)
    
    doc = getdoc(func)
    if doc is not None:
        if params:
            print(file=file)
        print(doc, file=file)

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
                format = "{format} . . .".format_map(locals())
            format = "[{format}]".format_map(locals())
        param = param.replace("_", "-")
        file.writelines((" ", format.format(param=param, value=value)))

def inspect(func, param_types):
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
    
    for (param, type) in getattr(func, "param_types", dict()):
        param_types.setdefault(param, type)
    
    return (func, argspec, param_types, defaults)

# Infer parameter modes from default values
def noarg_default(default):
    return default is False
def multi_default(default):
    return isinstance(default, (tuple, list, Set))
