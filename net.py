from urllib.parse import urlsplit, urlunsplit
import urllib.parse
from socketserver import BaseServer
import sys
from ssl import SSLError
from misc import Context
import urllib.request
import http.client
from errno import EPIPE, ENOTCONN, ECONNRESET
from select import select

try:  # Python 3.3
    ConnectionError
except NameError:  # Python < 3.3
    ConnectionError = ()

DISCONNECTION_ERRNOS = {EPIPE, ENOTCONN, ECONNRESET}

def url_port(url, scheme, ports):
    """Raises "ValueError" if the URL is not valid"""
    
    parsed = urlsplit(url, scheme=scheme)
    if not parsed.hostname:
        parsed = urlsplit("//" + url, scheme=scheme)
    if not parsed.hostname:
        raise ValueError("No host name specified: {0!r}".format(url))
    
    try:
        def_port = ports[parsed.scheme]
    except LookupError:
        raise ValueError("Unhandled scheme: {0}".format(parsed.scheme))
    port = parsed.port
    if port is None:
        port = def_port
    path = urlunsplit(("", "", parsed.path, parsed.query, parsed.fragment))
    return dict(scheme=parsed.scheme, hostname=parsed.hostname, port=port,
        path=path, username=parsed.username, password=parsed.password)

def Url(scheme="", netloc="", path="", params="", query="", fragment=""):
    return urllib.parse.ParseResult(
        scheme, netloc, path, params, query, fragment)

def url_replace(url,
scheme=None, netloc=None, path=None, params=None, query=None, fragment=None):
    res = list()
    mods = (scheme, netloc, path, params, query, fragment)
    for [orig, part] in zip(url, mods):
        if part is None:
            part = orig
        res.append(part)
    return urllib.parse.urlunparse(res)

def format_addr(address):
    [address, port] = address
    if not frozenset("[]:").isdisjoint(address):
        address = "[{}]".format(address)
    if port is not None:
        address = "{}:{}".format(address, port)
    return address

def parse_addr(address, defport=None):
    address = Url(netloc=address)
    host = address.hostname
    if host is None:
        host = ""
    port = address.port
    if port is None:
        port = defport
    return (host, port)

def header_list(message, header):
    for header in message.get_all(header, ()):
        yield from header_split(header, ",")

class HeaderParams(dict):
    def __init__(self, params):
        dict.__init__(self)
        for param in header_split(params, ";"):
            [param, value] = header_partition(param, "=")
            param = param.strip().lower()
            self.setdefault(param, list()).append(value.strip())
    
    def __missing__(*pos, **kw):
        return ()
    
    def get_single(self, name):
        value = self[name]
        if not value:
            raise KeyError("Missing {!r} parameter".format(name))
        if len(value) > 1:
            raise ValueError("Multiple {!r} parameters".format(name))
        [value] = value
        return value

def header_split(header, delim):
    while header:
        [elem, header] = header_partition(header, delim)
        if elem:
            yield elem

def header_partition(header, sep):
    sentinelled = header + sep + '"\\'
    pos = 0
    while True:  # For each quoted segment
        end = sentinelled.index(sep, pos)
        quote = sentinelled.index('"', pos)
        if end < quote:
            break
        pos = quote + 1
        while True:  # For each backslash escape in quote
            quote = sentinelled.index('"', pos)
            backslash = sentinelled.index("\\", pos)
            if quote < backslash:
                break
            pos = min(backslash + 2, len(header))
        pos = min(quote + 1, len(header))
    
    return (header[:end].strip(), header[end + 1:].strip())

def header_unquote(header):
    segments = list()
    while header:  # For each quoted segment
        [unquoted, _, header] = header.partition('"')
        segments.append(unquoted)
        
        sentinelled = header + '"\\'
        start = 0
        pos = 0
        while True:  # For each backslash escape in quote
            quote = sentinelled.index('"', pos)
            backslash = sentinelled.index("\\", pos)
            if quote < backslash:
                break
            segments.append(header[start:backslash])
            start = min(backslash + 1, len(header))
            pos = min(start + 2, len(header))
        segments.append(header[start:quote])
        header = header[quote + 1:]
    return "".join(segments)

class Server(BaseServer, Context):
    default_port = 0
    
    def __init__(self, address=("", None), RequestHandlerClass=None):
        [host, port] = address
        if port is None:
            port = self.default_port
        super().__init__((host, port), RequestHandlerClass)
    
    def close(self):
        return self.server_close()
    
    def handle_error(self, request, client_address):
        [_, exc, *_] = sys.exc_info()
        if isinstance(exc, ConnectionError):
            return
        if (isinstance(exc, SSLError) and
        exc.reason == "TLSV1_ALERT_UNKNOWN_CA"):
            return
        if not isinstance(exc, Exception):
            self.close_request(request)
            raise  # Force server loop to exit
        super().handle_error(request, client_address)

class PersistentConnectionHandler(urllib.request.BaseHandler):
    """URL handler for HTTP persistent connections
    
    with PersistentConnectionHandler(timeout=10) as handler:
        opener = urllib.request.build_opener(handler)
        
        # First request opens connection
        with opener.open("http://localhost/one") as response:
            response.read()
        
        # Subsequent requests reuse existing connection, unless it got closed
        with opener.open("http://localhost/two") as response:
            response.read()
        
        # Closes old connection when new host specified
        with opener.open("http://example/three") as response:
            response.read()
    # Socket freed at context manager exit
    
    Currently does not reuse an existing connection if
    two host names happen to resolve to the same Internet address.
    """
    
    conn_classes = {
        "http": http.client.HTTPConnection,
        "https": http.client.HTTPSConnection,
    }
    
    def __init__(self, *pos, **kw):
        self._type = None
        self._host = None
        self._pos = pos
        self._kw = kw
        self._connection = None
    
    def default_open(self, req):
        if req.type not in self.conn_classes:
            return None
        
        if req.type != self._type or req.host != self._host:
            if self._connection:
                self._connection.close()
            conn_class = self.conn_classes[req.type]
            self._connection = conn_class(req.host, *self._pos, **self._kw)
            self._type = req.type
            self._host = req.host
        
        headers = dict(req.header_items())
        response = None
        try:
            if self._connection.sock is None:
                pass  # On a fresh connection, only attempt request once
            elif any(select((self._connection.sock,), (), (), 0)):
                # Assume EOF or 408 Request Timeout has been signalled
                self._connection.close()
            else:
                # Attempt request on existing connection
                self._attempt_request(req, headers)
                try:
                    try:
                        response = self._connection.getresponse()
                    except EnvironmentError as err:  # Python < 3.3 compat.
                        if err.errno not in DISCONNECTION_ERRNOS:
                            raise
                        raise http.client.BadStatusLine(err) from err
                except (ConnectionError, http.client.BadStatusLine):
                    idempotents = {
                        "GET", "HEAD", "PUT", "DELETE", "TRACE", "OPTIONS"}
                    if req.get_method() not in idempotents:
                        raise
                    # Retry requests whose method indicates idempotence
                    self._connection.close()
                else:
                    if response.status == http.client.REQUEST_TIMEOUT:
                        # Server indicated it did not handle request
                        response = None
            if not response:
                # (Re)try request on a fresh connection
                self._attempt_request(req, headers)
                response = self._connection.getresponse()
        except:
            self._connection.close()
            raise
        
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

def http_request(url, types=None, *,
        urlopen=urllib.request.urlopen, headers=(), **kw):
    headers = dict(headers)
    if types is not None:
        headers["Accept"] = ", ".join(types)
    req = urllib.request.Request(url, headers=headers, **kw)
    response = urlopen(req)
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
