#coding=UTF-8
from __future__ import print_function

from sys import stderr
from lib import Function

class traced(Function):
    def __init__(self, func, name=None, abbrev=set()):
        self.func = func
        if name is None:
            self.name = func.__name__
        else:
            self.name = name
        self.abbrev = abbrev
    
    def __call__(self, *args, **kw):
        print(self.name, end="(", file=stderr)
        
        for (k, v) in enumerate(args):
            if k:
                print(", ", end="", file=stderr)
            if k in self.abbrev:
                v = "..."
            else:
                v = repr(v)
            print(v, end="", file=stderr)
        
        comma = bool(args)
        for (k, v) in kw:
            if comma:
                print(", ", end="", file=stderr)
            if k in self.abbrev:
                v = "..."
            else:
                v = repr(v)
            print("{}={}".format(k, v), end="", file=stderr)
            comma = True
        
        print(end=") ", file=stderr)
        stderr.flush()
        ret = self.func(*args, **kw)
        if "return" in self.abbrev:
            v = "..."
        else:
            v = repr(ret)
        print("->", v, file=stderr)
        return ret

def trace(func, *args, **kw):
    traced(func)(*args, **kw)
def tracer(name):
    return traced(nop, name=name, abbrev=set(("return",)))
def nop(*args, **kw):
    pass
