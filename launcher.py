import socket
import sys
import os
import splash_window

from core.updater import check_update_exe, cleanup_update_dir
if check_update_exe():
    sys.exit(0)

def _is_already_running():
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        s.bind(('0.0.0.0', 8000))
        return False
    except OSError:
        return True
    finally:
        try:
            s.close()
        except Exception:
            pass

if _is_already_running():
    sys.exit(0)

from core import state
from core.updater import cleanup_update_dir
cleanup_update_dir()
splash_window.show_splash(version=state.AYA_VERSION)

import eel
import time
import webbrowser
import threading

import core.security
import core.common
import core.config
import core.java
import core.players
import core.backup
import core.plugins
import core.servers
import core.remote
import core.tray
import core.tunnel
import core.updater

eel.init('web')

# 브라우저가 완전히 로딩될 때까지 스플래시를 유지하기 위함
def _close_splash():
    splash_window.close_splash()

@eel.expose
def mark_web_ready():
    _close_splash()
    return {"success": True}

@eel.expose
def splash_status(text):
    splash_window.set_status(text)
    return {"success": True}

if __name__ == "__main__":

    # 시스템 모니터 (CPU / 자동 백업)
    t = threading.Thread(target=core.tray.system_monitor_thread)
    t.daemon = True
    t.start()

    # 트레이 아이콘
    t_tray = threading.Thread(target=core.tray.setup_tray)
    t_tray.daemon = True
    t_tray.start()

    # 런처 구동 시 원격 제어 설정 상태를 읽어 바인딩 주소 결정
    launcher_conf = core.config.get_launcher_config_py(state.LOCAL_TOKEN)
    is_remote_enabled = launcher_conf.get("remote_enabled", False)
    ui_mode = launcher_conf.get("ui_mode", "browser")

    # [치명적 취약점 패치]: 원격 설정 상태에 따라 소켓 바인딩 주소 대입
    host_ip = '0.0.0.0' if is_remote_enabled else '127.0.0.1'

    # 스플래시는 브라우저가 로딩을 마칠 때까지 유지 (initApp 완료 시 mark_web_ready 호출)
    # 안전망: 25초 지나도 안 닫히면 강제 종료
    import threading as _th
    _th.Timer(25, _close_splash).start()

    url = f'http://localhost:8000/index.html?token={state.LOCAL_TOKEN}'

    def deferred_open():
        time.sleep(0.5)
        webbrowser.open(url)

    # 브라우저 모드: 기존 동작 (별도 브라우저로 구동, 트레이 상주)
    if ui_mode == 'browser':
        t_open = threading.Thread(target=deferred_open)
        t_open.daemon = True
        t_open.start()
        try:
            eel.start('index.html', mode=False, port=8000, host=host_ip, block=True, close_callback=core.tray.close_callback)
        except Exception as e:
            print(f"Eel Server Error: {e}")
        sys.exit(0)

    # 웹뷰 / 둘 다 모드: pywebview 네이티브 창 사용
    webview = None
    try:
        import webview
    except Exception as e:
        print("pywebview import failed:", e)

    # pywebview 미사용 가능 시 브라우저 모드로 폴백
    if webview is None:
        t_open = threading.Thread(target=deferred_open)
        t_open.daemon = True
        t_open.start()
        try:
            eel.start('index.html', mode=False, port=8000, host=host_ip, block=True, close_callback=core.tray.close_callback)
        except Exception as e:
            print(f"Eel Server Error: {e}")
        sys.exit(0)

    # eel 웹소켓 서버를 별도 스레드에서 기동 (block=True 로 gevent 이벤트 루프 가동)
    # block=False 로는 gevent 그린릿만 spawn 되고 이벤트 루프가 돎지 않아 서버가 리스닝되지 않음
    def _run_eel():
        try:
            eel.start('index.html', mode=False, port=8000, host=host_ip, block=True, close_callback=core.tray.close_callback)
        except Exception as e:
            print(f"Eel Server Error: {e}")
    t_eel = threading.Thread(target=_run_eel, daemon=True)
    t_eel.start()

    # 서버가 실제로 리스닝할 때까지 대기 (최대 ~5초)
    _ready = False
    for _ in range(50):
        try:
            _s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            _s.settimeout(0.2)
            _s.connect(('127.0.0.1', 8000))
            _s.close()
            _ready = True
            break
        except Exception:
            time.sleep(0.1)
    if not _ready:
        print("eel server not ready, falling back to browser")
        threading.Thread(target=deferred_open).start()
        while True:
            time.sleep(1)

    try:
        webview.create_window(
            'AYA Server Launcher',
            url,
            width=1180, height=760, resizable=True,
            background_color='#0b0e13', text_select=False, on_top=False
        )
        webview.start()
    except Exception as e:
        print("webview failed:", e)
        # 웹뷰 생성 실패(WebView2 누락 등) 시 브라우저로 폴백
        threading.Thread(target=deferred_open).start()
        while True:
            time.sleep(1)
    # 웹뷰 창이 닫히면 프로세스 전체 종료 (eel 서버 스레드 포함)
    os._exit(0)
