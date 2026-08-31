import os
import sys
import json
import time
import webbrowser
import threading
import subprocess
import psutil
import eel
from . import state, security, backup

try:
    from PIL import Image, ImageDraw
    import pystray
except Exception:
    Image = None
    pystray = None

def _res(name):
    if getattr(sys, "frozen", False):
        return os.path.join(getattr(sys, "_MEIPASS", ""), name)
    return os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), name)

def create_image():
    width = 64
    height = 64
    image = Image.new('RGB', (width, height), (60, 166, 255))
    dc = ImageDraw.Draw(image)
    dc.rectangle((16, 16, 48, 48), fill=(255, 255, 255))
    return image

def quit_app(icon, item):
    icon.stop()
    for name, p in list(state.active_processes.items()):
        if p.poll() is None:
            try:
                p.stdin.write("stop\n")
                p.stdin.flush()
            except:
                pass
    for p in list(state.active_processes.values()):
        if p.poll() is None:
            try:
                p.wait(timeout=5)
            except:
                try: p.terminate()
                except: pass
    os._exit(0)

def open_browser(icon, item):
    webbrowser.open(f'http://localhost:8000/index.html?token={state.LOCAL_TOKEN}')

def setup_tray():
    if pystray is None or Image is None:
        return
    image = create_image()
    p = _res("server.ico")
    if os.path.exists(p):
        try:
            image = Image.open(p)
        except Exception:
            pass

    menu = (
        pystray.MenuItem('Open Dashboard', open_browser, default=True),
        pystray.MenuItem('Quit', quit_app)
    )
    icon = pystray.Icon("server_launcher", image, "AYA Server Launcher", menu)
    icon.run()

def system_monitor_thread():
    while True:
        try:
            cpu = psutil.cpu_percent(interval=1)
            eel.update_cpu_usage_js(cpu)
            cur = time.time()
            for name in list(state.active_processes.keys()):
                if state.active_processes[name].poll() is None:
                    try:
                        cp = os.path.join(state.BASE_SERVERS_DIR, name, "nene_config.json")
                        if os.path.exists(cp):
                            with open(cp, 'r', encoding='utf-8') as f:
                                conf = json.load(f)
                                if conf.get("auto_backup", False):
                                    iv = int(conf.get("backup_interval", 60)) * 60
                                    lst = state.last_backup_times.get(name, 0)
                                    if lst == 0: state.last_backup_times[name] = cur
                                    elif (cur - lst) >= iv: backup.backup_server(name)
                    except: pass
        except: pass

def close_callback(route, websockets):
    pass


