from io import BufferedIOBase

class TeeWriter(BufferedIOBase):
    def __init__(self, *outputs):
        self.outputs = outputs
    def close(self):
        for output in self.outputs:
            output.close()
        return BufferedIOBase.close(self)
    def flush(self):
        for output in self.outputs:
            output.flush()
        return BufferedIOBase.flush(self)
    def write(self, b):
        for output in self.outputs:
            output.write(b)

class NullWriter(BufferedIOBase):
    def write(self, b):
        pass
nullwriter = NullWriter()

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
