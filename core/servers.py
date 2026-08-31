import os
import re
import sys
import shutil
import json
import datetime
import time
import threading
import subprocess
import requests
import gevent
import concurrent.futures
from urllib.parse import urlparse
import eel
from . import state, security, common, players

# ==========================================================
# [기능] 로컬 월드/코어 선택 다이얼로그
# ==========================================================
@eel.expose
def select_local_world_folder_py(token):
    if not security.is_auth_verified(token): return None
    initial_dir = os.path.join(os.environ.get('APPDATA', ''), '.minecraft', 'saves')
    if not os.path.exists(initial_dir):
        initial_dir = os.path.expanduser("~")
    from tkinter import filedialog
    folder_selected = filedialog.askdirectory(initialdir=initial_dir, title="Select Minecraft World Folder")
    return folder_selected if folder_selected else None

@eel.expose
def get_current_server_py(token):
    if not security.is_auth_verified(token): return None
    return state.current_view_server

@eel.expose
def try_close_app_py(token):
    if not security.is_auth_verified(token): return "blocked"
    for name, p in state.active_processes.items():
        if p.poll() is None:
            return "blocked"
    return "ok"

# ==========================================================
# [기능] 서버 목록 / 선택
# ==========================================================
@eel.expose
def get_server_list_py(token):
    if not security.is_auth_verified(token): return []
    if not os.path.exists(state.BASE_SERVERS_DIR): os.makedirs(state.BASE_SERVERS_DIR)
    server_list = []
    try:
        for name in os.listdir(state.BASE_SERVERS_DIR):
            full_path = os.path.join(state.BASE_SERVERS_DIR, name)
            if os.path.isdir(full_path):
                status = "Ready"
                if name in state.active_processes and state.active_processes[name].poll() is None: status = "Running"
                version = ""
                try:
                    config_path = os.path.join(full_path, "nene_config.json")
                    if os.path.exists(config_path):
                        with open(config_path, 'r', encoding='utf-8') as f: version = json.load(f).get("version", "")
                except: pass
                server_list.append({"name": name, "status": status, "version": version})
    except: pass
    return server_list

@eel.expose
def select_server_py(token, server_name):
    if not security.is_auth_verified(token): return " Unauthorized"
    state.current_view_server = server_name
    if server_name in state.server_logs: eel.restore_logs_js(state.server_logs[server_name][-1000:])()
    else: eel.restore_logs_js([])()
    is_running = False
    if server_name in state.active_processes and state.active_processes[server_name].poll() is None: is_running = True
    eel.update_status_js(is_running)
    players.update_ui_player_list(server_name)
    return f"Load: {server_name}"

USER_AGENT = "AYA-Server-Launcher/4.2.1 (https://github.com/AnomalyCo/opencode)"


def _ver_key(v):
    parts = re.split(r'[.\-+]', str(v))
    nums = []
    for p in parts:
        try:
            nums.append(int(p))
        except ValueError:
            nums.append(0)
    return nums


def _resolve_api(mirror_url):
    # PaperMC v2 API was sunset -> migrate api.papermc.io/v2 to fill.papermc.io/v3
    m = (mirror_url or "").strip().rstrip('/')
    if "purpurmc.org" in m:
        return "purpur", m
    base = m.replace("api.papermc.io/v2", "fill.papermc.io/v3")
    base = re.sub(r'/(versions|builds)(/.*)?$', '', base)
    base = base.rstrip('/')
    if not re.search(r'/projects/[^/]+$', base):
        raise ValueError("지원하지 않는 미러 URL입니다. 올바른 미러 주소를 입력하세요.")
    return "papermc", base


_OFFICIAL_HOSTS = ("fill.papermc.io", "fill-data.papermc.io", "api.papermc.io", "purpurmc.org")


