"""
API modelled around the built-in "http.client" package
"""

# Reference: https://tools.ietf.org/html/rfc2616

from http.client import (
    UnknownTransferEncoding, UnknownProtocol, HTTPException)
import http.client
import email.parser
import net
from . import AsyncioGenerator

class HTTPConnection:
    def __init__(self, sock):
        self.sock = sock
    
    async def putrequest(self, method, target):
        await self.sock.sendall(method.encode())
        await self.sock.sendall(b" ")
        for c in target.encode("utf-8"):
            if c <= ord(b" "):
                await self.sock.sendall(b"%{:02X}".format(c))
            else:
                await self.sock.sendall(bytes((c,)))
        
        await self.sock.sendall(b" HTTP/1.1\r\n")
    
    AGENT = "coroutines.http (Vadmium)"
    
    async def endheaders(self):
        await self.sock.sendall(b"\r\n")
    
    async def putheader(self, name, value):
        await self.sock.sendall(name.encode("ascii"))
        await self.sock.sendall(b": ")
        await self.sock.sendall(value.encode("ascii"))
        await self.sock.sendall(b"\r\n")
    
    async def getresponse(self):
        parser = Parser(self.sock)
        # else: parser.new_line()
        await parser.next_char()
        
        #~ try:
        if True:
            #~ # if response does not begin "HTTP/n.n 999 ", assume HTTP/0.9
            #~ # simple-response
            
            try:
                pre_space = await parser.space()
            except ExcessError as e:
                raise BadStatusLine(e.data)
            if parser.c == b"\n":
                raise BadStatusLine(pre_space + parser.c)
            
            pattern = b"HTTP/"
            for (i, p) in enumerate(pattern):
                if i:
                    await parser.next_char()
                if not parser.c or ord(parser.c) != p:
                    raise BadStatusLine(pre_space + pattern[:i] + parser.c)
            
            major = bytearray()
            for _ in range(parser.NUMBER_LIMIT):
                await parser.next_char()
                if parser.c == b".":
                    break
                major.extend(parser.c)
                if not parser.c.isdigit():
                    raise BadStatusLine(pre_space + pattern + major)
            else:
                raise BadStatusLine(pre_space + pattern + major)
            
            minor = bytearray()
            for _ in range(parser.NUMBER_LIMIT):
                await parser.next_char()
                if not parser.c.isdigit():
                    break
                minor.extend(parser.c)
            else:
                raise BadStatusLine(pre_space + pattern + major + b"." +
                    minor)
            
            mid_space = bytearray()
            for i in range(parser.TOKEN_LIMIT):
                if i:
                    await parser.next_char()
                if not parser.c or parser.c.isspace():
                    break
                mid_space.extend(parser.c)
            try:
                space = await parser.space()
            except ExcessError as e:
                raise BadStatusLine(pre_space + pattern + major + b"." +
                    minor + mid_space + e.data)
            mid_space.extend(space)
            if parser.c == b"\n":
                raise BadStatusLine(pre_space + pattern + major + b"." +
                    minor + mid_space + parser.c)
            
            status = bytearray()
            for i in range(3):
                if i:
                    await parser.next_char()
                status.extend(parser.c)
                if not parser.c.isdigit():
                    raise BadStatusLine(pre_space + pattern + major + b"." +
                        minor + mid_space + status)
        
        if int(major) != 1:
            raise UnknownProtocol("HTTP/{}".format(major))
        
        await parser.next_char()
        await parser.space()
        
        reason = bytearray()
        for _ in range(400):
            current = parser.c
            reason.extend(current)
            await parser.next_char()
            if current in b"\n" and not parser.at_lws():  # Including EOF
                break
        else:
            raise ExcessError("Status reason of 400 or more characters")
        reason = reason.rstrip()
        
        msg = await parser.headers()
        
        encodings = net.header_list(msg, "Transfer-Encoding")
        encoding = next(encodings, None)
        if not encoding:
            lengths = net.header_list(msg, "Content-Length")
            length = next(lengths, None)
            if length is None:
                return _EofResponse(status, reason, msg, self.sock)
            else:
                return _LengthResponse(status, reason, msg,
                    self.sock, length, lengths)
        
        # TODO: check for "identity"
        encodings = next(encodings, None)
        if encodings is not None or encoding.lower() != "chunked":
            raise UnknownTransferEncoding("Not chunked transfer encoding")
        del msg["Transfer-Encoding"]
        
        return _ChunkedResponse(status, reason, msg, self.sock)

