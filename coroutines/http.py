"""
API modelled around the built-in "http.client" package
"""

# Reference: https://tools.ietf.org/html/rfc2616

from http.client import (
    UnknownTransferEncoding, BadStatusLine, UnknownProtocol, HTTPException)
import coroutines
import email.parser

class HTTPConnection:
    def __init__(self, sock):
        self.sock = sock
    
    def request(self, method, hostname, path):
        yield from self.sock.sendall(method.encode())
        yield from self.sock.sendall(b" ")
        for c in path.encode("utf-8"):
            if c <= ord(b" "):
                yield from self.sock.sendall(b"%{:02X}".format(c))
            else:
                yield from self.sock.sendall(bytes((c,)))
        
        yield from self.sock.sendall(b" HTTP/1.1\r\n"
            
            # Mandatory for 1.1:
            b"Host: "
        )
        yield from self.sock.sendall(hostname.encode())
        # User-Agent: python-event-http
        # X-Forwarded-For: . . .
        yield from self.sock.sendall(b"\r\n"
            b"\r\n"
        )
    
    def getresponse(self):
        parser = Parser(self.sock)
        # else: parser.new_line()
        yield from parser.next_char()
        
        #~ try:
        if True:
            #~ # if response does not begin "HTTP/n.n 999 ", assume HTTP/0.9
            #~ # simple-response
            
            try:
                pre_space = yield from parser.space()
            except ExcessError as e:
                raise BadStatusLine(e.data)
            if parser.eol:
                raise BadStatusLine(pre_space + parser.eol + parser.c)
            
            pattern = b"HTTP/"
            for (i, p) in enumerate(pattern):
                if i:
                    yield from parser.next_char()
                if not parser.c or ord(parser.c) != p:
                    raise BadStatusLine(pre_space + pattern[:i] + parser.c)
            
            major = bytearray()
            for _ in range(parser.NUMBER_LIMIT):
                yield from parser.next_char()
                if parser.c == b".":
                    break
                major.extend(parser.c)
                if not parser.c.isdigit():
                    raise BadStatusLine(pre_space + pattern + major)
            else:
                raise BadStatusLine(pre_space + pattern + major)
            
            minor = bytearray()
            for _ in range(parser.NUMBER_LIMIT):
                yield from parser.next_char()
                if not parser.c.isdigit():
                    break
                minor.extend(parser.c)
            else:
                raise BadStatusLine(pre_space + pattern + major + b"." +
                    minor)
            
            mid_space = bytearray()
            for i in range(parser.TOKEN_LIMIT):
                if i:
                    yield from parser.next_char()
                if not parser.c or parser.c.isspace():
                    break
                mid_space.extend(parser.c)
            try:
                space = yield from parser.space()
            except ExcessError as e:
                raise BadStatusLine(pre_space + pattern + major + b"." +
                    minor + mid_space + e.data)
            mid_space.extend(space)
            if parser.eol:
                raise BadStatusLine(pre_space + pattern + major + b"." +
                    minor + mid_space + parser.eol + parser.c)
            
            status = bytearray()
            for i in range(3):
                if i:
                    yield from parser.next_char()
                status.extend(parser.c)
                if not parser.c.isdigit():
                    raise BadStatusLine(pre_space + pattern + major + b"." +
                        minor + mid_space + status)
        
        #~ except BadStatusLine as e:
        if False:
            (pending,) = e.args
            status = None
            reason = None
            from email import message_from_string
            msg = message_from_string("")
        
        else:
            if int(major) != 1:
                raise UnknownProtocol("HTTP/{}".format(major))
            
            yield from parser.next_char()
            yield from parser.space()
            
            reason = bytearray()
            for i in range(400):
                if i:
                    yield from parser.next_char()
                    yield from parser.after_eol()
                if parser.eol is not None:
                    if not parser.at_lws():
                        break
                    else:
                        reason.extend(parser.eol)
                reason.extend(parser.c)
            else:
                raise ExcessError("Status reason of 400 or more characters")
            reason = reason.rstrip()
            
            msg = yield from parser.headers()
            
            # pending = parser.c
        
        te = msg.get_all("Transfer-Encoding", [])
        if not te:
            yield from parser.after_eol()
            return IdentityResponse(status, reason, msg, self.sock, parser)
        
        last = te.pop()
        # TODO: better parsing: eliminate null elements; check for "identity"
        (prev, sep, last) = last.rpartition(",")
        if last.strip().lower() != "chunked":
            raise UnknownTransferEncoding("Not chunked transfer encoding")
        
        # Remove "chunked" from end of header value
        if sep:
            te.append(prev.rstrip())
        
        # Replace header fields back into message object
        del msg["Transfer-Encoding"]
        for i in te:
            msg["Transfer-Encoding"] = i
        
        return ChunkedResponse(status, reason, msg, self.sock, parser)

