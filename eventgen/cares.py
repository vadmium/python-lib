from __future__ import print_function

from . import Select
import cares
from socket import (AF_UNSPEC, AF_INET, AF_INET6)
from sys import stderr

def name_connect(event_driver, hostname, port, Socket,
callback=None, message=None):
    if message is not None:
        callback = MessageCallback(message)
    
    resolved = False
    
    for family in (AF_UNSPEC, AF_INET6, AF_INET):
        if callback is not None:
            callback.lookingup(hostname, family)
        try:
            hostent = (yield resolve(event_driver, hostname, family))
        except EnvironmentError as e:
            print(e, file=stderr)
            continue
        resolved = True
        
        sock = Socket(hostent.addrtype)
        try:
            for addr in hostent.addr_list:
                if callback is not None:
                    callback.connecting(addr, port)
                try:
                    yield sock.connect((addr, port))
                except EnvironmentError as e:
                    print(e, file=stderr)
                    continue
                break
            else:
                sock.close()
                continue
        except:
            sock.close()
            raise
        raise StopIteration(sock)
    
    else:
        if resolved:
            raise EnvironmentError("All addresses unconnectable: {0}".format(
                hostname))
        else:
            raise EnvironmentError("Failure resolving {0}".format(hostname))

class MessageCallback(object):
    def __init__(self, callback):
        self.callback = callback
    def lookingup(self, name, family):
        self.callback("Looking up {0} (family {1})".format(name, family))
    def connecting(self, addr, port):
        self.callback("Connecting to {0}:{1}".format(addr, port))

def resolve(event_driver, name, family=AF_UNSPEC):
    self = ResolveContext(event_driver)
    timer = event_driver.Timer()
    
    channel = cares.Channel(sock_state_cb=self.sock_state)
    
    channel.gethostbyname(name, family, self.host)
    while self.status is None:
        events = Select(self.files.values())
        
        timeout = channel.timeout()
        if timeout is not None:
            timer.start(timeout)
            events.add(timer)
        
        try:
            (trigger, args) = (yield events)
        finally:
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
