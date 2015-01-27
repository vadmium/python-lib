from collections import Mapping

class UnicodeMap(Mapping):
    """Base class for str.translate() dictionaries"""
    
    def __iter__(self):
        return iter(range(len(self)))
    def __len__(self):
        return sys.maxunicode + 1
    
    def __getitem__(self, cp):
        return self.map_char(chr(cp))
    def map_char(self, char):
        raise KeyError()