class HTTPResponse:
    def __init__(self, status, reason, msg):
        self.status = int(status)
        self.reason = reason.decode("latin-1")
        self.msg = msg

class _EofResponse(HTTPResponse):
    def __init__(self, status, reason, msg, sock):
        HTTPResponse.__init__(self, status, reason, msg)
        self.sock = sock
    
    def read(self, amt):
        return self.sock.recv(amt)

class _LengthResponse(HTTPResponse):
    def __init__(self, status, reason, msg, sock, length, lengths):
        HTTPResponse.__init__(self, status, reason, msg)
        self.sock = sock
        self.size = int(length)
        for dupe in lengths:
            if int(dupe) != self.size:
                raise HTTPException("Conflicting Content-Length values")
    
    async def read(self, amt):
        data = await self.sock.recv(min(self.size, amt))
        self.size -= len(data)
        return data

class _ChunkedResponse(HTTPResponse):
    def __init__(self, status, reason, msg, sock):
        HTTPResponse.__init__(self, status, reason, msg)
        self.sock = sock
        self.chunk_gen = AsyncioGenerator()
        self.chunks = self.Chunks()
        self.size = None
    
    async def read(self, amt):
        if not self.size:
            self.size = await self.chunk_gen.next(self.chunks)
        data = await self.sock.recv(min(self.size, amt))
        self.size -= len(data)
        return data
    
    async def Chunks(self):
        """
        Generator that returns chunk length
        """
        
        for _ in range(30000):
            await parser.next_char()
            if parser.c == b"\r":
                await parser.next_char()
            if parser.c == b"\n":
                await parser.next_char()
            await parser.space()
            
            size = 0
            for _ in range(30):
                try:
                    digit = int(parser.c, 16)
                except ValueError:
                    break
                size = size * 16 + digit
                await parser.next_char()
            else:
                raise ExcessError("Chunk size of 30 or more digits")
            
            i = 0
            while parser.c not in b"\n":  # Including EOF
                i += 1
                if i >= 3000:
                    raise ExcessError("Line of 3000 or more characters")
                await self.next_char()
            
            if not size:
                await self.chunk_gen.generate(0)
                break
            
            await self.chunk_gen.generate(size)
        else:
            raise ExcessError("30000 or more chunks")
        
        await parser.headers()

class Parser:
    """
    "c" may hold last read character; empty string at EOF
    """
    
    def __init__(self, sock):
        self.sock = sock
    
    SPACE_LIMIT = 8
    TOKEN_LIMIT = 120
    NUMBER_LIMIT = 9
    
    async def headers(self):
        """
        Entry with self.c = first character of headers
        Leaves with self.c not set
        """
        
        parser = email.parser.FeedParser()
        
        blank_line = True
        for _ in range(30000):
            if not self.c:
                break
            parser.feed(self.c.decode("latin-1"))
            if self.c == b"\n":
                if blank_line:
                    break
                blank_line = True
            elif self.c != b"\r":
                blank_line = False
            await self.next_char()
        else:
            raise ExcessError("30000 or more headers")
        return parser.close()
    
    async def space(self):
        """Read and skip over spaces
        
        Entry with c = any char
        """
        
        space = bytearray()
        for i in range(self.SPACE_LIMIT):
            if i:
                await self.next_char()
            if not self.at_lws():
                return bytes(space)
            space.extend(self.c)
        else:
            raise ExcessError("Excessive space", bytes(space))
    
    def at_lws(self):
        return self.c.isspace() and self.c not in CRLF
    
    async def next_char(self):
        self.c = await self.sock.recv(1)

class ExcessError(EnvironmentError):
    def __init__(self, msg, data=None):
        EnvironmentError.__init__(self, msg)
        self.data = data

class BadStatusLine(http.client.BadStatusLine):
    def __init__(self, line):
        Exception.__init__(self, repr(line))

CRLF = b"\r\n"
