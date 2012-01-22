# Reference: https://tools.ietf.org/html/rfc2616

SPACE_LIMIT = 8

def response_handler(sock):
    class Http0_9(BaseException):
        pass
    
    NUMBER_LIMIT = 9
    TOKEN_LIMIT = 120
    HEADER_LIMIT = 30000
    
    try:
        # if response does not begin "HTTP/n.n 999 ", assume HTTP/0.9
        # simple-response
        
        try:
            (c, eol, pre_space) = (yield parse_space(sock))
        except ExcessError as e:
            raise Http0_9(e.data)
        if eol:
            raise Http0_9(pre_space + eol + c)
        
        pattern = b"HTTP/"
        for (i, p) in enumerate(pattern):
            if i:
                c = (yield sock.recv(1))
            if not c or ord(c) != p:
                raise Http0_9(pre_space + pattern[:i] + c)
        
        major = bytearray()
        for _ in range(NUMBER_LIMIT):
            c = (yield sock.recv(1))
            if c == b".":
                break
            major.extend(c)
            if not c.isdigit():
                raise Http0_9(pre_space + pattern + major)
        else:
            raise Http0_9(pre_space + pattern + major)
        
        minor = bytearray()
        for _ in range(NUMBER_LIMIT):
            c = (yield sock.recv(1))
            if not c.isdigit():
                break
            minor.extend(c)
        else:
            raise Http0_9(pre_space + pattern + major + b"." + minor)
        
        mid_space = bytearray(c)
        for _ in range(TOKEN_LIMIT):
            if not c or c.isspace():
                break
            c = (yield sock.recv(1))
            mid_space.extend(c)
        try:
            (c, eol, space) = (yield parse_space(sock, c))
        except ExcessError as e:
            raise Http0_9(pre_space + pattern + major + b"." + minor +
                mid_space + e.data)
        mid_space.extend(space)
        if eol:
            raise Http0_9(pre_space + pattern + major + b"." + minor +
                mid_space + eol + c)
        
        status = bytearray()
        for i in range(3):
            if i:
                c = (yield sock.recv(1))
            status.extend(c)
            if not c.isdigit():
                raise Http0_9(pre_space + pattern + major + b"." + minor +
                    mid_space + status)
    
    except Http0_9 as e:
        (pending,) = e.args
        raise NotImplementedError("HTTP/0.9")
    
    else:
        if int(major) != 1:
            raise EnvironmentError("Unsupported: HTTP/{}".format(major))
        
        (c, eol, _) = (yield parse_space(sock))
        
        reason = bytearray()
        for i in range(400):
            if i:
                (c, eol) = (yield parse_eol(sock, (yield sock.recv(1))))
            if eol is not None:
                if not c.isspace() or c in CRLF:
                    break
                else:
                    reason.extend(eol)
            reason.extend(c)
        else:
            raise ExcessError("Excessive status reason")
        reason = reason.rstrip()
        
        print(status.decode("ISO-8859-1"), reason.decode("ISO-8859-1"))
        
        # End of headers if direct CRLF
        while c and c not in CRLF:
            # read <token> :
            # ws, chars except crlf and :, :, then rstrip token)
            # If crlf before :, ignore the line
            (c, eol, _) = (yield parse_space(sock, c))
            
            name = bytearray()
            pattern = b"Transfer-Encoding".lower()
            for p in pattern:
                if eol is not None or not c or ord(c.lower()) != p:
                    match = False
                    break
                (c, eol) = (yield parse_eol(sock, (yield sock.recv(1))))
            else:
                match = True
            for i in range(TOKEN_LIMIT):
                if i:
                    (c, eol) = (yield parse_eol(sock, (yield sock.recv(1))))
                
                if c.isspace() and c not in CRLF:
                    pass
                elif eol is not None or c == b":":
                    break
                else:
                    match = False
                
                if eol:
                    name.extend(eol)
                name.extend(c)
            else:
                raise ExcessError("Excessive token")
            
            if eol is None:
                (c, eol, _) = (yield parse_space(sock))
            
            if match:
                print("Transfer-Encoding")
                pattern = b"chunked".lower()
                for p in pattern:
                    if eol is not None or not c or ord(c.lower()) != p:
                        match = False
                        break
                    (c, eol) = (yield parse_eol(sock, (yield sock.recv(1))))
            for i in range(HEADER_LIMIT):
                if i:
                    (c, eol) = (yield parse_eol(sock, (yield sock.recv(1))))
                
                if c.isspace() and c not in CRLF:
                    pass
                elif eol is not None:
                    break
                else:
                    match = False
            else:
                raise ExcessError("Excessive header")
            
            if match:
                print("chunked")
        
        (pending, _) = (yield parse_eol(sock, c))
    
    from sys import stdout
    while True:
        #~ stdout.buffer.write(pending)
        
        pending = (yield sock.recv(0x1000))
        if not pending:
            break

def parse_space(sock, c=None):
    space = bytearray()
    for _ in range(SPACE_LIMIT):
        if c is None:
            c = (yield sock.recv(1))
        (c, eol) = (yield parse_eol(sock, c))
        if not c.isspace() or c in CRLF:
            raise StopIteration((c, eol, bytes(space)))
        
        if eol:
            space.extend(eol)
        space.extend(c)
        c = None
    else:
        raise ExcessError("Excessive space", bytes(space))

def parse_eol(sock, c):
    """eol, c -> (c, eol)
    eol, EOF -> ("", eol)
    EOF -> ("", "")
    c != eol -> (c, None)
    
    Check for EOF: c == ""
    Check for EOL incl EOF: eol is not None
    True EOL: bool(eol)
    Check for LWS: c.isspace()
    """
    
    if c and c not in CRLF:
        raise StopIteration((c, None))
    
    eol = c
    c = (yield sock.recv(1))
    if eol == b"\r" and c == b"\n":
        eol = CRLF
        c = (yield sock.recv(1))
    raise StopIteration((c, eol))

class ExcessError(EnvironmentError):
    def __init__(self, msg, data=None):
        EnvironmentError.__init__(self, msg)
        self.data = data

CRLF = b"\r\n"
