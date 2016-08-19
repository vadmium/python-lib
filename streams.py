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
