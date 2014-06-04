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
    (host, port) = address
    if not frozenset("[]:").isdisjoint(host):
        host = "[{}]".format(host)
    return "{}:{}".format(host, port)

def header_list(message, header):
    for header in message.get_all(header, ()):
        sentinelled = header + ',"\\'
        pos = 0
        while pos < len(header):  # For each comma-delimited list element
            start = pos
            while True:  # For each quoted section within list element
                comma = sentinelled.index(",", pos)
                quote = sentinelled.index('"', pos)
                if comma < quote:
                    break
                pos = quote + 1
                while True:  # For each backslash escape in quote
                    quote = sentinelled.index('"', pos)
                    backslash = sentinelled.index("\\", pos)
                    if quote < backslash:
                        break
                    pos = min(backslash + 2, len(header))
                pos = min(quote + 1, len(header))
            
            elem = header[start:comma].strip()
            if elem:
                yield elem
            pos = comma + 1

class Server(BaseServer):
    def serve_forever(self, *pos, **kw):
        try:
            return super().serve_forever(*pos, **kw)
        finally:
            self.server_close()
