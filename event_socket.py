import socket
import ssl
import errno

class Socket:
    """
    Wraps a Python socket. Provides co-routines for common blocking socket
    operations, intended for use with the event.Routine class.
    """
    
    def __init__(self, event_driver, *args, **kw):
        self.sock = socket.socket(*args, **kw)
        self.sock.setblocking(False)
        self.event = event_driver.FileEvent(self.sock.fileno())
    
    def connect(self, *args, **kw):
        while True:
            try:
                self.sock.connect(*args, **kw)
                break
            except socket.error as err:
                if err.errno != errno.EINPROGRESS:
                    raise
                # Avoid yielding in exception handler
            yield self.event.writable()
    
    def recv(self, *args, **kw):
        while True:
            try:
                raise StopIteration(self.sock.recv(*args, **kw))
            except ssl.SSLError as err:
                if err.args[0] != ssl.SSL_ERROR_WANT_READ:
                    raise
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
        
        self.ssl_events = {
            ssl.SSL_ERROR_WANT_READ: self.readable,
            ssl.SSL_ERROR_WANT_WRITE: self.writable,
        }
    
    def handshake(self, *args, **kw):
        while True:
            try:
                self.sock.do_handshake(*args, **kw)
                break
            except ssl.SSLError as err:
                if err.args[0] not in self.ssl_events:
                    raise
                # Avoid yielding in exception handler
                event = self.ssl_events[err.args[0]]
            yield event
