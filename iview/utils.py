import urllib.request
import http.client
from errno import EPIPE, ESHUTDOWN, ENOTCONN, ECONNRESET

try:  # Python 3.3
    ConnectionError
except NameError:  # Python < 3.3
    ConnectionError = ()

DISCONNECTION_ERRNOS = {EPIPE, ESHUTDOWN, ENOTCONN, ECONNRESET}

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
            self._connection = http.client.HTTPConnection(req.host,
                *self._pos, **self._kw)
            self._type = req.type
            self._host = req.host
        
        headers = dict(req.header_items())
        self._attempt_request(req, headers)
        try:
            try:
                response = self._connection.getresponse()
            except EnvironmentError as err:  # Python < 3.3 compatibility
                if err.errno not in DISCONNECTION_ERRNOS:
                    raise
                raise http.client.BadStatusLine(err) from err
        except (ConnectionError, http.client.BadStatusLine):
            idempotents = {
                "GET", "HEAD", "PUT", "DELETE", "TRACE", "OPTIONS"}
            if req.get_method() not in idempotents:
                raise
            # Retry requests whose method indicates they are idempotent
            self._connection.close()
            response = None
        else:
            if response.status == http.client.REQUEST_TIMEOUT:
                # Server indicated it did not handle request
                response = None
        if not response:
            # Retry request
            self._attempt_request(req, headers)
            response = self._connection.getresponse()
        
        # Odd impedance mismatch between "http.client" and "urllib.request"
        response.msg = response.reason
        return response
    
    def _attempt_request(self, req, headers):
        """Send HTTP request, ignoring broken pipe and similar errors"""
        try:
            self._connection.request(req.get_method(), req.selector,
                req.data, headers)
        except (ConnectionRefusedError, ConnectionAbortedError):
            raise  # Assume connection was not established
        except ConnectionError:
            pass  # Continue and read server response if available
        except EnvironmentError as err:  # Python < 3.3 compatibility
            if err.errno not in DISCONNECTION_ERRNOS:
                raise
    
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
