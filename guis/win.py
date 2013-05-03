from win32gui import (PumpMessages, PostQuitMessage, SendMessage)
from win32gui import (
    CreateDialogIndirect,
    CreateWindowEx, DestroyWindow, ShowWindow, GetWindowText, SetWindowText,
    GetDC, ReleaseDC,
    GetWindowRect, MoveWindow,
)
from win32con import (
    WS_VISIBLE, WS_OVERLAPPEDWINDOW, WS_CHILD, WS_TABSTOP, WS_DISABLED,
)
from win32con import (WS_EX_NOPARENTNOTIFY, WS_EX_CLIENTEDGE)
from win32con import (WM_DESTROY, WM_CLOSE, WM_SIZE)
from win32con import (WM_SETFONT, WM_INITDIALOG, WM_COMMAND, WM_NOTIFY)
from win32con import SW_SHOWNORMAL
from win32gui import GetStockObject
from win32gui import (SelectObject, GetTextMetrics)
from win32api import GetSystemMetrics
from win32con import (SM_CXSIZEFRAME, SM_CYSIZEFRAME, SM_CYCAPTION)
from win32con import (BS_GROUPBOX, BS_PUSHBUTTON)
from win32api import (LOWORD, HIWORD)
from commctrl import (LVS_SHOWSELALWAYS, LVS_REPORT, WC_LISTVIEW)
from commctrl import (
    LVM_GETEXTENDEDLISTVIEWSTYLE, LVM_SETEXTENDEDLISTVIEWSTYLE,
    LVM_INSERTCOLUMNW,
    LVM_DELETEALLITEMS, LVM_DELETEITEM, LVM_INSERTITEMW,
    LVM_SETITEMTEXTW, LVM_GETITEMTEXTW,
)
from commctrl import (LVS_EX_FULLROWSELECT, LVCFMT_LEFT)
from win32gui_struct import (
    PackLVCOLUMN, PackLVITEM, EmptyLVITEM, UnpackLVITEM,
)
from win32gui import InitCommonControls
from win32gui import (GetOpenFileNameW, GetSaveFileNameW)
from win32con import (
    OFN_HIDEREADONLY, OFN_EXPLORER, OFN_OVERWRITEPROMPT, OFN_NOCHANGEDIR,
)
import win32gui
from commctrl import LVIS_SELECTED
from win32api import MAKELONG
from win32gui import PyMakeBuffer
from struct import Struct
from commctrl import (LVN_ITEMCHANGED, LVIF_STATE, LVIF_TEXT)
from win32con import ES_AUTOHSCROLL
from functools import partial
from . import (Form, Section, Field, Inline, Entry, Button, List)
from . import stash

