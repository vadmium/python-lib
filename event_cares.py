from PyQt4 import QtCore
import event
import cares
import math
from socket import AF_UNSPEC

def resolve(name, family=AF_UNSPEC):
    self = ResolveContext()
    
    self.timer = QtCore.QTimer(singleShot=True)
    self.timer_event = QtSignalEvent(self.timer.timed_out)
    
    channel = cares.Channel(sock_state_cb=self.sock_state)
    
    channel.gethostbyname(name, family, self.host)
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
        
        fds = dict.fromkeys(self.sockops)
        if isinstance(trigger, SocketEvent):
            (fd,) = args
            fds[trigger.note.type()] = fd
        channel.process_fd(fds[self.read], fds[self.write])
    cares.check(self.status)
    raise StopIteration(self.hostent)

class ResolveContext:
    read = QtCore.QSocketNotifier.Read
    write = QtCore.QSocketNotifier.Write
    sockops = (read, write,)
    
    def __init__(self):
        self.status = None
        self.socks = dict((x, set()) for x in self.sockops)
    
    def sock_state(self, s, read, write):
        for op in self.sockops:
            if {self.read: read, self.write: write}[op]:
                self.socks[op].add(s)
            else:
                self.socks[op].discard(s)
    
    def host(self, status, timeouts, hostent):
        self.status = status
        self.hostent = hostent
