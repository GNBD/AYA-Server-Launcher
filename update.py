import customtkinter as ctk
import os
import sys
import subprocess
import threading
import zipfile
import shutil
import time
import ctypes
import json

try:
    import requests
except ImportError:
    sys.exit()

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("dark-blue")

GITHUB_USER = "GNBD"
REPO_NAME = "AYA-Server-Launcher"
TARGET_EXE = "Server Launcher.exe"

BG = "#141517"
ACCENT = "#5f6fff"

class Updater:
    def __init__(self):
        exe_dir = os.path.dirname(sys.executable if getattr(sys, 'frozen', False) else os.path.abspath(__file__))
        target = os.path.join(os.path.dirname(exe_dir), TARGET_EXE)
        self.install_dir = os.path.dirname(exe_dir)
        self.cfg_path = os.path.join(exe_dir, "config", "launcher_config.json")

        self._root = ctk.CTk()
        self._root.configure(fg_color=BG)

        try:
            base = sys._MEIPASS if hasattr(sys, '_MEIPASS') else os.getcwd()
            self._root.iconbitmap(os.path.join(base, "server.ico"))
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID('aya.updater.v1.0')
        except:
            pass

        title = ctk.CTkFrame(self._root, height=32, fg_color="#111213", corner_radius=0)
        title.pack(fill="x")
        title.bind("<Button-1>", self._drag)
        title.bind("<B1-Motion>", self._drag_move)

        ctk.CTkFrame(title, width=7, height=7, fg_color=ACCENT, corner_radius=4).place(x=14, rely=0.5, anchor="w")
        ctk.CTkLabel(title, text="AYA Updater",
            font=ctk.CTkFont(size=10), text_color="#909296").place(x=28, rely=0.5, anchor="w")

        ctk.CTkButton(title, text="\u2715", width=34, height=28,
            fg_color="transparent", hover_color="#e03131",
            text_color="#5c5f66", font=ctk.CTkFont(size=11), corner_radius=0,
            command=lambda: os._exit(0)).place(relx=1, x=-10, rely=0.5, anchor="center")

        body = ctk.CTkFrame(self._root, fg_color=BG, corner_radius=0)
        body.pack(fill="both", expand=True)

        ctk.CTkLabel(body, text="\u2699\uFE0F  AYA Updater",
            font=ctk.CTkFont(size=15, weight="bold"),
            text_color="white").pack(pady=(20, 6))

        self._status = ctk.CTkLabel(body, text="",
            font=ctk.CTkFont(size=11), text_color="#909296")
        self._status.pack(pady=(0, 8))

        self._bar = ctk.CTkProgressBar(body, width=280,
            fg_color="#25262b", progress_color=ACCENT,
            corner_radius=4, mode="indeterminate")
        self._bar.pack()

        self._center_window()
        self._remove_frame_and_pin()

        if not os.path.exists(target):
            self._status.configure(text="Server Launcher.exe를 찾을 수 없습니다")
            self._root.after(2000, self._root.destroy)
            self._root.mainloop()
            sys.exit()

        if not self._is_running():
            self._status.configure(text="Server Launcher가 실행 중이 아닙니다")
            self._root.after(2000, self._root.destroy)
            self._root.mainloop()
            sys.exit()

        self._status.configure(text="버전 확인 중...")
        self._bar.start()
        self._root.after(100, self._check_version)
        self._root.mainloop()

    def _center_window(self):
        win_w, win_h = 400, 145
        self._root.geometry(f'{win_w}x{win_h}+0+0')
        self._root.update()
        ws = self._root.winfo_screenwidth()
        hs = self._root.winfo_screenheight()
        x = max(0, (ws - win_w) // 2)
        y = max(0, (hs - win_h) // 2)
        self._root.geometry(f'{win_w}x{win_h}+{x}+{y}')

    def _drag(self, e):
        self.dx, self.dy = e.x, e.y

    def _drag_move(self, e):
        if self._hwnd:
            x = self._root.winfo_x() + e.x - self.dx
            y = self._root.winfo_y() + e.y - self.dy
            ctypes.windll.user32.SetWindowPos(self._hwnd, 0, x, y, 0, 0, 0x0001 | 0x0004)
        else:
            self._root.geometry(f"+{self._root.winfo_x()+e.x-self.dx}+{self._root.winfo_y()+e.y-self.dy}")

    def _remove_frame_and_pin(self):
        try:
            self._root.update()
            hwnd = ctypes.windll.user32.GetParent(self._root.winfo_id())
            if not hwnd:
                hwnd = self._root.winfo_id()
            self._hwnd = hwnd
            if hwnd:
                s = ctypes.windll.user32.GetWindowLongW(hwnd, -16)
                s = s & ~0x00C00000 & ~0x00080000 & ~0x00040000 & ~0x00800000
                ctypes.windll.user32.SetWindowLongW(hwnd, -16, s)
                ex = ctypes.windll.user32.GetWindowLongW(hwnd, -20)
                ex = ex | 0x00040000
                ex = ex & ~0x00000080
                ctypes.windll.user32.SetWindowLongW(hwnd, -20, ex)
                ctypes.windll.user32.SetWindowPos(hwnd, 0, 0, 0, 0, 0, 0x0002 | 0x0001 | 0x0004 | 0x0020)
        except:
            self._hwnd = None

    def _is_running(self):
        try:
            r = subprocess.run(['tasklist', '/fi', f'imagename eq {TARGET_EXE}'],
                             capture_output=True, text=True, timeout=3,
                             creationflags=subprocess.CREATE_NO_WINDOW)
            return TARGET_EXE in r.stdout
        except:
            return False

    def _set_status(self, text):
        self._root.after(0, lambda: self._status.configure(text=text))

    def _check_version(self):
        threading.Thread(target=self._do_check, daemon=True).start()

    def _do_check(self):
        local = None
        if os.path.exists(self.cfg_path):
            try:
                with open(self.cfg_path, "r", encoding="utf-8") as f:
                    local = json.load(f).get("version")
            except:
                pass

        try:
            r = requests.get(f"https://api.github.com/repos/{GITHUB_USER}/{REPO_NAME}/releases/latest", timeout=5)
            d = r.json()
            latest = d.get("tag_name", "")
        except:
            self._set_status("서버 연결 실패")
            time.sleep(2)
            self._root.after(0, self._root.destroy)
            return

        if local and local == latest:
            self._bar.stop()
            self._set_status("이미 최신 버전입니다")
            time.sleep(2)
            self._root.after(0, self._root.destroy)
            return

        self._set_status("서버 런처 종료 중...")
        subprocess.run(['taskkill', '/f', '/im', TARGET_EXE],
                     capture_output=True, creationflags=subprocess.CREATE_NO_WINDOW)
        time.sleep(0.5)
        self._do_download(latest)

    def _do_download(self, tag):
        try:
            r = requests.get(
                f"https://api.github.com/repos/{GITHUB_USER}/{REPO_NAME}/releases/latest",
                timeout=5)
            d = r.json()
            tag = d.get("tag_name", "")
            url = next((a["browser_download_url"] for a in d.get("assets", [])
                       if a["name"].endswith(".zip")), None)
            if not url:
                raise Exception("릴리즈 파일을 찾을 수 없습니다")

            tmp = os.path.join(os.environ["TEMP"], "aya_update")
            os.makedirs(tmp, exist_ok=True)
            zp = os.path.join(tmp, "update.zip")

            self._set_status(f"Downloading {tag}")
            with requests.get(url, stream=True) as rq, open(zp, 'wb') as f:
                total = int(rq.headers.get('content-length', 0))
                dl = 0
                for c in rq.iter_content(8192):
                    f.write(c)
                    dl += len(c)
                    if total:
                        self._root.after(0, lambda: self._bar.configure(mode="determinate"))
                        self._root.after(0, lambda p=dl/total: self._bar.set(p))

            self._set_status("설치 중...")
            extract = os.path.join(tmp, "extracted")
            os.makedirs(extract, exist_ok=True)
            with zipfile.ZipFile(zp, 'r') as z:
                z.extractall(extract)

            items = os.listdir(extract)
            src = os.path.join(extract, items[0]) if len(items) == 1 and os.path.isdir(os.path.join(extract, items[0])) else extract

            for item in os.listdir(src):
                s = os.path.join(src, item)
                d = os.path.join(self.install_dir, item)
                if os.path.exists(d):
                    (shutil.rmtree if os.path.isdir(d) else os.remove)(d)
                shutil.move(s, d)

            shutil.rmtree(tmp, ignore_errors=True)

            if os.path.exists(self.cfg_path):
                with open(self.cfg_path, "r", encoding="utf-8") as f:
                    cfg = json.load(f)
                cfg["version"] = tag
                with open(self.cfg_path, "w", encoding="utf-8") as f:
                    json.dump(cfg, f, indent=2, ensure_ascii=False)

            self._bar.stop()
            self._bar.set(1.0)
            self._set_status("업데이트 완료!")
            time.sleep(0.5)
            subprocess.Popen([os.path.join(self.install_dir, TARGET_EXE)], cwd=self.install_dir)
            time.sleep(1)

        except Exception as e:
            self._bar.stop()
            self._set_status(f"오류: {str(e)}")
            time.sleep(3)

        self._root.after(0, self._root.destroy)

if __name__ == "__main__":
    Updater()
