from win32gui import (PumpMessages, PostQuitMessage, SendMessage)
from win32gui import (
    CreateDialogIndirect,
    CreateWindowEx, DestroyWindow, ShowWindow,
    GetDC, ReleaseDC,
    GetWindowRect, MoveWindow, ScreenToClient,
)
from win32con import (WS_VISIBLE, WS_OVERLAPPEDWINDOW, WS_CHILD, WS_TABSTOP)
from win32con import WS_EX_NOPARENTNOTIFY
from win32con import (WM_DESTROY, WM_CLOSE, WM_SETFONT)
from win32con import SW_SHOWNORMAL
from win32gui import GetStockObject
from win32gui import (SelectObject, GetTextMetrics)
from guis import label_key
from guis import MethodClass
from win32api import GetSystemMetrics
from win32con import (SM_CXSIZEFRAME, SM_CYSIZEFRAME, SM_CYCAPTION)
from win32con import BS_GROUPBOX

class Win(object):
    def __init__(self):
        self.visible = set()
    
    def msg_loop(self):
        if self.visible:
            PumpMessages()
    
    class Window(object, metaclass=MethodClass):
        def __init__(self, gui, title=None):
            self.gui = gui
            
            template = (title, (0, 0, 0, 0), WS_OVERLAPPEDWINDOW)
            handlers = {
                WM_DESTROY: self.on_destroy,
                WM_CLOSE: self.on_close,
            }
            self.hwnd = CreateDialogIndirect(None, (template,), 0, handlers)
            
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
            
            self.height = 0
            self.label_height = round(9 * self.y_unit)
        
        def on_destroy(self, hwnd, msg, wparam, lparam):
            self.gui.visible.remove(self)
            PostQuitMessage(0)
        
        def on_close(self, hwnd, msg, wparam, lparam):
            DestroyWindow(self.hwnd)
        
        def show(self):
            (left, top, _, _) = GetWindowRect(self.hwnd)
            width = round(80 * self.x_unit)
            height = self.height
            width += GetSystemMetrics(SM_CXSIZEFRAME) * 2
            height += GetSystemMetrics(SM_CYSIZEFRAME) * 2
            height += GetSystemMetrics(SM_CYCAPTION)
            MoveWindow(self.hwnd, left, top, width, height, 0)
            
            ShowWindow(self.hwnd, SW_SHOWNORMAL)
            self.gui.visible.add(self)
        
        def add_field(self, label, field, key=None):
            label = label_key(label, key)
            create_control(self.hwnd, "STATIC",
                text=label,
                y=self.height,
                width=round(80 * self.x_unit), height=self.label_height,
            )
            self.height += self.label_height
        
        def start_section(self, label, key=None):
            label = label_key(label, key)
            create_control(self.hwnd, "BUTTON",
                style=BS_GROUPBOX, text=label,
                y=self.height, width=round(80 * self.x_unit),
            )
            self.height += self.label_height
        
        def end_section(self):
            self.height += round(4 * self.y_unit)
            (left, top, right, _) = GetWindowRect(self.group)
            (left, top) = ScreenToClient(self.hwnd, (left, top))
            (right, _) = ScreenToClient(self.hwnd, (right, 0))
            bottom = self.height
            MoveWindow(self.group, left, top, right - left, bottom - top, 0)

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