class Win(object):
    def __init__(self):
        self.visible = set()
    
    def msg_loop(self):
        if self.visible:
            PumpMessages()
    
    def new_window(self, win, parent=None, *, title=None, contents):
        template = (title, (0, 0, 0, 0), WS_OVERLAPPEDWINDOW)
        handlers = {
            WM_INITDIALOG: partial(self.on_init_dialog, win),
            WM_DESTROY: partial(self.on_destroy, win),
            WM_CLOSE: partial(self.on_close, win),
            WM_SIZE: partial(self.on_size, win),
            WM_COMMAND: partial(self.on_command, win),
            WM_NOTIFY: partial(self.on_notify, win),
        }
        win.contents = contents
        
        win.commands = dict()
        win.id = 1024
        
        if parent:
            parent = parent.hwnd
        
        win.init_exc = None  # Tunnel exceptions raised during WM_INITDIALOG
        try:
            CreateDialogIndirect(None, (template,), parent, handlers)
            if win.init_exc:
                raise win.init_exc
        finally:
            del win.init_exc
        
        (left, top, _, _) = GetWindowRect(win.hwnd)
        width = round(80 * win.x_unit) + round(160 * win.x_unit)
        height = round(250 * win.y_unit)
        width += GetSystemMetrics(SM_CXSIZEFRAME) * 2
        height += GetSystemMetrics(SM_CYSIZEFRAME) * 2
        height += GetSystemMetrics(SM_CYCAPTION)
        MoveWindow(win.hwnd, left, top, width, height, 0)
        
        ShowWindow(win.hwnd, SW_SHOWNORMAL)
        self.visible.add(win)
    
    def on_init_dialog(self, win, hwnd, msg, wparam, lparam):
        try:
            win.hwnd = hwnd
            
            dc = GetDC(win.hwnd)
            try:
                prev = SelectObject(dc, GetStockObject(DEFAULT_GUI_FONT))
                try:
                    tm = GetTextMetrics(dc)
                    win.x_unit = (tm["AveCharWidth"] + 1) / 4
                    win.y_unit = tm["Height"] / 8
                finally:
                    SelectObject(dc, prev)
            finally:
                ReleaseDC(win.hwnd, dc)
            
            win.label_height = round(9 * win.y_unit)
            
            win.notify = dict()
            self.controls[type(win.contents)].init(self, win.contents, win)
        
        except BaseException as exc:
            win.init_exc = exc
    
    def set_close(self, win):
        pass
    
    def on_destroy(self, win, hwnd, msg, wparam, lparam):
        self.visible.remove(win)
        if not self.visible:
            PostQuitMessage(0)
    
    def on_close(self, win, hwnd, msg, wparam, lparam):
        win.close()
    
    def close_window(self, win):
        DestroyWindow(win.hwnd)
    
    def on_size(self, win, hwnd, msg, wparam, lparam):
        cx = LOWORD(lparam)
        cy = HIWORD(lparam)
        move = self.controls[type(win.contents)].move
        move(self, win, win.contents, 0, 0, cx, cy)
        return 1
    
    def on_command(self, win, hwnd, msg, wparam, lparam):
        id = LOWORD(wparam)
        try:
            command = win.commands[id]
        except LookupError:
            return
        command()
    
    def on_notify(self, win, hwnd, msg, wparam, lparam):
        (hwndFrom, _, code) = NMHDR.unpack(lparam)
        try:
            notify = win.notify[hwndFrom]
        except LookupError:
            pass
        else:
            notify(code, lparam)
        return 1
    
    controls = dict()
    
    @stash(controls.__setitem__, Entry)
    class Entry(object):
        def init(gui, ctrl, parent):
            ctrl.place(gui)
            ctrl.parent = parent.hwnd
            ctrl.height = round(12 * parent.y_unit)
            ctrl.width = 0
            ctrl.hwnd = create_control(ctrl.parent, "EDIT",
                tabstop=True,
                text=ctrl.value,
                style=ES_AUTOHSCROLL,
                ex_style=WS_EX_CLIENTEDGE,
            )
        
        def move(gui, win, ctrl, left, top, width, height):
            top += (height - ctrl.height) // 2
            MoveWindow(ctrl.hwnd, left, top, width, ctrl.height, 1)
        
        def get(gui, ctrl):
            return GetWindowText(ctrl.hwnd)
        
        def set(gui, ctrl, text):
            SetWindowText(ctrl.hwnd, text)
    
    @stash(controls.__setitem__, Button)
    class Button(object):
        def init(gui, ctrl, parent):
            ctrl.parent = parent.hwnd
            if ctrl.command:
                id = parent.id
                parent.id += 1
                parent.commands[id] = ctrl.command
            else:
                id = None
            
            ctrl.width = round(50 * parent.x_unit)
            ctrl.height = round(14 * parent.y_unit)
            
            disabled = ctrl.command is None
            ctrl.hwnd = create_control(ctrl.parent, "BUTTON",
                style=BS_PUSHBUTTON | WS_DISABLED * disabled,
                tabstop=True,
                text=ctrl.label_key(),
                id=id,
            )
        
        def move(gui, win, ctrl, left, top, width, height):
            left += (width - ctrl.width) // 2
            top += (height - ctrl.height) // 2
            MoveWindow(ctrl.hwnd, left, top, ctrl.width, ctrl.height, 1)
    
    @stash(controls.__setitem__, List)
    class List(object):
        def init(gui, ctrl, parent):
            ctrl.place(gui)
            ctrl.sel_set = set()
            
            ctrl.parent = parent.hwnd
            ctrl.height = 0
            InitCommonControls()
            ctrl.hwnd = create_control(ctrl.parent, WC_LISTVIEW,
                style=LVS_SHOWSELALWAYS | LVS_REPORT,
                tabstop=True,
                ex_style=WS_EX_CLIENTEDGE,
            )
            parent.notify[ctrl.hwnd] = partial(gui.List.notify, gui, ctrl)
            
            style = SendMessage(ctrl.hwnd, LVM_GETEXTENDEDLISTVIEWSTYLE,
                0, 0)
            style |= LVS_EX_FULLROWSELECT
            SendMessage(ctrl.hwnd, LVM_SETEXTENDEDLISTVIEWSTYLE, 0, style)
            
            ctrl.column_refs = list()
            for (i, heading) in enumerate(ctrl.columns):
                (param, obj) = PackLVCOLUMN(
                    fmt=LVCFMT_LEFT, text=heading, cx=50,
                )
                ctrl.column_refs.append(obj)
                SendMessage(ctrl.hwnd, LVM_INSERTCOLUMNW, i, param)
            
            ctrl.items = list()
        
        def move(gui, win, ctrl, left, top, width, height):
            MoveWindow(ctrl.hwnd, left, top, width, height, 1)
        
        def clear(gui, ctrl):
            SendMessage(ctrl.hwnd, LVM_DELETEALLITEMS)
            del ctrl.items[:]
            ctrl.sel_set.clear()
        
        def add(gui, ctrl, columns, selected=False):
            item = len(ctrl.items)
            columns = iter(columns)
            (param, obj) = PackLVITEM(
                item=item,
                text=next(columns),
                stateMask=LVIS_SELECTED, state=LVIS_SELECTED * selected,
            )
            ctrl.items.append([obj])
            cb = ctrl.selected
            ctrl.selected = None
            item = SendMessage(ctrl.hwnd, LVM_INSERTITEMW, 0, param)
            ctrl.selected = cb
            
            for (col, text) in enumerate(columns, 1):
                (param, obj) = PackLVITEM(text=text, subItem=col)
                ctrl.items[-1].append(obj)
                SendMessage(ctrl.hwnd, LVM_SETITEMTEXTW, item, param)
            
            if selected:
                ctrl.sel_set.add(item)
                if ctrl.selected:
                    ctrl.selected()
        
        def remove(gui, ctrl, item):
            ctrl.items.pop(item)
            SendMessage(ctrl.hwnd, LVM_DELETEITEM, item)
        
        def notify(gui, ctrl, code, pnmh):
            if code != LVN_ITEMCHANGED:
                return
            (_, _, _, item, _, new, old, changed, _, _, _) = (
                NM_LISTVIEW.unpack(pnmh))
            if not changed & LVIF_STATE:
                return
            old &= LVIS_SELECTED
            new &= LVIS_SELECTED
            if old == new:
                return
            
            if new:
                ctrl.sel_set.add(item)
            else:
                ctrl.sel_set.remove(item)
            
            if ctrl.selected:
                ctrl.selected()
        
        def get(gui, ctrl, item):
            values = list()
            for col in range(len(ctrl.columns)):
                (lvitem, obj) = EmptyLVITEM(0, col, LVIF_TEXT)
                SendMessage(ctrl.hwnd, LVM_GETITEMTEXTW, item, lvitem)
                (_, _, _, _, text, _, _, _) = UnpackLVITEM(lvitem)
                values.append(text)
            return values
        
        def selection(gui, ctrl):
            return sorted(ctrl.sel_set)
        
        def iter(gui, ctrl):
            return iter(range(len(ctrl.items)))
    
    @stash(controls.__setitem__, Form)
    class Form:
        def init(gui, ctrl, win):
            ctrl.fixed_height = 0
            ctrl.var_heights = 0
            for section in ctrl.fields:
                if not isinstance(section, (Section, Field)):
                    gui.controls[type(section)].init(gui, section, win)
                    if section.height:
                        ctrl.fixed_height += section.height
                    else:
                        ctrl.var_heights += 1
                    continue
                
                label = section.label_key()
                section.hwnd = create_control(win.hwnd, "BUTTON",
                    style=BS_GROUPBOX, text=label,
                )
                ctrl.fixed_height += win.label_height
                
                for field in section.fields:
                    if isinstance(field, Field):
                        label = field.label_key()
                        target = field.field
                        
                        field.label = create_control(win.hwnd,
                            "STATIC", text=label)
                    else:
                        target = field
                    
                    gui.controls[type(target)].init(gui, target, win)
                    if target.height:
                        ctrl.fixed_height += max(win.label_height,
                            target.height)
                    else:
                        ctrl.var_heights += 1
                
                ctrl.fixed_height += round(4 * win.y_unit)
        
        def move(gui, win, ctrl, x, y, cx, cy):
            spare_height = cy - ctrl.fixed_height
            for section in ctrl.fields:
                if not isinstance(section, (Section, Field)):
                    field_height = section.height
                    if not field_height:
                        field_height = spare_height // ctrl.var_heights
                        spare_height += 1  # Distribute division rounding
                    move = gui.controls[type(section)].move
                    move(gui, win, section, 0, y, cx, field_height)
                    y += field_height
                    continue
                
                group_top = y
                y += win.label_height
                for field in section.fields:
                    if isinstance(field, Field):
                        target = field.field
                    else:
                        target = field
                    
                    if target.height:
                        field_height = max(win.label_height, target.height)
                        label_y = y + (field_height - win.label_height) // 2
                    else:
                        field_height = spare_height // ctrl.var_heights
                        spare_height += 1 # Distribute rounding from division
                        label_y = y
                    
                    if isinstance(field, Field):
                        label_width = round(80 * win.x_unit)
                        MoveWindow(field.label,
                            0, label_y, label_width, win.label_height, 1)
                    else:
                        label_width = 0
                    
                    target_width = cx - label_width
                    move = gui.controls[type(target)].move
                    move(gui, win, target,
                        label_width, y, target_width, field_height)
                    
                    y += field_height
                
                y += round(4 * win.y_unit)
                group_height = y - group_top
                MoveWindow(section.hwnd, 0, group_top, cx, group_height, 1)
    
    @stash(controls.__setitem__, Inline)
    class Inline:
        def init(gui, ctrl, parent):
            ctrl.height = 0
            ctrl.fixed_width = 0
            ctrl.var_widths = 0
            for cell in ctrl.cells:
                gui.controls[type(cell)].init(gui, cell, parent)
                ctrl.height = max(ctrl.height, cell.height)
                
                if cell.width:
                    ctrl.fixed_width += cell.width
                else:
                    ctrl.var_widths += 1
        
        def move(gui, win, ctrl, left, top, width, height):
            var_widths = ctrl.var_widths
            all_vary = not var_widths
            if all_vary:
                var_widths = len(ctrl.cells)
            
            width -= ctrl.fixed_width
            for cell in ctrl.cells:
                cell_width = cell.width
                if all_vary or not cell_width:
                    cell_width += width // var_widths
                    width += 1  # Distribute rounding from the division
                move = gui.controls[type(cell)].move
                move(gui, win, cell, left, top, cell_width, ctrl.height)
                left += cell_width
    
    def file_browse(self, mode, parent=None, *,
    title=None, types, file=None):
        filter = list()
        for (label, exts) in types:
            exts = ";".join("*." + ext for ext in exts)
            filter.append(
                "{label} ({exts})\0" "{exts}\0".format_map(locals()))
        filter.append("All (*)\0" "*\0")
        (_, defext) = types[0]
        
        mode = dict(open=GetOpenFileNameW, save=GetSaveFileNameW)[mode]
        try:
            (file, _, _) = mode(
                Filter="".join(filter),
                File=file,
                Title=title,
                Flags=OFN_HIDEREADONLY | OFN_EXPLORER | OFN_OVERWRITEPROMPT |
                    OFN_NOCHANGEDIR,
                DefExt=defext[0],
            )
        except win32gui.error as err:
            if err.winerror:
                raise
            file = None
        
        if not self.visible:
            PostQuitMessage(0)
            file = None
        
        return file

def create_control(parent, wndclass, text=None,
    tabstop=False, style=0, id=None,
    x=0, y=0, width=0, height=0,
    ex_style=0,
):
    style |= tabstop * WS_TABSTOP
    hwnd = CreateWindowEx(
        WS_EX_NOPARENTNOTIFY | ex_style,
        wndclass,
        text,
        WS_CHILD | WS_VISIBLE | style,
        x, y, width, height,
        parent,
        id,
        None,
    None)
    redraw = 0
    SendMessage(hwnd, WM_SETFONT,
        GetStockObject(DEFAULT_GUI_FONT), MAKELONG(redraw, 0))
    return hwnd

def nop():
    pass

class WinStruct(Struct):
    def unpack(self, p):
        return Struct.unpack(self, PyMakeBuffer(self.size, p))

DEFAULT_GUI_FONT = 17

# Python 3.2.3's Struct.format is actually a byte string

# Using signed integer for code because commctrl.LVM_ITEMCHANGED is negative
NMHDR = WinStruct(b"P I i")

NM_LISTVIEW = WinStruct(NMHDR.format + b"i i I I I 2l P")
