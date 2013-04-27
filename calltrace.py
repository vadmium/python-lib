"""Log function call details"""

from __future__ import print_function

from sys import stderr
from misc import (WrapperFunction, Function)
from contextlib import contextmanager
import inspect
from types import (
    FunctionType, MethodType, BuiltinFunctionType, BuiltinMethodType,
    ModuleType, GeneratorType,
)

try:  # Python 3
    import reprlib
except ImportError:  # Python < 3
    import repr as reprlib

try:  # Python < 3
    from types import (InstanceType, ClassType)
except ImportError:  # Python 3
    InstanceType = object
    ClassType = type

class traced(WrapperFunction):
    def __init__(self, func, abbrev=set()):
        WrapperFunction.__init__(self, func)
        self.abbrev = abbrev
    
    def __call__(self, *args, **kw):
        start()
        print_call(custrepr(self.__wrapped__), args, kw, self.abbrev)
        with trace_exc(abbrev=self.abbrev):
            ret = self.__wrapped__(*args, **kw)
        result()
        line("->", optrepr(ret, "return" in self.abbrev))
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
        line()

@contextmanager
def checkpoint(text, abbrev=()):
    start()
    stderr.write(text)
    with trace_exc(abbrev=abbrev):
        yield
    result()
    line("done")

@contextmanager
def trace_exc(abbrev=()):
    global indent
    
    stderr.flush()
    indent += 1
    try:
        yield
    except BaseException as exc:
        result()
        line("raise", optrepr(exc, "raise" in abbrev))
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
        line()
    margin()

def line(*pos, **kw):
    global midline
    print(*pos, file=stderr, **kw)
    midline = False

def margin():
    global midline
    for _ in range(indent):
        stderr.write("  ")
    midline = True
