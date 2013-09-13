"""Utilities for working with functions"""

import sys
import weakref
from types import MethodType
from functools import partial

class Bindable(object):
    def __get__(self, obj, cls=None):
        if obj is None:
            return self
        return MethodType(self, obj)

class Function(Bindable):
    def __init__(self, name=None):
        # By default, name the function after its class
        self.__name__ = name or type(self).__name__

class WrapperFunction(Function):
    from functools import (update_wrapper, WRAPPER_ASSIGNMENTS)
    def __init__(self, wrapped, assigned=WRAPPER_ASSIGNMENTS, *args, **kw):
        self.update_wrapper(wrapped, assigned, *args, **kw)
        
        # Python 2 does not add this, and Python 3 overwrites it with
        # wrapped.__wrapped__ when updating self.__dict__
        self.__wrapped__ = wrapped
        
        # Python 2 cannot assign these unless they are guaranteed to exist
        for name in {"__defaults__", "__code__"}.difference(assigned):
            try:
                value = getattr(wrapped, name)
            except AttributeError:
                continue
            setattr(self, name, value)
        
        try:
            self.__kwdefaults__ = wrapped.__kwdefaults__
        except AttributeError:
            pass
    
    def __get__(self, *pos, **kw):
        binding = self.__wrapped__.__get__(*pos, **kw)
        # Avoid Python 2's unbound methods, with __self__ = None
        if binding is self.__wrapped__ or binding.__self__ is None:
            return self
        else:
            return type(binding)(self, binding.__self__)

class decorator(WrapperFunction):
    """Decorator to help create other decorators
    
    This can be used to create simple decorators that accept arguments:
    
        @decorator
        def arg_decorator(func, param): return implementation(func, param)
        
        @arg_decorator("arg")
        def func(): ...
    
    is equivalent to
    
        def func(): ...
        func = implementation(func, "arg")
    
    This can also be used to create wrapper decorators:
    
        @decorator
        def wrapper(func, *args): return implementation(func, *args)
        
        class C:
            @wrapper
            def method(self, param): ...
        
        C().method("arg")
    
    is equivalent to
    
        implementation(C.method, C(), "arg")"""
    
    def __call__(self, *args, **kw):
        return BindingPartial(self.__wrapped__, *args, **kw)

class BindingPartial(partial, Bindable):
    pass

class weakmethod(object):
    """Decorator wrapper for methods that binds to objects using a weak
    reference"""
    def __init__(self, func):
        self.func = func
    def __get__(self, obj, cls):
        if obj is None:
            return self
        return WeakBinding(self.func, obj)

class WeakBinding(object):
    def __init__(self, func, obj):
        self.__func__ = func
        self.ref = weakref.ref(obj)
    
    @property
    def __self__(self):
        obj = self.ref()
        if obj is None:
            raise ReferenceError("weakly bound instance to method {0!r} "
                "no longer exists".format(self.__func__))
        return obj
    
    def __call__(self, *args, **kw):
        obj = self.__self__
        return self.__func__.__get__(obj, type(obj))(*args, **kw)
    
    def __repr__(self):
        return "<{0} of {1} to {2}>".format(
            type(self).__name__, self.__func__, self.ref())

@decorator
def attributes(f, *args, **kw):
    """Decorator to add arbitrary attributes to a function object
    
    Example:
        @attributes(key="value")
        def function(): ...
    """
    f.__dict__.update(*args, **kw)
    return f

def dummy(*args, **kw):
    pass

def setitem(dict, key):
    """Decorator that adds the definition to a dictionary with a given key"""
    def decorator(define):
        dict[key] = define
        return define
    return decorator
