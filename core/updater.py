import os
import sys
import time
import subprocess
import threading
import requests
import eel

from . import state

GITHUB_REPO = "GNBD/AYA-Server-Launcher"
GITHUB_API = f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest"
USER_AGENT = f"AYA-Server-Launcher/{state.AYA_VERSION}"

_download_progress = {"active": False, "percent": 0, "status": "", "error": ""}


def _get_exe_dir():
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _get_update_dir():
    d = os.path.join(_get_exe_dir(), "AYA_data", "update")
    os.makedirs(d, exist_ok=True)
    return d


def cleanup_update_dir():
    update_dir = _get_update_dir()
    if not os.path.isdir(update_dir):
        return
    for f in os.listdir(update_dir):
        fp = os.path.join(update_dir, f)
        try:
            if os.path.isfile(fp):
                os.remove(fp)
        except Exception:
            pass


def _compare_versions(current, latest):
    def parse(v):
        return [int(x) for x in v.strip("v").split(".")]
    try:
        return parse(latest) > parse(current)
    except Exception:
        return False


@eel.expose
def check_update_py(token):
    try:
        headers = {"User-Agent": USER_AGENT, "Accept": "application/vnd.github+json"}
        r = requests.get(GITHUB_API, headers=headers, timeout=10)
        r.raise_for_status()
        data = r.json()
        tag = data.get("tag_name", "")
        if not tag:
            return {"success": False, "error": "릴리즈 태그 없음"}
        has_update = _compare_versions(state.AYA_VERSION, tag)
        asset_url = ""
        asset_name = ""
        for asset in data.get("assets", []):
            if asset["name"].endswith(".zip"):
                asset_url = asset["browser_download_url"]
                asset_name = asset["name"]
                break
        return {
            "success": True,
            "has_update": has_update,
            "current_version": state.AYA_VERSION,
            "latest_version": tag,
            "release_name": data.get("name", tag),
            "release_notes": data.get("body", ""),
            "asset_url": asset_url,
            "asset_name": asset_name,
            "asset_size": next((a["size"] for a in data.get("assets", []) if a["name"] == asset_name), 0),
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


@eel.expose
def download_update_py(token, asset_url, asset_name):
    if _download_progress["active"]:
        return {"success": False, "error": "이미 다운로드 중입니다"}
    _download_progress.update({"active": True, "percent": 0, "status": "다운로드 준비 중...", "error": ""})

    def _do():
        import zipfile
        import tempfile
        try:
            update_dir = _get_update_dir()
            headers = {"User-Agent": USER_AGENT}
            r = requests.get(asset_url, headers=headers, stream=True, timeout=30)
            r.raise_for_status()
            total = int(r.headers.get("content-length", 0))
            downloaded = 0
            tmp_zip = os.path.join(tempfile.gettempdir(), "aya_update.zip")
            with open(tmp_zip, "wb") as f:
                for chunk in r.iter_content(chunk_size=1024 * 256):
                    if chunk:
                        f.write(chunk)
                        downloaded += len(chunk)
                        if total > 0:
                            _download_progress["percent"] = int(downloaded * 100 / total)
                            _download_progress["status"] = f"다운로드 중... {_download_progress['percent']}%"
            _download_progress["status"] = "압축 해제 중..."
            with zipfile.ZipFile(tmp_zip, "r") as zf:
                exe_names = [n for n in zf.namelist() if n.endswith(".exe")]
                if not exe_names:
                    raise Exception("ZIP에 .exe 파일이 없습니다")
                dest = os.path.join(update_dir, "Server Launcher.exe")
                with zf.open(exe_names[0]) as src, open(dest, "wb") as dst:
                    while True:
                        buf = src.read(1024 * 256)
                        if not buf:
                            break
                        dst.write(buf)
            try:
                os.remove(tmp_zip)
            except Exception:
                pass
            _download_progress["percent"] = 100
            _download_progress["status"] = "다운로드 완료"
        except Exception as e:
            _download_progress["error"] = str(e)
            _download_progress["status"] = "다운로드 실패"
        finally:
            _download_progress["active"] = False

    t = threading.Thread(target=_do, daemon=True)
    t.start()
    return {"success": True}


@eel.expose
def get_update_progress_py(token):
    return dict(_download_progress)


@eel.expose
def apply_update_py(token):
    """AYA_data/update/ exe를 --update + --old-pid로 실행. 기존은 즉시 종료 안 함."""
    update_exe = os.path.join(_get_update_dir(), "Server Launcher.exe")
    if not os.path.exists(update_exe):
        return {"success": False, "error": "업데이트 파일 없음"}
    original_exe = sys.executable if getattr(sys, "frozen", False) else ""
    if not original_exe:
        return {"success": False, "error": "실행 파일 경로를 알 수 없습니다"}
    try:
        my_pid = str(os.getpid())
        subprocess.Popen([update_exe, "--update", original_exe, "--old-pid", my_pid])
        return {"success": True}
    except Exception as e:
        return {"success": False, "error": str(e)}


def handle_update_mode():
    """--update: 스플래시 → 기존 PID kill → 메인에 복사 → 메인 실행 → 종료."""
    if "--update" not in sys.argv:
        return False
    idx = sys.argv.index("--update")
    original_path = sys.argv[idx + 1] if idx + 1 < len(sys.argv) else ""
    if not original_path:
        return False

    old_pid = None
    if "--old-pid" in sys.argv:
        pid_idx = sys.argv.index("--old-pid")
        if pid_idx + 1 < len(sys.argv):
            old_pid = sys.argv[pid_idx + 1]

    import splash_window
    splash_window.show_splash(version=state.AYA_VERSION)
    time.sleep(0.5)

    splash_window.set_status("기존 프로세스 종료 중...")
    if old_pid:
        try:
            subprocess.run(["taskkill", "/f", "/pid", old_pid], capture_output=True, timeout=5)
        except Exception:
            pass
    time.sleep(1.5)

    splash_window.set_status("파일 교체 중...")
    src = sys.executable if getattr(sys, "frozen", False) else __file__
    success = False
    for attempt in range(5):
        try:
            if os.path.exists(original_path):
                subprocess.run(["cmd", "/c", "del", "/f", "/q", f'"{original_path}"'], capture_output=True, timeout=5)
                time.sleep(0.5)
            subprocess.run(["cmd", "/c", "copy /y", f'"{src}"', f'"{original_path}"'], capture_output=True, timeout=30)
            if os.path.exists(original_path) and os.path.getsize(original_path) > 1000000:
                success = True
                break
        except Exception:
            pass
        time.sleep(1.0)

    if not success:
        splash_window.set_status("복사 실패!")
        time.sleep(2)
        splash_window.close_splash()
        return True

    splash_window.set_status("업데이트 완료! 재시작합니다...")
    time.sleep(0.5)
    splash_window.close_splash()

    subprocess.Popen([original_path])
    os._exit(0)
    return True
