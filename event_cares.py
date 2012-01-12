from __future__ import print_function

from lib import event
from lib import cares
from socket import (SOCK_STREAM, AF_UNSPEC, AF_INET, AF_INET6)
from event_socket import Socket
from sys import stderr

def name_connect(event_driver, hostname, port, type=SOCK_STREAM,
callback=None):
    sock = None
    
    for family in (AF_UNSPEC, AF_INET6, AF_INET):
        if callback is not None:
            callback.lookingup(hostname, family)
        try:
            hostent = (yield resolve(event_driver, hostname, family))
        except EnvironmentError as e:
            print(e, file=stderr)
            continue
        
        sock = Socket(event_driver, hostent.addrtype, type)
        
        for addr in hostent.addr_list:
            if callback is not None:
                callback.connecting(addr, port)
            try:
                yield sock.connect((addr, port))
            except EnvironmentError as e:
                print(e, file=stderr)
                continue
            raise StopIteration(sock)
    
    else:
        if sock is None:
            raise EnvironmentError("Failure resolving {0}".format(hostname))
        else:
            raise EnvironmentError("All addresses unconnectable: {0}".format(
                hostname))

def resolve(event_driver, name, family=AF_UNSPEC):
    self = ResolveContext(event_driver)
    timer = event_driver.Timer()
    
    channel = cares.Channel(sock_state_cb=self.sock_state)
    
    channel.gethostbyname(name, family, self.host)
    while self.status is None:
        events = event.Any(self.files.values())
        
        timeout = channel.timeout()
        if timeout is not None:
            timer.start(timeout)
            events.add(timer)
        
        (trigger, args) = (yield events)
        timer.stop()
        
        if trigger is timer:
            ops = ()
        else:
            (fd, ops) = args
        channel.process_fd(*(fd if (op in ops) else None for op in self.ops))
    cares.check(self.status)
    raise StopIteration(self.hostent)

class ResolveContext:
    def __init__(self, event_driver):
        self.FileEvent = event_driver.FileEvent
        self.status = None
        self.files = dict()  # File events by file descriptor
        self.ops = (self.FileEvent.READ, self.FileEvent.WRITE)
    
    def sock_state(self, s, *ops):
        if any(ops):
            try:
                event = self.files[s]
            except LookupError:
                event = self.FileEvent(s)
                self.files[s] = event
            event.watch(op for (op, enable) in zip(self.ops, ops) if enable)
        else:
            try:
                del self.files[s]
            except LookupError:
                pass
    
    def host(self, status, timeouts, hostent):
        self.status = status
        self.hostent = hostent
