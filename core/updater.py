import os
import sys
import json
import time
import subprocess
import threading
import requests
import eel

from . import state

GITHUB_REPO = "GNBD/AYA-Server-Launcher"
GITHUB_API = f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest"
USER_AGENT = f"AYA-Server-Launcher/{state.AYA_VERSION}"

# 다운로드 진행 상태
_download_progress = {"active": False, "percent": 0, "status": "", "error": ""}


def _get_exe_dir():
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _get_update_dir():
    d = os.path.join(_get_exe_dir(), "AYA_data", "update")
    os.makedirs(d, exist_ok=True)
    return d


def _compare_versions(current, latest):
    """current < latest 이면 True"""
    def parse(v):
        return [int(x) for x in v.strip("v").split(".")]
    try:
        c = parse(current)
        l = parse(latest)
        return l > c
    except Exception:
        return False


@eel.expose
def check_update_py(token):
    """GitHub에서 최신 릴리즈 확인. 새 버전 있으면 정보 반환."""
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
    """새 버전을 AYA_data/update/에 다운로드. 진행 상태는 get_update_progress_py로 폴링."""
    if _download_progress["active"]:
        return {"success": False, "error": "이미 다운로드 중입니다"}

    _download_progress.update({"active": True, "percent": 0, "status": "다운로드 준비 중...", "error": ""})

    def _do():
        try:
            update_dir = _get_update_dir()
            dest = os.path.join(update_dir, "Server Launcher.exe")
            headers = {"User-Agent": USER_AGENT}
            r = requests.get(asset_url, headers=headers, stream=True, timeout=30)
            r.raise_for_status()
            total = int(r.headers.get("content-length", 0))
            downloaded = 0
            with open(dest, "wb") as f:
                for chunk in r.iter_content(chunk_size=1024 * 256):
                    if chunk:
                        f.write(chunk)
                        downloaded += len(chunk)
                        if total > 0:
                            _download_progress["percent"] = int(downloaded * 100 / total)
                            _download_progress["status"] = f"다운로드 중... {_download_progress['percent']}%"
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
    """최신 버전 실행 (--update 플래그). 현재 프로세스는 종료."""
    update_exe = os.path.join(_get_update_dir(), "Server Launcher.exe")
    if not os.path.exists(update_exe):
        return {"success": False, "error": "업데이트 파일 없음"}
    original_exe = sys.executable if getattr(sys, "frozen", False) else ""
    if not original_exe:
        return {"success": False, "error": "실행 파일 경로를 알 수 없습니다"}
    try:
        subprocess.Popen([update_exe, "--update", original_exe])
        time.sleep(0.5)
        os._exit(0)
    except Exception as e:
        return {"success": False, "error": str(e)}


def handle_update_mode():
    """--update 플래그로 실행된 경우: 기존 프로세스 종료 → 자기 복사 → 재시작. True 반환."""
    if "--update" not in sys.argv:
        return False
    idx = sys.argv.index("--update")
    original_path = sys.argv[idx + 1] if idx + 1 < len(sys.argv) else ""
    if not original_path:
        return False

    import splash_window
    splash_window.show_splash(version=state.AYA_VERSION)
    splash_window.set_status("업데이트 진행중...")

    time.sleep(1.0)

    # 기존 프로세스 종료
    current_exe = os.path.abspath(sys.executable) if getattr(sys, "frozen", False) else None
    if current_exe and os.path.normcase(os.path.normpath(original_path)) != os.path.normcase(os.path.normpath(current_exe)):
        _kill_process_by_path(original_path)
        time.sleep(1.0)

    # 자기 자신을 원래 경로로 복사
    src = sys.executable if getattr(sys, "frozen", False) else __file__
    try:
        _copy_file(src, original_path)
    except Exception as e:
        splash_window.set_status(f"복사 실패: {e}")
        time.sleep(3)
        splash_window.close_splash()
        return True

    splash_window.close_splash()

    # 새 버전 실행
    subprocess.Popen([original_path])
    os._exit(0)
    return True


def _kill_process_by_path(exe_path):
    """경로로 실행 중인 프로세스를 찾 종료."""
    try:
        norm = os.path.normcase(os.path.normpath(exe_path))
        for proc in os.scandir("/proc") if sys.platform == "linux" else _win32_kill_by_name(os.path.basename(exe_path)):
            pass
    except Exception:
        pass


def _win32_kill_by_name(name):
    """Windows에서 프로세스 이름으로 종료."""
    try:
        result = subprocess.run(
            ["taskkill", "/f", "/im", name],
            capture_output=True, timeout=5
        )
    except Exception:
        pass


def _copy_file(src, dst):
    """Windows에서 파일 복사 (기존 파일 덮어쓰기)."""
    dst_dir = os.path.dirname(dst)
    os.makedirs(dst_dir, exist_ok=True)
    # Windows: 덮어쓰기 전 잠시 대기
    for attempt in range(3):
        try:
            if os.path.exists(dst):
                # 기존 파일 삭제 시도
                try:
                    os.remove(dst)
                except PermissionError:
                    subprocess.run(["cmd", "/c", "del", "/f", "/q", f'"{dst}"'], capture_output=True, timeout=5)
                    time.sleep(0.5)
            # 복사
            subprocess.run(["cmd", "/c", 'copy /y', f'"{src}"', f'"{dst}"'], capture_output=True, timeout=30)
            if os.path.exists(dst):
                return
        except Exception:
            time.sleep(1)
    raise Exception("파일 복사 실패 (3회 시도)")
