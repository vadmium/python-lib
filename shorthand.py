import sys
import weakref
from os.path import basename
import os
from types import MethodType
from functools import partial
from collections import namedtuple
from misc import deco_factory

try:
    import builtins
except ImportError:
    import __builtin__ as builtins

class Record(object):
    def __init__(self, *args, **kw):
        self.__dict__.update(*args, **kw)
    def __repr__(self):
        return "{0}({1})".format(type(self).__name__,
            ", ".join("{0}={1!r}".format(name, value)
            for (name, value) in self.__dict__.items()))

def assimilate(name, fromlist):
    module = __import__(name, fromlist=fromlist)
    for name in fromlist:
        setattr(builtins, name, getattr(module, name))

@deco_factory
def fields(f, *args, **kw):
    "Decorator factory to add arbitrary fields to function object"
    f.__dict__.update(*args, **kw)
    return f

def nop(*args, **kw):
    pass

FieldType = namedtuple("Field", "key, value")
def Field(**kw):
    (field,) = kw.items()
    return FieldType(*field)
