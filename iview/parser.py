from collections import Mapping

class UnicodeMap(Mapping):
    """Base class for str.translate() dictionaries"""
    
    # Only partially implementing the mapping interface
    def __iter__(self):
        raise NotImplementedError()
    def __len__(self):
        raise NotImplementedError()
    
    def __getitem__(self, cp):
        return self.map_char(chr(cp))
    def map_char(self, char):
        raise LookupError()
