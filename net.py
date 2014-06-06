from urllib.parse import urlsplit, urlunsplit
import urllib.parse
from socketserver import BaseServer

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

def formataddr(address):
    (address, port) = address
    if not frozenset("[]:").isdisjoint(address):
        addrss = "[{}]".format(address)
    if port is not None:
        address = "{}:{}".format(address, port)
    return address

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

class Server(BaseServer):
    default_port = 0
    
    def __init__(self, address=("", None), RequestHandlerClass=None):
        [host, port] = address
        if port is None:
            port = self.default_port
        super().__init__((host, port), RequestHandlerClass)
    
    def serve_forever(self, *pos, **kw):
        try:
            return super().serve_forever(*pos, **kw)
        finally:
            self.server_close()
