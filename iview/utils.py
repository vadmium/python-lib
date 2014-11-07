import urllib.request
from http.client import HTTPConnection
import http.client

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
            return self._openattempt(req, headers)
        except http.client.BadStatusLine as err:
            # If the server closed the connection before receiving this
            # request, the "http.client" module raises an exception with the
            # "line" attribute set to repr("")!
            if err.line != repr(""):
                raise
        self._connection.close()
        return self._openattempt(req, headers)
    
    def _openattempt(self, req, headers):
        """Attempt a request using any existing connection"""
        self._connection.request(req.get_method(), req.selector, req.data,
            headers)
        response = self._connection.getresponse()
        
        # Odd impedance mismatch between "http.client" and "urllib.request"
        response.msg = response.reason
        
        return response
    
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
