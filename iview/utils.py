import urllib.request
from http.client import HTTPConnection
import http.client
from errno import EPIPE, ESHUTDOWN, ENOTCONN, ECONNRESET

try:  # Python 3.3
    ConnectionError
except NameError:  # Python < 3.3
    ConnectionError = ()

class PersistentConnectionHandler(urllib.request.BaseHandler):
    """URL handler for HTTP persistent connections
    
    connection = PersistentConnectionHandler()
    session = urllib.request.build_opener(connection)
    
    # First request opens connection
    with session.open("http://localhost/one") as response:
        response.read()
    
    # Subsequent requests reuse the existing connection, unless it got closed
    with session.open("http://localhost/two") as response:
        response.read()
    
    # Closes old connection when new host specified
    with session.open("http://example/three") as response:
        response.read()
    
    connection.close()  # Frees socket
    
    Currently does not reuse an existing connection if
    two host names happen to resolve to the same Internet address.
    """
    
    def __init__(self, *pos, **kw):
        self._type = None
        self._host = None
        self._pos = pos
        self._kw = kw
        self._connection = None
    
    def default_open(self, req):
        if req.type != "http":
            return None
        
        if req.type != self._type or req.host != self._host:
            if self._connection:
                self._connection.close()
            self._connection = HTTPConnection(req.host,
                *self._pos, **self._kw)
            self._type = req.type
            self._host = req.host
        
        headers = dict(req.header_items())
        try:
            response = self._openattempt(req, headers)
        except (ConnectionError, http.client.BadStatusLine,
        EnvironmentError) as err:
            # If the server closed the connection,
            # by calling close() or shutdown(SHUT_WR),
            # before receiving a short request (<= 1 MB),
            # the "http.client" module raises a BadStatusLine exception.
            # 
            # To produce EPIPE:
            # 1. server: close() or shutdown(SHUT_RDWR)
            # 2. client: send(large request >> 1 MB)
            # 
            # ENOTCONN probably not possible with current Python,
            # but could be generated on Linux by:
            # 1. server: close() or shutdown(SHUT_RDWR)
            # 2. client: send(finite data)
            # 3. client: shutdown()
            # ENOTCONN not covered by ConnectionError even in Python 3.3.
            # 
            # To produce ECONNRESET:
            # 1. client: send(finite data)
            # 2. server: close() without reading all data
            # 3. client: send()
            errnos = {EPIPE, ESHUTDOWN, ENOTCONN, ECONNRESET}
            if (isinstance(err, EnvironmentError) and
                    not isinstance(err, ConnectionError) and
                    err.errno not in errnos):
                raise
            idempotents = {
                "GET", "HEAD", "PUT", "DELETE", "TRACE", "OPTIONS"}
            if req.get_method() not in idempotents:
                raise
            
            self._connection.close()
            response = self._openattempt(req, headers)
        
        # Odd impedance mismatch between "http.client" and "urllib.request"
        response.msg = response.reason
        return response
    
    def _openattempt(self, req, headers):
        """Attempt a request using any existing connection"""
        self._connection.request(req.get_method(), req.selector, req.data,
            headers)
        return self._connection.getresponse()
    
    def close(self):
        if self._connection:
            self._connection.close()
    
    def __enter__(self):
        return self
    def __exit__(self, *exc):
        self.close()

def http_get(session, url, types=None, *, headers=dict(), **kw):
    headers = dict(headers)
    if types is not None:
        headers["Accept"] = ", ".join(types)
    req = urllib.request.Request(url, headers=headers, **kw)
    response = session.open(req)
    try:
        headers = response.info()
        headers.set_default_type(None)
        type = headers.get_content_type()
        if types is not None and type not in types:
            msg = "Unexpected content type {}"
            raise TypeError(msg.format(type))
        return response
    except:
        response.close()
        raise
