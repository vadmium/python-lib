from tkinter import Tk
from tkinter.ttk import (Button, Entry, Frame, LabelFrame)
import tkinter
from tkinter.filedialog import (askopenfilename, asksaveasfilename)
from tkinter import Toplevel
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
        def __init__(self, gui, parent=None, *, title=None, sections):
            if parent:
                self.window = Toplevel(parent.window)
            else:
                self.window = gui.root
            
            if title is not None:
                self.window.title(title)
            
            form = Form(self.window, column=1)
            
            font = nametofont("TkDefaultFont")
            top = font.metrics("linespace")
            side = font_size(font["size"])
            padding = font_size(font["size"] / 2)
            
            focussed = False
            for section in sections:
                if not isinstance(section, Iterable):
                    focussed |= bool(section.place_on(form.master,
                        not focussed))
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
                    focussed |= bool(target.place_on(form.master,
                        not focussed))
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
        
        def close(self):
            self.window.destroy()
    
    class Entry(object):
        expand = True
        
        def __init__(self, value=None):
            self.value = value
        
        def place_on(self, master, focus=False):
            self.widget = Entry(master)
            if self.value:
                self.widget.insert(0, self.value)
            if focus:
                self.widget.focus_set()
                return True
        
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
        
        def place_on(self, master, focus=False):
            self.widget = Button(master, **self.kw)
            if self.disabled:
                self.widget.state(("disabled",))
            if focus:
                self.focus_set()
                return True
    
    class List(object):
        multiline = True
        
        def __init__(self, headings, selected=None):
            self.headings = headings
            self.selected = selected
        
        def place_on(self, master, focus=False):
            self.widget = ScrolledTree(master, tree=False,
                columns=self.headings)
            
            if self.selected:
                #~ self.select_binding = self.evc_list.bind_select(self.select)
                self.widget.bind_select(self.select)
            
            if focus:
                self.widget.tree.focus_set()
                return True
        
        def clear(self):
            return self.widget.tree.delete(*self.widget.tree.get_children())
        
        def add(self, columns, selected=False):
            item = self.widget.add(values=columns)
            if selected:
                # Empty selection returns empty string?!
                selection = tuple(self.widget.tree.selection())
                self.widget.tree.selection_set(selection + (item,))
        
        def remove(self, item):
            focus = self.widget.tree.focus()
            if focus == item:
                new = self.widget.tree.next(focus)
                if not new:
                    new = self.widget.tree.prev(focus)
            else:
                new = ""
            
            self.widget.tree.delete(item)
            
            if new:
                self.widget.tree.focus(new)
        
        def get(self, item):
            return self.widget.tree.item(item, option="values")
        
        def selection(self):
            return self.widget.tree.selection()
        
        def select(self, event):
            self.selected()
        
        def __iter__(self):
            return iter(self.widget.tree.get_children())
    
    class Layout(object):
        def __init__(self, cells):
            self.cells = cells
        
        def place_on(self, master, focus):
            focussed = False
            self.widget = Frame(master)
            all_expand = not any(getattr(cell, "expand", False)
                for cell in self.cells)
            for (col, cell) in enumerate(self.cells):
                focussed |= bool(cell.place_on(self.widget,
                    not focussed and focus))
                sticky = list()
                if getattr(cell, "expand", False):
                    sticky.append(tkinter.EW)
                cell.widget.grid(row=0, column=col, sticky=sticky)
                if all_expand or getattr(cell, "expand", False):
                    self.widget.columnconfigure(col, weight=1)
            return focussed
    
    def file_browse(self, mode, parent=None, *,
    title=None, types, file=None):
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
        if parent is not None:
            kw.update(parent=parent.window)
        file = mode(filetypes=filetypes, **kw)
        if not file:
            return None
        return file

def convert_label(label, key=None):
    label = label_key(label, key)
    if label is None:
        return dict()
    (head, sep, tail) = label.partition("&")
    if sep:
        return dict(text=head + tail, underline=len(head))
    else:
        return dict(text=label)
