"""Log function call details"""

from __future__ import print_function

from sys import stderr
from misc import (WrapperFunction, Function)
from contextlib import contextmanager

try:  # Python 3
    import reprlib
except ImportError:  # Python < 3
    import repr as reprlib

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
        line("->", repr(ret, "return" in self.abbrev))
        return ret
    
    def __repr__(self):
        return "{0.__class__.__name__}({1})".format(
            self, funcname(self.name))

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
        line("raise", repr(exc, "raise" in abbrev))
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