class HTTPResponse:
    def __init__(self, status, reason, msg):
        self.status = int(status)
        self.reason = reason.decode("latin-1")
        self.msg = msg

class IdentityResponse(HTTPResponse):
    def __init__(self, status, reason, msg, sock, parser):
        HTTPResponse.__init__(self, status, reason, msg)
        self.sock = sock
        length = iter(self.msg.get_all("Content-Length", ()))
        self.size = int(next(length))
        for dupe in length:
            if int(dupe) != self.size:
                raise HTTPException("Conflicting Content-Length values")
        if self.size:
            self.data = parser.c
        else:
            self.data = None
    
    def read(self, amt):
        if self.data is None:
            data = yield from self.sock.recv(min(self.size, amt))
        else:
            data = self.data
            self.data = None
        self.size -= len(data)
        return data

class ChunkedResponse(HTTPResponse):
    def __init__(self, status, reason, msg, sock, parser):
        HTTPResponse.__init__(self, status, reason, msg)
        self.sock = sock
        self.chunks = self.Chunks(parser)
        self.size = None
    
    def read(self, amt):
        if self.size:
            data = yield from self.sock.recv(min(self.size, amt))
        else:
            (self.size, data) = yield from self.chunks
        self.size -= len(data)
        return data
    
    def Chunks(self, parser):
        """
        Generator that returns chunk length and the first byte of each chunk
        
        Entry with parser.c = Start of EOL following headers
        """
        
        for _ in range(30000):
            yield from parser.after_eol()
            yield from parser.space()
            
            size = 0
            if parser.eol is None:
                for _ in range(30):
                    try:
                        digit = int(parser.c, 16)
                    except ValueError:
                        break
                    size = size * 16 + digit
                    yield from parser.next_char()
                else:
                    raise ExcessError("Chunk size of 30 or more digits")
                yield from parser.after_eol()
            
            i = 0
            while parser.eol is None:
                i += 1
                if i >= 3000:
                    raise ExcessError("Line of 3000 or more characters")
                yield from self.next_char()
                yield from self.after_eol()
            
            if not size:
                yield from coroutines.Yield((0, b""))
                break
            
            yield from coroutines.Yield((size, parser.c))
            
            yield from parser.next_char()
        else:
            raise ExcessError("30000 or more chunks")
        
        yield from parser.headers()

class Parser:
    """
    "c" may hold last read character; empty string at EOF
    "eol" may ...
    """
    
    def __init__(self, sock):
        self.sock = sock
    
    SPACE_LIMIT = 8
    TOKEN_LIMIT = 120
    NUMBER_LIMIT = 9
    
    def headers(self):
        """
        Entry with self.c = first character of headers
        Leaves with self.c = start of EOL which terminated the headers
        """
        
        parser = email.parser.FeedParser()
        
        self.eol = b""
        for _ in range(30000):
            if self.eol is not None:
                if self.at_eol():
                    return parser.close()
                else:
                    parser.feed(self.eol.decode("latin-1"))
            parser.feed(self.c.decode("latin-1"))
            yield from self.next_char()
            yield from self.after_eol()
        else:
            raise ExcessError("30000 or more headers")
    
    def space(self):
        """Read and skip over spaces
        
        Entry with c = any char
        """
        
        space = bytearray()
        for i in range(self.SPACE_LIMIT):
            if i:
                yield from self.next_char()
            yield from self.after_eol()
            if not self.at_lws():
                return bytes(space)
            
            if self.eol:
                space.extend(self.eol)
            space.extend(self.c)
        else:
            raise ExcessError("Excessive space", bytes(space))

    def after_eol(self):
        """Parses potential end of line and reads the next character
        
        Sets self.eol = EOL character sequence, if "self.c" was at EOL, or
            "None"
        Returns with self.c = next character, following EOL if found
        
        eol, c -> (c, eol)
        eol, EOF -> ("", eol)
        EOF -> ("", "")
        c != eol -> (c, None)
        
        Check for EOF: c == ""
        Check for EOL incl EOF: eol is not None
        True EOL: bool(eol)
        Check for LWS: c.isspace()
        """
        
        if not self.at_eol():
            self.eol = None
            return
        
        self.eol = self.c
        yield from self.next_char()
        if self.eol == b"\r" and self.c == b"\n":
            self.eol = CRLF
            yield from self.next_char()
    
    def at_eol(self):
        return not self.c or self.c in CRLF
    
    def at_lws(self):
        return self.c.isspace() and self.c not in CRLF
    
    def next_char(self):
        self.c = yield from self.sock.recv(1)

class ExcessError(EnvironmentError):
    def __init__(self, msg, data=None):
        EnvironmentError.__init__(self, msg)
        self.data = data

CRLF = b"\r\n"
