from sys import stderr
from io import BufferedIOBase
from net import http_request
from urllib.parse import urlsplit
import os, os.path
import hashlib
from base64 import urlsafe_b64encode
from email.message import Message
import email.generator

def get_cached(url, urlopen, cleanup):
    print(end="GET {} ".format(url), flush=True, file=stderr)
    split = urlsplit(url)
    path = split.path.split("/")
    dir = os.path.join(split.scheme, split.netloc, *path[:-1])
    suffix = hashlib.md5(url.encode()).digest()[:6]
    suffix = urlsafe_b64encode(suffix).decode("ascii")
    if path[-1]:
        suffix = path[-1] + os.extsep + suffix
    suffix += os.extsep
    metadata = os.path.join(dir, suffix + "mime")
    try:
        metadata = open(metadata, "rb")
    except FileNotFoundError:
        os.makedirs(dir, exist_ok=True)
        suffix += "html"
        cache = open(os.path.join(dir, suffix), "xb")
        cleanup.enter_context(cache)
        with open(metadata, "xb") as metadata:
            types = ("text/html",)
            response = http_request(url, types, urlopen=urlopen)
            cleanup.enter_context(response)
            print(response.status, response.reason, flush=True, file=stderr)
            msg = Message()
            msg.add_header("Content-Type",
                "message/external-body; access-type=local-file",
                name=suffix)
            msg.attach(response.info())
            metadata = email.generator.BytesGenerator(metadata,
                mangle_from_=False, maxheaderlen=0)
            metadata.flatten(msg)
        return (response.info(), TeeReader(response, cache.write))
    with metadata:
        msg = email.message_from_binary_file(metadata)
    cache = os.path.join(dir, msg.get_param("name"))
    [msg] = msg.get_payload()
    response = cleanup.enter_context(open(cache, "rb"))
    print("(cached)", flush=True, file=stderr)
    return (msg, response)

class TeeReader(BufferedIOBase):
    def readable(self):
        return True
    
    def __init__(self, source, *write):
        self._source = source
        self._write = write
    
    def read(self, *pos, **kw):
        result = self._source.read(*pos, **kw)
        self._call_write(result)
        return result
    def read1(self, *pos, **kw):
        result = self._source.read1(*pos, **kw)
        self._call_write(result)
        return result
    
    def readinto(self, b):
        n = self._readinto(b)
        with memoryview(b) as view, view.cast("B") as bytes:
            self._call_write(bytes[:n])
        return n
    def readinto1(self, b):
        n = self._readinto(b)
        with memoryview(b) as view, view.cast("B") as bytes:
            self._call_write(bytes[:n])
        return n
    
    def _call_write(self, b):
        for write in self._write:
            write(b)
