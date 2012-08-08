from win32gui import (PumpMessages, PostQuitMessage, SendMessage)
from win32gui import (
    CreateDialogIndirect,
    CreateWindowEx, DestroyWindow, ShowWindow,
    GetDC, ReleaseDC,
    GetWindowRect, MoveWindow, ScreenToClient,
)
from win32con import (WS_VISIBLE, WS_OVERLAPPEDWINDOW, WS_CHILD, WS_TABSTOP)
from win32con import (WS_EX_NOPARENTNOTIFY, WS_EX_CLIENTEDGE)
from win32con import (WM_DESTROY, WM_CLOSE, WM_SIZE)
from win32con import (WM_SETFONT, WM_INITDIALOG)
from win32con import SW_SHOWNORMAL
from win32gui import GetStockObject
from win32gui import (SelectObject, GetTextMetrics)
from guis import label_key
from guis import InnerClass
from win32api import GetSystemMetrics
from win32con import (SM_CXSIZEFRAME, SM_CYSIZEFRAME, SM_CYCAPTION)
from win32con import BS_GROUPBOX
from win32api import (LOWORD, HIWORD)
from win32con import ES_AUTOHSCROLL

class Win(object):
    def __init__(self):
        self.visible = set()
    
    def msg_loop(self):
        if self.visible:
            PumpMessages()
    
    class Window(object, metaclass=InnerClass):
        def __init__(self, gui, title=None, *, sections):
            self.gui = gui
            
            template = (title, (0, 0, 0, 0), WS_OVERLAPPEDWINDOW)
            handlers = {
                WM_INITDIALOG: self.on_init_dialog,
                WM_DESTROY: self.on_destroy,
                WM_CLOSE: self.on_close,
                WM_SIZE: self.on_size,
            }
            self.sections = sections
            CreateDialogIndirect(None, (template,), 0, handlers)
            
            (left, top, _, _) = GetWindowRect(self.hwnd)
            width = round(80 * self.x_unit) + round(160 * self.x_unit)
            height = self.height
            width += GetSystemMetrics(SM_CXSIZEFRAME) * 2
            height += GetSystemMetrics(SM_CYSIZEFRAME) * 2
            height += GetSystemMetrics(SM_CYCAPTION)
            MoveWindow(self.hwnd, left, top, width, height, 0)
            
            ShowWindow(self.hwnd, SW_SHOWNORMAL)
            self.gui.visible.add(self)
        
        def on_init_dialog(self, hwnd, msg, wparam, lparam):
            self.hwnd = hwnd
            
            dc = GetDC(self.hwnd)
            try:
                prev = SelectObject(dc, GetStockObject(DEFAULT_GUI_FONT))
                try:
                    tm = GetTextMetrics(dc)
                    self.x_unit = (tm["AveCharWidth"] + 1) / 4
                    self.y_unit = tm["Height"] / 8
                finally:
                    SelectObject(dc, prev)
            finally:
                ReleaseDC(self.hwnd, dc)
            
            self.fields = list()
            self.groups = list()
            self.height = 0
            label_height = round(9 * self.y_unit)
            
            for section in self.sections:
                label = label_key(section["label"], section.get("access"))
                self.groups.append(create_control(self.hwnd, "BUTTON",
                    style=BS_GROUPBOX, text=label,
                ))
                group_top = self.height
                self.height += label_height
                
                for field in section["fields"]:
                    label = label_key(field["label"], field.get("access"))
                    field = field["field"]
                    
                    field.set_parent(self)
                    entry_height = field.height
                    field_height = max(label_height, entry_height)
                    create_control(self.hwnd, "STATIC",
                        text=label,
                        y=self.height + (field_height - label_height) // 2,
                        width=round(80 * self.x_unit), height=label_height,
                    )
                    field.place(
                        x=round(80 * self.x_unit),
                        y=self.height + (field_height - entry_height) // 2,
                    )
                    self.fields.append(field)
                    
                    self.height += field_height
                
                self.height += round(4 * self.y_unit)
                group_height = self.height - group_top
                MoveWindow(self.groups[-1], 0, group_top, 0, group_height, 0)
        
        def on_destroy(self, hwnd, msg, wparam, lparam):
            self.gui.visible.remove(self)
            PostQuitMessage(0)
        
        def on_close(self, hwnd, msg, wparam, lparam):
            DestroyWindow(self.hwnd)
        
        def on_size(self, hwnd, msg, wparam, lparam):
            cx = LOWORD(lparam)
            cy = HIWORD(lparam)
            
            for group in self.groups:
                (left, top, _, bottom) = GetWindowRect(group)
                (left, top) = ScreenToClient(self.hwnd, (left, top))
                (_, bottom) = ScreenToClient(self.hwnd, (0, bottom))
                MoveWindow(group, left, top, cx - left, bottom - top, 1)
            
            for field in self.fields:
                (left, top, _, height) = field.geom()
                field.move(left, top, cx - left, height)
            
            return 1
    
    class Entry(object):
        def __init__(self, value=None):
            self.value = value
        
        def set_parent(self, parent):
            self.parent = parent.hwnd
            self.height = round(12 * parent.y_unit)
        
        def place(self, x, y):
            self.hwnd = create_control(self.parent, "EDIT",
                tabstop=True,
                text=self.value,
                x=x, y=y,
                height=self.height,
                style=ES_AUTOHSCROLL,
                ex_style=WS_EX_CLIENTEDGE,
            )
        
        def geom(self):
            (left, top, right, _) = GetWindowRect(self.hwnd)
            width = right - left
            (left, top) = ScreenToClient(self.parent, (left, top))
            return (left, top, width, self.height)
        
        def move(self, left, top, width, height):
            MoveWindow(self.hwnd, left, top, width, self.height, 1)

def create_control(parent, wndclass, text=None,
    tabstop=False, style=0,
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
        None,
        None,
    None)
    SendMessage(hwnd, WM_SETFONT, GetStockObject(DEFAULT_GUI_FONT), 0 << 0)
    return hwnd

DEFAULT_GUI_FONT = 17
