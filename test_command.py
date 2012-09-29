#! /usr/bin/env python

import sys
from io import StringIO
from unittest import (TestCase, TestSuite)
from misc import deco_factory
from funcparams import command
import funcparams

@deco_factory
def suite_add(suite, Test):
    suite.addTest(Test())
    return Test

@deco_factory
def testfunc(func, base=TestCase):
    return type(func.__name__, (base,), dict(runTest=func))

def load_tests(loader, default, pattern):
    return suite
suite = TestSuite()

@suite_add(suite)
@testfunc()
def help(self):
    """Test help works and everything that is meant to be there is there"""
    
    capture = StringIO()
    funcparams.help(Fixture().f, capture)
    
    self.maxDiff = None
    self.assertEqual(capture.getvalue(), """\
Parameters: [-mand] <str> [[-defnone] <str>] [-noarg | <str>] [[-multi] <str> . . .] [<var> . . .] -mand-opt=<str> [-optzero=<str>] [-noarg-opt] [-multi-opt=<str> . . .]
Defaults: -multi=() -optzero=0 -multi-opt=frozenset()

Test docstring
""")

@suite_add(suite)
@testfunc()
def positional(self):
    """Test function is called correctly"""
    fixture = Fixture()
    command(fixture.f, "em -mand-opt emo".split())
    self.assertEqual(fixture.values, dict(fixture.defaults,
        mand="em", mand_opt="emo"))

@suite_add(suite)
@testfunc()
def options(self):
    fixture = Fixture()
    command(fixture.f,
        "-mand=em -defnone=dee -noarg -multi m1 "
        "-mand-opt=emo -multi=m2 -optzero ozed -multi-opt mo1 -noarg-opt".
    split())
    self.assertEqual(fixture.values, dict(fixture.defaults,
        mand="em", defnone="dee", noarg=True, multi=["m1", "m2"],
        mand_opt="emo", optzero="ozed", multi_opt=["mo1"], noarg_opt=True,
    ))

@suite_add(suite)
@testfunc()
def types(self):
    """Test argument types"""
    fixture = Fixture()
    fixture.f.param_types = dict(
        {"*": float}, mand_opt=set, optzero=int, multi_opt=float)
    command(fixture.f,
        "-mand-opt=hallo -optzero -12 -multi-opt=inf -multi-opt=01.0e+01 "
        "mand x x x -- 0 -1 +.625e-1".
    split())
    
    self.assertEqual(fixture.values["mand"], "mand")
    self.assertEqual(fixture.values["var"], (0, -1, 0.0625))
    self.assertEqual(fixture.values["mand_opt"], set("halo"))
    self.assertEqual(fixture.values["optzero"], -12)
    self.assertEqual(fixture.values["multi_opt"], [float("inf"), 10])

@suite_add(suite)
@testfunc()
def type_names(self):
    """Parameter name checking for "param_types" attribute"""
    fixture = Fixture()
    fixture.f.param_types = dict({"*": int}, optzero=int, invalid=int)
    with self.assertRaises(TypeError):
        command(fixture.f, "x -mand-opt=x".split())

@suite_add(suite)
@testfunc()
def nodoc(self):
    """Help should work without any docstring"""
    
    def f():
        pass
    funcparams.help(f, StringIO())

@suite_add(suite)
@testfunc()
def frozen(self):
    """Input parameters should not be modified"""
    
    def f(a, b):
        pass
    f.param_types = dict(a=int)
    
    args = "7 42".split()
    param_types = dict(b=int)
    command(f, args, param_types=param_types)
    self.assertEqual(args, "7 42".split())
    self.assertEqual(param_types, dict(b=int))

# Test variable arguments
# Test variable keyword arguments
# Test __main__.main and argv defaults
# Skip testing keyword-only arguments for Python 2

class Fixture(object):
    params = (
        "mand, defnone, noarg, multi, var, "
        "mand_opt, optzero, noarg_opt, multi_opt".
    split(", "))
    
    defaults = dict(
        defnone=None, noarg=False, multi=(), var=(),
        optzero=0, noarg_opt=False, multi_opt=frozenset(),
    )
    
    def __init__(self):
        self.values = dict()
        
        def func(mand, defnone=None, noarg=False, multi=(), *var,
        mand_opt, optzero=0, noarg_opt=False, multi_opt=frozenset()):
            """Test docstring"""
            nonlocal self
            for name in self.params:
                self.values[name] = vars()[name]
        self.f = func

if __name__ == "__main__":
    import unittest
    unittest.main()
