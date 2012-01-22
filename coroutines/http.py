# Reference: https://tools.ietf.org/html/rfc2616

from http.client import (
    HTTP_PORT, UnknownTransferEncoding, BadStatusLine, UnknownProtocol)
from lib import event
import email.parser

def get(sock, hostname, path):
    yield sock.send(b"GET ")
    for c in path.encode("UTF-8"):
        if c <= ord(b" "):
            yield sock.send(b"%{:02X}".format(c))
        else:
            yield sock.send(bytes((c,)))
    
    yield sock.send(b" HTTP/1.1\r\n"
        
        # Mandatory for 1.1:
        b"Host: "
    )
    yield sock.send(hostname.encode())
    yield sock.send(b"\r\n"
        b"\r\n"
    )

class HTTPConnection(object):
    def __init__(self, sock):
        self.sock = sock
    
    def getresponse(self):
        parser = Parser(self.sock)
        # else: parser.new_line()
        yield parser.next_char()
        
        try:
            # if response does not begin "HTTP/n.n 999 ", assume HTTP/0.9
            # simple-response
            
            try:
                pre_space = (yield parser.space())
            except ExcessError as e:
                raise BadStatusLine(e.data)
            if parser.eol:
                raise BadStatusLine(pre_space + parser.eol + parser.c)
            
            pattern = b"HTTP/"
            for (i, p) in enumerate(pattern):
                if i:
                    yield parser.next_char()
                if not parser.c or ord(parser.c) != p:
                    raise BadStatusLine(pre_space + pattern[:i] + parser.c)
            
            major = bytearray()
            for _ in range(parser.NUMBER_LIMIT):
                yield parser.next_char()
                if parser.c == b".":
                    break
                major.extend(parser.c)
                if not parser.c.isdigit():
                    raise BadStatusLine(pre_space + pattern + major)
            else:
                raise BadStatusLine(pre_space + pattern + major)
            
            minor = bytearray()
            for _ in range(parser.NUMBER_LIMIT):
                yield parser.next_char()
                if not parser.c.isdigit():
                    break
                minor.extend(parser.c)
            else:
                raise BadStatusLine(pre_space + pattern + major + b"." +
                    minor)
            
            mid_space = bytearray()
            for i in range(parser.TOKEN_LIMIT):
                if i:
                    yield parser.next_char()
                if not parser.c or parser.c.isspace():
                    break
                mid_space.extend(parser.c)
            try:
                space = (yield parser.space())
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
                    yield parser.next_char()
                status.extend(parser.c)
                if not parser.c.isdigit():
                    raise BadStatusLine(pre_space + pattern + major + b"." +
                        minor + mid_space + status)
        
        except BadStatusLine as e:
            (pending,) = e.args
            msg = message_from_string(b"")
        
        else:
            if int(major) != 1:
                raise UnknownProtocol("HTTP/{}".format(major))
            
            yield parser.next_char()
            yield parser.space()
            
            reason = bytearray()
            for i in range(400):
                if i:
                    yield parser.next_char()
                    yield parser.after_eol()
                if parser.eol is not None:
                    if not parser.at_lws():
                        break
                    else:
                        reason.extend(parser.eol)
                reason.extend(parser.c)
            else:
                raise ExcessError("Excessive status reason")
            reason = reason.rstrip()
            
            msg = (yield parser.headers())
            
            # pending = parser.c
        
        te = msg.get_all("Transfer-Encoding", [])
        try:
            last = te[-1]
        except LookupError:
            yield parser.after_eol()
            raise StopIteration(IdentityResponse(self.sock, parser, msg))
        
        # TODO: better parsing: eliminate null elements; check for "identity"
        (*split, last) = last.rsplit(",", 1)
        if last.strip().lower() != "chunked":
            raise UnknownTransferEncoding("Not chunked transfer encoding")
        
        # Remove "chunked" from end of header value
        try:
            (split,) = split
        except ValueError:
            te.pop()
        else:
            te[-1] = split.rstrip()
        
        # Replace header fields back into message object
        del msg["Transfer-Encoding"]
        for i in te:
            msg["Transfer-Encoding"] = i
        
        raise StopIteration(ChunkedResponse(self.sock, parser, msg))

class IdentityResponse(object):
    def __init__(self, sock, parser, msg):
        self.sock = sock
        self.msg = msg
        (self.size,) = self.msg.get_all("Content-Length", [])
        self.size = int(self.size)
        if self.size:
            self.data = parser.c
        else:
            self.data = None
    
    def read(self, amt):
        if self.data is None:
            data = (yield self.sock.recv(min(self.size, amt)))
        else:
            data = self.data
            self.data = None
        self.size -= len(data)
        raise StopIteration(data)

class ChunkedResponse(object):
    def __init__(self, sock, parser, msg):
        self.sock = sock
        self.msg = msg
        self.chunks = self.Chunks(parser)
        self.size = None
    
    def read(self, amt):
        if self.size:
            data = (yield self.sock.recv(min(self.size, amt)))
        else:
            (self.size, data) = (yield self.chunks)
        self.size -= len(data)
        raise StopIteration(data)
    
    def Chunks(self, parser):
        """
        Generator that returns chunk length and the first byte of each chunk
        
        Entry with parser.c = Start of EOL following headers
        """
        
        for _ in range(30000):
            yield parser.after_eol()
            yield parser.space()
            
            size = 0
            if parser.eol is None:
                for _ in range(30):
                    try:
                        digit = int(parser.c, 16)
                    except ValueError:
                        break
                    size = size * 16 + digit
                    yield parser.next_char()
                else:
                    raise ExcessError("Excessive chunk size")
                yield parser.after_eol()
            
            i = 0
            while parser.eol is None:
                i += 1
                if i >= 3000:
                    raise ExcessError("Excessive line")
                yield self.next_char()
                yield self.after_eol()
            
            if not size:
                yield event.Yield((0, b""))
                break
            
            yield event.Yield((size, parser.c))
            
            yield parser.next_char()
        else:
            raise ExcessError("Excessive number of chunks")
        
        yield parser.headers()

class Parser(object):
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
                    raise StopIteration(parser.close())
                else:
                    parser.feed(self.eol.decode("Latin-1"))
            parser.feed(self.c.decode("Latin-1"))
            yield self.next_char()
            yield self.after_eol()
        else:
            raise ExcessError("Excessive headers")
    
    def space(self):
        """Read and skip over spaces
        
        Entry with c = any char
        """
        
        space = bytearray()
        for i in range(self.SPACE_LIMIT):
            if i:
                yield self.next_char()
            yield self.after_eol()
            if not self.at_lws():
                raise StopIteration(bytes(space))
            
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
        yield self.next_char()
        if self.eol == b"\r" and self.c == b"\n":
            self.eol = CRLF
            yield self.next_char()
    
    def at_eol(self):
        return not self.c or self.c in CRLF
    
    def at_lws(self):
        return self.c.isspace() and self.c not in CRLF
    
    def next_char(self):
        self.c = (yield self.sock.recv(1))

class ExcessError(EnvironmentError):
    def __init__(self, msg, data=None):
        EnvironmentError.__init__(self, msg)
        self.data = data

CRLF = b"\r\n"
