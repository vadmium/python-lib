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
                if ("import" not in abbrev and
                getattr(func, "__module__", None) is not None):
                    self.name = "{0}.{1}".format(func.__module__, self.name)
        else:
            self.name = name
        self.abbrev = abbrev
    
    def __call__(self, *args, **kw):
        global startline
        global indent
        
        if not startline:
            print(file=stderr)
        margin(stderr)
        startline = False
        
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
        global startline
        global indent
        
        indent -= 1
        
        if disp is None:
            disp = key
        
        if startline:
            margin(stderr)
        else:
            stderr.write(" ")
        print(disp, repr(v, key in self.abbrev), file=stderr)
        startline = True

def Tracer(name):
    return traced(nop, name=name, abbrev=set(("return",)))

def print_call(name, args, kw, abbrev=set()):
    print(name, end="(", file=stderr)
    
    for (k, v) in enumerate(args):
        if k:
            stderr.write(", ")
        stderr.write(repr(v, k in abbrev))
    
    comma = bool(args)
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
startline = True

def margin(file):
    for _ in range(indent):
        file.write("  ")

def nop(*pos, **kw):
    pass
