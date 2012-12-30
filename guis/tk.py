from tkinter import Tk
from tkinter.ttk import (Button, Entry, Frame, LabelFrame, OptionMenu)
import tkinter
from tkinter.filedialog import (askopenfilename, asksaveasfilename)
from tkinter import StringVar
from tkinter import Toplevel
from tkwrap import ScrolledTree
from tkinter.font import nametofont
from tkwrap import font_size
from tkwrap import Form
from . import InnerClass
from . import label_key

class Ttk(object):
    def __init__(self):
        self.root = Tk()
    
    def msg_loop(self):
        self.root.mainloop()
    
    class Window(object, metaclass=InnerClass):
        def __init__(self, gui, parent=None, *,
        contents, title=None, command=None):
            if parent:
                self.window = Toplevel(parent.window)
            else:
                self.window = gui.root
            
            if title is not None:
                self.window.title(title)
            
            self.command = command
            if self.command:
                self.window.bind("<Return>", self.activate)
            self.window.bind("<Escape>", self.escape)
            
            contents.place_on(self, self.window, focus=True, resize=True)
            contents.widget.pack(fill=tkinter.BOTH, expand=True)
        
        def close(self):
            self.window.destroy()
        
        def activate(self, event):
            self.command()
        def escape(self, event):
            self.close()
    
    class Entry(object):
        expand = True
        
        def __init__(self, value=None):
            self.value = value
        
        def place_on(self, window, master, focus=False, resize=False):
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
        def __init__(self, label, command=None, access=None,
        default=False, close=False):
            if default:
                command = self.default
            elif close:
                command = self.close
            
            self.default = default
            self.close = close
            self.kw = dict()
            self.disabled = command is None
            if not self.disabled:
                self.kw.update(command=command)
            self.kw.update(convert_label(label, access))
            if self.default:
                self.kw.update(default="active")
        
        def place_on(self, window, master, focus=False, resize=False):
            self.window = window
            self.widget = Button(master, **self.kw)
            if self.disabled:
                self.widget.state(("disabled",))
            if focus:
                self.focus_set()
                return True
        
        def default(self):
            if self.window.command:
                self.window.command()
        
        def close(self):
            self.window.close()
    
    class TreeBase(object):
        multiline = True
        expand = True
        
        def __init__(self, columns=1, selected=None, opened=None):
            """
            columns: Sequence of dict() objects for each column, or column
                headings. Keys can be "text" and "width". Width is measured
                in digits (U+2007 "Figure space"). Default: single unnamed
                column"""
            
            self.columns = columns
            self.selected = selected
            self.opened = opened
        
        def place_on(self, window, master, focus=False, resize=False, **kw):
            self.widget = ScrolledTree(master, columns=self.columns,
                resize=resize, **kw)
            
            if self.selected:
                #~ self.select_binding = self.evc_list.bind_select(self.select)
                self.widget.bind_select(self.select)
            if self.opened:
                self.widget.tree.bind("<<TreeviewOpen>>", self.open)
            if window.command:
                self.widget.tree.bind("<Double-1>", window.activate)
            
            if focus:
                self.widget.tree.focus_set()
                return True
        
        def clear(self):
            return self.widget.tree.delete(*self.widget.tree.get_children())
        
        def add(self, *pos, selected=False, **kw):
            item = self.widget.add(*pos, **kw)
            if selected:
                # Empty selection returns empty string?!
                selection = tuple(self.widget.tree.selection())
                self.widget.tree.selection_set(selection + (item,))
            return item
        
        def remove(self, item):
            focus = self.widget.tree.focus()
            if focus == item:
                new = self.widget.tree.next(focus)
                if not new:
                    new = self.widget.tree.prev(focus)
                if not new:
                    new = self.widget.tree.parent(focus)
            else:
                new = ""
            
            self.widget.tree.delete(item)
            
            if new:
                self.widget.tree.focus(new)
        
        def selection(self):
            return self.widget.tree.selection()
        
        def select(self, event):
            self.selected()
        
        def open(self, event):
            self.opened(self.widget.tree.focus())
        
        def __iter__(self):
            return iter(self.widget.tree.get_children())
    
    class List(TreeBase):
        def place_on(self, *pos, **kw):
            return Ttk.TreeBase.place_on(self, *pos, tree=False, **kw)
        
        def add(self, columns, *pos, **kw):
            return Ttk.TreeBase.add(self, *pos, values=columns, **kw)
        
        def get(self, item):
            return self.widget.tree.item(item, option="values")
    
    class Tree(TreeBase):
        def add(self, parent, text, *pos, **kw):
            if not parent:
                parent = ""
            return Ttk.TreeBase.add(self, parent, *pos, text=text, **kw)
        
        def children(self, parent):
            if not parent:
                parent = ""
            return self.widget.tree.get_children(parent)
        
        def set(self, item, text):
            self.widget.tree.item(item, text=text)
    
    class MenuEntry(object):
        expand = True
        
        def __init__(self, menu, value):
            self.menu = menu
            self.value = value
        
        def place_on(self, window, master, focus, resize=False):
            self.var = StringVar()
            self.widget = OptionMenu(master, self.var, self.value,
                *self.menu)
            if focus:
                self.widget.focus_set()
                return True
        
        def get(self):
            return self.var.get()
    
    class Inline(object):
        expand = True
        
        def __init__(self, *cells):
            self.cells = cells
        
        def place_on(self, window, master, focus, resize=False):
            focussed = False
            self.widget = Frame(master)
            all_expand = not any(getattr(cell, "expand", False)
                for cell in self.cells)
            for (col, cell) in enumerate(self.cells):
                resize_this = resize and col == len(self.cells)
                focussed |= bool(cell.place_on(window, self.widget,
                    not focussed and focus, resize_this))
                sticky = list()
                if getattr(cell, "expand", False):
                    sticky.append(tkinter.EW)
                cell.widget.grid(row=0, column=col, sticky=sticky)
                if all_expand or getattr(cell, "expand", False):
                    self.widget.columnconfigure(col, weight=1)
            return focussed
    
    class Form(object):
        def __init__(self, *fields):
            self.fields = fields
            self.depth = self.get_depth(self.fields)
        
        def get_depth(self, fields):
            depth = 0
            for field in fields:
                if isinstance(field, Ttk.Section):
                    depth = max(depth, 1 + self.get_depth(field.fields))
            return depth
        
        def place_on(self, window, master, focus, resize=False):
            self.widget = Frame(master)
            form = Form(self.widget, column=self.depth)
            
            if self.depth:
                font = nametofont("TkDefaultFont")
                self.top = font.metrics("linespace")
                self.side = font_size(font["size"])
                self.padding = font_size(font["size"] / 2)
                for level in range(self.depth):
                    form.master.columnconfigure(level, minsize=self.side)
                    col = self.depth * 2 + 2 - level - 1
                    form.master.columnconfigure(col, minsize=self.side)
            
            return self.place_fields(self.fields, window, form, 0, focus)
        
        def place_fields(self, fields, window, form, level, focus):
            focussed = False
            for field in fields:
                if isinstance(field, Ttk.Section):
                    group = LabelFrame(form.master, **field.label)
                    (_, group_row) = form.master.size()
                    span = (self.depth - level) * 2 + 2
                    group.grid(
                        column=level, columnspan=span,
                        sticky=tkinter.NSEW,
                        padx=self.padding, pady=(0, self.padding),
                    )
                    
                    focussed |= bool(self.place_fields(field.fields, window,
                        form, level + 1, not focussed and focus))
                    
                    (_, rows) = form.master.size()
                    group.grid(rowspan=rows + 1 - group_row)
                    form.master.rowconfigure(group_row, minsize=self.top)
                    form.master.rowconfigure(rows, minsize=self.side)
                    continue
                
                if isinstance(field, Ttk.Field):
                    target = field.field
                else:
                    target = field
                focussed |= bool(target.place_on(window, form.master,
                    not focussed and focus))
                multiline = getattr(target, "multiline", False)
                
                if isinstance(field, Ttk.Field):
                    kw = convert_label(field.label, field.access)
                    if multiline:
                        kw["multiline"] = True
                    form.add_field(target.widget, **kw)
                else:
                    sticky = list()
                    if getattr(target, "expand", False):
                        sticky.append(tkinter.EW)
                    if multiline:
                        sticky.append(tkinter.NS)
                    span = (self.depth - level) * 2 + 2
                    target.widget.grid(column=level, columnspan=span,
                        sticky=sticky)
                    if multiline:
                        row = target.widget.grid_info()["row"]
                        form.master.rowconfigure(row, weight=1)
            
            return focussed
    
    class Section(object):
        def __init__(self, label, *fields, access=None):
            self.fields = fields
            self.label = convert_label(label, access)
    class Field(object):
        def __init__(self, label, field, access=None):
            self.label = label
            self.field = field
            self.access = access
    
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
    
    def EventDriver(self):
        from eventgen.tk import Driver
        return Driver(self.root)

def convert_label(label, key=None):
    label = label_key(label, key)
    if label is None:
        return dict()
    (head, sep, tail) = label.partition("&")
    if sep:
        return dict(text=head + tail, underline=len(head))
    else:
        return dict(text=label)
