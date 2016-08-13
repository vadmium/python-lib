import tkinter
from tkinter.ttk import Label, Scrollbar, Sizegrip
from tkinter.ttk import Treeview
from tkinter.font import nametofont
from math import ceil
from itertools import cycle
from tkinter import getboolean
from collections import (Sequence, Iterable)

class Form(object):
    def __init__(self, master, column=0):
        self.master = master
        self.column = column
        self.master.columnconfigure(column + 1, weight=1)
        en = font_size(nametofont("TkDefaultFont")["size"] / 2)
        self.master.columnconfigure(column + 0, pad=en)
    
    def add_field(self, widget, multiline=False, **kw):
        label_sticky = [tkinter.EW]
        widget_sticky = [tkinter.EW]
        if multiline:
            label_sticky.append(tkinter.N)
            widget_sticky.append(tkinter.NS)
        
        label = Label(self.master, **kw)
        label.grid(column=self.column + 0, sticky=label_sticky)
        row = grid_row(label)
        if multiline:
            self.master.rowconfigure(row, weight=1)
        widget.grid(row=row, column=self.column + 1, sticky=widget_sticky)

def scroll(view, vert=True, horiz=True, resize=True):
    kw = dict()
    if resize:
        if not horiz:
            kw.update(rowspan=2)
        if not vert:
            kw.update(colspan=2)
    view.grid(sticky=(tkinter.EW, tkinter.NS), **kw)
    
    view.master.rowconfigure(0, weight=1)
    view.master.columnconfigure(0, weight=1)
    
    if vert:
        scroll = Scrollbar(view.master, orient=tkinter.VERTICAL,
            command=view.yview)
        scroll.grid(row=0, column=1, sticky=(tkinter.W, tkinter.NS))
        view.configure(yscrollcommand=scroll.set)
    if horiz:
        scroll = Scrollbar(view.master, orient=tkinter.HORIZONTAL,
            command=view.xview)
        scroll.grid(row=1, column=0, sticky=(tkinter.N, tkinter.EW))
        view.configure(xscrollcommand=scroll.set)
    if resize:
        resize = Sizegrip(view.master)
        resize.grid(row=1, column=1, sticky=(tkinter.EW, tkinter.NS))

class Tree(Treeview):
    def __init__(self, master, columns=1, tree=True, headings=True):
        """
        columns: int, or len(columns): Number of columns; default: 1
        iter(columns): Iterator of dict() objects; optional. Elements may
            also be strings, equivalent to the "heading" value. Keys:
                "heading": Optional
                "width": Optional"""
        
        try:
            self.nontree_columns = len(columns)
        except TypeError:
            if isinstance(columns, Iterable):
                columns = tuple(columns)
                self.nontree_columns = len(columns)
            else:
                self.nontree_columns = columns
                columns = cycle((dict(),))
        
        show = list()
        self.tree_shown = tree
        if self.tree_shown:
            show.append("tree")
            self.nontree_columns -= 1
        if headings:
            show.append("headings")
        
        self.nontree_columns = range(self.nontree_columns)
        Treeview.__init__(self, master, show=show,
            columns=tuple(self.nontree_columns))
        
        self.heading_font = nametofont("TkHeadingFont")
        self.heading_space = "\N{EN QUAD}"
        self.space_size = self.heading_font.measure(self.heading_space)
        self.text_font = nametofont("TkTextFont")
        
        self.auto_width = list()
        for (key, value) in zip(self.columns(), columns):
            if isinstance(value, str):
                value = dict(heading=value)
            
            if headings:
                try:
                    heading = value["heading"]
                except LookupError:
                    pass
                else:
                    self.heading(key, text=heading)
            
            try:
                width = value["width"]
            except LookupError:
                auto = True
                
                if headings:
                    text = self.heading(key, option="text")
                    text += self.heading_space
                    width = self.heading_font.measure(text)
            
            else:
                auto = False
                
                try:
                    (width, unit) = width
                except TypeError:
                    unit = self.FIGURE
                width *= self.text_font.measure(unit)
                width += self.space_size
            
            self.auto_width.append(auto)
            width = max(width, self.column(key, option="minwidth"))
            stretch = value.get("stretch", False)
            self.column(key, stretch=stretch, width=width)
        
        self.bind("<End>", self.end)
    
    FIGURE = "\N{FIGURE SPACE}"
    
    def end(self, event):
        item = ""
        while True:
            children = self.get_children(item)
            if not children:
                break
            item = children[-1]
            
            # Sometimes the "open" option is the integer 0; other times it is
            # a Tcl_Obj() with a string value of "true" or "false"!
            if not getboolean(str(self.item(item, option="open"))):
                break
        self.focus(item)
        self.selection_set((item,))
        self.see(item)
    
    def columns(self):
        if self.tree_shown:
            yield "#0"
        for column in self.nontree_columns:
            yield column
    
    def add(self, parent="", *args, expand=False, **kw):
        if not isinstance(kw.get("values", ()), Sequence):
            kw["values"] = tuple(kw["values"])
        child = self.insert(parent, "end", *args, **kw)
        if not self.focus():
            self.focus(child)
        if not expand:
            return child
        
        auto = iter(self.auto_width)
        if self.tree_shown and next(auto):
            width = 1
            while parent:
                width += 1
                parent = self.parent(parent)
            em = font_size(self.text_font["size"])
            width *= self.winfo_fpixels(em)
            
            try:
                text = kw["text"]
            except LookupError:
                pass
            else:
                width += self.text_font.measure(text) + self.space_size
            
            if width > self.column("#0", option="width"):
                self.column("#0", width=ceil(width))
        
        for (i, value) in enumerate(kw.get("values", ())):
            if not next(auto):
                continue
            width = self.text_font.measure(value) + self.space_size
            if width > self.column(i, option="width"):
                self.column(i, width=width)
        
        return child
    
    def bind_select(self, *args, **kw):
        return self.bind("<<TreeviewSelect>>", *args, **kw)
    def unbind_select(self, *args, **kw):
        return self.unbind("<<TreeviewSelect>>", *args, **kw)

def font_size(size):
    if size < 0:
        return -size
    else:
        return "{}p".format(size)

def grid_row(widget):
    """Workaround for Issue 16809: "Tk 8.6.0 introduces TypeError"
    http://bugs.python.org/issue16809"""
    
    grid = widget.tk.splitlist(str(widget.tk.call("grid", "info", widget)))
    for i in range(0, len(grid), 2):
        if grid[i + 0] == "-row":
            return grid[i + 1]
