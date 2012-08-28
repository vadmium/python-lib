from tkinter import Tk
from tkinter.ttk import (Button, Entry, Frame, LabelFrame)
import tkinter
from lib.tk import ScrolledTree
from tkinter.font import nametofont
from lib.tk import font_size
from lib.tk import Form
from guis import InnerClass
from guis import label_key

class Ttk(object):
    def __init__(self):
        self.root = Tk()
    
    def msg_loop(self):
        self.root.mainloop()
    
    class Window(object, metaclass=InnerClass):
        def __init__(self, gui, title=None, *, sections):
            if title is not None:
                gui.root.title(title)
            
            form = Form(gui.root, column=1)
            
            font = nametofont("TkDefaultFont")
            top = font.metrics("linespace")
            side = font_size(font["size"])
            padding = font_size(font["size"] / 2)
            
            for section in sections:
                access = section.get("access")
                label = convert_label(section["label"], access)
                group = LabelFrame(form.master, **label)
                (_, group_row) = form.master.size()
                group.grid(
                    column=form.column - 1, columnspan=4,
                    sticky=tkinter.NSEW,
                    padx=padding, pady=(0, padding),
                )
                
                for field in section["fields"]:
                    target = field["field"]
                    #~ #ca_entry.focus_set()
                    kw = convert_label(field["label"], field.get("access"))
                    if getattr(target, "multiline", False):
                        kw["multiline"] = True
                    target.place_on(form.master)
                    form.add_field(target.widget, **kw)
                
                (_, rows) = form.master.size()
                group.grid(rowspan=rows + 1 - group_row)
                form.master.rowconfigure(group_row, minsize=top)
                form.master.columnconfigure(form.column - 1, minsize=side)
                form.master.columnconfigure(form.column + 2, minsize=side)
                form.master.rowconfigure(rows, minsize=side)
    
    class Entry(object):
        def __init__(self, value=None):
            self.value = value
        
        def place_on(self, master):
            self.widget = Entry(master)
            if self.value:
                self.widget.insert(0, self.value)
    
    class Button(object):
        def __init__(self, label, access=None):
            self.label = convert_label(label, access)
        
        def place_on(self, master):
            self.widget = Button(master, **self.label)
    
    class List(object):
        multiline = True
        
        def __init__(self, headings, selected=None):
            self.headings = headings
            self.selected = selected
        
        def place_on(self, master):
            self.widget = ScrolledTree(master, tree=False,
                columns=self.headings)
            
            if self.selected:
                #~ self.select_binding = self.evc_list.bind_select(self.select)
                self.widget.bind_select(self.selected)
    
    class Layout(object):
        def __init__(self, cells):
            self.cells = cells
        
        def place_on(self, master):
            self.widget = Frame(master)
            self.widget.columnconfigure(0, weight=1)
            for (col, cell) in enumerate(self.cells):
                cell.place_on(self.widget)
                cell.widget.grid(row=0, column=col, sticky=tkinter.EW)

def convert_label(label, key=None):
    label = label_key(label, key)
    (head, sep, tail) = label.partition("&")
    if sep:
        return dict(text=head + tail, underline=len(head))
    else:
        return dict(text=label)
