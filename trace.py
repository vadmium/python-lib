#coding=UTF-8
from __future__ import print_function

from sys import stderr
from lib import Function
from lib import nop

class traced(Function):
    def __init__(self, func, name=None, abbrev=set()):
        self.func = func
        if name is None:
            try:
                self.name = func.__name__
            except AttributeError:
                self.name = repr(func)
            else:
                if "from" not in abbrev and func.__module__ is not None:
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
            ret = self.func(*args, **kw)
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
        
        if key in self.abbrev:
            v = "..."
        else:
            v = repr(v)
        if startline:
            margin(stderr)
        else:
            stderr.write(" ")
        print(disp, v, file=stderr)
        startline = True

def trace(func, *args, **kw):
    return traced(func)(*args, **kw)
def Tracer(name):
    return traced(nop, name=name, abbrev=set(("return",)))

def print_call(name, args, kw, abbrev=set()):
    print(name, end="(", file=stderr)
    
    for (k, v) in enumerate(args):
        if k:
            stderr.write(", ")
        if k in abbrev:
            v = "..."
        else:
            v = repr(v)
        stderr.write(v)
    
    comma = bool(args)
    for (k, v) in kw.items():
        if comma:
            stderr.write(", ")
        if k in abbrev:
            v = "..."
        else:
            v = repr(v)
        stderr.write("{0}={1}".format(k, v))
        comma = True
    
    stderr.write(")")

indent = 0
startline = True

def margin(file):
    for _ in range(indent):
        file.write("  ")
