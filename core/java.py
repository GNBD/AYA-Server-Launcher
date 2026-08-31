import os
import sys
import json
import subprocess
import eel
from . import state, security


def load_global_java_setting():
    global DEFAULT_JAVA
    try:
        if os.path.exists(state.LAUNCHER_CONFIG_FILE):
            with open(state.LAUNCHER_CONFIG_FILE, 'r', encoding='utf-8') as f:
                conf = json.load(f)
                state.DEFAULT_JAVA = conf.get("global_java", "java")
    except:
        pass

@eel.expose
def scan_java_versions_py(token, target_path=None):
    if not security.is_auth_verified(token): return []
    java_list = []
    current_path = target_path if target_path else state.DEFAULT_JAVA
    current_ver = get_java_version_string(current_path)

    java_list.append({
        "path": current_path,
        "version": current_ver,
        "is_current": True
    })

    if current_path != "java":
        sys_ver = get_java_version_string("java")
        if sys_ver != "Unknown":
            java_list.append({"path": "java", "version": sys_ver, "is_current": False})

    search_dirs = [
        r"C:\Program Files\Java",
        r"C:\Program Files (x86)\Java",
        r"C:\Program Files\Eclipse Adoptium",
        r"C:\Program Files\Zulu",
        r"C:\Program Files\Microsoft",
        r"C:\Program Files\BellSoft"
    ]

    # 레지스트리에서 Java 설치 경로 추가 수집
    try:
        import winreg
        for key_path in [r"SOFTWARE\JavaSoft\Java Runtime Environment",
                         r"SOFTWARE\JavaSoft\Java Development Kit",
                         r"SOFTWARE\Eclipse Adoptium\JDK",
                         r"SOFTWARE\Eclipse Adoptium\JRE"]:
            try:
                with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, key_path) as root_key:
                    i = 0
                    while True:
                        try:
                            subkey_name = winreg.EnumKey(root_key, i)
                            sub_path = os.path.join(key_path, subkey_name)
                            try:
                                with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, sub_path) as sk:
                                    java_home, _ = winreg.QueryValueEx(sk, "JavaHome")
                                    exe_path = os.path.join(java_home, "bin", "java.exe")
                                    if os.path.exists(exe_path) and exe_path not in seen_paths:
                                        search_dirs.append(os.path.dirname(os.path.dirname(exe_path)))
                            except: pass
                            i += 1
                        except (OSError, StopIteration):
                            break
            except: pass
    except: pass

    for root_dir in search_dirs:
        try:
            if os.path.exists(root_dir):
                for item in os.listdir(root_dir):
                    try:
                        full_path = os.path.join(root_dir, item, "bin", "java.exe")
                        if os.path.exists(full_path) and full_path != current_path:
                            ver = get_java_version_string(full_path)
                            java_list.append({
                                "path": full_path,
                                "version": ver if ver != "Unknown" else "Detected",
                                "is_current": False
                            })
                    except:
                        pass
        except:
            pass

    unique_list = []
    seen_paths = set()
    for j in java_list:
        if j['path'] not in seen_paths:
            unique_list.append(j)
            seen_paths.add(j['path'])

    return unique_list

def get_java_version_string(path):
    try:
        cmd = [path, "-version"]
        si = subprocess.STARTUPINFO()
        si.dwFlags |= subprocess.STARTF_USESHOWWINDOW if os.name == 'nt' else 0
        result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=10, startupinfo=si)
        output = result.stderr
        for line in output.split('\n'):
            if "version" in line:
                return line.split('"')[1]
        return "Detected"
    except:
        return "Unknown"

@eel.expose
def set_global_java_py(token, new_path):
    if not security.is_auth_verified(token): return "❌ Unauthorized"
    if len(state.active_processes) > 0:
        return "⚠️ Running"

    try:
        config = {}
        if os.path.exists(state.LAUNCHER_CONFIG_FILE):
            with open(state.LAUNCHER_CONFIG_FILE, 'r', encoding='utf-8') as f:
                config = json.load(f)

        config["global_java"] = new_path

        with open(state.LAUNCHER_CONFIG_FILE, 'w', encoding='utf-8') as f:
            json.dump(config, f, indent=4)

        state.DEFAULT_JAVA = new_path
        return "✅ Saved"
    except Exception as e:
        return f"❌ Error: {e}"

@eel.expose
def check_any_server_running_py(token):
    if not security.is_auth_verified(token): return False
    return len(state.active_processes) > 0

@eel.expose
def kill_all_java_processes_py(token):
    if not security.is_auth_verified(token): return "❌ Unauthorized"
    count = 0
    try:
        if os.name == 'nt':
            os.system("taskkill /f /im java.exe")
            os.system("taskkill /f /im javaw.exe")
            return "✅ 모든 자바 프로세스를 종료 명령을 보냈습니다."
        else:
            import psutil
            for proc in psutil.process_iter(['pid', 'name']):
                if 'java' in proc.info['name'].lower():
                    proc.kill()
                    count += 1
            return f"✅ 자바 프로세스 {count}개를 종료했습니다."
    except Exception as e:
        return f"❌ 오류 발생: {e}"

@eel.expose
def restart_launcher_py(token):
    if not security.is_auth_verified(token): return False
    try:
        subprocess.Popen([sys.executable] + sys.argv)
        os._exit(0)
    except:
        return False
