import socket
import ssl
from ssl import SSLWantReadError, SSLWantWriteError

class Socket:
    """Provides coroutines for common blocking socket operations"""
    
    def __init__(self, event_driver, *args, **kw):
        self.sock = socket.socket(*args, **kw)
        self.sock.setblocking(False)
        self.event = event_driver.FileEvent(self.sock.fileno())
    
    def connect(self, *args, **kw):
        while True:
            try:
                self.sock.connect(*args, **kw)
                break
            except BlockingIOError:
                # Avoid yielding in exception handler
            yield self.event.writable()
    
    def recv(self, *args, **kw):
        while True:
            try:
                return self.sock.recv(*args, **kw)
            except (BlockingIOError, SSLWantReadError):
                # Avoid yielding in exception handler
            yield self.event.readable()
    
    def send(self, data, *args, **kw):
        while data:
            data = data[self.sock.send(data, *args, **kw):]
        if False:
            yield
    
    def close(self, *args, **kw):
        self.sock.close(*args, **kw)

class Ssl(Socket):
    def __init__(self, *args, **kw):
        Socket.__init__(self, *args, **kw)
        self.sock = ssl.wrap_socket(self.sock, do_handshake_on_connect=False)
    
    def handshake(self, *args, **kw):
        while True:
            try:
                self.sock.do_handshake(*args, **kw)
                break
            except SSLWantReadError:
                event = self.event.readable
            except SSLWantWriteError:
                event = self.event.writable
            yield event()
