import socket
import ssl
from ssl import SSLWantReadError, SSLWantWriteError
from misc import Context
from asyncio import Future

class Socket(Context):
    """Provides coroutines for common blocking socket operations"""
    
    def __init__(self, *args, loop, **kw):
        self.loop = loop
        self.sock = socket.socket(*args, **kw)
        self.sock.setblocking(False)
    
    async def connect(self, *args, **kw):
        while True:
            try:
                self.sock.connect(*args, **kw)
                break
            except BlockingIOError:
                pass
            future = Future(loop=self.loop)
            self.loop.add_writer(self.sock.fileno(), future.set_result, None)
            await future
    
    async def recv(self, *args, **kw):
        while True:
            try:
                return self.sock.recv(*args, **kw)
            except (BlockingIOError, SSLWantReadError):
                pass
            future = Future(loop=self.loop)
            self.loop.add_reader(self.sock.fileno(), future.set_result, None)
            await future
    
    async def sendall(self, data, *args, **kw):
        while data:
            try:
                data = data[self.sock.send(data, *args, **kw):]
                break
            except SSLWantReadError:
                future = Future(loop=self.loop)
                self.loop.add_reader(self.sock.fileno(), future.set_result,
                    None)
                await future
    
    def close(self, *args, **kw):
        self.sock.close(*args, **kw)

class Ssl(Socket):
    def __init__(self, context, socket):
        self.loop = socket.loop
        self.sock = context.wrap_socket(socket.sock,
            do_handshake_on_connect=False)
    
    async def handshake(self, *args, **kw):
        while True:
            try:
                self.sock.do_handshake(*args, **kw)
                break
            except SSLWantReadError:
                add_watcher = self.loop.add_reader
            except SSLWantWriteError:
                add_watcher = self.loop.add_writer
            future = Future(loop=self.loop)
            add_watcher(self.sock.fileno(), future.set_result, None)
            await future
