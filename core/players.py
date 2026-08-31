import os
import re
import json
import gzip
import datetime
import eel
from . import state, security

# ==========================================================
# [기능] 플레이어 UI 목록 갱신 (서버 로그 기반 + 플러그인 userdata)
# ==========================================================
def update_ui_player_list(server_name):
    if state.current_view_server == server_name:
        players_list = []

        if server_name in state.server_players:
            for p_name, p_data in state.server_players[server_name].items():
                players_list.append({
                    "name": p_name,
                    "online": p_data.get("online", False),
                    "uuid": p_data.get("uuid", "-"),
                    "join_time": p_data.get("join_time", "-")
                })

        try:
            userdata_dir = os.path.join(state.BASE_SERVERS_DIR, server_name, "plugins", "AYADETAIL", "userdata")
            if os.path.exists(userdata_dir):
                for f in os.listdir(userdata_dir):
                    if f.endswith(".json"):
                        p_name = f.replace(".json", "").strip('"')
                        if not re.match(r'^[a-zA-Z0-9_]{3,16}$', p_name):
                            continue

                        exists = False
                        for p in players_list:
                            if p["name"] == p_name:
                                exists = True
                                break

                        if not exists:
                            players_list.append({
                                "name": p_name,
                                "online": False,
                                "uuid": "-",
                                "join_time": "-"
                            })
        except:
            pass

        eel.update_player_list_js(players_list)()

def parse_player_event(server_name, line):
    if server_name not in state.server_players: state.server_players[server_name] = {}

    if "UUID of player" in line:
        try:
            parts = line.split("UUID of player ")
            if len(parts) > 1:
                rest = parts[1].strip()
                if " is " in rest:
                    p_name, p_uuid = rest.split(" is ", 1)
                    p_name = p_name.strip().strip('"')
                    p_uuid = p_uuid.strip().strip('"')

                    if not p_name or not p_uuid:
                        return

                    now = datetime.datetime.now().strftime("%H:%M:%S")
                    state.server_players[server_name][p_name] = {"join_time": now, "uuid": p_uuid, "online": True}
                    update_ui_player_list(server_name)
        except: pass

    if "logged in with entity id" in line:
        try:
            parts = line.split(" logged in with entity id")
            m = re.search(r'([a-zA-Z0-9_]+)(?:\[[^\]]*\])?\s*$', parts[0].strip())
            if m:
                name = m.group(1)
                if name:
                    now = datetime.datetime.now().strftime("%H:%M:%S")
                    saved_uuid = "-"
                    if name in state.server_players[server_name]:
                        saved_uuid = state.server_players[server_name][name].get("uuid", "-")
                    state.server_players[server_name][name] = {"join_time": now, "uuid": saved_uuid, "online": True}
                    update_ui_player_list(server_name)
        except: pass

    elif "lost connection" in line:
        try:
            parts = line.split(" lost connection")
            m = re.search(r'([a-zA-Z0-9_]+)(?:\[[^\]]*\])?\s*$', parts[0].strip())
            if m:
                name = m.group(1)
                if name in state.server_players[server_name]:
                    state.server_players[server_name][name]["online"] = False
                    update_ui_player_list(server_name)
        except: pass

    elif "left the game" in line:
        try:
            parts = line.split(" left the game")
            m = re.search(r'([a-zA-Z0-9_]+)(?:\[[^\]]*\])?\s*$', parts[0].strip())
            if m:
                name = m.group(1)
                if name in state.server_players[server_name]:
                    state.server_players[server_name][name]["online"] = False
                    update_ui_player_list(server_name)
        except: pass

@eel.expose
def get_nene_player_data_py(token, player_name):
    if not security.is_auth_verified(token): return None
    try:
        path = os.path.join(state.BASE_SERVERS_DIR, state.current_view_server, "plugins", "AYADETAIL", "userdata", f"{player_name}.json")
        if os.path.exists(path):
            with open(path, 'r', encoding='utf-8') as f:
                return json.load(f)
    except: pass
    return None

# ==========================================================
# [추가 기능] 서버 상세 정보 (Server Info)
# ==========================================================
@eel.expose
def get_server_extended_info_py(token):
    if not security.is_auth_verified(token): return None
    if not state.current_view_server: return None

    server_path = os.path.join(state.BASE_SERVERS_DIR, state.current_view_server)
    config_path = os.path.join(server_path, "nene_config.json")

    info = {
        "created_at": "Unknown",
        "source_url": "Unknown (Old Server)",
        "java_version": "Unknown",
        "disk_usage": "0 MB",
        "player_count": 0,
        "world_name": "world"
    }

    if os.path.exists(config_path):
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                info["created_at"] = data.get("created_at", "Unknown")
                info["source_url"] = data.get("download_source", "Unknown (Old Server)")
                info["java_version"] = data.get("java_path", "java")
        except: pass

    if info["created_at"] == "Unknown":
        try:
            ctime = os.path.getctime(server_path)
            info["created_at"] = datetime.datetime.fromtimestamp(ctime).strftime("%Y-%m-%d %H:%M:%S")
        except: pass

    try:
        total_size = 0
        for dirpath, dirnames, filenames in os.walk(server_path):
            for f in filenames:
                fp = os.path.join(dirpath, f)
                if not os.path.islink(fp):
                    total_size += os.path.getsize(fp)

        mb_size = total_size / (1024 * 1024)
        if mb_size > 1024:
            info["disk_usage"] = f"{mb_size/1024:.2f} GB"
        else:
            info["disk_usage"] = f"{mb_size:.2f} MB"
    except: pass

    try:
        prop_path = os.path.join(server_path, "server.properties")
        if os.path.exists(prop_path):
            with open(prop_path, 'r') as f:
                for line in f:
                    if line.startswith("level-name="):
                        info["world_name"] = line.split("=")[1].strip()
                        break
    except: pass

    try:
        log_dir = os.path.join(server_path, "logs")
        unique_players = set()
        if os.path.exists(log_dir):
            latest_log = os.path.join(log_dir, "latest.log")
            if os.path.exists(latest_log):
                with open(latest_log, 'r', encoding='utf-8', errors='ignore') as f:
                    for line in f:
                        m = re.search(r'UUID of player (\S+) is (\S+)', line)
                        if m:
                            name = m.group(1).strip('"')
                            unique_players.add(name)
            for fname in os.listdir(log_dir):
                if fname.endswith('.log.gz'):
                    try:
                        with gzip.open(os.path.join(log_dir, fname), 'rt', encoding='utf-8', errors='ignore') as f:
                            for line in f:
                                m = re.search(r'UUID of player (\S+) is (\S+)', line)
                                if m:
                                    unique_players.add(m.group(1))
                    except:
                        pass
        info["player_count"] = len(unique_players)
    except:
        pass

    return info
