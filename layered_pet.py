"""Present the premultiplied VTS framebuffer through the Windows desktop compositor."""
import ctypes as C
import struct
import win32api
import win32con as K
import win32gui as G


class LayeredPet:
    def __init__(self, left, top, width, height, max_width):
        self.size = width, height
        self.closed = False
        self.max_width = max_width
        wc = G.WNDCLASS()
        wc.hInstance = win32api.GetModuleHandle(None)
        wc.lpszClassName = 'JingyuLayeredPet'
        wc.lpfnWndProc = self.message
        G.RegisterClass(wc)
        self.hwnd = G.CreateWindowEx(K.WS_EX_LAYERED | K.WS_EX_TOPMOST | K.WS_EX_TOOLWINDOW,
            wc.lpszClassName, '鲸语 · 高清 VTS 桌宠', K.WS_POPUP, left, top, width, height,
            0, 0, wc.hInstance, None)
        self.dc = G.CreateCompatibleDC(0)
        self.bitmap = self.old = None
        self.buffer_size = None
        self.shown = False

    def message(self, hwnd, msg, wp, lp):
        if msg == K.WM_LBUTTONDOWN:
            G.ReleaseCapture()
            G.SendMessage(hwnd, K.WM_NCLBUTTONDOWN, K.HTCAPTION, 0)
        elif msg == K.WM_MOUSEWHEEL:
            width, height = self.size
            width2 = max(240, min(self.max_width, round(width * 1.12 ** (C.c_short(wp >> 16).value / 120))))
            self.size = width2, round(width2 * height / width)
        elif msg in (K.WM_CLOSE, K.WM_RBUTTONDOWN) or (msg == K.WM_KEYDOWN and wp == K.VK_ESCAPE):
            self.closed = True
        else:
            return G.DefWindowProc(hwnd, msg, wp, lp)
        return 0

    def present(self, gl, w, h):
        if self.buffer_size != (w, h):
            self.free_bitmap()
            # Positive DIB height and OpenGL both store the bottom scanline first.
            info = struct.pack('<IiiHHIIiiII', 40, w, h, 1, 32, 0, 0, 0, 0, 0, 0)
            self.bits = C.c_void_p()
            make = C.windll.gdi32.CreateDIBSection
            make.restype = C.c_void_p
            self.bitmap = make(C.c_void_p(self.dc), info, 0, C.byref(self.bits), None, 0)
            if not self.bitmap:
                raise C.WinError()
            self.old = G.SelectObject(self.dc, self.bitmap)
            self.buffer_size = w, h
        gl.glReadPixels(0, 0, w, h, 0x80E1, 0x1401, self.bits)  # BGRA
        G.UpdateLayeredWindow(self.hwnd, 0, None, (w,h), self.dc, (0,0), 0, (0,0,255,1), 2)

        if not self.shown:
            G.ShowWindow(self.hwnd, K.SW_SHOWNOACTIVATE)
            self.shown = True

    def free_bitmap(self):
        if self.bitmap:
            G.SelectObject(self.dc, self.old)
            G.DeleteObject(self.bitmap)
            self.bitmap = None

    def close(self):
        self.free_bitmap()
        G.DeleteDC(self.dc)
        G.DestroyWindow(self.hwnd)
