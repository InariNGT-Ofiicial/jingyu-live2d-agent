"""Display VTS's native Spout image as a movable Windows desktop pet."""
import time
import tkinter as tk
from PIL import Image, ImageTk
from vts_capture import Receiver, fit_rgba

def main():
    receiver=Receiver()
    try:
        root=tk.Tk()
        root.title('鲸语 · VTS 透明桌宠')
        width,height=512,320
        key='#010203'
        root.geometry(f'{width}x{height}+{max(0,root.winfo_screenwidth()-width)}+{max(0,root.winfo_screenheight()-height-64)}')
        root.overrideredirect(True)
        root.attributes('-topmost',True)
        root.attributes('-transparentcolor',key)
        panel=tk.Label(root,bg=key,bd=0,highlightthickness=0)
        panel.pack(fill='both',expand=True)
        origin=[0,0]
        def grab(e):
            origin[:]=[e.x_root-root.winfo_x(),e.y_root-root.winfo_y()]
        def drag(e):
            root.geometry(f'+{max(0,e.x_root-origin[0])}+{max(0,e.y_root-origin[1])}')
        panel.bind('<ButtonPress-1>',grab)
        panel.bind('<B1-Motion>',drag)
        panel.bind('<Button-3>',lambda _:root.destroy())
        root.bind('<Escape>',lambda _:root.destroy())
        frame_count=0
        def render():
            nonlocal frame_count
            start=time.monotonic()
            try:
                raw,size,_=receiver.read(timeout=1)
                image=fit_rgba(Image.frombytes('RGBA',size,raw),width,height)
                # Tk's Windows transparent-color window supports binary alpha.
                canvas=Image.new('RGB',(width,height),(1,2,3))
                canvas.paste(image.convert('RGB'),mask=image.getchannel('A').point(lambda a:255 if a>=128 else 0))
                panel.photo=ImageTk.PhotoImage(canvas)
                panel.configure(image=panel.photo)
                if image.getchannel('A').getextrema()[1]>0:
                    frame_count+=1
                    if frame_count==3:print(f'Native pet ready: {receiver.name}, {size}',flush=True)
            except Exception as error:
                print(str(error),flush=True);root.destroy();return
            root.after(max(1,round(1000*(1/15-time.monotonic()+start))),render)
        root.after(1,render)
        root.mainloop()
    finally:receiver.close()

if __name__=='__main__':main()
