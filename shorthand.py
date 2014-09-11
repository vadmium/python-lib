from contextlib import contextmanager

try:
    from types import SimpleNamespace
except ImportError:
    class SimpleNamespace(object):
        """Generic object with attributes provided as keyword arguments"""
        def __init__(self, **kw):
            self.__dict__.update(kw)
        def __repr__(self):
            return "{0}({1})".format(type(self).__name__,
                ", ".join("{0}={1!r}".format(name, value)
                for (name, value) in self.__dict__.items()))

def strip(s, start="", end=""):
    if start and not s.startswith(start):
        raise ValueError("Expected {0!r} starting string".format(start))
    if end and not s.endswith(end):
        raise ValueError("Expected {0!r} ending string".format(end))
    if len(s) < len(start) + len(end):
        raise ValueError(
            "String not enclosed by {0!r} and {1!r}".format(start, end))
    return s[len(start):len(s) - len(end)]

def bitmask(size):
    return ~(~0 << size)
