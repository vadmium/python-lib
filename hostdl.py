from xml.etree.ElementTree import TreeBuilder
from html.parser import HTMLParser

class HtmlTreeParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self._builder = TreeBuilder()
        
        # Avoid error about multiple top-level elements
        self._builder.start("", dict())
    
    def close(self):
        super().close()
        return self._builder.close()
    
    def handle_starttag(self, tag, attrs):
        d = dict()
        for [name, value] in attrs:
            if value is None:  # Empty HTML attribute, as in <input selected>
                value = ''
            d[name] = value
        self._builder.start(tag, d)
    
    def handle_endtag(self, *pos, **kw):
        self._builder.end(*pos, **kw)
    def handle_data(self, *pos, **kw):
        self._builder.data(*pos, **kw)
