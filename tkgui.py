from tkinter.tix import Tk
from tkinter.ttk import Frame
from lib.tk import Form
from guis import MethodClass

class Tix(object):
    def __init__(self):
        self.root = Tk()
    
    def msg_loop(self):
        self.root.mainloop()
    
    class Window(object, metaclass=MethodClass):
        def __init__(self, gui, title=None):
            if title is not None:
                gui.root.title(title)
            
            self.form = Form(gui.root, column=1)
        
        def show(self):
            pass
        
        def add_field(self, label, field):
            (head, sep, tail) = label.partition("&")
            if sep:
                kw = dict(underline=len(head))
                label = head + tail
            else:
                kw = dict()
            self.form.add_field(Frame(), text=label, **kw)
