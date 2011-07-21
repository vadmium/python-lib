from PyQt4 import QtCore
import event
import cares
import math

def resolve(name):
    self = ResolveContext()
    
    self.timer = QtCore.QTimer(singleShot=True)
    self.timer_event = QtSignalEvent(self.timer.timed_out)
    
    channel = cares.Channel(sock_state_cb=self.sock_state)
    
    channel.gethostbyname(name, 0, self.host)
    while self.status is None:
        events = event.EventSet()
        
        timeout = channel.timeout()
        if timeout is not None:
            timer.start(math.ceil(timeout * 1000))
            events.add(timer.event)
        
        for op in self.sockops:
            for sock in self.socks[op]:
                events.add(QtSocketEvent(sock, qt_type))
        
        (trigger, args) = (yield events)
        timer.stop()
        
        fds = {x: None for x in self.sockops}
        if isinstance(trigger, SocketEvent):
            (fd,) = args
            fds[trigger.note.type()] = fd
        channel.process_fd(fds[self.read], fds[self.write])
    cares.check(self.status)
    raise StopIteration(
        (self.hostent["addrtype"], self.hostent["addr_list"][0],))

class ResolveContext:
    read = QtCore.QSocketNotifier.Read
    write = QtCore.QSocketNotifier.Write
    sockops = (read, write,)
    
    def __init__(self):
        self.status = None
        self.socks = {x: set() for x in self.sockops}
    
    def sock_state(self, s, read, write):
        for op in self.sockops:
            if {self.read: read, self.write: write}[op]:
                self.socks[op].add(s)
            else:
                self.socks[op].discard(s)
    
    def host(self, status, timeouts, hostent):
        self.status = status
        self.hostent = hostent
