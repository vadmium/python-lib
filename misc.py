import sys
from os.path import basename
import os
from functions import setitem
from functions import Function, WrapperFunction
from functools import partial
import os.path
from collections import Mapping

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
    
    def fixup_rename(new, old, self, *pos, **kw):
        try:
            self.__wrapped__(new, *pos, **kw)
        except ImportError:
            module = self.__wrapped__(old, *pos, **kw)
            (parent, sep, name) = new.partition(".")
            if sep:
                # Parent module (if any) should be imported despite error
                setattr(sys.modules[parent], name, module)
            sys.modules[new] = module
    
    for (new, old) in (
        ("builtins", "__builtin__"),
        ("reprlib", "repr"),
        ("tkinter", "Tkinter"),
        ("tkinter.filedialog", "tkFileDialog"),
        ("tkinter.ttk", "ttk"),
        ("urllib.parse", "urlparse"),
    ):
        fixups[new] = partial(fixup_rename, new, old)
    
    @setitem(fixups, "io")
    def fixup_io(self, *pos, **kw):
        io = self.__wrapped__("io", *pos, **kw)
        if not hasattr(io, "SEEK_CUR"):
            io.SEEK_CUR = self.__wrapped__("os", *pos, **kw).SEEK_CUR
    
    @setitem(fixups, "types")
    def fixup_types(self, *pos, **kw):
        types = self.__wrapped__("types", *pos, **kw)
        if not hasattr(types, "InstanceType"):
            types.InstanceType = object
        if not hasattr(types, "ClassType"):
            types.ClassType = type

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

def joinpath(path, base=""):
    """Validates and joins a sequence of path elements into an OS path
    
    Each path element is an individual directory, subdirectory or file
    name. Raises ValueError if an element name is not supported by the
    OS."""
    
    illegal_names = frozenset(
        ("", os.path.curdir, os.path.pardir, os.path.devnull))
    for elem in path:
        if os.path.dirname(elem) or elem in illegal_names:
            fmt = "Path element not supported by OS: {0!r}"
            raise ValueError(fmt.format(elem))
    return os.path.join(base, *path)

def relpath(path, start=""):
    """Converts an OS path string to an OS independent path tuple
    
    The given path must be relative to the starting directory."""
    
    p = parsepath(path)
    s = parsepath(os.path.normcase(start))
    startlen = len(s)
    if (len(p) < startlen or
    any(os.path.normcase(p) != s for (p, s) in zip(p[:startlen], s))):
        fmt = "Path {!r} does not start with {!r}"
        raise ValueError(fmt.format(path, start))
    return p[startlen:]

def parsepath(path):
    """Returns a tuple (root, dir, subdir, . . ., file)
    
    The "root" element is always present. It is an empty string when a
    relative path is given. The other elements may be missing if the path
    was simply the root element (or empty)."""
    
    # Strip any trailing slashes not part of the root
    (head, tail) = os.path.split(path)
    if not tail:
        path = head
    
    parts = list()
    while True:
        (path, tail) = os.path.split(path)
        if not tail:
            break
        parts.append(tail)
    parts.append(path)
    parts.reverse()
    return tuple(parts)

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

class UnicodeMap(Mapping):
    """Base class for str.translate() dictionaries"""
    
    def __iter__(self):
        return iter(range(len(self)))
    def __len__(self):
        return sys.maxunicode + 1
    
    def __getitem__(self, cp):
        return self.map_char(chr(cp))
    def map_char(self, char):
        raise KeyError()
