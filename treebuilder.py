from xml.etree.ElementTree import TreeBuilder
from html.parser import HTMLParser

class HtmlParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self._builder = TreeBuilder()
        self._open = list()  # Stack of pending open tags
        
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
        self._open.append(tag)
    
    def handle_endtag(self, tag):
        for [i, open_tag] in enumerate(reversed(self._open)):
            if open_tag == tag:
                break
        else:
            return
        for i in range(i + 1):
            self._builder.end(self._open.pop())
    
    def handle_data(self, *pos, **kw):
        self._builder.data(*pos, **kw)
