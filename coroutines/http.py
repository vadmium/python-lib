# Reference: https://tools.ietf.org/html/rfc2616

def response_handler(sock):
    parser = Parser(sock)
    yield parser.next_char()
    
    class Http0_9(BaseException):
        pass
    
    try:
        # if response does not begin "HTTP/n.n 999 ", assume HTTP/0.9
        # simple-response
        
        try:
            pre_space = (yield parser.space())
        except ExcessError as e:
            raise Http0_9(e.data)
        if parser.eol:
            raise Http0_9(pre_space + parser.eol + parser.c)
        
        pattern = b"HTTP/"
        for (i, p) in enumerate(pattern):
            if i:
                yield parser.next_char()
            if not parser.c or ord(parser.c) != p:
                raise Http0_9(pre_space + pattern[:i] + parser.c)
        
        major = bytearray()
        for _ in range(parser.NUMBER_LIMIT):
            yield parser.next_char()
            if parser.c == b".":
                break
            major.extend(parser.c)
            if not parser.c.isdigit():
                raise Http0_9(pre_space + pattern + major)
        else:
            raise Http0_9(pre_space + pattern + major)
        
        minor = bytearray()
        for _ in range(parser.NUMBER_LIMIT):
            yield parser.next_char()
            if not parser.c.isdigit():
                break
            minor.extend(parser.c)
        else:
            raise Http0_9(pre_space + pattern + major + b"." + minor)
        
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
            raise Http0_9(pre_space + pattern + major + b"." + minor +
                mid_space + e.data)
        mid_space.extend(space)
        if parser.eol:
            raise Http0_9(pre_space + pattern + major + b"." + minor +
                mid_space + parser.eol + parser.c)
        
        status = bytearray()
        for i in range(3):
            if i:
                yield parser.next_char()
            status.extend(parser.c)
            if not parser.c.isdigit():
                raise Http0_9(pre_space + pattern + major + b"." + minor +
                    mid_space + status)
    
    except Http0_9 as e:
        (pending,) = e.args
        chunked = False
    
    else:
        if int(major) != 1:
            raise EnvironmentError("Unsupported: HTTP/{}".format(major))
        
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
        
        chunked = (yield parser.headers())
        
        # pending = parser.c
    
    if not chunked:
        raise NotImplementedError("Not chunked transfer encoding")
    
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
        yield parser.line()
        
        if not size:
            break
        
        if size > 3000000:
            raise ExcessError("Excessive chunk")
        data = parser.c
        from sys import stdout
        while True:
            stdout.buffer.write(data)
            size -= len(data)
            if size <= 0:
                break
            
            data = (yield sock.recv(min(size, 0x1000)))
            if not data:
                break
        
        yield parser.next_char()
    else:
        raise ExcessError("Excessive number of chunks")
    
    print("done")
    yield parser.headers()
    print("parsed trailers")

class Parser(object):
    def __init__(self, sock):
        self.sock = sock
    
    SPACE_LIMIT = 8
    TOKEN_LIMIT = 120
    NUMBER_LIMIT = 9
    
    def headers(self):
        """
        Entry with c = any char
        Leaves with c = start of eol
        """
        
        chunked = False
        
        #~ message = Message()
        
        for _ in range(300):
            # End of headers if direct CRLF
            if self.at_eol():
                raise StopIteration(chunked)
            
            # read <token> :
            # ws, chars except crlf and :, :, then rstrip token)
            # If crlf before :, ignore the line
            yield self.space()
            
            name = bytearray()
            pattern = b"Transfer-Encoding".lower()
            for p in pattern:
                if (self.eol is not None or
                not self.c or ord(self.c.lower()) != p):
                    match = False
                    break
                yield self.next_char()
                yield self.after_eol()
            else:
                match = True
            for i in range(self.TOKEN_LIMIT):
                if i:
                    yield self.next_char()
                    yield self.after_eol()
                
                if self.at_lws():
                    pass
                elif self.eol is not None or self.c == b":":
                    break
                else:
                    match = False
                
                #~ if eol:
                    #~ name.extend(eol)
                #~ name.extend(c)
            else:
                raise ExcessError("Excessive token")
            
            if self.eol is None:
                yield self.next_char()
                yield self.space()
            
            if match:
                pattern = b"chunked".lower()
                for p in pattern:
                    if (self.eol is not None or
                    not self.c or ord(self.c.lower()) != p):
                        match = False
                        break
                    yield self.next_char()
                    yield self.after_eol()
            substance = (yield self.line())
            
            chunked |= match and not substance
        else:
            raise ExcessError("Excessive number of headers")
    
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
    
    def line(self):
        """Skip until the end of line is reached
        
        Entry after calling after_eol
        """
        
        substance = False
        for i in range(3000):
            if i:
                yield self.next_char()
                yield self.after_eol()
            
            if self.at_lws():
                pass
            elif self.eol is not None:
                raise StopIteration(substance)
            else:
                substance = True
        else:
            raise ExcessError("Excessive line")

    def after_eol(self):
        """eol, c -> (c, eol)
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
