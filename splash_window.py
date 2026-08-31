import sys
import threading
import os

_root = None
_canvas = None
_label = None


def _icon_path():
    base = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base, "server.ico")


def _run():
    global _root, _canvas, _label
    try:
        import tkinter as tk
        from PIL import Image, ImageTk
    except Exception:
        return

    _root = tk.Tk()
    _root.overrideredirect(True)
    _root.attributes("-topmost", True)
    _root.configure(bg="#0b0e13")

    W, H = 460, 280
    sw = _root.winfo_screenwidth()
    sh = _root.winfo_screenheight()
    _root.geometry("%dx%d+%d+%d" % (W, H, int(sw / 2 - W / 2), int(sh / 2 - H / 2)))

    canvas = tk.Canvas(_root, width=W, height=H, bg="#0b0e13", highlightthickness=0)
    canvas.pack(fill="both", expand=True)

    # 그라데이션 배경
    bg = Image.new("RGB", (W, H), (11, 14, 19))
    px = bg.load()
    top = (18, 24, 33)
    bot = (9, 11, 15)
    for y in range(H):
        t = y / (H - 1)
        r = int(top[0] + (bot[0] - top[0]) * t)
        g = int(top[1] + (bot[1] - top[1]) * t)
        b = int(top[2] + (bot[2] - top[2]) * t)
        for x in range(W):
            px[x, y] = (r, g, b)
    bg_img = ImageTk.PhotoImage(bg)
    canvas.create_image(0, 0, image=bg_img, anchor="nw")
    canvas.bg_img = bg_img

    # 하단 액센트 라인
    canvas.create_line(0, H - 2, W, H - 2, fill="#00c8dc", width=2)

    # 로고
    try:
        logo = Image.open(_icon_path()).convert("RGBA").resize((76, 76), Image.LANCZOS)
        logo_img = ImageTk.PhotoImage(logo)
        canvas.create_image(W / 2, 72, image=logo_img, anchor="center")
        canvas.logo_img = logo_img
    except Exception:
        pass

    # 타이틀
    canvas.create_text(W / 2, 142, text="AYA Server Launcher",
                       fill="#eaf2f7", font=("Malgun Gothic", 19, "bold"))
    canvas.create_text(W / 2, 166, text="Minecraft Server Manager",
                       fill="#5b6b78", font=("Malgun Gothic", 10))

    # 상태 텍스트
    _label = canvas.create_text(W / 2, 205, text="", fill="#9aa6b0",
                                font=("Malgun Gothic", 11))

    _canvas = canvas
    _root.mainloop()


def show_splash():
    if not getattr(sys, "frozen", False):
        return
    t = threading.Thread(target=_run, daemon=True)
    t.start()


def close_splash():
    global _root
    if _root is not None:
        try:
            _root.after(0, _root.destroy)
        except Exception:
            pass
        _root = None


def set_status(text):
    global _root, _canvas, _label
    if _root is not None and _canvas is not None and _label is not None:
        try:
            _root.after(0, lambda: _canvas.itemconfig(_label, text=text))
        except Exception:
            pass
