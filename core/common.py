import os
import sys
import shutil
import tkinter as tk
from tkinter import filedialog
from . import state

# ==========================================================
# PyInstaller exe 번들 리소스 경로 해석
# ==========================================================
def resource_path(relative_path):
    try:
        base_path = sys._MEIPASS
    except AttributeError:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)

# ==========================================================
# AYA_data 베이스 폴더 생성
# ==========================================================
if not os.path.exists(state.AYA_BASE):
    os.makedirs(state.AYA_BASE)

# ==========================================================
# 레거시 마이그레이션: 기존 루트 폴더 -> AYA_data/ 로 이동
# ==========================================================
_legacy_migrations = [
    ("servers", state.BASE_SERVERS_DIR),
    ("backup", state.BACKUP_ROOT_DIR),
    ("config", state.CONFIG_DIR),
    ("languages", state.LANG_DIR),
]
for old_name, new_path in _legacy_migrations:
    if os.path.exists(old_name) and not os.path.exists(new_path):
        try:
            shutil.move(old_name, new_path)
        except:
            pass

# config 폴더 생성
if not os.path.exists(state.CONFIG_DIR):
    os.makedirs(state.CONFIG_DIR)
legacy_config = "launcher_config.json"
legacy_key = "launcher_remote.key"
if os.path.exists(legacy_config) and not os.path.exists(state.LAUNCHER_CONFIG_FILE):
    try: shutil.move(legacy_config, state.LAUNCHER_CONFIG_FILE)
    except: pass
if os.path.exists(legacy_key) and not os.path.exists(state.REMOTE_KEY_FILE):
    try: shutil.move(legacy_key, state.REMOTE_KEY_FILE)
    except: pass

# ==========================================================
# 번들된 Detail plugin 리소스를 설정 폴더로 추출 (exe 최초 실행 시)
# ==========================================================
if not os.path.exists(state.DETAIL_PLUGIN_DIR):
    try:
        os.makedirs(state.DETAIL_LANG_DIR, exist_ok=True)
        bundled_jar = resource_path(os.path.join("Detail plugin", "AYAdetail-1.0-SNAPSHOT.jar"))
        if os.path.exists(bundled_jar):
            shutil.copy(bundled_jar, os.path.join(state.DETAIL_PLUGIN_DIR, "AYAdetail-1.0-SNAPSHOT.jar"))
        bundled_lang = resource_path(os.path.join("Detail plugin languages"))
        if os.path.exists(bundled_lang):
            for f in os.listdir(bundled_lang):
                shutil.copy(os.path.join(bundled_lang, f), os.path.join(state.DETAIL_LANG_DIR, f))
    except:
        pass
else:
    os.makedirs(state.DETAIL_LANG_DIR, exist_ok=True)

# 번들된 언어팩(languages/) 을 설정 폴더로 추출 (ko/en 외 추가 언어팩)
try:
    bundled_lang_root = resource_path("languages")
    if os.path.exists(bundled_lang_root):
        if not os.path.exists(state.LANG_DIR):
            os.makedirs(state.LANG_DIR)
        for f in os.listdir(bundled_lang_root):
            if f.endswith(".json"):
                target = os.path.join(state.LANG_DIR, f)
                if not os.path.exists(target):
                    shutil.copy(os.path.join(bundled_lang_root, f), target)
except:
    pass

# update.exe 를 AYA_data/ 로 자동 복사 (최초 실행 시)
try:
    bundled_update = resource_path("update.exe")
    update_target = os.path.join(state.AYA_BASE, "update.exe")
    if os.path.exists(bundled_update) and not os.path.exists(update_target):
        shutil.copy(bundled_update, update_target)
except:
    pass

# ==========================================================
# 전역 Tkinter 인스턴스 (다이얼로그용 루프 방지)
# ==========================================================
root = tk.Tk()
root.withdraw()
root.attributes("-topmost", True)  # 다이얼로그가 항상 위에 뜨도록 설정
