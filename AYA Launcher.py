import tkinter as tk
from tkinter import ttk
import os
import sys
import subprocess
import threading
import zipfile
import shutil
import webbrowser
import socket
import time
import ctypes
from tkinter import font

# 외부 라이브러리 체크
try:
    import requests
except ImportError:
    import tkinter.messagebox
    root = tk.Tk()
    root.withdraw()
    tk.messagebox.showerror("오류", "필수 모듈이 없습니다.\n'pip install requests'")
    sys.exit()

# ==========================================
# [설정] 사용자 수정 영역
# ==========================================
GITHUB_USER = "GNBD"
REPO_NAME = "AYA-Server-Launcher"
APP_TITLE = "AYA AIO"
MAIN_TITLE = "AYA AIO"
ICON_FILENAME = "server.ico"
LOCK_PORT = 54321

LANG_PACK = {
    "ko": {
        "title": "AYA AIO KR",
        "ready": "준비됨",
        "ver_check": "버전 확인 필요",
        "ver_current": "현재: {}",
        "ver_none": "없음",
        "settings": "⚙ 설정",
        "update_check": "업데이트 확인",
        "checking": "확인 중...",
        "run": "실행하기",
        "install_needed": "설치 필요",
        "apps_list": "APPS LIST",
        "manage": "관리",
        "repair": "파일 복구 (재설치)",
        "open_folder": "설치 폴더 열기",
        "lang_sel": "언어 선택 (Language)",
        "info": "정보",
        "license": "오픈소스 라이선스",
        "helper_info": "Server Launcher 정보",
        "ep_info": "NeneEP 정보",
        "made_by": "만든 이: GNBD(JIN)",
        "gemini": "Made with Google Gemini",
        "update_avail": "업데이트 가능",
        "new_ver_msg": "새로운 버전이 있습니다!\n\n현재: {}\n최신: {}",
        "later": "나중에",
        "update": "업데이트",
        "error": "오류",
        "server_fail": "서버 연결 실패",
        "net_error": "인터넷 연결을 확인해주세요.\n{}",
        "latest_msg": "최신 버전입니다.",
        "folder_error": "폴더를 열 수 없습니다:\n{}",
        "no_folder": "설치된 폴더가 없습니다.",
        "lang_changed": "언어가 '{}'(으)로 변경되었습니다.\n(UI가 갱신됩니다)",
        "downloading": "다운로드 중...",
        "installing": "설치 중...",
        "done": "완료!",
        "success_msg": "설치 완료!",
        "fail_msg": "실패",
        "file_missing": "파일 없음",
        "running": "{} 실행 중...",
        "app_desc_1": "Server Launcher를 실행합니다.",
        "app_desc_2": "NeneEP 를 실행합니다."
    },
    "en": {
        "title": "AYA AIO EN",
        "ready": "Ready",
        "ver_check": "Check Version",
        "ver_current": "Current: {}",
        "ver_none": "None",
        "settings": "⚙ Settings",
        "update_check": "Check Update",
        "checking": "Checking...",
        "run": "Launch",
        "install_needed": "Install Needed",
        "apps_list": "APPS LIST",
        "manage": "Manage",
        "repair": "Repair Files (Reinstall)",
        "open_folder": "Open Folder",
        "lang_sel": "Select Language",
        "info": "Info",
        "license": "Open Source Licenses",
        "helper_info": "Server Launcher Info",
        "ep_info": "NeneEP Info",
        "made_by": "Created by: {}",
        "gemini": "Made with Google Gemini",
        "update_avail": "Update Available",
        "new_ver_msg": "New version available!\n\nCurrent: {}\nLatest: {}",
        "later": "Later",
        "update": "Update",
        "error": "Error",
        "server_fail": "Server Connection Failed",
        "net_error": "Check internet connection.\n{}",
        "latest_msg": "You are using the latest version.",
        "folder_error": "Cannot open folder:\n{}",
        "no_folder": "Folder not found.",
        "lang_changed": "Language changed to '{}'.\n(UI will refresh)",
        "downloading": "Downloading...",
        "installing": "Installing...",
        "done": "Done!",
        "success_msg": "Installation Complete!",
        "fail_msg": "Failed",
        "file_missing": "File Missing",
        "running": "Running {}...",
        "app_desc_1": "Launch Server Launcher.",
        "app_desc_2": "Launch NeneEP."
    },
    "jp": {
        "title": "AYA AIO JP",
        "ready": "準備完了",
        "ver_check": "バージョン確認",
        "ver_current": "現在: {}",
        "ver_none": "なし",
        "settings": "⚙ 設定",
        "update_check": "更新確認",
        "checking": "確認中...",
        "run": "起動",
        "install_needed": "インストール必要",
        "apps_list": "アプリ一覧",
        "manage": "管理",
        "repair": "修復 (再インストール)",
        "open_folder": "フォルダを開く",
        "lang_sel": "言語選択 (Language)",
        "info": "情報",
        "license": "オープンソースライセンス",
        "helper_info": "Server Launcher 情報",
        "ep_info": "NeneEP 情報",
        "made_by": "作成者: {}",
        "gemini": "Made with Google Gemini",
        "update_avail": "アップデート可能",
        "new_ver_msg": "新しいバージョンがあります！\n\n現在: {}\n最新: {}",
        "later": "後で",
        "update": "更新",
        "error": "エラー",
        "server_fail": "サーバー接続失敗",
        "net_error": "インターネット接続を確認してください。\n{}",
        "latest_msg": "最新バージョンです。",
        "folder_error": "フォルダを開けません:\n{}",
        "no_folder": "インストールフォルダがありません。",
        "lang_changed": "言語が '{}' に変更されました。\n(UIが更新されます)",
        "downloading": "ダウンロード中...",
        "installing": "インストール中...",
        "done": "完了!",
        "success_msg": "インストール完了!",
        "fail_msg": "失敗",
        "file_missing": "ファイルなし",
        "running": "{} 実行中...",
        "app_desc_1": "Server Launcherを起動します。",
        "app_desc_2": "NeneEPを起動します。"
    },
    "cn": {
        "title": "AYA AIO CN",
        "ready": "准备就绪",
        "ver_check": "检查版本",
        "ver_current": "当前: {}",
        "ver_none": "无",
        "settings": "⚙ 设置",
        "update_check": "检查更新",
        "checking": "检查中...",
        "run": "启动",
        "install_needed": "需安装",
        "apps_list": "应用列表",
        "manage": "管理",
        "repair": "修复 (重新安装)",
        "open_folder": "打开文件夹",
        "lang_sel": "语言选择 (Language)",
        "info": "信息",
        "license": "开源许可",
        "helper_info": "Server Launcher 信息",
        "ep_info": "NeneEP 信息",
        "made_by": "作者: {}",
        "gemini": "Made with Google Gemini",
        "update_avail": "有可用更新",
        "new_ver_msg": "发现新版本！\n\n当前: {}\n最新: {}",
        "later": "稍后",
        "update": "更新",
        "error": "错误",
        "server_fail": "服务器连接失败",
        "net_error": "请检查网络连接。\n{}",
        "latest_msg": "已是最新版本。",
        "folder_error": "无法打开文件夹:\n{}",
        "no_folder": "未找到安装文件夹。",
        "lang_changed": "语言已更改为 '{}'。\n(UI将刷新)",
        "downloading": "下载中...",
        "installing": "安装中...",
        "done": "完成!",
        "success_msg": "安装完成!",
        "fail_msg": "失败",
        "file_missing": "文件丢失",
        "running": "正在运行 {}...",
        "app_desc_1": "启动 Server Launcher。",
        "app_desc_2": "启动 NeneEP。"
    }
}
# ==========================================