def _apply_download_mirror(download_url, mirror_url):
    # 사용자 지정 미러(공식 호스트가 아닌 경우)가 지정되면 jar 다운로드 호스트도 미러로 치환한다.
    # (Paper의 다운로드는 API 응답의 fill-data.papermc.io 로 고정되므로, 미러 설정이 다운로드에
    #  실효성을 갖도록 하기 위함. 미러는 fill-data.papermc.io 를 프록시해야 함)
    m = (mirror_url or "").strip()
    if not m:
        return download_url
    try:
        mp = urlparse(m)
        if not mp.netloc or mp.netloc.lower() in _OFFICIAL_HOSTS:
            return download_url
        dp = urlparse(download_url)
        if not dp.netloc:
            return download_url
        new = f"{mp.scheme or dp.scheme}://{mp.netloc}{dp.path}"
        if dp.query:
            new += "?" + dp.query
        return new
    except Exception:
        return download_url


def _resolve_paper_download(version, mirror_url, headers):
    base = (mirror_url or "").strip().rstrip('/') if mirror_url else ""
    if not base:
        raise ValueError("미러 URL이 설정되지 않았습니다.")
    low = base.lower()
    if "purpurmc.org" in low:
        r = _offload(lambda: requests.get(f"{base}/{version}", headers=headers, timeout=10))
        r.raise_for_status(); data = r.json()
        latest = data['builds']['latest']
        return f"{base}/{version}/{latest}/download", f"purpur-{version}-{latest}.jar"
    is_v3 = ("fill.papermc.io/v3" in low) or low.endswith("/v3/projects/paper")
    if is_v3:
        r = _offload(lambda: requests.get(f"{base}/versions/{version}/builds", headers=headers, timeout=10))
        r.raise_for_status(); builds = r.json()
        if not isinstance(builds, list):
            builds = builds.get("builds", [])
        stable = [b for b in builds if str(b.get("channel", "")).upper() == "STABLE"]
        chosen = stable[-1] if stable else (builds[-1] if builds else None)
        if not chosen:
            raise Exception("No builds found for version " + version)
        dl = chosen["downloads"]["server:default"]
        return dl["url"], dl["name"]
    # 구버전 v2 API
    r = _offload(lambda: requests.get(f"{base}/versions/{version}", headers=headers, timeout=10))
    if r.status_code == 200:
        data = r.json(); latest = data['builds'][-1]
        r2 = _offload(lambda: requests.get(f"{base}/versions/{version}/builds/{latest}", headers=headers, timeout=10))
        r2.raise_for_status(); bd = r2.json()
        fn = bd['downloads']['application']['name']
        return f"{base}/versions/{version}/builds/{latest}/downloads/{fn}", fn
    raise ValueError(f"미러 서버에서 버전 {version}을 찾을 수 없습니다. 미러 URL을 확인하세요.")


def _offload(block, progress_holder=None, progress_cb=None):
    # 차단 I/O(requests 등)를 실제 OS 스레드에서 실행하고, gevent 허브를 막지 않도록
    # 0.05s 단위로 양보하며 결과를 기다린다. (monkey.patch 없이도 UI 응답성 유지)
    fut = concurrent.futures.Future()

    def _run():
        try:
            fut.set_result(block())
        except Exception as e:
            fut.set_exception(e)

    threading.Thread(target=_run, daemon=True).start()
    while not fut.done():
        gevent.sleep(0.05)
        if progress_holder is not None and progress_cb is not None:
            p = progress_holder.get('pct')
            if p is not None and p != progress_holder.get('_sent'):
                progress_holder['_sent'] = p
                try:
                    progress_cb(p)
                except Exception:
                    pass
    return fut.result()


