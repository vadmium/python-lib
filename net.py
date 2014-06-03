from urllib.parse import urlsplit, urlunsplit
import urllib.parse

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
