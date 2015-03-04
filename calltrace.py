"""Log function call details"""

from __future__ import print_function

from misc import wrap_import
wrap_import()

from sys import stderr
from functions import (WrapperFunction, Function)
from contextlib import contextmanager
import inspect
from types import (
    FunctionType, MethodType, BuiltinFunctionType, BuiltinMethodType,
    ModuleType, GeneratorType, InstanceType, ClassType,
)
import reprlib
import time

class traced(WrapperFunction):
    def __init__(self, func, abbrev=set()):
        WrapperFunction.__init__(self, func)
        self.abbrev = abbrev
    
    def __call__(self, *args, **kw):
        start()
        print_call(custrepr(self.__wrapped__), args, kw, self.abbrev)
        start_time = time.monotonic()
        with trace_exc(abbrev=self.abbrev):
            ret = self.__wrapped__(*args, **kw)
        period = _format_si(time.monotonic() - start_time, 3)
        result()
        line("-> {} after {}s", optrepr(ret, "return" in self.abbrev), period)
        return ret
    
    def __repr__(self):
        return "{0.__class__.__name__}({1})".format(
            self, custrepr(self.__wrapped__))

class tracer(Function):
    def __init__(self, name, abbrev=()):
        Function.__init__(self, name)
        self.abbrev = abbrev
    def __call__(self, *pos, **kw):
        start()
        print_call(self.__name__, pos, kw, abbrev=self.abbrev)
        line("")

@contextmanager
def checkpoint(text, abbrev=()):
    start()
    stderr.write(text)
    start_time = time.monotonic()
    with trace_exc(abbrev=abbrev):
        yield
    period = time.monotonic() - start_time
    result()
    line("{}s", _format_si(period, 3), period)

@contextmanager
def trace_exc(abbrev=()):
    global indent
    
    stderr.flush()
    indent += 1
    start = time.monotonic()
    try:
        yield
    except BaseException as exc:
        period = _format_si(time.monotonic() - start, 3)
        result()
        line("raise {} after {}s", optrepr(exc, "raise" in abbrev), period)
        raise

def result():
    global indent
    indent -= 1
    if midline:
        stderr.write(" ")
    else:
        margin()

def print_call(func, pos=(), kw=dict(), abbrev=()):
    print(func, end="(", file=stderr)
    
    for (k, v) in enumerate(pos):
        if k:
            stderr.write(", ")
        stderr.write(optrepr(v, k in abbrev))
    
    comma = pos
    for (k, v) in kw.items():
        if comma:
            stderr.write(", ")
        stderr.write("{0}={1}".format(k, optrepr(v, k in abbrev)))
        comma = True
    
    stderr.write(")")

def optrepr(v, abbrev=False):
    if abbrev:
        return "..."
    else:
        return custrepr(v)

def custrepr(obj):
    return Repr().repr(obj)

class OrderedSubclasses(dict):
    """Adds a "subclasses" list in topological order to each value"""
    
    def __init__(self, universe):
        self.universe = universe
        self.superclasses = set()
        for cls in self.universe:
            self[cls]
    
    def __missing__(self, cls):
        self.superclasses.add(cls)
        subclasses = list()
        for subclass in self.universe:
            if subclass == cls or not issubclass(subclass, cls):
                continue
            if subclass in self.superclasses:
                raise ValueError("{0!r} is both a subclass and a superclass "
                    "of {1!r}".format(subclass, cls))
            existing = set(subclasses)
            for subclass in self[subclass]:
                if subclass not in existing:
                    subclasses.append(subclass)
        self.superclasses.remove(cls)
        subclasses.append(cls)
        self[cls] = subclasses
        return subclasses

