import os
import time
import zipfile
import shutil
import tempfile
import threading
import datetime
import eel
from . import state, security

@eel.expose
def trigger_backup_py(token, server_name):
    if not security.is_auth_verified(token):
        security.add_access_log("Backup Run", "blocked", "Unauthorized")
        return "❌ Unauthorized"
    t = threading.Thread(target=backup_server, args=(server_name,))
    t.start()
    security.add_access_log("Backup Run", "success", f"Server '{server_name}' backup started")
    return "Backup started"

def backup_server(server_name):
    try:
        server_dir = os.path.join(state.BASE_SERVERS_DIR, server_name)
        backup_root = os.path.join(state.BACKUP_ROOT_DIR, server_name)
        if not os.path.exists(backup_root):
            os.makedirs(backup_root)

        ts = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        zip_name = f"backup_{ts}.zip"
        zip_path = os.path.join(backup_root, zip_name)

        if state.current_view_server == server_name: eel.add_log_js(f"[SYSTEM] 백업 시작: {zip_name}")()

        with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as z:
            for r, d, f in os.walk(server_dir):
                if "backups" in d: d.remove("backups")
                for file in f:
                    fp = os.path.join(r, file)
                    try: z.write(fp, os.path.relpath(fp, server_dir))
                    except: pass

        state.last_backup_times[server_name] = time.time()
        if state.current_view_server == server_name: eel.add_log_js("[SYSTEM] 백업 완료")()
    except Exception as e:
        if state.current_view_server == server_name: eel.add_log_js(f"[ERROR] 백업 실패: {e}")()

@eel.expose
def list_backups_py(token, server_name):
    if not security.is_auth_verified(token):
        security.add_access_log("Backup List", "blocked", "Unauthorized")
        return []
    backup_dir = os.path.join(state.BACKUP_ROOT_DIR, server_name)
    if not os.path.exists(backup_dir):
        return []
    backups = []
    for f in sorted(os.listdir(backup_dir), reverse=True):
        if f.endswith(".zip"):
            fp = os.path.join(backup_dir, f)
            size_mb = os.path.getsize(fp) / (1024 * 1024)
            backups.append({
                "filename": f,
                "date": f.replace("backup_", "").replace(".zip", "").replace("_", " "),
                "size_mb": round(size_mb, 2)
            })
    security.add_access_log("Backup List", "success", f"Server '{server_name}' {len(backups)} backups found")
    return backups

@eel.expose
def restore_backup_py(token, server_name, filename):
    if not security.is_auth_verified(token):
        security.add_access_log("Backup Restore", "blocked", "Unauthorized")
        return "❌ Unauthorized"
    t = threading.Thread(target=restore_server, args=(server_name, filename))
    t.start()
    security.add_access_log("Backup Restore", "start", f"Server '{server_name}' → {filename}")
    return "Restore started"

def restore_server(server_name, filename):
    try:
        server_dir = os.path.join(state.BASE_SERVERS_DIR, server_name)
        backup_path = os.path.join(state.BACKUP_ROOT_DIR, server_name, filename)

        if not os.path.exists(backup_path):
            if state.current_view_server == server_name: eel.add_log_js(f"[ERROR] 백업 파일 없음: {filename}")()
            return

        # 1. Extract to a temp dir first to count files
        tmpdir = tempfile.mktemp()
        total_files = 0
        with zipfile.ZipFile(backup_path, 'r') as z:
            total_files = len(z.namelist())

        if total_files == 0:
            if state.current_view_server == server_name: eel.add_log_js("[ERROR] 백업 파일이 비어있음")()
            shutil.rmtree(tmpdir, ignore_errors=True)
            return

        # 2. Delete existing server files
        if os.path.exists(server_dir):
            if state.current_view_server == server_name: eel.add_log_js("[SYSTEM] 기존 서버 파일 삭제 중...")()
            eel.update_restore_progress_js(0, "Deleting old files...")()
            for item in os.listdir(server_dir):
                item_path = os.path.join(server_dir, item)
                try:
                    if os.path.isfile(item_path) or os.path.islink(item_path):
                        os.unlink(item_path)
                    elif os.path.isdir(item_path):
                        shutil.rmtree(item_path)
                except Exception as e:
                    if state.current_view_server == server_name: eel.add_log_js(f"[WARN] 삭제 실패 {item}: {e}")()

        # 3. Extract backup with progress
        extracted = 0
        with zipfile.ZipFile(backup_path, 'r') as z:
            for entry in z.namelist():
                dest_path = os.path.join(server_dir, entry)
                dest_dir = os.path.dirname(dest_path)
                if not os.path.exists(dest_dir):
                    os.makedirs(dest_dir)
                try:
                    z.extract(entry, server_dir)
                except Exception as e:
                    if state.current_view_server == server_name: eel.add_log_js(f"[WARN] 복원 실패 {entry}: {e}")()
                extracted += 1
                percent = int((extracted / total_files) * 100)
                filename_only = os.path.basename(entry) if entry else entry
                eel.update_restore_progress_js(percent, filename_only)()

        shutil.rmtree(tmpdir, ignore_errors=True)

        if state.current_view_server == server_name:
            eel.add_log_js(f"[SYSTEM] 복원 완료: {filename} ({total_files}개 파일)")()
            eel.showToast("복원 완료!", "success")
    except Exception as e:
        if state.current_view_server == server_name:
            eel.add_log_js(f"[ERROR] 복원 실패: {e}")()
            eel.showToast(f"복원 실패: {e}", "error")
