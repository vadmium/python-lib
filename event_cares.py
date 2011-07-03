from PyQt4 import QtCore
import event
import cares
import math

class CaresResolver:
    def __init__(self):
        self.event = CaresQtEvent(self)
        self.channel = cares.Channel(sock_state_cb=self.event.sock_state_cb)
    
    def resolve(self, name):
        self.status = None
        self.channel.gethostbyname(name, 0, self.host_callback)
        while self.status is None:
            yield self.event
        cares.check(self.status)
        raise StopIteration(
            (self.hostent["addrtype"], self.hostent["addr_list"][0],))
    
    def host_callback(self, status, timeouts, hostent):
        self.status = status
        self.hostent = hostent

class CaresEvent(event.Event):
    note_types = {
        "read": QtCore.QSocketNotifier.Read,
        "write": QtCore.QSocketNotifier.Write,
    }
    
    def __init__(self, resolver):
        self.resolver = resolver
        self.socks = dict((x, dict(),) for x in self.note_types.keys())
        self.timer = QtCore.QTimer(singleShot=True, timeout=self.timed_out)
    
    def sock_state_cb(self, s, read, write):
        if not read and not write:
            for x in self.socks.values():
                x.pop(s, None)
            return
        
        for (type, active, callback,) in (
            ("read", read, self.readable,),
            ("write", write, self.writable,),
        ):
            socks = self.socks[type]
            try:
                socks[s].active = active
            except KeyError:
                if active:
                    note = QtCore.QSocketNotifier(s, self.note_types[type],
                        activated=callback)
                    note.setEnabled(False)
                    socks[s] = dict(note=note, active=True)
    
    def arm(self, callback):
        self.client = callback
        timeout = self.resolver.channel.timeout()
        if timeout is not None:
            self.timer.start(math.ceil(timeout * 1000))
        self.set_armed(True)
    
    def readable(self, socket):
        self.triggered((socket, None,))
    def writable(self, socket):
        self.triggered((None, socket,))
    def timed_out(self):
        self.triggered((None, None,))
    
    def triggered(self, cares_fds):
        self.timer.stop()
        self.set_armed(False)
        
        self.resolver.channel.process_fd(*cares_fds)
        
        self.client()
    
    def set_armed(self, enabled):
        for socks in self.socks.values():
            for sock in socks.values():
                if sock["active"]:
                    sock["note"].setEnabled(enabled)
