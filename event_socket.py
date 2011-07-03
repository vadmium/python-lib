from PyQt4 import QtCore
import socket
import ssl
import errno

class Socket:
    """
    Wraps a Python socket and corresponding QT read and write notification
    events. Provides co-routines for common blocking socket operations,
    intended for use with the event.Routine class.
    """
    
    def __init__(self, *args, **kw):
        self.sock = socket.socket(*args, **kw)
        self.sock.setblocking(False)
        
        self.readable = \
            SocketQtEvent(self.sock.fileno(), QtCore.QSocketNotifier.Read)
        self.writable = \
            SocketQtEvent(self.sock.fileno(), QtCore.QSocketNotifier.Write)
    
    def connect(self, *args, **kw):
        while True:
            try:
                self.sock.connect(*args, **kw)
                break
            except socket.error as err:
                if err.errno != errno.EINPROGRESS:
                    raise
                yield self.writable
    
    def recv(self, *args, **kw):
        while True:
            try:
                raise StopIteration(self.sock.recv(*args, **kw))
            except ssl.SSLError as err:
                if err.args[0] != ssl.SSL_ERROR_WANT_READ:
                    raise
                yield self.readable
    
    def send(self, data, *args, **kw):
        while data:
            data = data[self.sock.send(data, *args, **kw):]
        if False:
            yield

class Ssl(Socket):
    def __init__(self, *args, **kw):
        Socket.__init__(self, *args, **kw)
        self.sock = ssl.wrap_socket(self.sock, do_handshake_on_connect=False)
    
    def handshake(self, *args, **kw):
        while True:
            try:
                self.sock.do_handshake(*args, **kw)
                break
            except ssl.SSLError as err:
                if err.args[0] == ssl.SSL_ERROR_WANT_READ:
                    yield self.readable
                elif err.args[0] != ssl.SSL_ERROR_WANT_WRITE:
                    yield self.writable
                else:
                    raise
