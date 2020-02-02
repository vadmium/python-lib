from io import BufferedIOBase, IOBase
from functions import instantiated

class DelegateWriter(IOBase):
    def __init__(self, *delegates):
        self.delegates = list(delegates)
    def write(self, x):
        for write in self.delegates:
            write(x)
        return len(x)

def streamcopy(input, output, length):
    if length < 0:
        raise ValueError("Negative length")
    while length:
        chunk = input.read(min(length, 0x10000))
        if not chunk:
            raise EOFError()
        output.write(chunk)
        length -= len(chunk)

class CounterWriter(BufferedIOBase):
    def __init__(self, output):
        self.length = 0
        self.output = output
    def write(self, b):
        self.length += len(b)
        return self.output.write(b)
    def tell(self):
        return self.length

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
