#coding=UTF-8
from __future__ import print_function

from sys import stderr
from lib import Function

class traced(Function):
    def __init__(self, func, name=None, abbrev=set()):
        self.func = func
        if name is None:
            self.name = "{0.__module__}.{0.__name__}".format(func)
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
        finally:
            indent -= 1
        
        if "return" in self.abbrev:
            v = "..."
        else:
            v = repr(ret)
        if startline:
            margin(stderr)
        else:
            stderr.write(" ")
        print("->", v, file=stderr)
        startline = True
        return ret

def trace(func, *args, **kw):
    return traced(func)(*args, **kw)
def tracer(name):
    return traced(nop, name=name, abbrev=set(("return",)))
def nop(*args, **kw):
    pass

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
