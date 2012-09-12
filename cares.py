from __future__ import division

# C-ares library man pages: http://c-ares.haxx.se/docs.html

# See also:
# http://pyuv.readthedocs.org/en/latest/dns.html

import atexit
import math
import weakref

from ctypes import (
    CDLL,
    c_char_p, c_void_p, c_int, c_char, c_ushort, c_long,
    byref, CFUNCTYPE, POINTER, Structure,
)
from misc import exc_sink
from misc import weakmethod
from collections import namedtuple
from socket import inet_ntop

import socket
globals().update((k, v)
    for (k, v) in vars(socket).items() if k.startswith("AF_"))

# Standard <netdb.h> structure
class HostEntC(Structure):
    _fields_ = (
        ("h_name", c_char_p,),
        ("h_aliases", POINTER(c_char_p),),
        ("h_addrtype", c_int,),
        ("h_length", c_int,),
        ("h_addr_list", POINTER(POINTER(c_char)),),
    )
HostEnt = namedtuple("HostEnt",
    (k[len("h_"):] for (k, _) in HostEntC._fields_))

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
    return f(res).decode()

def version():
    f = lib.ares_version
    f.restype = c_char_p
    return f(None)

class Channel:
    def __init__(self, **options):
        self.channel = c_void_p()
        self.host_callback_refs = set()
        
        opt_struct = Options()
        optmask = 0
        
        try:
            self.sock_state_cb_ref = (
                SockStateCb(options["sock_state_cb"]).cfunc())
        except LookupError:
            pass
        else:
            opt_struct.sock_state_cb = self.sock_state_cb_ref
            opt_struct.sock_state_cb_data = None
            optmask ^= 1 << 9
        
        check(lib.ares_init_options(byref(self.channel),
            byref(opt_struct), optmask))
    
    def __del__(self):
        lib.ares_destroy(self.channel)
    
    def gethostbyname(self, name, family, callback):
        callback = HostCallback().arm(self.host_callback_refs, callback)
        lib.ares_gethostbyname(self.channel, c_char_p(name.encode()),
            c_int(family), callback, None)
    
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

class SockStateCb:
    def __init__(self, callback):
        self.callback = callback
    
    def cfunc(self):
        return self.ctype(self)
    
    ctype = CFUNCTYPE(None, c_void_p, c_int, c_int, c_int)
    
    @exc_sink
    def __call__(self, arg, s, read, write):
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
        ("sock_state_cb", SockStateCb.ctype),
        ("sock_state_cb_data", c_void_p,),
        ("sortlist", c_void_p,),
        ("nsort", c_int,),
    )

class HostCallback:
    def arm(self, refs, callback):
        self.callback = callback
        refs.add(self)
        self.refs = weakref.ref(refs)
        
        self.cfunc = CFUNCTYPE(None,
            c_void_p, c_int, c_int, POINTER(HostEntC))(self.proxy)
        return self.cfunc
        
    @weakmethod
    @exc_sink
    def proxy(self, arg, status, timeouts, hostent):
        # Assuming each callback is only ever called once
        self.refs().remove(self)
        
        if status != 0:
            hostent = None
        else:
            addr_list = []
            while True:
                addr = hostent.contents.h_addr_list[len(addr_list)]
                if not addr:
                    break
                addr_list.append(inet_ntop(hostent.contents.h_addrtype,
                    addr[:hostent.contents.h_length]))
            hostent = HostEnt(
                name=hostent.contents.h_name,
                aliases=NotImplemented,
                addrtype=hostent.contents.h_addrtype,
                length=hostent.contents.h_length,
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
