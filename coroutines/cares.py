import cares
from socket import (AF_UNSPEC, AF_INET, AF_INET6)
from sys import stderr
from asyncio import Future
from net import format_addr

async def name_connect(event_driver, address, Socket, *,
        callback=None, message=None):
    hostname = address[0]
    if message is not None:
        callback = MessageCallback(message)
    
    resolved = False
    
    for family in (AF_UNSPEC, AF_INET6, AF_INET):
        if callback is not None:
            callback.lookingup(hostname, family)
        try:
            hostent = await resolve(event_driver, hostname, family)
        except EnvironmentError as e:
            print(e, file=stderr)
            continue
        resolved = True
        
        sock = Socket(hostent.addrtype)
        try:
            for attempt in hostent.addr_list:
                attempt = (attempt,) + address[1:]
                if callback is not None:
                    callback.connecting(attempt)
                try:
                    await sock.connect(attempt)
                except EnvironmentError as e:
                    print(e, file=stderr)
                    continue
                break
            else:
                sock.close()
                continue
            return sock
        except:
            sock.close()
            raise
    
    else:
        if resolved:
            raise EnvironmentError("All addresses unconnectable: {}".format(
                hostname))
        else:
            raise EnvironmentError("Failure resolving {}".format(hostname))

class MessageCallback:
    def __init__(self, callback):
        self.callback = callback
    def lookingup(self, name, family):
        self.callback("Looking up {} (family {})".format(name, family))
    def connecting(self, address):
        self.callback("Connecting to " + format_addr(address))

async def resolve(event_driver, name, family=AF_UNSPEC):
    self = ResolveContext(loop=event_driver)
    channel = cares.Channel(sock_state_cb=self.sock_state)
    channel.gethostbyname(name, family, self.host)
    while self.status is None:
        timeout = channel.timeout()
        if timeout is not None:
            timeout_result = (None, None)
            timeout = event_driver.call_later(timeout,
                self.sock_future.set_result, timeout_result)
        result = await self.sock_future
        if timeout is not None and result is not timeout_result:
            timeout.cancel()
        self.sock_future = Future(loop=event_driver)
        [read, write] = result
        if read is not None:
            self.loop.add_reader(read, self.sock_future.set_result, result)
        if write is not None:
            self.loop.add_writer(write, self.sock_future.set_result, result)
        channel.process_fd(read, write)
    cares.check(self.status)
    return self.hostent

class ResolveContext:
    def __init__(self, *, loop):
        self.loop = loop
        self.sock_future = Future(loop=self.loop)
        self.status = None
        self.reading = set()
        self.writing = set()
    
    def sock_state(self, s, read, write):
        if read:
            if s not in self.reading:
                result = (s, None)
                self.loop.add_reader(s, self.sock_future.set_result, result)
                self.reading.add(s)
        else:
            if s in self.reading:
                self.loop.remove_reader(s)
                self.reading.remove(s)
        
        if write:
            if s not in self.writing:
                result = (None, s)
                self.loop.add_writer(s, self.sock_future.set_result, result)
                self.writing.add(s)
        else:
            if s in self.writing:
                self.loop.remove_writer(s)
                self.writing.remove(s)
    
    def host(self, status, timeouts, hostent):
        self.status = status
        self.hostent = hostent
