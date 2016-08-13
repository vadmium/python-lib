#! /usr/bin/env python3

import sys
from unittest import TestCase, TestSuite, SkipTest
from functions import decorator
from clifunc import run
import clifunc

try:  # Python < 3
    from cStringIO import StringIO
except ImportError:  # Python 3
    from io import StringIO

@decorator
def suite_add(suite, Test):
    suite.addTest(Test())
    return Test

@decorator
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
    clifunc.help(Fixture().f, capture)
    
    self.maxDiff = None
    self.assertEqual("""\
Summary line

parameters: [-mand] <str> [[-defnone] <str>] [-noarg] [[-multi] <str> . . .] [<var> . . .] -mand-opt=<str> [-optzero=<str>] [-noarg-opt] [-multi-opt=<str> . . .]
defaults: -optzero=0

Docstring body
""", capture.getvalue())

@suite_add(suite)
@testfunc()
def positional(self):
    """Test function is called correctly"""
    fixture = Fixture()
    run(fixture.f, "em -mand-opt emo".split())
    self.assertEqual(dict(fixture.defaults, mand="em", mand_opt="emo"),
        fixture.values)

@suite_add(suite)
@testfunc()
def options(self):
    fixture = Fixture()
    run(fixture.f,
        "-mand=em -defnone=dee -noarg -multi m1 "
        "-mand-opt=emo -multi=m2 -optzero ozed -multi-opt mo1 -noarg-opt".
    split())
    self.assertEqual(dict(fixture.defaults,
        mand="em", defnone="dee", noarg=True, multi=["m1", "m2"],
        mand_opt="emo", optzero="ozed", multi_opt=["mo1"], noarg_opt=True,
    ), fixture.values)

@suite_add(suite)
@testfunc()
def types(self):
    """Test argument types"""
    fixture = Fixture()
    fixture.f.param_types = dict(
        var=float, mand_opt=set, optzero=int, multi_opt=float)
    run(fixture.f,
        "-mand-opt=hallo -optzero -12 -multi-opt=inf -multi-opt=01.0e+01 "
        "mand x x x -- 0 -1 +.625e-1".
    split())
    
    self.assertEqual("mand", fixture.values["mand"])
    self.assertEqual((0, -1, 0.0625), fixture.values["var"])
    self.assertEqual(set("halo"), fixture.values["mand_opt"])
    self.assertEqual(-12, fixture.values["optzero"])
    self.assertEqual([float("inf"), 10], fixture.values["multi_opt"])

@suite_add(suite)
@testfunc()
def type_names(self):
    """Parameter name checking for "param_types" attribute"""
    fixture = Fixture()
    fixture.f.param_types = dict({"*": int}, optzero=int, invalid=int)
    with self.assertRaises(TypeError):
        run(fixture.f, "x -mand-opt=x".split())

@suite_add(suite)
@testfunc()
def nodoc(self):
    """Help should work without any docstring"""
    
    def f():
        pass
    clifunc.help(f, StringIO())

@suite_add(suite)
@testfunc()
def frozen(self):
    """Input parameters should not be modified"""
    
    def f(a, b):
        pass
    f.param_types = dict(a=int)
    
    args = "7 42".split()
    param_types = dict(b=int)
    run(f, args, param_types=param_types)
    self.assertEqual("7 42".split(), args)
    self.assertEqual(dict(b=int), param_types)

# Test variable arguments
# Test variable keyword arguments
# Test __main__.main and argv defaults

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
        
        scope = dict()
        try:  # Python 3
            exec(r'''\
                def func(mand, defnone=None, noarg=False, multi=(), *var,
                mand_opt, optzero=0, noarg_opt=False, multi_opt=frozenset()):
                    """Summary line
                    
                    Docstring body"""
                    
                    for name in self.params:
                        self.values[name] = vars()[name]
                ''', locals(), scope)
        except SyntaxError as err:  # Python < 3
            raise SkipTest(err)
        self.f = scope["func"]

if __name__ == "__main__":
    import unittest
    unittest.main()
