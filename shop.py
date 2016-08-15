from xml.etree.ElementTree import TreeBuilder
from html.parser import HTMLParser

class HtmlTreeParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self._builder = TreeBuilder()
    
    def close(self):
        super().close()
        return self._builder.close()
    
    def handle_starttag(self, tag, attrs):
        self._builder.start(tag, dict(attrs))
    def handle_endtag(self, *pos, **kw):
        self._builder.end(*pos, **kw)
    def handle_data(self, *pos, **kw):
        self._builder.data(*pos, **kw)
