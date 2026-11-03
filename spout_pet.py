"""Windows VTS pet: copy Spout texture on the GPU and composite per-pixel alpha."""
import argparse
import ctypes as C
import json
import time

import glfw
import SpoutGL
from vts_capture import choose_sender

TEXTURE = 0x0DE1
RGBA = 0x1908
BYTE = 0x1401

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--width', type=int, default=960)
    parser.add_argument('--fps', type=int, choices=range(15,145), default=60, metavar='15..144')
    parser.add_argument('--snapshot', help='Save one composited RGBA framebuffer for diagnostics')
    args = parser.parse_args()
    try:
        C.windll.user32.SetProcessDpiAwarenessContext(C.c_void_p(-4))
    except AttributeError:
        C.windll.user32.SetProcessDPIAware()
    if not glfw.init():
        raise RuntimeError('GLFW 初始化失败')
    receiver = None
    try:
        for hint in (glfw.FLOATING, glfw.TRANSPARENT_FRAMEBUFFER):
            glfw.window_hint(hint, glfw.TRUE)
        glfw.window_hint(glfw.DECORATED, glfw.FALSE)
        glfw.window_hint(glfw.FOCUS_ON_SHOW, glfw.FALSE)
        width = max(240, min(args.width, 1920))
        win = glfw.create_window(width, round(width*0.625), '鲸语 · 高清 VTS 桌宠', None, None)
        if not win:
            raise RuntimeError('无法创建透明 OpenGL 窗口')
        if not glfw.get_window_attrib(win, glfw.TRANSPARENT_FRAMEBUFFER):
            raise RuntimeError('桌面合成器未提供逐像素透明窗口')
        glfw.make_context_current(win)
        glfw.swap_interval(1)
        monitor = glfw.get_primary_monitor()
        left, top, sw, sh = glfw.get_monitor_workarea(monitor)
        glfw.set_window_pos(win, left+max(0,sw-width), top+max(0,sh-round(width*.625)))
        gl = C.windll.opengl32
        gl.glGetString.restype = C.c_char_p
        gpu = gl.glGetString(0x1F01).decode(errors='replace')
        tex = C.c_uint()
        gl.glGenTextures(1, C.byref(tex))
        gl.glBindTexture(TEXTURE, tex)
        for param in (0x2800,0x2801):
            gl.glTexParameteri(TEXTURE,param,0x2601)
        for param in (0x2802,0x2803):
            gl.glTexParameteri(TEXTURE,param,0x812F)
        gl.glClearColor(*(C.c_float(0) for _ in range(4)))
        receiver = SpoutGL.SpoutReceiver()
        sender = choose_sender(receiver.getSenderList())
        receiver.setReceiverName(sender)
        drag = []
        def mouse(w, button, action, mods):
            if button == glfw.MOUSE_BUTTON_RIGHT and action == glfw.PRESS:
                glfw.set_window_should_close(w, True)
            if button == glfw.MOUSE_BUTTON_LEFT:
                drag[:] = glfw.get_cursor_pos(w) if action == glfw.PRESS else []
        def move(w,x,y):
            if drag:
                a,b = glfw.get_window_pos(w)
                glfw.set_window_pos(w,round(a+x-drag[0]),round(b+y-drag[1]))
        def zoom(w,x,y):
            a,b = glfw.get_window_size(w)
            new = max(240,min(sw,round(a*1.12**y)))
            glfw.set_window_size(w,new,round(new*b/a))
        glfw.set_mouse_button_callback(win,mouse)
        glfw.set_cursor_pos_callback(win,move)
        glfw.set_scroll_callback(win,zoom)
        size = None
        count = 0
        benchmark = bool(args.snapshot)
        distinct = set()
        started = last_ok = time.perf_counter()
        while not glfw.window_should_close(win):
            begin = time.perf_counter()
            glfw.poll_events()
            if glfw.get_key(win,glfw.KEY_ESCAPE)==glfw.PRESS:break
            ok = receiver.receiveTexture(tex.value if size else 0, TEXTURE if size else 0, False, 0)
            updated = receiver.isUpdated()
            dims = receiver.getSenderWidth(), receiver.getSenderHeight()
            if min(dims)>0 and (updated or dims!=size):
                size=dims
                gl.glBindTexture(TEXTURE,tex)
                gl.glTexImage2D(TEXTURE,0,RGBA,*size,0,RGBA,BYTE,None)
                continue
            if not ok or not size or not receiver.isConnected():
                if time.perf_counter()-last_ok>4:raise RuntimeError('Spout 帧流中断，请检查 VTS 和接收 GPU')
                glfw.wait_events_timeout(.015)
                continue
            last_ok=time.perf_counter()
            w,h=glfw.get_framebuffer_size(win)
            scale=min(w/size[0],h/size[1])
            dw,dh=round(size[0]*scale),round(size[1]*scale)
            gl.glViewport((w-dw)//2,(h-dh)//2,dw,dh)
            gl.glClear(0x4000)
            gl.glEnable(TEXTURE)
            gl.glBindTexture(TEXTURE,tex)
            gl.glBegin(7)
            for x,y,u,v in [(-1,1,0,0),(1,1,1,0),(1,-1,1,1),(-1,-1,0,1)]:
                gl.glTexCoord2i(u,v);gl.glVertex2i(x,y)
            gl.glEnd()
            if benchmark:
                # Measure actual pixel changes in the diagnostic run only.
                pw,ph=max(1,w//2),max(1,h//2)
                pixels=(C.c_ubyte*(pw*ph*4))()
                gl.glReadPixels(w//4,h//4,pw,ph,RGBA,BYTE,pixels)
                distinct.add(hash(bytes(pixels)))
            if args.snapshot and count==12:
                from PIL import Image
                data=(C.c_ubyte*(w*h*4))()
                gl.glReadPixels(0,0,w,h,RGBA,BYTE,data)
                Image.frombytes('RGBA',(w,h),bytes(data)).transpose(Image.Transpose.FLIP_TOP_BOTTOM).save(args.snapshot)
                args.snapshot=None
            glfw.swap_buffers(win)
            delay=1/args.fps-(time.perf_counter()-begin)
            if delay>0:time.sleep(delay)
            count+=1
            now=time.perf_counter()
            if now-started>=5:
                report=dict(presentFPS=round(count/(now-started),1),source=size,framebuffer=[w,h],gpu=gpu)
                if benchmark:
                    report['distinctSampleFPS']=round(len(distinct)/(now-started),1)
                    benchmark=False;distinct.clear()
                print(json.dumps(report),flush=True)
                count=0;started=now
    finally:
        if receiver:receiver.releaseReceiver()
        glfw.terminate()

if __name__=='__main__':
    main()
