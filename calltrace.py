#coding=UTF-8
from __future__ import print_function

from sys import stderr
from misc import WrapperFunction
import reprlib

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
        global indent
        
        start()
        print_call(self.name, args, kw, self.abbrev)
        stderr.flush()
        indent += 1
        try:
            ret = self.__wrapped__(*args, **kw)
        except BaseException as exc:
            self.print_result("raise", exc)
            raise
        else:
            self.print_result("return", ret, "->")
            return ret
    
    def print_result(self, key, v, disp=None):
        global indent
        indent -= 1
        
        if disp is None:
            disp = key
        
        if midline:
            stderr.write(" ")
        else:
            margin(stderr)
        line(disp, repr(v, key in self.abbrev))

class Tracer(WrapperFunction):
    def __init__(self, name, abbrev=()):
        self.name = name
        self.abbrev = abbrev
    def __call__(self, *pos, **kw):
        start()
        print_call(self.name, pos, kw, abbrev=self.abbrev)
        line()

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
