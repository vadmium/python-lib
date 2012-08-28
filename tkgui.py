from tkinter import Tk
from tkinter.ttk import (Button, Entry, Frame, LabelFrame)
import tkinter
from tkinter.filedialog import (askopenfilename, asksaveasfilename)
from lib.tk import ScrolledTree
from tkinter.font import nametofont
from lib.tk import font_size
from lib.tk import Form
from guis import InnerClass
from guis import label_key
from collections import (Mapping, Iterable)

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
                if not isinstance(section, Iterable):
                    section.place_on(form.master)
                    section.widget.grid(columnspan=4)
                    continue
                
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
                    if isinstance(field, Mapping):
                        target = field["field"]
                    else:
                        target = field
                    target.place_on(form.master)
                    multiline = getattr(target, "multiline", False)
                    
                    if isinstance(field, Mapping):
                        kw = convert_label(field["label"], field.get("access"))
                        if multiline:
                            kw["multiline"] = True
                        form.add_field(target.widget, **kw)
                    else:
                        sticky = [tkinter.EW]
                        if multiline:
                            sticky.append(tkinter.NS)
                        target.widget.grid(column=form.column, columnspan=2,
                            sticky=sticky)
                        if multiline:
                            row = target.widget.grid_info()["row"]
                            form.master.rowconfigure(row, weight=1)
                
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
        
        def get(self):
            return self.widget.get()
        
        def set(self, text):
            self.widget.delete(0, tkinter.END)
            self.widget.insert(0, text)
    
    class Button(object):
        def __init__(self, label, command=None, access=None):
            self.kw = dict()
            self.disabled = command is None
            if not self.disabled:
                self.kw.update(command=command)
            self.kw.update(convert_label(label, access))
        
        def place_on(self, master):
            self.widget = Button(master, **self.kw)
            if self.disabled:
                self.widget.state(("disabled",))
    
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
    
    def file_browse(self, mode, *, title=None, types, file=None):
        filetypes = list()
        for (label, exts) in types:
            filetypes.append((label, tuple("." + ext for ext in exts)))
        filetypes.append(("All", ("*",)))
        
        mode = dict(open=askopenfilename, save=asksaveasfilename)[mode]
        kw = dict()
        if title is not None:
            kw.update(title=title)
        if file is not None:
            kw.update(initialfile=file)
        #~ parent=self.window
        file = mode(filetypes=filetypes, **kw)
        if not file:
            return None
        return file

def convert_label(label, key=None):
    label = label_key(label, key)
    (head, sep, tail) = label.partition("&")
    if sep:
        return dict(text=head + tail, underline=len(head))
    else:
        return dict(text=label)
