#coding=UTF-8
from __future__ import print_function

from sys import stderr
from misc import WrapperFunction
from contextlib import contextmanager

try:
    import reprlib
except ImportError:  # Library renamed from Python 2
    import repr as reprlib

class traced(WrapperFunction):
    def __init__(self, func, name=None, abbrev=set()):
        WrapperFunction.__init__(self, func)
        if name is None:
            try:
                self.name = func.__name__
            except AttributeError:
                self.name = reprlib.repr(func)
            else:
                if "import" not in abbrev:
                    module = getattr(func, "__module__", None)
                    if module is not None:
                        self.name = "{0}.{1}".format(module, self.name)
        else:
            self.name = name
        self.abbrev = abbrev
    
    def __call__(self, *args, **kw):
        start()
        print_call(self.name, args, kw, self.abbrev)
        with trace_exc(abbrev=self.abbrev):
            ret = self.__wrapped__(*args, **kw)
        result()
        line("->", repr(ret, "return" in self.abbrev))
        return ret

class Tracer(WrapperFunction):
    def __init__(self, name, abbrev=()):
        self.name = name
        self.abbrev = abbrev
    def __call__(self, *pos, **kw):
        start()
        print_call(self.name, pos, kw, abbrev=self.abbrev)
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
        line("raise", repr(exc, "raise" in abbrev))
        raise

def result():
    global indent
    indent -= 1
    if midline:
        stderr.write(" ")
    else:
        margin()

def print_call(name, pos=(), kw=dict(), abbrev=()):
    print(name, end="(", file=stderr)
    
    for (k, v) in enumerate(pos):
        if k:
            stderr.write(", ")
        stderr.write(repr(v, k in abbrev))
    
    comma = pos
    for (k, v) in kw.items():
        if comma:
            stderr.write(", ")
        stderr.write("{0}={1}".format(k, repr(v, k in abbrev)))
        comma = True
    
    stderr.write(")")

def repr(v, abbrev=False):
    if abbrev:
        return "..."
    else:
        return reprlib.repr(v)

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
