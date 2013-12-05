from tkinter import Tk
from tkinter import ttk
import tkinter
from tkinter.filedialog import (askopenfilename, asksaveasfilename)
from tkinter import StringVar
from tkinter import Toplevel
from tkwrap import ScrolledTree
from tkinter.font import nametofont
from tkwrap import font_size
import tkwrap
from functools import partial
from . import (Form, Section, Field, Inline)
from . import (Entry, Button, List, Tree, MenuEntry)
from functions import setitem
from tkwrap import grid_row
from coroutines.tk import EventLoop

class Ttk(object):
    def __init__(self):
        self.root = Tk()
        self.loop = EventLoop(self.root)
    
    def new_window(self, win, parent=None, *,
    contents, title=None, command=None):
        if parent:
            win.window = Toplevel(parent.window)
        else:
            win.window = self.root
        
        if title is not None:
            win.window.title(title)
        
        win.command = command
        if win.command:
            win.window.bind("<Return>", partial(self.activate, win))
        win.window.bind("<Escape>", partial(self.escape, win))
        
        place = self.controls[type(contents)].init
        place(self, contents, win, win.window, focus=True, resize=True)
        contents.widget.pack(fill=tkinter.BOTH, expand=True)
    
    def set_close(self, win):
        win.window.protocol("WM_DELETE_WINDOW", win.close)
    
    def close_window(self, win):
        win.window.destroy()
    
    def activate(self, win, event):
        win.command()
    def escape(self, win, event):
        win.close()
    
    controls = dict()
    
    @setitem(controls, Entry)
    class Entry(object):
        def init(gui, ctrl, window, master, focus=False, resize=False):
            ctrl.place(gui)
            ctrl.widget = ttk.Entry(master)
            if ctrl.value:
                ctrl.widget.insert(0, ctrl.value)
            if focus:
                ctrl.widget.focus_set()
                return True
        
        def get(gui, ctrl):
            return ctrl.widget.get()
        
        def set(gui, ctrl, text):
            ctrl.widget.delete(0, tkinter.END)
            ctrl.widget.insert(0, text)
    
    @setitem(controls, Button)
    class Button(object):
        def init(gui, ctrl, window, master, focus=False, resize=False):
            if ctrl.default:
                command = partial(ctrl.activate_default, window)
            elif ctrl.close:
                command = partial(ctrl.activate_close, window)
            else:
                command = ctrl.command
            
            disabled = command is None
            kw = dict()
            if not disabled:
                kw.update(command=command)
            kw.update(convert_label(ctrl))
            if ctrl.default:
                kw.update(default="active")
            
            ctrl.widget = ttk.Button(master, **kw)
            if disabled:
                ctrl.widget.state(("disabled",))
            if focus:
                ctrl.widget.focus_set()
                return True
    
    class TreeBase(object):
        def init(gui, ctrl, window, master, focus=False, resize=False,
        **kw):
            ctrl.place(gui)
            ctrl.widget = ScrolledTree(master, columns=ctrl.columns,
                resize=resize, **kw)
            
            if ctrl.selected:
                #~ self.select_binding = self.evc_list.bind_select(self.select)
                select = partial(gui.TreeBase.select, gui, ctrl)
                ctrl.widget.bind_select(select)
            if ctrl.opened:
                open = partial(gui.TreeBase.open, gui, ctrl)
                ctrl.widget.tree.bind("<<TreeviewOpen>>", open)
            if window.command:
                activate = partial(gui.activate, window)
                ctrl.widget.tree.bind("<Double-1>", activate)
            
            if focus:
                ctrl.widget.tree.focus_set()
                return True
        
        def clear(gui, ctrl):
            return ctrl.widget.tree.delete(*ctrl.widget.tree.get_children())
        
        def add(gui, ctrl, *pos, selected=False, **kw):
            item = ctrl.widget.add(*pos, **kw)
            if selected:
                # Empty selection returns empty string?!
                selection = tuple(ctrl.widget.tree.selection())
                ctrl.widget.tree.selection_set(selection + (item,))
            return item
        
        def remove(gui, ctrl, item):
            focus = ctrl.widget.tree.focus()
            if focus == item:
                new = ctrl.widget.tree.next(focus)
                if not new:
                    new = ctrl.widget.tree.prev(focus)
                if not new:
                    new = ctrl.widget.tree.parent(focus)
            else:
                new = ""
            
            ctrl.widget.tree.delete(item)
            
            if new:
                ctrl.widget.tree.focus(new)
        
        def selection(gui, ctrl):
            return ctrl.widget.tree.selection()
        
        def select(gui, ctrl, event):
            ctrl.selected()
            
        def open(gui, ctrl, event):
            ctrl.opened(ctrl.widget.tree.focus())
        
        def iter(gui, ctrl):
            return iter(ctrl.widget.tree.get_children())
    
    @setitem(controls, List)
    class List(TreeBase):
        def init(gui, *pos, **kw):
            return gui.TreeBase.init(gui, *pos, tree=False, **kw)
        
        def add(gui, ctrl, columns, *pos, **kw):
            return gui.TreeBase.add(gui, ctrl, *pos, values=columns, **kw)
            
        def get(gui, ctrl, item):
            return ctrl.widget.tree.item(item, option="values")
    
    @setitem(controls, Tree)
    class Tree(TreeBase):
        def add(gui, ctrl, parent, text, *pos, **kw):
            if not parent:
                parent = ""
            return gui.TreeBase.add(gui, ctrl, parent, *pos, text=text, **kw)
        
        def children(gui, ctrl, parent):
            if not parent:
                parent = ""
            return ctrl.widget.tree.get_children(parent)
        
        def set(gui, ctrl, item, text):
            ctrl.widget.tree.item(item, text=text)
    
    @setitem(controls, MenuEntry)
    class MenuEntry(object):
        def init(gui, ctrl, window, master, focus, resize=False):
            ctrl.place(gui)
            ctrl.var = StringVar()
            ctrl.widget = ttk.OptionMenu(master, ctrl.var, ctrl.value,
                *ctrl.menu)
            if focus:
                ctrl.widget.focus_set()
                return True
        
        def get(gui, ctrl):
            return ctrl.var.get()
    
    @setitem(controls, Inline)
    class Inline:
        def init(gui, ctrl, window, master, focus, resize=False):
            focussed = False
            ctrl.widget = ttk.Frame(master)
            all_expand = not any(getattr(cell, "expand", False)
                for cell in ctrl.cells)
            for (col, cell) in enumerate(ctrl.cells):
                resize_this = resize and col == len(ctrl.cells) - 1
                place = gui.controls[type(cell)].init
                focussed |= bool(place(gui, cell, window, ctrl.widget,
                    not focussed and focus, resize_this))
                sticky = list()
                if getattr(cell, "expand", False):
                    sticky.append(tkinter.EW)
                cell.widget.grid(row=0, column=col, sticky=sticky)
                if all_expand or getattr(cell, "expand", False):
                    ctrl.widget.columnconfigure(col, weight=1)
            return focussed
    
    @setitem(controls, Form)
    class Form:
        def init(gui, ctrl, window, master, focus, resize=False):
            ctrl.widget = ttk.Frame(master)
            form = tkwrap.Form(ctrl.widget, column=ctrl.depth)
            
            if ctrl.depth:
                font = nametofont("TkDefaultFont")
                ctrl.top = font.metrics("linespace")
                ctrl.side = font_size(font["size"])
                ctrl.padding = font_size(font["size"] / 2)
                for level in range(ctrl.depth):
                    form.master.columnconfigure(level, minsize=ctrl.side)
                    col = ctrl.depth * 2 + 2 - level - 1
                    form.master.columnconfigure(col, minsize=ctrl.side)
            
            place = gui.controls[Form].place_fields
            return place(gui, ctrl, ctrl.fields, window, form, 0, focus)
        
        def place_fields(gui, ctrl, fields, window, form, level, focus):
            focussed = False
            for field in fields:
                if isinstance(field, Section):
                    label = convert_label(field)
                    group = ttk.LabelFrame(form.master, **label)
                    (_, group_row) = form.master.size()
                    span = (ctrl.depth - level) * 2 + 2
                    group.grid(
                        column=level, columnspan=span,
                        sticky=tkinter.NSEW,
                        padx=ctrl.padding, pady=(0, ctrl.padding),
                    )
                    
                    place = gui.controls[Form].place_fields
                    focussed |= bool(place(gui, ctrl, field.fields, window,
                        form, level + 1, not focussed and focus))
                    
                    (_, rows) = form.master.size()
                    group.grid(rowspan=rows + 1 - group_row)
                    form.master.rowconfigure(group_row, minsize=ctrl.top)
                    form.master.rowconfigure(rows, minsize=ctrl.side)
                    continue
                
                if isinstance(field, Field):
                    target = field.field
                else:
                    target = field
                place = gui.controls[type(target)].init
                focussed |= bool(place(gui, target, window, form.master,
                    not focussed and focus))
                multiline = getattr(target, "multiline", False)
                
                if isinstance(field, Field):
                    kw = convert_label(field)
                    if multiline:
                        kw["multiline"] = True
                    form.add_field(target.widget, **kw)
                else:
                    sticky = list()
                    if getattr(target, "expand", False):
                        sticky.append(tkinter.EW)
                    if multiline:
                        sticky.append(tkinter.NS)
                    span = (ctrl.depth - level) * 2 + 2
                    target.widget.grid(column=level, columnspan=span,
                        sticky=sticky)
                    if multiline:
                        row = grid_row(target.widget)
                        form.master.rowconfigure(row, weight=1)
            
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

def convert_label(ctrl):
    label = ctrl.label_key()
    if label is None:
        return dict()
    (head, sep, tail) = label.partition("&")
    if sep:
        return dict(text=head + tail, underline=len(head))
    else:
        return dict(text=label)
