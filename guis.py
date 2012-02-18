from types import MethodType

class MethodClass(type):
    def __get__(self, obj, cls):
        if obj is None:
            return self
        return MethodType(self, obj)
