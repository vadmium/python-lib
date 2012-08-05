from tkinter.tix import Tk
from tkinter.ttk import (Frame, LabelFrame)
import tkinter
from tkinter.font import nametofont
from lib.tk import font_size
from lib.tk import Form
from guis import MethodClass
from guis import label_key

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
            
            font = nametofont("TkDefaultFont")
            self.top = font.metrics("linespace")
            self.side = font_size(font["size"])
            self.padding = font_size(font["size"] / 2)
        
        def show(self):
            pass
        
        def add_field(self, label, field, key=None):
            self.form.add_field(Frame(), **convert_label(label, key))
        
        def start_section(self, label, key=None):
            label = convert_label(label, key)
            self.group = LabelFrame(self.form.master, **label)
            self.group.grid(
                column=self.form.column - 1, columnspan=4,
                sticky=tkinter.NSEW,
                padx=self.padding, pady=(0, self.padding),
            )
        
        def end_section(self):
            # All fields returned from grid_info() are strings!
            row = int(self.group.grid_info()["row"])
            
            master = self.form.master
            (_, rows) = master.size()
            self.group.grid(rowspan=rows + 1 - row)
            master.rowconfigure(row, minsize=self.top)
            master.columnconfigure(self.form.column - 1, minsize=self.side)
            master.columnconfigure(self.form.column + 2, minsize=self.side)
            master.rowconfigure(rows, minsize=self.side)

def convert_label(label, key=None):
    label = label_key(label, key)
    (head, sep, tail) = label.partition("&")
    if sep:
        return dict(text=head + tail, underline=len(head))
    else:
        return dict(text=label)