@eel.expose
def get_papermc_versions_py(token):
    if not security.is_auth_verified(token): return []
    try:
        mirror_url = "https://fill.papermc.io/v3/projects/paper"
        if os.path.exists(state.LAUNCHER_CONFIG_FILE):
            with open(state.LAUNCHER_CONFIG_FILE, 'r', encoding='utf-8') as f:
                conf = json.load(f)
                mirror_url = conf.get("mirror_url", mirror_url).strip().rstrip('/')

        headers = {'User-Agent': USER_AGENT}
        low = mirror_url.lower()
        if "purpurmc.org" in low:
            r = _offload(lambda: requests.get(mirror_url, headers=headers, timeout=8))
            if r.status_code == 200:
                return r.json().get("versions", [])[::-1]
            return ["1.21.4", "1.21.3", "1.21.1", "1.20.4", "1.16.5", "1.12.2"]

        # Paper: 사용자 미러에서 버전 목록 조회
        if "fill.papermc.io/v3" not in low and not low.endswith("/v3/projects/paper"):
            r = _offload(lambda: requests.get(mirror_url, headers=headers, timeout=8))
            if r.status_code == 200:
                data = r.json()
                versions = data.get("versions", {})
                if isinstance(versions, dict):
                    allv = []
                    for lst in versions.values():
                        if isinstance(lst, list):
                            allv.extend(lst)
                    stable = [v for v in allv if "-" not in v]
                    if not stable:
                        stable = allv
                    stable = list(dict.fromkeys(stable))
                    stable.sort(key=_ver_key, reverse=True)
                    return stable
                elif isinstance(versions, list):
                    return versions[::-1]

        # Fill v3
        r = _offload(lambda: requests.get(mirror_url, headers=headers, timeout=8))
        if r.status_code == 200:
            versions = r.json().get("versions", {})
            if isinstance(versions, dict):
                allv = []
                for lst in versions.values():
                    if isinstance(lst, list):
                        allv.extend(lst)
                stable = [v for v in allv if isinstance(v, str) and "-" not in v]
                if not stable:
                    stable = [v for v in allv if isinstance(v, str)]
                stable = list(dict.fromkeys(stable))
                stable.sort(key=_ver_key, reverse=True)
                return stable
            elif isinstance(versions, list):
                versions = [v for v in versions if isinstance(v, str)]
                versions.sort(key=_ver_key, reverse=True)
                return versions

    except Exception as e:
        print("get_papermc_versions_py error:", e)
    return []

