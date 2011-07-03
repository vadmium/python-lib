from __future__ import division

import atexit
import sys
import math

from ctypes import (
    CDLL,
    c_char_p, c_void_p, c_int, c_char, c_ushort, c_long,
    byref, CFUNCTYPE, POINTER, Structure,
)

# Maybe platform-dependent?
class HostEnt(Structure):
    _fields_ = (
        ("h_name", c_char_p,),
        ("h_aliases", POINTER(c_char_p),),
        ("h_addrtype", c_int,),
        ("h_length", c_int,),
        ("h_addr_list", POINTER(POINTER(c_char)),),
    )

lib = CDLL("libcares.so.2")

def library_init():
    check(lib.ares_library_init(1))

def library_cleanup():
    lib.ares_library_cleanup()

def check(res):
    if res:
        raise EnvironmentError(res, strerror(res))

def strerror(res):
    f = lib.ares_strerror
    f.restype = c_char_p
    return f(res)

def version():
    f = lib.ares_version
    f.restype = c_char_p
    return f(None)

class Channel:
    def __init__(self, **options):
        self.channel = c_void_p()
        self.host_callbacks = set()
        
        opt_struct = Options()
        optmask = 0
        
        if "sock_state_cb" in options:
            self.sock_state_cb = SockStateCb(options["sock_state_cb"])
            opt_struct.sock_state_cb = self.sock_state_cb.c_func
            opt_struct.sock_state_cb_data = None
            optmask ^= 1 << 9
        
        check(lib.ares_init_options(byref(self.channel),
            byref(opt_struct), optmask))
    
    def __del__(self):
        lib.ares_destroy(self.channel)
    
    def gethostbyname(self, name, family, callback):
        lib.ares_gethostbyname(self.channel, c_char_p(name.encode()),
            c_int(family),
            HostCallback(callback).arm(self.host_callbacks), None)
    
    # TODO: getnameinfo?
    
    def timeout(self):
        """
        Returns the maximum time before "process" should be called. If there
        is no limit, "None" is returned.
        """
        
        tv = Timeval()
        f = lib.ares_timeout
        f.restype = POINTER(Timeval)
        if f(self.channel, None, byref(tv)):
            return float(tv)
        else:
            return None
    
    def process_fd(self, read_fd, write_fd):
        # Beware: Windows's FDs are special
        if read_fd is None:
            read_fd = -1
        if write_fd is None:
            write_fd = -1
        
        f = lib.ares_process_fd
        f.restype = None
        f(self.channel, c_int(read_fd), c_int(write_fd))

class CCallback:
    def __init__(self, callback):
        self.callback = callback
        self.c_func = self.type(self.exc_trap)
    
    def exc_trap(self, *args):
        """
        Trap all exceptions to avoid waking dragons in C-types-land
        """
        
        try:
            self.py_func(*args)
        except:
            sys.excepthook(*sys.exc_info())

class SockStateCb(CCallback):
    type = CFUNCTYPE(None, c_void_p, c_int, c_int, c_int)
    def py_func(self, arg, s, read, write):
        self.callback(s, read, write)

class Options(Structure):
    _fields_ = (
        ("flags", c_int,),
        ("timeout", c_int,),
        ("tries", c_int,),
        ("ndots", c_int,),
        ("udp_port", c_ushort,),
        ("tcp_port", c_ushort,),
        ("socket_send_buffer_size", c_int,),
        ("socket_receive_buffer_size", c_int,),
        ("servers", c_void_p,),
        ("nservers", c_int,),
        ("domains", c_void_p,),
        ("ndomains", c_int,),
        ("lookups", c_void_p,),
        ("sock_state_cb", SockStateCb.type,),
        ("sock_state_cb_data", c_void_p,),
        ("sortlist", c_void_p,),
        ("nsort", c_int,),
    )

class HostCallback(CCallback):
    type = CFUNCTYPE(None, c_void_p, c_int, c_int, POINTER(HostEnt))
    
    def arm(self, refs):
        refs.add(self)
        self.refs = refs
        return self.c_func
    
    def py_func(self, arg, status, timeouts, hostent):
        # Assuming each callback is only ever called once
        self.refs.remove(self)
        del self.c_func # Break circular garbage reference
        
        if status != 0:
            hostent = None
        else:
            addr_list = []
            while True:
                addr = hostent.contents.h_addr_list[len(addr_list)]
                if not addr:
                    break
                addr_list.append(bytes(addr[:4]))
            hostent=dict(
                name=hostent.contents.h_name,
                #~ h_aliases=
                addrtype=hostent.contents.h_addrtype,
                #~ h_length=hostent.contents.h_length,
                addr_list=addr_list,
            )
        
        self.callback(status, timeouts, hostent)

library_init()
atexit.register(library_cleanup)

class Timeval(Structure):
    _fields_ = (("tv_sec", c_long,), ("tv_usec", c_long,),)
    USEC_SECS = 10 ** 6
    
    def __float__(self):
        return self.tv_sec + self.tv_usec / self.USEC_SECS