class Repr(reprlib.Repr):
    def __init__(self, *pos, **kw):
        reprlib.Repr.__init__(self, *pos, **kw)
        
        self.maxother = max(self.maxother, 80)
        if InstanceType is not object:
            # "maxstring" used for "old-style" instances
            self.maxstring = max(self.maxstring, 80)
    
    def repr1(self, obj, level):
        """See if a custom repr() is provided that overrides the object's
        repr()"""
        
        self.level = level
        
        for base in inspect.getmro(getattr(obj, "__class__", type(obj))):
            # Check for subclasses of the object's base class, so that a
            # custom representation of a virtual base class not in the MRO
            # has priority over a common concrete base class's representation
            for subclass in self.subclasses.get(base, ()):
                if isinstance(obj, subclass):
                    return self.classes[subclass](self, obj)
            
            # Let an object's specialised repr() have priority over custom
            # representations for more basic classes
            if vars(base).get("__repr__"):
                return reprlib.Repr.repr1(self, obj, level)
        
        if isinstance(obj, InstanceType):
            return self.obj(obj)
        return reprlib.Repr.repr1(self, obj, level)
    
    def recurse(self, obj):
        return self.repr1(obj, self.level - 1)
    
    classes = dict()
    
    def obj(self, obj):
        """Mimic object representation printed by the garbage collector"""
        return "<{0} 0x{1:X}>".format(self.recurse(obj.__class__), id(obj))
    classes[object] = obj
    
    def named(self, obj):
        name = getattr(obj, "__qualname__", obj.__name__)
        if False:
            module = getattr(obj, "__module__", None)
            if module is not None:
                name = "{0}.{1}".format(module, name)
        return name
    classes[FunctionType] = named
    classes[type] = named
    classes[ClassType] = named
    
    def method(self, method):
        binding = method.__self__ or getattr(method, "im_class", None)
        if binding:
            return "{0}.{1.__func__.__name__}".format(
                self.recurse(binding), method)
        else:
            return self.recurse(method.__func__)
    classes[MethodType] = method
    
    def builtin(self, builtin):
        binding = builtin.__self__
        # Built-in functions tend to set __self__ to their module
        if binding and (not isinstance(binding, ModuleType) or
        binding.__name__ != builtin.__module__):
            return "{0}.{1.__name__}".format(self.recurse(binding), builtin)
        else:
            return self.named(builtin)
    classes[BuiltinFunctionType] = builtin
    classes[BuiltinMethodType] = builtin
    
    def generator(self, gen):
        return "<{0} 0x{1:X}>".format(self.named(gen), id(gen))
    classes[GeneratorType] = generator
    
    subclasses = OrderedSubclasses(classes.keys())

indent = 0
midline = False

def start():
    if midline:
        line("")
    margin()

def line(format_string, *pos, **kw):
    global midline
    print(format_string.format(*pos, **kw), file=stderr)
    midline = False

def margin():
    global midline
    for _ in range(indent):
        stderr.write("  ")
    midline = True

def _format_si(number, ndigits):
    '''
    format_si(0, 3) -> "0.00 "  # Only leading zero; significant digits
    format_si(10150, 3) -> "10.2 k"  # Round half up to even
    format_si(222500, 3) -> "222 k"  # Half down to even; no decimal point
    format_si(0.99949, 3) -> "999 m"  # Prefer more accurate rounding
    format_si(1.380648813e-23, 3) -> "1.38e-23 "  # Extreme value
    '''
    scientific = "{:.{}e}".format(number, ndigits - 1)
    [significand, exponent] = scientific.rsplit("e", 2)
    [prefix, scaled_exp] = divmod(int(exponent), 3)
    significand = significand.replace(".", "", 1)
    if significand.startswith("-"):
        digits_start = 1
    else:
        digits_start = 0
    dec_pos = digits_start + 1 + scaled_exp
    fraction = significand[dec_pos:]
    if fraction:
        fraction = "." + fraction
    if prefix:
        if prefix < 0:
            prefixes = "mµnpfazy"
            prefix = -prefix
        else:
            prefixes = "kMGTPEZY"
        if prefix > len(prefixes):
            return scientific + " "
        prefix = prefixes[prefix - 1]
    else:
        prefix = ""
    return "{}{} {}".format(significand[:dec_pos], fraction, prefix)