class NeneLauncherApp:
    def __init__(self, root):
        self.root = root
        
        # 중복 실행 방지
        self.enforce_single_instance()
        
        self.selected_language = "ko"
        self.root.title(APP_TITLE)
        self.load_icon()
        self.root.overrideredirect(True)
        
        self.is_minimized = False
        self.is_first_map = True
        self.current_app = None 
        
        try:
            myappid = 'nene.launcher.v1.0' 
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid)
        except:
            pass

        
        self.width = 800
        self.height = 500
        self.center_window(self.width, self.height)
        
        
        self.colors = {
            "bg": "#2f3136",          
            "sidebar": "#202225",     
            "fg": "#ffffff",          
            "sub_fg": "#b9bbbe",      
            "btn_bg": "#228B22",      
            "btn_hover": "#7CFC00",   
            "btn_disabled": "#4f545c",
            "item_hover": "#34373c",  
            "item_select": "#006400", 
            "title_bar": "#202225",   
            "close_hover": "#ed4245", 
            "accent": "#3ba55c"       
        }
        
        self.root.configure(bg=self.colors["bg"])
        
      
        self.title_font = font.Font(family="Malgun Gothic", size=24, weight="bold")
        self.desc_font = font.Font(family="Malgun Gothic", size=11)
        self.list_font = font.Font(family="Malgun Gothic", size=10, weight="bold")
        self.btn_font = font.Font(family="Malgun Gothic", size=14, weight="bold")
        self.status_font = font.Font(family="Malgun Gothic", size=9)

        
        self.current_dir = os.getcwd()
        self.game_folder = os.path.join(self.current_dir, "Server Launcher")
        self.exe_helper = "Server Launcher.exe"
        self.exe_ep = "NeneEP.exe"
        self.version_file = "version.txt"
        
        
        self.app_list = [
            {
                "name": "Server Launcher",
                "exe": self.exe_helper,
                "desc_key": "app_desc_1", 
                "icon": "🛠️"
            },
            {
                "name": "EasyPort",
                "exe": self.exe_ep,
                "desc_key": "app_desc_2", 
                "icon": "🔌"
            }
        ]
        self.sidebar_widgets = {} 

       
        self.create_widgets()
        self.check_installation()
        self.display_local_version_only()
        
        
        self.select_app(self.app_list[0]["name"])
        
        
        self.root.after(200, self.set_appwindow)
        self.root.bind("<Map>", self.on_map)

    
    def T(self, key):
        return LANG_PACK.get(self.selected_language, LANG_PACK["ko"]).get(key, key)

   
    def refresh_ui_text(self):
        
        self.lbl_main_title_bar.config(text=self.T("title"))
        
       
        self.lbl_sidebar_title.config(text=self.T("apps_list"))
        
        
        self.btn_settings.config(text=self.T("settings"))
        self.btn_update.config(text=self.T("update_check"))
        self.status_label.config(text=self.T("ready"))
        
       
        if self.current_app:
            self.lbl_main_desc.config(text=self.T(self.current_app["desc_key"]))
            self.check_run_button_state()
            
        
        self.display_local_version_only()

    def enforce_single_instance(self):
        self.lock_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            self.lock_socket.bind(('127.0.0.1', LOCK_PORT))
            self.lock_socket.listen(1)
            threading.Thread(target=self._listen_kill, daemon=True).start()
        except OSError:
            try:
                s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                s.connect(('127.0.0.1', LOCK_PORT)); s.send(b'kill'); s.close()
                time.sleep(0.5)
                self.lock_socket.bind(('127.0.0.1', LOCK_PORT))
                self.lock_socket.listen(1)
                threading.Thread(target=self._listen_kill, daemon=True).start()
            except: pass

    def _listen_kill(self):
        try:
            while True:
                c, _ = self.lock_socket.accept()
                if c.recv(1024) == b'kill': os._exit(0)
        except: pass

    def load_icon(self):
        try:
            base = sys._MEIPASS if hasattr(sys, '_MEIPASS') else os.getcwd()
            self.root.iconbitmap(default=os.path.join(base, ICON_FILENAME))
        except: pass

    def set_appwindow(self):
        try:
            if not self.root.winfo_exists(): return
            hwnd = ctypes.windll.user32.GetParent(self.root.winfo_id())
            if not hwnd: hwnd = self.root.winfo_id()
            if hwnd:
                ctypes.windll.user32.SetParent(hwnd, 0)
                style = ctypes.windll.user32.GetWindowLongW(hwnd, -20)
                style = style & ~0x00000080 | 0x00040000
                ctypes.windll.user32.SetWindowLongW(hwnd, -20, style)
                ctypes.windll.user32.SetWindowPos(hwnd, 0, 0, 0, 0, 0, 0x0002|0x0001|0x0004|0x0020|0x0040)
        except: pass

    def center_window(self, w, h):
        ws = self.root.winfo_screenwidth()
        hs = self.root.winfo_screenheight()
        self.root.geometry(f'{w}x{h}+{int((ws-w)/2)}+{int((hs-h)/2)}')

    # --- UI 구성 ---
    def create_widgets(self):
        # 1. 타이틀바
        self.title_bar = tk.Frame(self.root, bg=self.colors["title_bar"], height=30)
        self.title_bar.pack(side="top", fill="x")
        self.title_bar.bind("<Button-1>", self.start_move)
        self.title_bar.bind("<B1-Motion>", self.do_move)

        self.lbl_main_title_bar = tk.Label(self.title_bar, text=self.T("title"), bg=self.colors["title_bar"], fg="#aaa", font=("Malgun Gothic", 9, "bold"))
        self.lbl_main_title_bar.pack(side="left", padx=10)
        
        btn_close = tk.Button(self.title_bar, text="✕", bg=self.colors["title_bar"], fg="white", bd=0, width=4, 
                              activebackground=self.colors["close_hover"], activeforeground="white", command=self.root.destroy)
        btn_close.pack(side="right", fill="y")
        btn_close.bind("<Enter>", lambda e: btn_close.config(bg=self.colors["close_hover"]))
        btn_close.bind("<Leave>", lambda e: btn_close.config(bg=self.colors["title_bar"]))

      # btn_min = tk.Button(self.title_bar, text="―", bg=self.colors["title_bar"], fg="white", bd=0, width=4, 
                         #  activebackground="#3a3a3a", activeforeground="white", command=self.minimize_window)
        #btn_min.pack(side="right", fill="y")
        #btn_min.bind("<Enter>", lambda e: btn_min.config(bg="#3a3a3a"))
        #btn_min.bind("<Leave>", lambda e: btn_min.config(bg=self.colors["title_bar"]))

       
        body_frame = tk.Frame(self.root, bg=self.colors["bg"])
        body_frame.pack(side="top", fill="both", expand=True)

        
        self.sidebar = tk.Frame(body_frame, bg=self.colors["sidebar"], width=220)
        self.sidebar.pack(side="left", fill="y")
        self.sidebar.pack_propagate(False)

        self.lbl_sidebar_title = tk.Label(self.sidebar, text=self.T("apps_list"), bg=self.colors["sidebar"], fg="#555", font=("Arial", 8, "bold"))
        self.lbl_sidebar_title.pack(anchor="w", padx=20, pady=(20, 10))

       
        for app in self.app_list:
            btn_f = tk.Frame(self.sidebar, bg=self.colors["sidebar"], cursor="hand2", height=50)
            btn_f.pack(fill="x", pady=2)
            btn_f.pack_propagate(False)
            
            for w in [btn_f]:
                w.bind("<Button-1>", lambda e, name=app["name"]: self.select_app(name))
            
            icon_l = tk.Label(btn_f, text=app["icon"], bg=self.colors["sidebar"], fg=self.colors["sub_fg"], font=("Segoe UI Emoji", 14))
            icon_l.pack(side="left", padx=(20, 10))
            
            name_l = tk.Label(btn_f, text=app["name"], bg=self.colors["sidebar"], fg=self.colors["sub_fg"], font=self.list_font)
            name_l.pack(side="left")
            
            icon_l.bind("<Button-1>", lambda e, name=app["name"]: self.select_app(name))
            name_l.bind("<Button-1>", lambda e, name=app["name"]: self.select_app(name))

            self.sidebar_widgets[app["name"]] = {"frame": btn_f, "icon": icon_l, "text": name_l}

        
        self.content = tk.Frame(body_frame, bg=self.colors["bg"])
        self.content.pack(side="right", fill="both", expand=True)
        
        self.center_info = tk.Frame(self.content, bg=self.colors["bg"])
        self.center_info.place(relx=0.5, rely=0.45, anchor="center", relwidth=0.9)

        self.lbl_main_icon = tk.Label(self.center_info, text="", font=("Segoe UI Emoji", 60), bg=self.colors["bg"], fg=self.colors["fg"])
        self.lbl_main_icon.pack(pady=(0, 10))

        self.lbl_main_title = tk.Label(self.center_info, text="", font=self.title_font, bg=self.colors["bg"], fg=self.colors["fg"])
        self.lbl_main_title.pack(pady=5)

        self.lbl_main_desc = tk.Label(self.center_info, text="", font=self.desc_font, bg=self.colors["bg"], fg=self.colors["sub_fg"], justify="center")
        self.lbl_main_desc.pack(pady=10)

        self.btn_main_launch = tk.Button(self.center_info, text=self.T("run"), font=self.btn_font, 
                                         bg=self.colors["btn_bg"], fg="white", relief="flat", cursor="hand2", width=18, height=2,
                                         command=self.run_current_app)
        self.btn_main_launch.pack(pady=30)

      
        bottom_frame = tk.Frame(self.root, bg=self.colors["sidebar"], height=45)
        bottom_frame.pack(side="bottom", fill="x")
        bottom_frame.pack_propagate(False)

        self.status_label = tk.Label(bottom_frame, text=self.T("ready"), font=self.status_font, bg=self.colors["sidebar"], fg=self.colors["sub_fg"])
        self.status_label.pack(side="left", padx=20)
        
        tk.Label(bottom_frame, text="|", bg=self.colors["sidebar"], fg="#444").pack(side="left")
        
        self.version_label = tk.Label(bottom_frame, text=self.T("ver_check"), font=("Malgun Gothic", 8), bg=self.colors["sidebar"], fg=self.colors["sub_fg"])
        self.version_label.pack(side="left", padx=10)

        self.btn_settings = tk.Button(bottom_frame, text=self.T("settings"), font=("Malgun Gothic", 9), bg=self.colors["sidebar"], fg="white", 
                                      relief="flat", cursor="hand2", command=self.open_settings_window)
        self.btn_settings.pack(side="right", padx=15, pady=8)

        self.btn_update = tk.Button(bottom_frame, text=self.T("update_check"), font=("Malgun Gothic", 9, "bold"), 
                                    bg=self.colors["accent"], fg="white", relief="flat", cursor="hand2",
                                    command=self.start_check_version_thread)
        self.btn_update.pack(side="right", padx=5, pady=8)

 
    def select_app(self, app_name):
        self.current_app = next((a for a in self.app_list if a["name"] == app_name), None)
        if not self.current_app: return

        for name, w in self.sidebar_widgets.items():
            is_sel = (name == app_name)
            col = self.colors["item_select"] if is_sel else self.colors["sidebar"]
            fg_col = "white" if is_sel else self.colors["sub_fg"]
            w["frame"].config(bg=col)
            w["icon"].config(bg=col, fg=fg_col)
            w["text"].config(bg=col, fg=fg_col)

        self.lbl_main_icon.config(text=self.current_app["icon"])
        self.lbl_main_title.config(text=self.current_app["name"])
        self.lbl_main_desc.config(text=self.T(self.current_app["desc_key"]))
        
        self.check_run_button_state()

    def check_run_button_state(self):
        if not self.current_app: return
        path = os.path.join(self.game_folder, self.current_app["exe"])
        if os.path.exists(path):
            self.btn_main_launch.config(state="normal", bg=self.colors["btn_bg"], text=self.T("run"))
        else:
            self.btn_main_launch.config(state="disabled", bg="#4f545c", text=self.T("install_needed"))

    def run_current_app(self):
        if self.current_app: self.run_program(self.current_app["exe"])

    
    def start_move(self, e): self.x, self.y = e.x, e.y
    def do_move(self, e): self.root.geometry(f"+{self.root.winfo_x()+e.x-self.x}+{self.root.winfo_y()+e.y-self.y}")
    def minimize_window(self):
        self.is_minimized = True; self.root.overrideredirect(False); self.root.iconify()
    def on_map(self, e):
        if (self.is_first_map or self.is_minimized) and self.root.state() == 'normal':
            self.is_first_map = False; self.is_minimized = False; self.root.overrideredirect(True); self.set_appwindow()

    def open_settings_window(self):
        sw = tk.Toplevel(self.root); sw.overrideredirect(True); sw.attributes('-topmost', True); sw.configure(bg=self.colors["bg"])
        w,h=400,500
        sw.geometry(f'{w}x{h}+{self.root.winfo_x()+(self.width-w)//2}+{self.root.winfo_y()+(self.height-h)//2}')
        f = tk.Frame(sw, bg=self.colors["bg"], highlightbackground="#555", highlightthickness=1); f.pack(fill="both", expand=True)
        tb = tk.Frame(f, bg=self.colors["title_bar"], height=30); tb.pack(fill="x", side="top")
        def mm(e): sw.geometry(f"+{e.x_root-sw.x}+{e.y_root-sw.y}")
        def ss(e): sw.x, sw.y = e.x, e.y
        tb.bind("<Button-1>", ss); tb.bind("<B1-Motion>", mm)
        tk.Label(tb, text=self.T("settings"), bg=self.colors["title_bar"], fg="white", font=("bold", 9)).pack(side="left", padx=10)
        tk.Button(tb, text="✕", bg=self.colors["title_bar"], fg="white", bd=0, command=sw.destroy, activebackground="red").pack(side="right", padx=5)
        
        c = tk.Frame(f, bg=self.colors["bg"]); c.pack(expand=True, fill="both", padx=20, pady=20)
        def mkbtn(t, cmd): tk.Button(c, text=t, bg=self.colors["sidebar"], fg="white", relief="flat", width=30, command=cmd).pack(pady=3)
        
        tk.Label(c, text=self.T("manage"), bg=self.colors["bg"], fg="#aaa").pack(anchor="w"); mkbtn(self.T("repair"), lambda: self.confirm_repair(sw)); mkbtn(self.T("open_folder"), self.open_file_location)
        
        
        mkbtn(self.T("lang_sel"), self.open_language_selector)

        tk.Label(c, text=self.T("info"), bg=self.colors["bg"], fg="#aaa").pack(anchor="w", pady=(15,0))
        mkbtn(self.T("license"), self.open_license_window); mkbtn(self.T("helper_info"), self.open_helper_info_window); mkbtn(self.T("ep_info"), self.open_ep_info_window)
        l = tk.Label(c, text=self.T("made_by").format(GITHUB_USER), bg=self.colors["bg"], fg="#888", cursor="hand2"); l.pack(pady=(15,0))
        l.bind("<Button-1>", lambda e: webbrowser.open_new(f"https://github.com/{GITHUB_USER}"))
        tk.Label(c, text=self.T("gemini"), bg=self.colors["bg"], fg="#666", font=("Arial", 7)).pack()

    def confirm_repair(self, p): p.destroy(); self.start_update_thread()
    def open_file_location(self): 
        if os.path.exists(self.game_folder): os.startfile(self.game_folder)
        else: self.show_custom_popup(self.T("info"), self.T("no_folder"), False)
    
   
    def open_language_selector(self):
        lw = tk.Toplevel(self.root); lw.overrideredirect(True); lw.attributes('-topmost', True); lw.configure(bg=self.colors["bg"])
        w,h=300,300; lw.geometry(f'{w}x{h}+{self.root.winfo_x()+(self.width-w)//2}+{self.root.winfo_y()+(self.height-h)//2}')
        f = tk.Frame(lw, bg=self.colors["bg"], highlightbackground="#555", highlightthickness=1); f.pack(fill="both", expand=True)
        
       
        tb = tk.Frame(f, bg=self.colors["title_bar"], height=30); tb.pack(fill="x", side="top")
        def mm(e): lw.geometry(f"+{e.x_root-lw.x}+{e.y_root-lw.y}")
        def ss(e): lw.x, lw.y = e.x, e.y
        tb.bind("<Button-1>", ss); tb.bind("<B1-Motion>", mm)
        tk.Label(tb, text=self.T("lang_sel"), bg=self.colors["title_bar"], fg="white").pack(side="left", padx=10)
        tk.Button(tb, text="✕", bg=self.colors["title_bar"], fg="white", bd=0, command=lw.destroy, activebackground="red").pack(side="right", padx=5)

        c = tk.Frame(f, bg=self.colors["bg"]); c.pack(expand=True, fill="both", padx=20, pady=20)
        
        def set_lang(lang_code, name):
            self.selected_language = lang_code
            self.refresh_ui_text() 
            self.show_custom_popup(self.T("info"), self.T("lang_changed").format(name), False)
            lw.destroy()

        def mk_lang_btn(name, code):
            tk.Button(c, text=name, bg=self.colors["sidebar"], fg="white", relief="flat", width=25, 
                      command=lambda: set_lang(code, name)).pack(pady=5)

        mk_lang_btn("한국어 (Korean)", "ko")
        mk_lang_btn("English", "en")
        mk_lang_btn("日本語 (Japanese)", "jp")
        mk_lang_btn("简体中文 (Simplified Chinese)", "cn")

    def _text_win(self, t, i):
        lw = tk.Toplevel(self.root); lw.overrideredirect(True); lw.attributes('-topmost', True); lw.configure(bg=self.colors["bg"])
        w,h=400,400; lw.geometry(f'{w}x{h}+{self.root.winfo_x()+(self.width-w)//2}+{self.root.winfo_y()+(self.height-h)//2}')
        f = tk.Frame(lw, bg=self.colors["bg"], highlightbackground="#555", highlightthickness=1); f.pack(fill="both", expand=True)
        tb = tk.Frame(f, bg=self.colors["title_bar"], height=30); tb.pack(fill="x", side="top")
        def mm(e): lw.geometry(f"+{e.x_root-lw.x}+{e.y_root-lw.y}")
        def ss(e): lw.x, lw.y = e.x, e.y
        tb.bind("<Button-1>", ss); tb.bind("<B1-Motion>", mm)
        tk.Label(tb, text=t, bg=self.colors["title_bar"], fg="white").pack(side="left", padx=10)
        tk.Button(tb, text="✕", bg=self.colors["title_bar"], fg="white", bd=0, command=lw.destroy, activebackground="red").pack(side="right", padx=5)
        tx = tk.Text(f, bg="#1e1e1e", fg="#ccc", relief="flat", padx=10, pady=10); tx.pack(fill="both", expand=True, padx=10, pady=10); tx.insert("1.0", i); tx.config(state="disabled")

    def open_license_window(self):
        info = """[AYA AIO Open Source License]
        
1. Python (PSF License)\nCopyright (c) Python Software Foundation.\nLicense: PSF License\n\n
2. Tkinter (Tcl/Tk License)\nCopyright (c) Regents of the University of California, Sun Microsystems, Inc., Scriptics Corporation, and other parties.\nLicense: Tcl/Tk License\n\n
3. Requests (Apache 2.0)\nCopyright (c) Kenneth Reitz.\nLicense: Apache 2.0\n\n

Thanks to all open source libraries used, even if not mentioned here.

"""
        self._text_win(self.T("license"), info)

    def open_helper_info_window(self): self._text_win(self.T("helper_info"), "Server Launcher\n\n 누구나 마인크래프트 자바 에디션 서버를 쉽고 빠르게 구축하고 관리할 수 있도록 돕는 도구입니다.\n\nPaperMC API(또는 사용자 지정 API)를 통해 최신 서버 코어 파일을 자동으로 가져오며, Python과 HTML/CSS로 제작된 직관적인 웹 GUI를 제공합니다.\n\n 이 프로젝트는 현재 지속적으로 개발 중입니다. 사용 중 버그가 발생하거나 제안 사항이 있다면 언제든지\n[GitHub Issues]탭에 남겨주세요.\n\n자세한 정보는 https://github.com/GNBD/를 방문 하십시오.")
    def open_ep_info_window(self): self._text_win(self.T("ep_info"), "EasyPort\n\n마크서버 초보운영자들을 위한 초간단 UPnP 포트 포워딩 도구입니다.\n복잡한 공유기 설정 없이 버튼 하나로 25565 포트를 개방할 수 있습니다.\n\n자세한 정보는 https://github.com/GNBD/NeneEP를 방문 하십시오.")

    def get_local_version(self):
        try:
            p = os.path.join(self.game_folder, self.version_file)
            if os.path.exists(p):
                with open(p, "r", encoding="utf-8") as f:
                    return f.read().strip()
        except: pass
        return None

    def display_local_version_only(self): v = self.get_local_version(); self.version_label.config(text=self.T("ver_current").format(v if v else self.T("ver_none")))
    def start_check_version_thread(self): self.btn_update.config(state="disabled", text=self.T("checking")); threading.Thread(target=self._check_v, daemon=True).start()
    def _check_v(self):
        try:
            l = self.get_local_version()
            r = requests.get(f"https://api.github.com/repos/{GITHUB_USER}/{REPO_NAME}/releases/latest", timeout=3)
            if r.status_code==200:
                s = r.json().get("tag_name", "Unknown")
                self.root.after(0, lambda: self._res(l, s))
            else: self.root.after(0, lambda: self.show_custom_popup(self.T("error"), self.T("server_fail"), False))
        except Exception as e: self.root.after(0, lambda: self.show_custom_popup(self.T("error"), str(e), False))
        finally: self.root.after(0, lambda: self.btn_update.config(state="normal", text=self.T("update_check")))
    def _res(self, l, s):
        if l==s: self.show_custom_popup(self.T("info"), self.T("latest_msg"), False)
        else: self.show_update_confirm_popup(l, s)
    def show_update_confirm_popup(self, l, s):
        p = tk.Toplevel(self.root); p.overrideredirect(True); p.attributes('-topmost', True); p.configure(bg=self.colors["bg"])
        w,h=320,180; p.geometry(f'{w}x{h}+{self.root.winfo_x()+(self.width-w)//2}+{self.root.winfo_y()+(self.height-h)//2}')
        f = tk.Frame(p, bg=self.colors["bg"], highlightbackground="#555", highlightthickness=1); f.pack(fill="both", expand=True)
        tk.Label(f, text=self.T("update_avail"), bg=self.colors["bg"], fg="white", font=("bold", 10)).pack(pady=(15,5))
        tk.Label(f, text=self.T("new_ver_msg").format(l if l else self.T("ver_none"), s), bg=self.colors["bg"], fg="#ccc").pack(expand=True)
        b = tk.Frame(f, bg=self.colors["bg"]); b.pack(pady=15)
        tk.Button(b, text=self.T("later"), bg=self.colors["sidebar"], fg="white", relief="flat", command=p.destroy).pack(side="left", padx=5)
        tk.Button(b, text=self.T("update"), bg=self.colors["accent"], fg="white", relief="flat", command=lambda:[p.destroy(), self.start_update_thread()]).pack(side="left", padx=5)
        p.lift(); p.focus_force(); p.grab_set()
    def check_installation(self): self.check_run_button_state()
    def run_program(self, exe): threading.Thread(target=self._run, args=(exe,), daemon=True).start()
    def _run(self, exe):
        p = os.path.join(self.game_folder, exe)
        if os.path.exists(p):
            self.root.after(0, lambda: self.status_label.config(text=self.T("running").format(exe)))
            try: subprocess.Popen([p], cwd=self.game_folder)
            except Exception as e: self.root.after(0, lambda: self.show_custom_popup(self.T("error"), str(e), False))
        else: self.root.after(0, lambda: self.show_custom_popup(self.T("error"), self.T("file_missing"), False))
    def start_update_thread(self): self.btn_update.config(state="disabled", text="...", bg=self.colors["btn_disabled"]); threading.Thread(target=self.update_process, daemon=True).start()
    
    
    def update_process(self):
        try:
            self.update_status(self.T("checking"))
            r = requests.get(f"https://api.github.com/repos/{GITHUB_USER}/{REPO_NAME}/releases/latest", timeout=5)
            d = r.json(); t = d.get("tag_name"); u = next((a["browser_download_url"] for a in d.get("assets", []) if a["name"].endswith(".zip")), None)
            if not u: raise Exception(self.T("file_missing"))
            
           
            tmp = os.path.join(self.current_dir, "temp")
            os.makedirs(tmp, exist_ok=True)
            zp = os.path.join(tmp, "u.zip")
            
            
            self.update_status(self.T("downloading"))
            with requests.get(u, stream=True) as rq:
                with open(zp, 'wb') as f:
                    for c in rq.iter_content(8192): f.write(c)
            
            self.update_status(self.T("installing"))
            os.makedirs(self.game_folder, exist_ok=True)
            
            
            extract_path = os.path.join(tmp, "extracted")
            os.makedirs(extract_path, exist_ok=True)
            
            with zipfile.ZipFile(zp, 'r') as z: 
                z.extractall(extract_path)
            
            
            items = os.listdir(extract_path)
            if len(items) == 1 and os.path.isdir(os.path.join(extract_path, items[0])):
                
                root_item = os.path.join(extract_path, items[0])
                for sub_item in os.listdir(root_item):
                    src = os.path.join(root_item, sub_item)
                    dst = os.path.join(self.game_folder, sub_item)
                    
                    
                    if os.path.exists(dst):
                        if os.path.isdir(dst): shutil.rmtree(dst)
                        else: os.remove(dst)
                    shutil.move(src, dst)
            else:
                
                for item in items:
                    src = os.path.join(extract_path, item)
                    dst = os.path.join(self.game_folder, item)
                    
                    if os.path.exists(dst):
                        if os.path.isdir(dst): shutil.rmtree(dst)
                        else: os.remove(dst)
                    shutil.move(src, dst)

            
            with open(os.path.join(self.game_folder, self.version_file), "w", encoding="utf-8") as f: f.write(t)
            
            
            try: shutil.rmtree(tmp)
            except: pass
            
            self.update_status(self.T("done")); self.root.after(0, lambda: self.show_custom_popup(self.T("info"), self.T("success_msg"), False)); self.root.after(0, self.display_local_version_only)
        except Exception as e: self.update_status(self.T("fail_msg")); self.root.after(0, lambda: self.show_custom_popup(self.T("error"), str(e), False))
        finally: self.root.after(0, lambda: [self.check_installation(), self.btn_update.config(state="normal", text=self.T("update_check"), bg=self.colors["accent"])])

    def update_status(self, m): self.root.after(0, lambda: self.status_label.config(text=m))
    def show_custom_popup(self, t, m, b=True):
        p = tk.Toplevel(self.root); p.overrideredirect(True); p.attributes('-topmost', True); p.configure(bg=self.colors["bg"])
        w,h=300,150; p.geometry(f'{w}x{h}+{self.root.winfo_x()+(self.width-w)//2}+{self.root.winfo_y()+(self.height-h)//2}')
        f = tk.Frame(p, bg=self.colors["bg"], highlightbackground="#555", highlightthickness=1); f.pack(fill="both", expand=True)
        tk.Label(f, text=t, bg=self.colors["bg"], fg="white", font=("bold", 10)).pack(pady=(15,5))
        tk.Label(f, text=m, bg=self.colors["bg"], fg="#ccc", wraplength=250).pack(expand=True)
        tk.Button(f, text="OK", bg=self.colors["btn_bg"], fg="white", relief="flat", command=p.destroy).pack(pady=15)
        p.lift(); p.focus_force()
        if b: p.grab_set(); self.root.wait_window(p)

if __name__ == "__main__":
    root = tk.Tk()
    app = NeneLauncherApp(root)
    root.mainloop()