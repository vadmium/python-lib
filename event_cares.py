from PyQt4 import QtCore
import event
import cares
import math

class CaresResolver:
    sock_notes = {
        "r": QtCore.QSocketNotifier.Read,
        "w": QtCore.QSocketNotifier.Write,
    }
    
    def __init__(self):
        self.channel = cares.Channel(sock_state_cb=self.sock_state_cb)
        
        self.timer = QtCore.QTimer(singleShot=True)
        self.timer_event = QtSignalEvent(self.timer.timed_out)
        
        self.active_socks = dict((x, set(),) for x in sock_notes.keys())
    
    def sock_state_cb(self, s, read, write):
        for (type, active,) in {"r": read, "w": write}.items():
            if active:
                self.socks[type].add(s)
            else:
                self.socks[type].discard(s)
        
        if not read and not write:
            for x in self.socks.values():
                x.pop(s, None)
            return
    
    def resolve(self, name):
        self.status = None
        
        self.channel.gethostbyname(name, 0, self.host_callback)
        while self.status is None:
            events = event.EventSet()
            
            timeout = self.resolver.channel.timeout()
            if timeout is not None:
                self.timer.start(math.ceil(timeout * 1000))
                events.add(self.timer.event, ("timer",))
            
            for (type, qt_type,) in self.sock_notes.items():
                for sock in self.socks[type]:
                    events.add(QtSocketEvent(sock, qt_type), ("sock", type,))
            
            ((id, *args,), result,) = (yield events)
            
            fds = dict.fromkeys(self.sock_notes.keys(), None)
            if id == "sock":
                self.timer.stop()
                fds[args[0]] = result
            self.resolver.channel.process_fd(fds["r"], fds["w"])
        
        cares.check(self.status)
        raise StopIteration(
            (self.hostent["addrtype"], self.hostent["addr_list"][0],))
    
    def host_callback(self, status, timeouts, hostent):
        self.status = status
        self.hostent = hostent