@eel.expose
def get_manage_list_py(token, file_type):
    if not security.is_auth_verified(token): return []
    if not state.current_view_server: return []
    filename = "whitelist.json"
    if file_type == "banlist": filename = "banned-players.json"
    elif file_type == "ip-banlist": filename = "banned-ips.json"
    path = os.path.join(state.BASE_SERVERS_DIR, state.current_view_server, filename)
    res = []
    if os.path.exists(path):
        try:
            with open(path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                for i in data:
                    if file_type == "ip-banlist":
                        if "ip" in i: res.append(i["ip"])
                    else:
                        if "name" in i: res.append(i["name"])
        except: pass
    return res

@eel.expose
def get_player_detail_py(token, player_name):
    if not security.is_auth_verified(token): return None
    if not state.current_view_server: return None
    info = { "name": player_name, "join_time": "-", "uuid": "-" }
    if state.current_view_server in state.server_players and player_name in state.server_players[state.current_view_server]:
        info.update(state.server_players[state.current_view_server][player_name])
    return info

@eel.expose
def execute_command_py(token, cmd):
    if not security.is_auth_verified(token):
        security.add_access_log("Execute Command", "blocked", f"Unauthorized: {cmd}")
        return "❌ Unauthorized"
    send_command_py(token, cmd)
    return f"Cmd: {cmd}"

@eel.expose
def get_singleplayer_worlds_py(token):
    if not security.is_auth_verified(token): return []
    saves_path = os.path.join(os.environ.get('APPDATA', ''), '.minecraft', 'saves')
    if not os.path.exists(saves_path): return []
    try:
        return [d for d in os.listdir(saves_path) if os.path.isdir(os.path.join(saves_path, d))]
    except: return []

# ==========================================================
# [기능] 폴더 복사 (진행률 표시)
# ==========================================================
def copy_folder_with_progress(src, dst):
    if not os.path.exists(src): return
    if not os.path.exists(dst): os.makedirs(dst)

    files_to_copy = []
    for root, dirs, files in os.walk(src):
        for f in files:
            files_to_copy.append(os.path.join(root, f))

    total = len(files_to_copy)
    if total == 0: return

    count = 0
    for f in files_to_copy:
        rel_path = os.path.relpath(f, src)
        dest_path = os.path.join(dst, rel_path)
        dest_dir = os.path.dirname(dest_path)
        if not os.path.exists(dest_dir): os.makedirs(dest_dir)
        shutil.copy2(f, dest_path)
        count += 1
        percent = int((count / total) * 100)
        eel.update_download_progress_js(f"Copying World ({percent}%)...")()

# ==========================================================
# [기능] 서버 생성 / 코어 업데이트 / 불러오기 / 삭제
# ==========================================================
@eel.expose
def create_new_server_real_py(token, server_name, version, mirror_url, custom_java_path, difficulty="normal", gamemode="survival", ram=4, world_name=None):
    if not security.is_auth_verified(token): return "❌ Unauthorized"
    clean = re.sub(r'[<>:"/\\|?*]', '', server_name).strip()
    if not clean: return "❌ Name Error"
    target = os.path.join(state.BASE_SERVERS_DIR, clean)
    if os.path.exists(target): return "⚠️ Exists"

    try:
        os.makedirs(target)
        headers = {'User-Agent': USER_AGENT}

        eel.update_download_progress_js("Checking API...")()

        download_url, file_name = _resolve_paper_download(version, mirror_url, headers)

        eel.update_download_progress_js("Downloading...")()

        progress_holder = {'pct': None, '_sent': -1}
        try:
            def _download():
                last = -1
                with requests.get(download_url, headers=headers, stream=True, timeout=(10, 120)) as r:
                    r.raise_for_status()
                    total = int(r.headers.get('Content-Length', 0)) or 0
                    done = 0
                    with open(os.path.join(target, "server.jar"), 'wb') as f:
                        for chunk in r.iter_content(chunk_size=8192):
                            if chunk:
                                f.write(chunk)
                                if total:
                                    done += len(chunk)
                                    pct = int(done / total * 100)
                                    if pct != last:
                                        last = pct
                                        progress_holder['pct'] = pct
            _offload(_download, progress_holder,
                     lambda p: eel.update_download_progress_js(f"Downloading... {p}%")())
        except requests.exceptions.RequestException as e:
            raise Exception(f"다운로드 연결 실패: {e}")

        with open(os.path.join(target, "eula.txt"), 'w') as f: f.write("eula=true")

        if world_name:
            if os.path.isabs(world_name):
                saves_path = world_name
            else:
                saves_path = os.path.join(os.environ.get('APPDATA', ''), '.minecraft', 'saves', world_name)

            if os.path.exists(saves_path):
                dest_world = os.path.join(target, "world")
                copy_folder_with_progress(saves_path, dest_world)

        now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with open(os.path.join(target, "nene_config.json"), 'w', encoding='utf-8') as f:
            json.dump({
                "java_path": custom_java_path,
                "version": version,
                "auto_backup": False,
                "backup_interval": 60,
                "original_jar": file_name,
                "created_at": now_str,
                "download_source": (mirror_url or "https://fill.papermc.io/v3/projects/paper").rstrip('/'),
                "ram_allocation": ram
            }, f, indent=4)

        try:
            props = {
                "motd": server_name,
                "difficulty": difficulty,
                "gamemode": gamemode,
                "level-name": "world",
                "server-port": "25565"
            }
            with open(os.path.join(target, "server.properties"), 'w', encoding='utf-8') as f:
                f.write("# Minecraft server properties\n")
                for k, v in props.items():
                    f.write(f"{k}={v}\n")
        except: pass

        # 1.19 버전 이상일 경우 NeneBridge 플러그인 자동 복사
        try:
            ver_parts = version.split('.')
            is_target_version = False

            if len(ver_parts) >= 1:
                major_ver = int(ver_parts[0])

                if major_ver >= 26:
                    is_target_version = True
                elif major_ver == 1 and len(ver_parts) >= 2:
                    minor_ver = int(ver_parts[1])
                    if minor_ver >= 19:
                        is_target_version = True

            if is_target_version:
                plugin_src = os.path.join(state.DETAIL_PLUGIN_DIR, "AYAdetail-1.0-SNAPSHOT.jar")

                if os.path.exists(plugin_src):
                    plugins_dir = os.path.join(target, "plugins")
                    if not os.path.exists(plugins_dir):
                        os.makedirs(plugins_dir)

                    shutil.copy(plugin_src, os.path.join(plugins_dir, "AYAdetail-1.0-SNAPSHOT.jar"))

                    if os.path.exists(state.DETAIL_LANG_DIR):
                        detail_data_dir = os.path.join(target, "plugins", "AYAdetail")
                        lang_target = os.path.join(detail_data_dir, "languages")
                        if not os.path.exists(lang_target):
                            os.makedirs(lang_target)
                        for f in os.listdir(state.DETAIL_LANG_DIR):
                            try:
                                shutil.copy(os.path.join(state.DETAIL_LANG_DIR, f), os.path.join(lang_target, f))
                            except:
                                pass

        except Exception as e:
            print(f"AYA DETAIL Auto Copy Failed: {e}")

        return "✅ Done"

    except Exception as e:
        if os.path.exists(target): shutil.rmtree(target)
        return f"❌ Error: {e}"

@eel.expose
def update_server_core_py(token, version, mirror_url):
    if not security.is_auth_verified(token): return "❌ Unauthorized"
    if not state.current_view_server: return "❌ No Server"
    if state.current_view_server in state.active_processes: return "⚠️ Running"

    target = os.path.join(state.BASE_SERVERS_DIR, state.current_view_server)
    config_path = os.path.join(target, "nene_config.json")

    try:
        jar_name = "server.jar"
        config = {}
        if os.path.exists(config_path):
            try:
                with open(config_path, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                    jar_name = config.get("custom_jar", "server.jar")
            except: pass

        headers = {'User-Agent': USER_AGENT}

        download_url, file_name = _resolve_paper_download(version, mirror_url, headers)

        progress_holder = {'pct': None, '_sent': -1}
        try:
            def _download():
                last = -1
                with requests.get(download_url, headers=headers, stream=True, timeout=(10, 120)) as r:
                    r.raise_for_status()
                    total = int(r.headers.get('Content-Length', 0)) or 0
                    done = 0
                    with open(os.path.join(target, jar_name), 'wb') as f:
                        for chunk in r.iter_content(chunk_size=8192):
                            if chunk:
                                f.write(chunk)
                                if total:
                                    done += len(chunk)
                                    pct = int(done / total * 100)
                                    if pct != last:
                                        last = pct
                                        progress_holder['pct'] = pct
            _offload(_download, progress_holder,
                     lambda p: eel.update_download_progress_js(f"Downloading... {p}%")())
        except requests.exceptions.RequestException as e:
            raise Exception(f"다운로드 연결 실패: {e}")

        config["version"] = version
        with open(config_path, 'w', encoding='utf-8') as f:
            json.dump(config, f, indent=4)

        return f"✅ {version} ({jar_name}) 최신 빌드로 업데이트 완료"

    except Exception as e:
        return f"❌ 실패: {e}"

@eel.expose
def select_local_core_py(token):
    if not security.is_auth_verified(token): return "❌ Unauthorized"
    if not state.current_view_server: return "❌ No Server"
    if state.current_view_server in state.active_processes: return "⚠️ Running"

    from tkinter import filedialog
    root = __import__('tkinter').Tk()
    root.withdraw()
    root.attributes("-topmost", True)

    target_dir = os.path.abspath(os.path.join(state.BASE_SERVERS_DIR, state.current_view_server))
    target_dir = os.path.normpath(target_dir)

    jar_path = filedialog.askopenfilename(
        title="Select Minecraft Server JAR",
        initialdir=target_dir,
        filetypes=[("JAR files", "*.jar")]
    )
    if not jar_path: return "⚠️ Cancelled"

    target_dir = os.path.abspath(os.path.join(state.BASE_SERVERS_DIR, state.current_view_server))
    jar_name = os.path.basename(jar_path)
    dest_path = os.path.join(target_dir, jar_name)

    try:
        if os.path.abspath(jar_path) != os.path.abspath(dest_path):
            shutil.copy2(jar_path, dest_path)

        config_path = os.path.join(target_dir, "nene_config.json")
        if os.path.exists(config_path):
            with open(config_path, 'r', encoding='utf-8') as f:
                config = json.load(f)
            config["custom_jar"] = jar_name
            with open(config_path, 'w', encoding='utf-8') as f:
                json.dump(config, f, indent=4)

        return f"✅ {jar_name} 코어 등록 완료"
    except Exception as e:
        return f"❌ 오류: {e}"

@eel.expose
def import_existing_server_py(token):
    if not security.is_auth_verified(token): return "❌ Unauthorized"

    from tkinter import filedialog
    root = __import__('tkinter').Tk()
    root.withdraw()
    root.attributes("-topmost", True)
    src_folder = filedialog.askdirectory(title="Select Existing Minecraft Server Folder")
    if not src_folder: return "⚠️ Cancelled"

    jar_path = filedialog.askopenfilename(
        title="Select Server JAR file to Run",
        initialdir=src_folder,
        filetypes=[("JAR files", "*.jar")]
    )
    if not jar_path: return "⚠️ Cancelled (JAR not selected)"

    jar_name = os.path.basename(jar_path)

    folder_name = os.path.basename(src_folder)
    clean_name = re.sub(r'[<>:"/\\|?*]', '', folder_name).strip()
    target = os.path.join(state.BASE_SERVERS_DIR, clean_name)

    base_target = target
    counter = 1
    while os.path.exists(target):
        target = f"{base_target}_{counter}"
        counter += 1

    final_name = os.path.basename(target)

    try:
        eel.update_download_progress_js(f"Importing {final_name}...")()
        copy_folder_with_progress(src_folder, target)

        config_path = os.path.join(target, "nene_config.json")
        now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        with open(config_path, 'w', encoding='utf-8') as f:
            json.dump({
                "java_path": "java",
                "version": "Unknown",
                "auto_backup": False,
                "backup_interval": 60,
                "created_at": now_str,
                "download_source": "Imported",
                "ram_allocation": 4,
                "custom_jar": jar_name
            }, f, indent=4)

        return f"✅ {final_name} 불러오기 성공"

    except Exception as e:
        if os.path.exists(target): shutil.rmtree(target)
        return f"❌ 오류: {e}"

@eel.expose
def delete_server_real_py(token, name):
    if not security.is_auth_verified(token): return "❌ Unauthorized"
    if name in state.active_processes: return "⚠️ Running"
    try:
        shutil.rmtree(os.path.join(state.BASE_SERVERS_DIR, name))
        if name in state.server_logs: del state.server_logs[name]
        if name in state.server_players: del state.server_players[name]
        return "✅ Deleted"
    except: return "❌ Failed"

# ==========================================================
# [기능] server.properties 보정
# ==========================================================
def ensure_valid_properties(server_dir):
    path = os.path.join(server_dir, "server.properties")
    if not os.path.exists(path):
        return

    defaults = {
        "max-players": "20",
        "server-port": "25565",
        "view-distance": "10",
        "simulation-distance": "10",
        "max-tick-time": "60000",
        "network-compression-threshold": "256",
        "rate-limit": "0",
        "max-world-size": "29999984",
        "spawn-protection": "16",
        "player-idle-timeout": "0",
        "op-permission-level": "4",
        "query.port": "25565",
        "rcon.port": "25575",
        "entity-broadcast-range-percentage": "100",
        "max-chained-neighbor-updates": "1000000"
    }

    try:
        lines = []
        with open(path, 'r', encoding='utf-8', errors='replace') as f:
            lines = f.readlines()

        modified = False
        new_lines = []
        keys_found = set()

        for line in lines:
            line_str = line.strip()
            if "=" in line_str and not line_str.startswith("#"):
                parts = line_str.split("=", 1)
                k = parts[0].strip()
                v = parts[1].strip()
                keys_found.add(k)
                if k in defaults and not v:
                    new_lines.append(f"{k}={defaults[k]}\n")
                    modified = True
                else:
                    new_lines.append(line)
            else:
                new_lines.append(line)

        for k, v in defaults.items():
            if k not in keys_found:
                new_lines.append(f"{k}={v}\n")
                modified = True

        if modified:
            with open(path, 'w', encoding='utf-8') as f:
                f.writelines(new_lines)
    except:
        pass

# ==========================================================
# [기능] 서버 시작 / 실행 / 콘솔
# ==========================================================
@eel.expose
def start_server_py(token, ram):
    if not security.is_auth_verified(token):
        security.add_access_log("Server Start", "blocked", "Unauthorized")
        return "❌ Unauthorized"
    name = state.current_view_server
    if not name:
        security.add_access_log("Server Start", "fail", "No server selected")
        return "❌ Select Server"
    if name in state.active_processes:
        security.add_access_log("Server Start", "fail", f"Server '{name}' already running")
        return "⚠️ Running"

    server_dir = os.path.join(state.BASE_SERVERS_DIR, name)

    ensure_valid_properties(server_dir)
    jar_name = "server.jar"

    try:
        cfg_path = os.path.join(server_dir, "nene_config.json")
        if os.path.exists(cfg_path):
            with open(cfg_path, 'r', encoding='utf-8') as f:
                cfg = json.load(f)
                jar_name = cfg.get("custom_jar", "server.jar")
    except: pass

    jar = os.path.join(server_dir, jar_name)
    if not os.path.exists(jar): return f"❌ No Jar ({jar_name})"
    if name not in state.server_logs: state.server_logs[name] = []

    if name not in state.server_players:
        state.server_players[name] = {}
    else:
        for p in state.server_players[name]:
            state.server_players[name][p]["online"] = False

    if state.current_view_server == name:
        players.update_ui_player_list(name)

    t = threading.Thread(target=run_server, args=(name, jar, ram))
    t.daemon = True
    t.start()
    security.add_access_log("Server Start", "success", f"Server '{name}' started (RAM: {ram}GB)")
    return "🚀 Starting..."

def run_server(name, jar, ram):
    d = os.path.dirname(jar)
    java = "java"
    try:
        with open(os.path.join(d, "nene_config.json"), 'r', encoding='utf-8') as f: java = json.load(f).get("java_path", "java")
    except: pass
    cmd = [java, f"-Xms{ram}G", f"-Xmx{ram}G", "-jar", os.path.basename(jar), "nogui"]
    si = subprocess.STARTUPINFO()
    si.dwFlags |= subprocess.STARTF_USESHOWWINDOW if os.name == 'nt' else 0
    try:
        p = subprocess.Popen(cmd, cwd=d, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding='utf-8', errors='replace', startupinfo=si)
        state.active_processes[name] = p
        if state.current_view_server == name: eel.update_status_js(True)()
        while True:
            line = p.stdout.readline()
            if not line and p.poll() is not None: break
            if line:
                clean = line.strip()
                append_log(name, clean)
                players.parse_player_event(name, clean)
        append_log(name, "[SYSTEM] Stopped")
        if name in state.active_processes: del state.active_processes[name]

        if name in state.server_players:
            for p_name in state.server_players[name]:
                state.server_players[name][p_name]["online"] = False

        if state.current_view_server == name:
            eel.update_status_js(False)
            players.update_ui_player_list(name)

    except Exception as e:
        append_log(name, f"[ERROR] {e}")
        if name in state.active_processes: del state.active_processes[name]

def append_log(name, msg):
    if name not in state.server_logs: state.server_logs[name] = []
    state.server_logs[name].append(msg)
    if state.current_view_server == name: eel.add_log_js(msg)

@eel.expose
def send_command_py(token, cmd):
    if not security.is_auth_verified(token):
        security.add_access_log("Execute Command", "blocked", f"Unauthorized: {cmd}")
        return
    if state.current_view_server and state.current_view_server in state.active_processes:
        p = state.active_processes[state.current_view_server]
        if p.poll() is None:
            try:
                p.stdin.write(cmd+"\n"); p.stdin.flush(); append_log(state.current_view_server, f"> {cmd}")
                security.add_access_log("Execute Command", "success", f"Server '{state.current_view_server}': {cmd}")
            except:
                security.add_access_log("Execute Command", "error", f"Command send fail: {cmd}")
                pass

# ==========================================================
# [기능] 서버 속성 로드/저장
# ==========================================================
@eel.expose
def load_properties_py(token):
    if not security.is_auth_verified(token): return None
    if not state.current_view_server: return None
    props = {}
    d = os.path.join(state.BASE_SERVERS_DIR, state.current_view_server)
    try:
        with open(os.path.join(d, "server.properties"), 'r') as f:
            for l in f:
                if "=" in l and not l.startswith("#"):
                    k,v = l.strip().split("=", 1)
                    props[k] = v
    except: pass
    try:
        with open(os.path.join(d, "nene_config.json"), 'r', encoding='utf-8') as f: props.update(json.load(f))
    except: pass
    return props

@eel.expose
def save_properties_py(token, data):
    if not security.is_auth_verified(token): return " Unauthorized"
    if not state.current_view_server: return " No Server"
    d = os.path.join(state.BASE_SERVERS_DIR, state.current_view_server)
    current_conf = {}
    try:
        with open(os.path.join(d, "nene_config.json"), 'r', encoding='utf-8') as f: current_conf = json.load(f)
    except: pass

    special_keys = ["java_path", "auto_backup", "backup_interval", "ram_allocation"]
    for key in special_keys:
        if key in data:
            current_conf[key] = data[key]
            del data[key]

    try:
        with open(os.path.join(d, "nene_config.json"), 'w', encoding='utf-8') as f: json.dump(current_conf, f, indent=4)
        path = os.path.join(d, "server.properties")
        lines = []
        if os.path.exists(path):
            with open(path, 'r') as f: lines = f.readlines()
        else: lines = ["# Minecraft Properties\n"]
        final = []
        keys = []
        for l in lines:
            if "=" in l and not l.startswith("#"):
                k = l.split("=")[0].strip()
                if k in data:
                    final.append(f"{k}={str(data[k]).lower()}\n")
                    keys.append(k)
                else: final.append(l)
            else: final.append(l)
        for k,v in data.items():
            if k not in keys: final.append(f"{k}={str(v).lower()}\n")
        with open(path, 'w') as f: f.writelines(final)
        return " Saved"
    except: return " Failed"

@eel.expose
def check_java_status_py(token):
    try:
        subprocess.check_output([state.DEFAULT_JAVA, "-version"], stderr=subprocess.STDOUT)
        return {"status": "ok"}
    except: return {"status": "error"}

@eel.expose
def open_folder_py(token, server_name, mode):
    if not security.is_auth_verified(token): return " Unauthorized"
    if not server_name: return " No Server Selected"

    if mode == "backup":
        path = os.path.join(state.BACKUP_ROOT_DIR, server_name)
    else:
        path = os.path.join(state.BASE_SERVERS_DIR, server_name)

    if not os.path.exists(path):
        try:
            os.makedirs(path)
        except:
            return " Create Failed"
    try:
        if os.name == 'nt':
            os.startfile(path)
        elif sys.platform == 'darwin':
            subprocess.Popen(['open', path])
        else:
            subprocess.Popen(['xdg-open', path])
        return " Opened"
    except Exception as e:
        return f" Error: {e}"

@eel.expose
def get_public_ip_py(token):
    try:
        return requests.get('https://api.ipify.org', timeout=3).text
    except:
        return "Unknown"
