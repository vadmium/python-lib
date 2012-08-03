from types import MethodType

def probe():
    try:
        from wingui import Win
    except ImportError:
        from tkgui import Tix
        return Tix()
    return Win()

class MethodClass(type):
    def __get__(self, obj, cls):
        if obj is None:
            return self
        return MethodType(self, obj)
