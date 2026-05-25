import eel
import sys
import os
import subprocess
import threading
import requests
import re
import shutil
import json
import datetime
import time
import psutil
import zipfile
import webbrowser 
import hashlib  # SHA-256 암호화를 위한 라이브러리
from PIL import Image, ImageDraw
import pystray
import uuid
import secrets
import tkinter as tk
from tkinter import filedialog
import threading

# WebSocket 클라이언트 IP 추적용 스레드 로컬 저장소
_client_ip_local = threading.local()

# Eel의 _process_message를 후킹하여 클라이언트 IP 캡처
original_process_message = eel._process_message

def patched_process_message(message, ws):
    try:
        environ = ws.environ if hasattr(ws, 'environ') else {}
        _client_ip_local.value = environ.get('REMOTE_ADDR', 'unknown')
    except:
        _client_ip_local.value = 'unknown'
    return original_process_message(message, ws)

eel._process_message = patched_process_message

eel.init('web')

# 전역 Tkinter 인스턴스 (다이얼로그용 루프 방지)
root = tk.Tk()
root.withdraw()
root.attributes("-topmost", True) # 다이얼로그가 항상 위에 뜨도록 설정

@eel.expose
def select_local_world_folder_py(token):
    if not is_auth_verified(token): return None
    # 마인크래프트 기본 세이브 경로를 초기 경로로 설정
    initial_dir = os.path.join(os.environ.get('APPDATA', ''), '.minecraft', 'saves')
    if not os.path.exists(initial_dir):
        initial_dir = os.path.expanduser("~") # 경로 없으면 사용자 홈 폴더
        
    folder_selected = filedialog.askdirectory(initialdir=initial_dir, title="Select Minecraft World Folder")
    return folder_selected if folder_selected else None

# 전역 변수
AYA_VERSION = "4.0.0"
AYA_BASE = "AYA_data"
DEFAULT_JAVA = "java"
BASE_SERVERS_DIR = os.path.join(AYA_BASE, "servers")
BACKUP_ROOT_DIR = os.path.join(AYA_BASE, "backup")
CONFIG_DIR = os.path.join(AYA_BASE, "config")
LAUNCHER_CONFIG_FILE = os.path.join(CONFIG_DIR, "launcher_config.json")
REMOTE_KEY_FILE = os.path.join(CONFIG_DIR, "launcher_remote.key")
ACCESS_LOG_FILE = os.path.join(CONFIG_DIR, "access.log")
LANG_DIR = os.path.join(AYA_BASE, "languages")

active_processes = {}
server_logs = {}
current_view_server = None 
server_players = {}
last_backup_times = {}

# [보안 상태 제어 변수]
# F12 우회 원천 차단을 위해 백엔드 세션 인증 플래그 도입
authenticated_sessions = {}  # token -> id mapping
failed_attempts_per_ip = {}  # IP별 타임스탬프 목록 (Rate Limiting)
LOCAL_TOKEN = secrets.token_hex(16)  # 로컬 접속 전용 일회성 보안 토큰

# AYA_data 베이스 폴더 생성
if not os.path.exists(AYA_BASE):
    os.makedirs(AYA_BASE)

# ==========================================================
# 레거시 마이그레이션: 기존 루트 폴더 → AYA_data/ 로 이동
# ==========================================================
_legacy_migrations = [
    ("servers", BASE_SERVERS_DIR),
    ("backup", BACKUP_ROOT_DIR),
    ("config", CONFIG_DIR),
    ("languages", LANG_DIR),
]
for old_name, new_path in _legacy_migrations:
    if os.path.exists(old_name) and not os.path.exists(new_path):
        try:
            shutil.move(old_name, new_path)
        except:
            pass

# config 폴더 생성
if not os.path.exists(CONFIG_DIR):
    os.makedirs(CONFIG_DIR)
legacy_config = "launcher_config.json"
legacy_key = "launcher_remote.key"
if os.path.exists(legacy_config) and not os.path.exists(LAUNCHER_CONFIG_FILE):
    try: shutil.move(legacy_config, LAUNCHER_CONFIG_FILE)
    except: pass
if os.path.exists(legacy_key) and not os.path.exists(REMOTE_KEY_FILE):
    try: shutil.move(legacy_key, REMOTE_KEY_FILE)
    except: pass

# ==========================================================
# PyInstaller exe 번들 리소스 경로 해석 + 상세 플러그인 리소스 초기화
# ==========================================================
DETAIL_PLUGIN_DIR = os.path.join(AYA_BASE, "Detail plugin")
DETAIL_LANG_DIR = os.path.join(DETAIL_PLUGIN_DIR, "languages")

def resource_path(relative_path):
    try:
        base_path = sys._MEIPASS
    except AttributeError:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)

# 번들된 Detail plugin 리소스를 설정 폴더로 추출 (exe 최초 실행 시)
if not os.path.exists(DETAIL_PLUGIN_DIR):
    try:
        os.makedirs(DETAIL_LANG_DIR, exist_ok=True)
        bundled_jar = resource_path(os.path.join("Detail plugin", "AYAdetail-1.0-SNAPSHOT.jar"))
        if os.path.exists(bundled_jar):
            shutil.copy(bundled_jar, os.path.join(DETAIL_PLUGIN_DIR, "AYAdetail-1.0-SNAPSHOT.jar"))
        bundled_lang = resource_path(os.path.join("Detail plugin languages"))
        if os.path.exists(bundled_lang):
            for f in os.listdir(bundled_lang):
                shutil.copy(os.path.join(bundled_lang, f), os.path.join(DETAIL_LANG_DIR, f))
    except:
        pass
else:
    os.makedirs(DETAIL_LANG_DIR, exist_ok=True)

# 번들된 언어팩(languages/) 을 설정 폴더로 추출 (ko/en 외 추가 언어팩)
try:
    bundled_lang_root = resource_path("languages")
    if os.path.exists(bundled_lang_root):
        if not os.path.exists(LANG_DIR):
            os.makedirs(LANG_DIR)
        for f in os.listdir(bundled_lang_root):
            if f.endswith(".json"):
                target = os.path.join(LANG_DIR, f)
                if not os.path.exists(target):
                    shutil.copy(os.path.join(bundled_lang_root, f), target)
except:
    pass

# update.exe 를 AYA_data/ 로 자동 복사 (최초 실행 시)
try:
    bundled_update = resource_path("update.exe")
    update_target = os.path.join(AYA_BASE, "update.exe")
    if os.path.exists(bundled_update) and not os.path.exists(update_target):
        shutil.copy(bundled_update, update_target)
except:
    pass

# 접속 기록 로그
access_logs = []

def get_client_ip():
    return getattr(_client_ip_local, 'value', 'unknown')

def add_access_log(action, result, detail=""):
    now = datetime.datetime.now()
    timestamp = now.strftime("%H:%M:%S")
    ip = get_client_ip()
    entry = {
        "time": timestamp,
        "ip": ip,
        "action": action,
        "result": result,
        "detail": detail
    }
    access_logs.append(entry)
    try:
        with open(ACCESS_LOG_FILE, 'a', encoding='utf-8') as f:
            f.write(json.dumps(entry, ensure_ascii=False) + '\n')
    except:
        pass

# [기본 언어 데이터]
DEFAULT_TRANSLATIONS = {
    "ko": {
        "title_launcher": "SERVER<br>LAUNCHER", "btn_new_server": "새 서버", "msg_select_server": "서버를 선택하세요",
        "tab_dashboard": "대시보드", "tab_env": "서버 관리", "tab_players": "플레이어 관리", "tab_broadcast": "📢 광고/공지", "tab_settings": "전체 설정", "tab_info": "ℹ️ 서버 정보", "tab_danger": "⛔ 위험 구간",
        "card_player": "Player", "card_status": "Status", "ph_cmd_input": "명령어 입력...", "btn_start": "서버 시작", "btn_stop": "서버 종료", "btn_restart": "재시작",
        "title_time": "⏰ 시간 제어", "env_morning": "아침", "env_noon": "점심", "env_evening": "저녁", "env_night": "밤",
        "title_weather": "🌥️ 날씨 제어", "env_clear": "맑음", "env_rain": "비", "env_thunder": "폭풍우", "env_lock": "날씨 고정",
        "title_player_list": "접속자 목록", "btn_whitelist": "화이트리스트 관리", "btn_banlist": "차단 목록 관리", "btn_ip_banlist": "IP 차단 관리", "msg_no_players": "접속 중인 플레이어가 없습니다.",
        "title_broadcast": "📢 광고 / 공지 보내기", "desc_broadcast": "서버에 접속한 모든 플레이어에게 메시지를 띄웁니다.",
        "lbl_bc_title": "🖥️ 화면 중앙 타이틀 (Title)", "desc_bc_title": "가장 크게 보이는 제목입니다.",
        "lbl_bc_subtitle": "📝 서브 타이틀 (Subtitle)", "desc_bc_subtitle": "타이틀 아래에 작게 나오는 설명입니다. (타이틀과 함께 보낼 때 사용)",
        "lbl_bc_actionbar": "💬 액션 바 (Actionbar)", "desc_bc_actionbar": "아이템 슬롯 위에 작게 뜨는 메시지입니다.",
        "btn_bc_send": "보내기 (Send)", "btn_bc_set": "설정 (Set)", "btn_bc_clear": "지우기",
        "btn_save_settings": "💾 설정 저장하기", "title_backup": "💾 백업 설정", "set_auto_backup": "자동 백업 활성화", "set_backup_interval": "백업 주기 (분)",
        "btn_backup_now": "지금 백업하기", "title_java": "☕ Java 설정", "set_java_path": "실행 경로 (java.exe)", "msg_java_tip": "* 1.18 이상은 Java 17+, 그 이하는 Java 8 권장",
        "title_general": "📝 일반 설정", "set_motd": "서버 이름 (MOTD)", "set_server_port": "서버 포트", "set_server_ip": "서버 IP", "set_max_players": "최대 인원",
        "set_online_mode": "정품 인증 (Online Mode)", "set_white_list": "화이트리스트 사용", "set_enforce_whitelist": "화이트리스트 강제",
        "title_performance": "🚀 성능 및 네트워크", "set_ram": "메모리 할당", "set_view_distance": "시야 거리", "set_simulation_distance": "연산 거리",
        "set_max_tick_time": "최대 틱 시간", "set_network_compression_threshold": "네트워크 압축 임계값", "set_rate_limit": "패킷 제한",
        "set_use_native_transport": "네이티브 전송 사용", "set_enable_status": "상태 표시 활성화", "set_broadcast_rcon_to_ops": "RCON 로그 방송", "set_broadcast_console_to_ops": "콘솔 로그 방송",
        "title_world": "🌍 월드 및 생성", "set_level_name": "월드 폴더명", "set_level_seed": "월드 시드", "set_level_type": "월드 타입", "set_generator_settings": "생성기 설정",
        "set_max_world_size": "월드 최대 크기", "set_allow_nether": "네더(지옥) 허용", "set_generate_structures": "구조물 생성",
        "title_gameplay": "🎮 게임 플레이", "set_gamemode": "기본 게임모드", "set_force_gamemode": "게임모드 강제", "set_difficulty": "난이도",
        "set_hardcore": "하드코어", "set_pvp": "PVP 허용", "set_allow_flight": "비행 허용", "set_spawn_monsters": "몬스터 스폰", "set_spawn_animals": "동물 스폰",
        "set_spawn_npcs": "NPC 스폰", "set_spawn_protection": "스폰 보호 구역", "set_enable_command_block": "커맨드 블록 허용", "set_player_idle_timeout": "잠수 추방 시간 (분)",
        "title_security": "🔒 보안 및 기타", "set_op_permission_level": "OP 권한 레벨", "set_log_ips": "IP 기록", "set_enforce_secure_profile": "보안 프로필 강제",
        "set_prevent_proxy_connections": "프록시 연결 방지", "set_resource_pack": "리소스팩 URL", "set_require_resource_pack": "리소스팩 강제",
        "set_enable_rcon": "RCON 활성화", "set_rcon_port": "RCON 포트", "set_rcon_password": "RCON 비밀번호", "set_enable_query": "Query 활성화", "set_query_port": "Query 포트",
        "set_sync_chunk_writes": "청크 동기화 저장", "set_enable_jmx_monitoring": "JMX 모니터링", "set_entity_broadcast_range_percentage": "엔티티 방송 범위(%)",
        "set_max_chained_neighbor_updates": "최대 이웃 업데이트", "set_region_file_compression": "청크 압축 방식", "set_accepts_transfers": "서버 이동 허용",
        "set_bug_report_link": "버그 리포트 링크", "set_initial_enabled_packs": "초기 활성 팩", "set_initial_disabled_packs": "초기 비활성 팩", "set_debug": "디버그 모드",
        "title_folder_check": "📂 파일 위치 확인", "desc_folder_check": "서버 파일이나 백업 파일이 저장된 실제 폴더를 엽니다.", "btn_open_server_folder": "📂 서버 폴더 열기", "btn_open_backup_folder": "💾 백업 폴더 열기",
        "title_danger": "🚫 서버 삭제 (Danger Zone)", "msg_danger": "현재 서버를 영구 삭제합니다. 복구할 수 없습니다.", "btn_delete_server": "🗑️ 서버 영구 삭제",
        "modal_p_join": "접속 시간", "modal_p_status": "상태", "btn_whisper": "💬 귓속말 (Whisper)", "btn_tp": "🚀 이동 (TP)",
        "act_op": "관리자 (OP)", "act_deop": "권한 해제 (DEOP)", "act_kick": "추방 (KICK)", "act_ban": "차단 (BAN)", "btn_close": "닫기",
        "modal_whisper_title": "💬 귓속말 보내기", "modal_tp_title": "🚀 텔레포트 (TP)", "msg_tp_ask": "누구에게 이동하시겠습니까?", "msg_tp_empty": "이동할 상대가 없습니다.",
        "modal_ban_opt_title": "🚫 차단 옵션 선택", "msg_ban_opt": "어떤 방식으로 차단하시겠습니까?", "btn_ban_name": "닉네임 차단 (Name Ban)", "btn_ban_ip": "IP 차단 (IP Ban)", "btn_ban_both": "둘 다 차단 (Both)",
        "btn_cancel": "취소", "btn_confirm": "확인", "btn_create": "생성", "btn_save": "저장", "btn_delete": "제거", "btn_add": "추가",
        "modal_confirm_title": "⚠️ 실행 확인", "modal_list_title": "목록 관리", "ph_nickname": "닉네임 / IP 입력",
        "modal_new_title": "✨ 새 서버 생성", "modal_new_name": "서버 이름", "modal_new_ver": "버전", "modal_setting_title": "⚙️ 런처 설정", "modal_setting_lang": "언어 (Language)", "modal_setting_mirror": "미러 URL",
        "modal_del_title": "🚫 정말 삭제하시겠습니까?", "modal_del_msg": "선택된 서버: ", "modal_eula_title": "⚖️ EULA 동의", "msg_eula_content": "마인크래프트 서버를 생성하려면<br>Mojang의 EULA(최종 사용자 라이선스 계약)에<br>동의해야 합니다.",
        "btn_agree": "동의합니다", "btn_disagree": "거절", "msg_cannot_close": "⚠️ 서버가 실행 중입니다! 먼저 서버를 종료해주세요.",
        "diff_peaceful": "평화로움", "diff_easy": "쉬움", "diff_normal": "보통", "diff_hard": "어려움",
        "modal_restart_title": "🔄 서버 재시작 확인", "msg_restart_confirm": "정말 서버를 다시 시작하시겠습니까?<br>(종료 후 다시 시작됩니다)",
        "title_server_info": "ℹ️ 서버 정보", "info_created": "생성 일자", "info_source": "다운로드 출처", "info_size": "디스크 사용량", "info_java": "Java 버전/경로", "info_players": "방문한 플레이어 수",
        "remote_nav_btn": "🌐 원격 연결 제어 관리", "remote_modal_title": "🌐 원격 연결 (베타)", "remote_modal_desc": "타 PC나 모바일 웹브라우저에서 이 런처에 접속하여 원격으로 제어할 수 있도록 도와줍니다.", "remote_addr_label": "내 외부 원격 접속 주소",
        "remote_enable_label": "원격 제어 활성화", "remote_restart_needed": "(재시작 필요)", "remote_pw_label": "새 원격 비밀번호 설정", "remote_pw_placeholder": "새 비밀번호 입력 (빈 칸 입력 시 변경 없음)",
        "remote_pw_warning": "* 안전한 환경을 위해 비밀번호 설정을 권장합니다.", "restart_title": "런처 재시작 안내", "restart_desc": "원격 제어 설정 변경을 적용하기 위해 <b>프로그램을 재시작합니다.</b><br>확인 버튼을 누르거나 잠시 기다려 주세요.",
        "restart_btn_text": "확인 및 재시작", "security_warning_banner": "보안 경고: 원격 제어용 비밀번호가 설정되어 있지 않습니다!", "btn_go_to_settings": "비밀번호 설정하러 가기",
        "remote_lock_title": "원격 제어 잠금", "remote_lock_desc": "이 컴퓨터는 원격 제어 보안 모드가 켜져 있습니다.", "remote_auth_pw_label": "인증 비밀번호 입력", "remote_auth_pw_placeholder": "비밀번호를 입력하세요",
        "remote_remember_pw": "암호 기억하기 (비추천)", "btn_authenticate": "인증하기",
        "remote_ip_warning": "⚠️ 주의: 외부 접속 주소와 비밀번호가 유출되면 타인이 이 서버를 제어할 수 있습니다. 신뢰할 수 없는 사람에게는 절대 주소를 공유하지 마세요!",
        "remote_enabled_banner": "⚠️ 원격제어가 활성화되어 있습니다. 외부에서의 비인가 접근 등 혹시 모를 위험에 항상 주의하세요."
    },
    "en": {
        "title_launcher": "SERVER<br>LAUNCHER", "btn_new_server": "New Server", "msg_select_server": "Select a server",
        "tab_dashboard": "Dashboard", "tab_env": "Manage Server", "tab_players": "Manage Players", "tab_broadcast": "📢 Broadcast", "tab_settings": "Settings", "tab_info": "ℹ️ Server Info", "tab_danger": "⛔ Danger Zone",
        "card_player": "Player", "card_status": "Status", "ph_cmd_input": "Enter command...", "btn_start": "Start Server", "btn_stop": "Stop Server", "btn_restart": "Restart",
        "title_time": "⏰ Time Control", "env_morning": "Morning", "env_noon": "Noon", "env_evening": "Evening", "env_night": "Night",
        "title_weather": "🌥️ Weather Control", "env_clear": "Clear", "env_rain": "Rain", "env_thunder": "Thunder", "env_lock": "Lock Weather",
        "title_player_list": "Player List", "btn_whitelist": "Manage Whitelist", "btn_banlist": "Manage Banlist", "btn_ip_banlist": "Manage IP Bans", "msg_no_players": "No players online.",
        "title_broadcast": "📢 Send Broadcast", "desc_broadcast": "Display a message to all players on the server.",
        "lbl_bc_title": "🖥️ Title", "desc_bc_title": "Large text in the center of the screen.",
        "lbl_bc_subtitle": "📝 Subtitle", "desc_bc_subtitle": "Small text under the title.",
        "lbl_bc_actionbar": "💬 Actionbar", "desc_bc_actionbar": "Small message above the item slots.",
        "btn_bc_send": "Send", "btn_bc_set": "Set", "btn_bc_clear": "Clear",
        "btn_save_settings": "💾 Save Settings", "title_backup": "💾 Backup Settings", "set_auto_backup": "Enable Auto Backup", "set_backup_interval": "Backup Interval (min)",
        "btn_backup_now": "Backup Now", "title_java": "☕ Java Settings", "set_java_path": "Executable Path (java.exe)", "msg_java_tip": "* Java 17+ for 1.18+, Java 8 for older versions",
        "title_general": "📝 General Settings", "set_motd": "Server Name (MOTD)", "set_server_port": "Server Port", "set_server_ip": "Server IP", "set_max_players": "Max Players",
        "set_online_mode": "Online Mode", "set_white_list": "Whitelist", "set_enforce_whitelist": "Enforce Whitelist",
        "title_performance": "🚀 Performance & Network", "set_ram": "RAM Allocation", "set_view_distance": "View Distance", "set_simulation_distance": "Simulation Distance",
        "set_max_tick_time": "Max Tick Time", "set_network_compression_threshold": "Network Compression Threshold", "set_rate_limit": "Packet Rate Limit",
        "set_use_native_transport": "Use Native Transport", "set_enable_status": "Enable Status", "set_broadcast_rcon_to_ops": "Broadcast RCON to OPs", "set_broadcast_console_to_ops": "Broadcast Console to OPs",
        "title_world": "🌍 World Generation", "set_level_name": "Level Name", "set_level_seed": "Level Seed", "set_level_type": "Level Type", "set_generator_settings": "Generator Settings",
        "set_max_world_size": "Max World Size", "set_allow_nether": "Allow Nether", "set_generate_structures": "Generate Structures",
        "title_gameplay": "🎮 Gameplay", "set_gamemode": "Default Gamemode", "set_force_gamemode": "Force Gamemode", "set_difficulty": "Difficulty",
        "set_hardcore": "Hardcore", "set_pvp": "Allow PVP", "set_allow_flight": "Allow Flight", "set_spawn_monsters": "Spawn Monsters", "set_spawn_animals": "Spawn Animals",
        "set_spawn_npcs": "Spawn NPCs", "set_spawn_protection": "Spawn Protection", "set_enable_command_block": "Enable Command Blocks", "set_player_idle_timeout": "Idle Timeout (min)",
        "title_security": "🔒 Security & Misc", "set_op_permission_level": "OP Permission Level", "set_log_ips": "Log IPs", "set_enforce_secure_profile": "Enforce Secure Profile",
        "set_prevent_proxy_connections": "Prevent Proxy Connections", "set_resource_pack": "Resource Pack URL", "set_require_resource_pack": "Require Resource Pack",
        "set_enable_rcon": "Enable RCON", "set_rcon_port": "RCON Port", "set_rcon_password": "RCON Password", "set_enable_query": "Enable Query", "set_query_port": "Query Port",
        "set_sync_chunk_writes": "Sync Chunk Writes", "set_enable_jmx_monitoring": "JMX Monitoring", "set_entity_broadcast_range_percentage": "Entity Broadcast Range (%)",
        "set_max_chained_neighbor_updates": "Max Chained Neighbor Updates", "set_region_file_compression": "Region File Compression", "set_accepts_transfers": "Accept Transfers",
        "set_bug_report_link": "Bug Report Link", "set_initial_enabled_packs": "Initial Enabled Packs", "set_initial_disabled_packs": "Initial Disabled Packs", "set_debug": "Debug Mode",
        "title_folder_check": "📂 Check Folder", "desc_folder_check": "Open the actual folder where server or backup files are saved.", "btn_open_server_folder": "📂 Open Server Folder", "btn_open_backup_folder": "💾 Open Backup Folder",
        "title_danger": "🚫 Delete Server (Danger Zone)", "msg_danger": "Permanently delete the current server. Cannot be undone.", "btn_delete_server": "🗑️ Delete Server",
        "modal_p_join": "Joined At", "modal_p_status": "Status", "btn_whisper": "💬 Whisper", "btn_tp": "🚀 TP",
        "act_op": "OP", "act_deop": "DEOP", "act_kick": "KICK", "act_ban": "BAN", "btn_close": "Close",
        "modal_whisper_title": "💬 Send Whisper", "modal_tp_title": "🚀 텔레포트 (TP)", "msg_tp_ask": "누구에게 이동하시겠습니까?", "msg_tp_empty": "이동할 상대가 없습니다.",
        "modal_ban_opt_title": "🚫 Ban Options", "msg_ban_opt": "How would you like to ban?", "btn_ban_name": "Name Ban", "btn_ban_ip": "IP Ban", "btn_ban_both": "Both",
        "btn_cancel": "Cancel", "btn_confirm": "Confirm", "btn_create": "Create", "btn_save": "Save", "btn_delete": "Delete", "btn_add": "Add",
        "modal_confirm_title": "⚠️ Confirm Execution", "modal_list_title": "Manage List", "ph_nickname": "Enter Nickname / IP",
        "modal_new_title": "✨ Create New Server", "modal_new_name": "Server Name", "modal_new_ver": "Version", "modal_setting_title": "⚙️ 런처 설정", "modal_setting_lang": "Language", "modal_setting_mirror": "Mirror URL",
        "modal_del_title": "🚫 Are you sure?", "modal_del_msg": "Selected Server: ", "modal_eula_title": "⚖️ EULA Agreement", "msg_eula_content": "To create a Minecraft server, you must agree to Mojang's EULA.",
        "btn_agree": "I Agree", "btn_disagree": "Decline", "msg_cannot_close": "⚠️ Server is running! Please stop the server first.",
        "diff_peaceful": "Peaceful", "diff_easy": "Easy", "diff_normal": "Normal", "diff_hard": "Hard",
        "modal_restart_title": "🔄 Restart Confirmation", "msg_restart_confirm": "Are you sure you want to restart the server?\n(It will stop and start again)",
        "title_server_info": "ℹ️ Server Info", "info_created": "Created At", "info_source": "Source", "info_size": "Disk Usage", "info_java": "Java Ver/Path", "info_players": "Total Players Visitors",
        "remote_nav_btn": "🌐 Remote Access Management", "remote_modal_title": "🌐 Remote Access (Beta)", "remote_modal_desc": "Control this launcher remotely from other PCs or mobile browsers.", "remote_addr_label": "External Access Address",
        "remote_enable_label": "Enable Remote Control", "remote_restart_needed": "(Restart Required)", "remote_pw_label": "Set New Remote Password", "remote_pw_placeholder": "Enter new password (leave blank to keep current)",
        "remote_pw_warning": "* Password is highly recommended for security.", "restart_title": "Launcher Restarting", "restart_desc": "Applying remote settings... <b>The launcher will restart.</b><br>Please wait or click the button.",
        "restart_btn_text": "Confirm and Restart", "security_warning_banner": "Security Warning: Remote password is not set!", "btn_go_to_settings": "Go to Settings",
        "remote_lock_title": "Remote Access Locked", "remote_lock_desc": "This computer is in remote security mode.", "remote_auth_pw_label": "Enter Password", "remote_auth_pw_placeholder": "Enter your password",
        "remote_remember_pw": "Remember Password (Not Recommended)", "btn_authenticate": "Authenticate",
        "remote_ip_warning": "⚠️ Caution: If your access address and password leak, others could control your server. Never share them with untrusted individuals!",
        "remote_enabled_banner": "⚠️ Remote control is active. Always be cautious of unknown risks such as unauthorized access."
    }
}

# ==========================================================
# [보안 검증 헬퍼 함수]
# 개발자 도구(F12) 우회 및 무력화 방지를 위한 서버 측 2차 권한 검증 수립
# ==========================================================
def is_auth_verified(token):
    # 1. 로컬 토큰 확인
    if token == LOCAL_TOKEN:
        return True
    
    # 2. 인증된 세션 토큰 확인
    # (이미 이 리스트에 있다면 이전에 비밀번호 검증을 통과한 유효한 세션임)
    return token in authenticated_sessions

# ==========================================================
# [기능] 시스템 초기화
# ==========================================================
@eel.expose
def init_system_py(token):
    # 시스템 초기화 시에도 최소한의 세션 검증 수행
    # (로컬 클라이언트는 토큰이 있으므로 통과, 외부 클라이언트는 인증 전까지 차단)
    if not is_auth_verified(token): return
    
    # 시스템 초기화 시에는 최소한의 디렉토리 구성만 수행
    if not os.path.exists(BASE_SERVERS_DIR): os.makedirs(BASE_SERVERS_DIR)
    if not os.path.exists(BACKUP_ROOT_DIR): os.makedirs(BACKUP_ROOT_DIR)
    first_run = False
    if not os.path.exists(LAUNCHER_CONFIG_FILE):
        first_run = True
        with open(LAUNCHER_CONFIG_FILE, 'w', encoding='utf-8') as f:
            json.dump({
                "version": AYA_VERSION,
                "language": "ko", 
                "mirror_url": "https://api.purpurmc.org/v2/purpur",
                "remote_enabled": False  # 원격 활성 제어 설정 초기화
            }, f, indent=4)
    if not os.path.exists(LANG_DIR): os.makedirs(LANG_DIR)
    
    # 글로벌 자바 설정 로드
    load_global_java_setting()
    
    for lang_code, default_data in DEFAULT_TRANSLATIONS.items():
        lang_file = os.path.join(LANG_DIR, f"{lang_code}.json")
        final_data = default_data.copy()
        if os.path.exists(lang_file):
            try:
                with open(lang_file, 'r', encoding='utf-8') as f:
                    existing_data = json.load(f)
                    final_data.update(existing_data)
                    for k, v in default_data.items():
                        if k not in final_data: final_data[k] = v
            except: pass
        with open(lang_file, 'w', encoding='utf-8') as f:
            json.dump(final_data, f, indent=4, ensure_ascii=False)
            
    return first_run

@eel.expose
def get_launcher_config_py(token):
    # 인증 여부 먼저 확인
    authenticated = is_auth_verified(token)
    
    # 1. 인증되지 않은 경우 (최초 접속 혹은 세션 만료)
    if not authenticated:
        try:
            if os.path.exists(LAUNCHER_CONFIG_FILE):
                with open(LAUNCHER_CONFIG_FILE, 'r', encoding='utf-8') as f:
                    full_conf = json.load(f)
                    return {
                        "remote_enabled": full_conf.get("remote_enabled", False),
                        "is_authenticated": False
                    }
        except: pass
        return {"remote_enabled": False, "is_authenticated": False}

    # 2. 인증된 경우 전체 설정 반환
    if os.path.exists(LAUNCHER_CONFIG_FILE):
        try:
            with open(LAUNCHER_CONFIG_FILE, 'r', encoding='utf-8') as f:
                conf = json.load(f)
                conf["remote_key_exists"] = os.path.exists(REMOTE_KEY_FILE)
                conf["is_authenticated"] = True
                return conf
        except: pass
    return {
        "language": "ko", 
        "mirror_url": "https://api.papermc.io/v2/projects/paper", 
        "remote_enabled": False, 
        "remote_key_exists": os.path.exists(REMOTE_KEY_FILE),
        "is_authenticated": True
    }

@eel.expose
def save_launcher_config_py(token, data):
    if not is_auth_verified(token): return "❌ Unauthorized"
    try:
        current = {}
        if os.path.exists(LAUNCHER_CONFIG_FILE):
            with open(LAUNCHER_CONFIG_FILE, 'r', encoding='utf-8') as f:
                current = json.load(f)
        
        current.update(data)
        
        with open(LAUNCHER_CONFIG_FILE, 'w', encoding='utf-8') as f: json.dump(current, f, indent=4)
        return "✅ 저장 완료"
    except: return "❌ 실패"

@eel.expose
def get_available_languages_py(token):
    langs = []
    if os.path.exists(LANG_DIR):
        for f in sorted(os.listdir(LANG_DIR)):
            if f.endswith('.json'):
                code = f[:-5]
                langs.append({"code": code, "name": code})
    return langs

@eel.expose
def get_translation_py(token, lang_code):
    # 번역 정보는 비교적 안전하므로 검증 제외 혹은 기본 검증만 수행
    file_path = os.path.join(LANG_DIR, f"{lang_code}.json")
    if os.path.exists(file_path):
        try:
            with open(file_path, 'r', encoding='utf-8') as f: return json.load(f)
        except: pass
    return DEFAULT_TRANSLATIONS.get(lang_code, {})

@eel.expose
def get_current_server_py(token):
    if not is_auth_verified(token): return None
    return current_view_server

@eel.expose
def try_close_app_py(token):
    if not is_auth_verified(token): return "blocked"
    for name, p in active_processes.items():
        if p.poll() is None:
            return "blocked"
    return "ok"

# ==========================================================
# [추가] 원격 제어 (베타) 관련 Python 함수
# ==========================================================
@eel.expose
def save_remote_setting_py(token, enabled, raw_password):
    if not is_auth_verified(token): return "❌ Unauthorized"
    try:
        # 1. 런처 일반 환경설정에 원격 온오프 상태 저장
        config = get_launcher_config_py(token)
        config["remote_enabled"] = enabled
        
        # 권한 상태 임시 업데이트 허용
        # (세션은 재시작 시 자동으로 초기화되므로 즉시 클리어하지 않음)
            
        # 설정 저장 수행
        try:
            current = {}
            if os.path.exists(LAUNCHER_CONFIG_FILE):
                with open(LAUNCHER_CONFIG_FILE, 'r', encoding='utf-8') as f:
                    current = json.load(f)
            current.update(config)
            with open(LAUNCHER_CONFIG_FILE, 'w', encoding='utf-8') as f: 
                json.dump(current, f, indent=4)
        except:
            return "❌ 저장 실패"

        # 2. 패스워드가 입력되었을 경우 SHA-256 방식으로 엄격 암호화하여 저장
        if raw_password and raw_password.strip() != "":
            hashed_pw = hashlib.sha256(raw_password.encode('utf-8')).hexdigest()
            with open(REMOTE_KEY_FILE, 'w', encoding='utf-8') as f:
                f.write(hashed_pw)

        # 3. 원격 제어를 끄면 모든 세션 브라우저에 새로고침 신호 전송
        if not enabled:
            try:
                eel.remote_refresh_js()()
            except:
                pass
        
        action = "Remote Disable" if not enabled else "Remote Config Change"
        add_access_log(action, "success")
        return "✅ Remote config saved"
    except Exception as e:
        add_access_log("Remote Config Change", "error", str(e))
        return f"❌ Error: {e}"

@eel.expose
def get_access_logs_py(token):
    if not is_auth_verified(token): return []
    logs = []
    try:
        if os.path.exists(ACCESS_LOG_FILE):
            with open(ACCESS_LOG_FILE, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if line:
                        try:
                            logs.append(json.loads(line))
                        except:
                            pass
    except:
        pass
    return list(reversed(logs[-500:]))

@eel.expose
def log_access_blocked_py(token):
    ip = get_client_ip()
    add_access_log("Page Access", "blocked", "Unauthenticated session")
    return "ok"

@eel.expose
def verify_remote_password_py(token, raw_password):
    now = time.time()
    client_ip = getattr(_client_ip_local, 'value', 'unknown')
    global failed_attempts_per_ip

    if client_ip not in failed_attempts_per_ip:
        failed_attempts_per_ip[client_ip] = []
    attempts = [t for t in failed_attempts_per_ip[client_ip] if now - t < 300]
    failed_attempts_per_ip[client_ip] = attempts
    remaining = max(0, 5 - len(attempts))

    if len(attempts) >= 5:
        add_access_log("Password Auth", "blocked", "IP blocked (5+ attempts)")
        return {"success": False, "remaining": 0, "token": None}

    config = get_launcher_config_py(token)
    if not config.get("remote_enabled", False):
        return {"success": False, "remaining": remaining, "token": None}

    if not os.path.exists(REMOTE_KEY_FILE):
        add_access_log("Password Auth", "fail", "Password file not found")
        return {"success": False, "remaining": remaining, "token": None}

    try:
        with open(REMOTE_KEY_FILE, 'r', encoding='utf-8') as f:
            stored_hashed = f.read().strip()

        input_hashed = hashlib.sha256(raw_password.encode('utf-8')).hexdigest()
        success = (input_hashed == stored_hashed)
        if success:
            new_token = secrets.token_hex(16)
            authenticated_sessions[new_token] = True
            add_access_log("Password Auth", "success", "Remote access authenticated")
            return {"success": True, "remaining": remaining, "token": new_token}
        failed_attempts_per_ip[client_ip].append(now)
        remaining = max(0, 5 - len(failed_attempts_per_ip[client_ip]))
        add_access_log("Password Auth", "fail", f"Wrong password (attempts left: {remaining})")
        return {"success": False, "remaining": remaining, "token": None}
    except:
        add_access_log("Password Auth", "error", "Auth exception")
        return {"success": False, "remaining": remaining, "token": None}

# ==========================================================
# [기능] 서버 관련
# ==========================================================
@eel.expose
def get_server_list_py(token):
    if not is_auth_verified(token): return []
    if not os.path.exists(BASE_SERVERS_DIR): os.makedirs(BASE_SERVERS_DIR)
    server_list = []
    try:
        for name in os.listdir(BASE_SERVERS_DIR):
            full_path = os.path.join(BASE_SERVERS_DIR, name)
            if os.path.isdir(full_path):
                status = "Ready"
                if name in active_processes and active_processes[name].poll() is None: status = "Running"
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
    if not is_auth_verified(token): return "❌ Unauthorized"
    global current_view_server
    current_view_server = server_name
    if server_name in server_logs: eel.restore_logs_js(server_logs[server_name][-1000:])()
    else: eel.restore_logs_js([])()
    is_running = False
    if server_name in active_processes and active_processes[server_name].poll() is None: is_running = True
    eel.update_status_js(is_running)
    update_ui_player_list(server_name)
    return f"Load: {server_name}"

@eel.expose
def get_papermc_versions_py(token):
    if not is_auth_verified(token): return []
    try:
        mirror_url = "https://api.papermc.io/v2/projects/paper"
        if os.path.exists(LAUNCHER_CONFIG_FILE):
            with open(LAUNCHER_CONFIG_FILE, 'r', encoding='utf-8') as f:
                conf = json.load(f)
                mirror_url = conf.get("mirror_url", mirror_url).strip().rstrip('/')

        headers = {'User-Agent': 'Mozilla/5.0'}
        
        if "purpurmc.org" in mirror_url:
            r = requests.get(mirror_url, headers=headers, timeout=3)
            if r.status_code == 200:
                return r.json().get("versions", [])[::-1]
        else:
            r = requests.get(mirror_url, headers=headers, timeout=3)
            if r.status_code == 200:
                return r.json().get("versions", [])[::-1]

    except: pass
    return ["1.21.4", "1.21.3", "1.21.1", "1.20.4", "1.16.5", "1.12.2"]

@eel.expose
def get_manage_list_py(token, file_type):
    if not is_auth_verified(token): return []
    if not current_view_server: return []
    filename = "whitelist.json"
    if file_type == "banlist": filename = "banned-players.json"
    elif file_type == "ip-banlist": filename = "banned-ips.json"
    path = os.path.join(BASE_SERVERS_DIR, current_view_server, filename)
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
    if not is_auth_verified(token): return None
    if not current_view_server: return None
    info = { "name": player_name, "join_time": "-", "uuid": "-" }
    if current_view_server in server_players and player_name in server_players[current_view_server]:
        info.update(server_players[current_view_server][player_name])
    return info

@eel.expose
def execute_command_py(token, cmd):
    if not is_auth_verified(token):
        add_access_log("Execute Command", "blocked", f"Unauthorized: {cmd}")
        return "❌ Unauthorized"
    send_command_py(cmd)
    add_access_log("Execute Command", "success", cmd)
    return f"Cmd: {cmd}"

@eel.expose
def get_singleplayer_worlds_py(token):
    if not is_auth_verified(token): return []
    saves_path = os.path.join(os.environ.get('APPDATA', ''), '.minecraft', 'saves')
    if not os.path.exists(saves_path): return []
    try:
        return [d for d in os.listdir(saves_path) if os.path.isdir(os.path.join(saves_path, d))]
    except: return []

def copy_folder_with_progress(src, dst):
    """실시간 프로그레스를 업데이트하며 폴더 복사 (파일 단위)"""
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
        # 실시간 프로그레스 전송 (%) - "Copying World (35%)..." 형태
        percent = int((count / total) * 100)
        eel.update_download_progress_js(f"Copying World ({percent}%)...")()

@eel.expose
def create_new_server_real_py(token, server_name, version, mirror_url, custom_java_path, difficulty="normal", gamemode="survival", ram=4, world_name=None):
    if not is_auth_verified(token): return "❌ Unauthorized"
    clean = re.sub(r'[<>:"/\\|?*]', '', server_name).strip()
    if not clean: return "❌ Name Error"
    target = os.path.join(BASE_SERVERS_DIR, clean)
    if os.path.exists(target): return "⚠️ Exists"
    
    try:
        os.makedirs(target)
        headers = {'User-Agent': 'Mozilla/5.0'}
        base = mirror_url.strip().rstrip('/') if mirror_url else "https://api.papermc.io/v2/projects/paper"
        
        eel.update_download_progress_js("Checking API...")()
        
        download_url = ""
        file_name = "server.jar"

        if "purpurmc.org" in base:
            r = requests.get(f"{base}/{version}", headers=headers)
            data = r.json()
            latest_build = data['builds']['latest']
            download_url = f"{base}/{version}/{latest_build}/download"
            file_name = f"purpur-{version}-{latest_build}.jar"
        else:
            r = requests.get(f"{base}/versions/{version}", headers=headers)
            data = r.json()
            latest_build = data['builds'][-1]
            r2 = requests.get(f"{base}/versions/{version}/builds/{latest_build}", headers=headers)
            build_data = r2.json()
            actual_filename = build_data['downloads']['application']['name']
            download_url = f"{base}/versions/{version}/builds/{latest_build}/downloads/{actual_filename}"
            file_name = actual_filename

        eel.update_download_progress_js("Downloading...")()
        
        with requests.get(download_url, headers=headers, stream=True) as r:
            r.raise_for_status()
            with open(os.path.join(target, "server.jar"), 'wb') as f:
                for chunk in r.iter_content(chunk_size=8192): 
                    f.write(chunk)
                    
        with open(os.path.join(target, "eula.txt"), 'w') as f: f.write("eula=true")
        
        # 싱글플레이 월드 복사 (선택된 경우)
        if world_name:
            # [수정] 절대 경로가 전달된 경우(탐색기 선택) 그대로 사용, 아니면 기본 경로 사용
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
                "download_source": base,
                "ram_allocation": ram # RAM 설정 저장
            }, f, indent=4)
            
        # server.properties 동기화 및 생성
        try:
            props = {
                "motd": server_name, # 서버 이름과 MOTD 동기화
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
                plugin_src = os.path.join(DETAIL_PLUGIN_DIR, "AYAdetail-1.0-SNAPSHOT.jar")
                
                if os.path.exists(plugin_src):
                    plugins_dir = os.path.join(target, "plugins")
                    if not os.path.exists(plugins_dir):
                        os.makedirs(plugins_dir)
                    
                    shutil.copy(plugin_src, os.path.join(plugins_dir, "AYAdetail-1.0-SNAPSHOT.jar"))
                    
                    # 언어 파일도 함께 복사
                    if os.path.exists(DETAIL_LANG_DIR):
                        detail_data_dir = os.path.join(target, "plugins", "AYAdetail")
                        lang_target = os.path.join(detail_data_dir, "languages")
                        if not os.path.exists(lang_target):
                            os.makedirs(lang_target)
                        for f in os.listdir(DETAIL_LANG_DIR):
                            try:
                                shutil.copy(os.path.join(DETAIL_LANG_DIR, f), os.path.join(lang_target, f))
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
    if not is_auth_verified(token): return "❌ Unauthorized"
    if not current_view_server: return "❌ No Server"
    if current_view_server in active_processes: return "⚠️ Running"
    
    target = os.path.join(BASE_SERVERS_DIR, current_view_server)
    config_path = os.path.join(target, "nene_config.json")
    
    try:
        # nene_config.json에서 기존 설정 확인
        jar_name = "server.jar"
        config = {}
        if os.path.exists(config_path):
            try:
                with open(config_path, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                    jar_name = config.get("custom_jar", "server.jar")
            except: pass

        headers = {'User-Agent': 'Mozilla/5.0'}
        base = mirror_url.strip().rstrip('/') if mirror_url else "https://api.papermc.io/v2/projects/paper"
        
        download_url = ""

        # API 호출 및 다운로드 링크 확인
        if "purpurmc.org" in base:
            r = requests.get(f"{base}/{version}", headers=headers)
            data = r.json()
            latest_build = data['builds']['latest']
            download_url = f"{base}/{version}/{latest_build}/download"
        else:
            r = requests.get(f"{base}/versions/{version}", headers=headers)
            data = r.json()
            latest_build = data['builds'][-1]
            r2 = requests.get(f"{base}/versions/{version}/builds/{latest_build}", headers=headers)
            build_data = r2.json()
            actual_filename = build_data['downloads']['application']['name']
            download_url = f"{base}/versions/{version}/builds/{latest_build}/downloads/{actual_filename}"

        # 실제 다운로드 및 덮어쓰기 (기존 jar_name 유지)
        with requests.get(download_url, headers=headers, stream=True) as r:
            r.raise_for_status()
            with open(os.path.join(target, jar_name), 'wb') as f:
                for chunk in r.iter_content(chunk_size=8192): 
                    f.write(chunk)

        # nene_config.json 업데이트
        config["version"] = version
        # [수정] 빌드 업데이트 시에도 기존 커스텀 JAR 이름을 유지하도록 함
        with open(config_path, 'w', encoding='utf-8') as f:
            json.dump(config, f, indent=4)

        return f"✅ {version} ({jar_name}) 최신 빌드로 업데이트 완료"
        
    except Exception as e:
        return f"❌ 실패: {e}"

@eel.expose
def select_local_core_py(token):
    if not is_auth_verified(token): return "❌ Unauthorized"
    if not current_view_server: return "❌ No Server"
    if current_view_server in active_processes: return "⚠️ Running"
    
    # 1. 파일 선택 (JAR 전용)
    root = tk.Tk()
    root.withdraw()
    root.attributes("-topmost", True)
    
    # 현재 서버의 절대 경로를 Windows 형식에 맞게 변환
    target_dir = os.path.abspath(os.path.join(BASE_SERVERS_DIR, current_view_server))
    target_dir = os.path.normpath(target_dir)
    
    jar_path = filedialog.askopenfilename(
        title="Select Minecraft Server JAR", 
        initialdir=target_dir,
        filetypes=[("JAR files", "*.jar")]
    )
    if not jar_path: return "⚠️ Cancelled"
    
    target_dir = os.path.abspath(os.path.join(BASE_SERVERS_DIR, current_view_server))
    jar_name = os.path.basename(jar_path)
    dest_path = os.path.join(target_dir, jar_name)
    
    try:
        # 2. 파일 복사 (원본과 대상이 다른 경우에만)
        if os.path.abspath(jar_path) != os.path.abspath(dest_path):
            shutil.copy2(jar_path, dest_path)
        
        # 3. nene_config.json 업데이트
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
    if not is_auth_verified(token): return "❌ Unauthorized"
    
    # 1. 폴더 선택
    root = tk.Tk()
    root.withdraw()
    root.attributes("-topmost", True)
    src_folder = filedialog.askdirectory(title="Select Existing Minecraft Server Folder")
    if not src_folder: return "⚠️ Cancelled"
    
    # 2. 실행할 JAR 파일 선택 (동일 폴더 내)
    jar_path = filedialog.askopenfilename(
        title="Select Server JAR file to Run",
        initialdir=src_folder,
        filetypes=[("JAR files", "*.jar")]
    )
    if not jar_path: return "⚠️ Cancelled (JAR not selected)"
    
    # 선택된 JAR가 폴더 내에 있는지 확인 (보안 및 경로 단순화 위해 파일명만 추출)
    jar_name = os.path.basename(jar_path)
    
    # 3. 서버 이름 결정 및 타겟 경로 설정
    folder_name = os.path.basename(src_folder)
    clean_name = re.sub(r'[<>:"/\\|?*]', '', folder_name).strip()
    target = os.path.join(BASE_SERVERS_DIR, clean_name)
    
    base_target = target
    counter = 1
    while os.path.exists(target):
        target = f"{base_target}_{counter}"
        counter += 1
    
    final_name = os.path.basename(target)
    
    try:
        # 4. 폴더 복사
        eel.update_download_progress_js(f"Importing {final_name}...")()
        copy_folder_with_progress(src_folder, target)
        
        # 5. nene_config.json 생성
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
                "custom_jar": jar_name  # 선택한 JAR 파일명 저장
            }, f, indent=4)
            
        return f"✅ {final_name} 불러오기 성공"
        
    except Exception as e:
        if os.path.exists(target): shutil.rmtree(target)
        return f"❌ 오류: {e}"

@eel.expose
def delete_server_real_py(token, name):
    if not is_auth_verified(token): return "❌ Unauthorized"
    if name in active_processes: return "⚠️ Running"
    try:
        shutil.rmtree(os.path.join(BASE_SERVERS_DIR, name))
        if name in server_logs: del server_logs[name]
        if name in server_players: del server_players[name]
        return "✅ Deleted"
    except: return "❌ Failed"

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
        # 'utf-8' 혹은 시스템 인코딩으로 시도 (안전하게 replace 처리)
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

        # 누락된 필수 키 추가
        for k, v in defaults.items():
            if k not in keys_found:
                new_lines.append(f"{k}={v}\n")
                modified = True

        if modified:
            with open(path, 'w', encoding='utf-8') as f:
                f.writelines(new_lines)
    except:
        pass

@eel.expose
def start_server_py(token, ram):
    if not is_auth_verified(token):
        add_access_log("Server Start", "blocked", "Unauthorized")
        return "❌ Unauthorized"
    global current_view_server
    name = current_view_server
    if not name:
        add_access_log("Server Start", "fail", "No server selected")
        return "❌ Select Server"
    if name in active_processes:
        add_access_log("Server Start", "fail", f"Server '{name}' already running")
        return "⚠️ Running"
    
    server_dir = os.path.join(BASE_SERVERS_DIR, name)
    
    # [수정] 서버 구동 전 빈 필수값들을 기본값으로 자동 보정
    ensure_valid_properties(server_dir)
    jar_name = "server.jar"
    
    # nene_config.json에서 커스텀 JAR 이름 확인
    try:
        cfg_path = os.path.join(server_dir, "nene_config.json")
        if os.path.exists(cfg_path):
            with open(cfg_path, 'r', encoding='utf-8') as f:
                cfg = json.load(f)
                jar_name = cfg.get("custom_jar", "server.jar")
    except: pass

    jar = os.path.join(server_dir, jar_name)
    if not os.path.exists(jar): return f"❌ No Jar ({jar_name})"
    if name not in server_logs: server_logs[name] = []
    
    if name not in server_players:
        server_players[name] = {}
    else:
        for p in server_players[name]:
            server_players[name][p]["online"] = False

    if current_view_server == name: 
        update_ui_player_list(name)
        
    t = threading.Thread(target=run_server, args=(name, jar, ram))
    t.daemon = True
    t.start()
    add_access_log("Server Start", "success", f"Server '{name}' started (RAM: {ram}GB)")
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
        active_processes[name] = p
        if current_view_server == name: eel.update_status_js(True)()
        while True:
            line = p.stdout.readline()
            if not line and p.poll() is not None: break
            if line:
                clean = line.strip()
                append_log(name, clean)
                parse_player_event(name, clean)
        append_log(name, "[SYSTEM] Stopped")
        if name in active_processes: del active_processes[name]
        
        if name in server_players:
            for p_name in server_players[name]:
                server_players[name][p_name]["online"] = False

        if current_view_server == name: 
            eel.update_status_js(False)
            update_ui_player_list(name)
            
    except Exception as e:
        append_log(name, f"[ERROR] {e}")
        if name in active_processes: del active_processes[name]

def append_log(name, msg):
    if name not in server_logs: server_logs[name] = []
    server_logs[name].append(msg)
    if current_view_server == name: eel.add_log_js(msg)

def update_ui_player_list(server_name):
    if current_view_server == server_name:
        players_list = []
        
        if server_name in server_players:
            for p_name, p_data in server_players[server_name].items():
                players_list.append({
                    "name": p_name,
                    "online": p_data.get("online", False),
                    "uuid": p_data.get("uuid", "-"),
                    "join_time": p_data.get("join_time", "-")
                })
        
        try:
            userdata_dir = os.path.join(BASE_SERVERS_DIR, server_name, "plugins", "AYADETAIL", "userdata")
            if os.path.exists(userdata_dir):
                for f in os.listdir(userdata_dir):
                    if f.endswith(".json"):
                        p_name = f.replace(".json", "")
                        
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
    if server_name not in server_players: server_players[server_name] = {}
    
    if "UUID of player" in line:
        try:
            parts = line.split("UUID of player ")
            if len(parts) > 1:
                rest = parts[1].strip()
                if " is " in rest:
                    p_name, p_uuid = rest.split(" is ")
                    p_name = p_name.strip()
                    p_uuid = p_uuid.strip()
                    
                    if p_name not in server_players[server_name]:
                        server_players[server_name][p_name] = {"join_time": "-", "uuid": "-", "online": False}
                    
                    server_players[server_name][p_name]["uuid"] = p_uuid
        except: pass

    if "logged in with entity id" in line:
        try:
            parts = line.split(" logged in with entity id")
            raw = parts[0].strip().split(" ")[-1]
            name = raw.split("[")[0] if "[" in raw else raw
            name = re.sub(r'[^a-zA-Z0-9_]', '', name)
            if name:
                now = datetime.datetime.now().strftime("%H:%M:%S")
                
                saved_uuid = "-"
                if name in server_players[server_name]:
                    saved_uuid = server_players[server_name][name].get("uuid", "-")
                
                server_players[server_name][name] = {"join_time": now, "uuid": saved_uuid, "online": True}
                update_ui_player_list(server_name)
        except: pass
    
    elif "lost connection" in line:
        try:
            parts = line.split(" lost connection")
            name = parts[0].strip().split(" ")[-1]
            name = re.sub(r'[^a-zA-Z0-9_]', '', name)
            if name in server_players[server_name]:
                server_players[server_name][name]["online"] = False
                update_ui_player_list(server_name)
        except: pass

    elif "left the game" in line:
        try:
            parts = line.split(" left the game")
            name = parts[0].strip().split(" ")[-1]
            name = re.sub(r'[^a-zA-Z0-9_]', '', name)
            if name in server_players[server_name]:
                server_players[server_name][name]["online"] = False
                update_ui_player_list(server_name)
        except: pass

@eel.expose
def get_nene_player_data_py(token, player_name):
    if not is_auth_verified(token): return None
    try:
        path = os.path.join(BASE_SERVERS_DIR, current_view_server, "plugins", "AYADETAIL", "userdata", f"{player_name}.json")
        if os.path.exists(path):
            with open(path, 'r', encoding='utf-8') as f:
                return json.load(f)
    except: pass
    return None

@eel.expose
def load_properties_py(token):
    if not is_auth_verified(token): return None
    if not current_view_server: return None
    props = {}
    d = os.path.join(BASE_SERVERS_DIR, current_view_server)
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
    if not is_auth_verified(token): return "❌ Unauthorized"
    if not current_view_server: return "❌ No Server"
    d = os.path.join(BASE_SERVERS_DIR, current_view_server)
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
        return "✅ Saved"
    except: return "❌ Failed"

@eel.expose
def check_java_status_py(token):
    # 시스템 상태 확인은 토큰 검증 없이 수행해도 되지만 일관성을 위해 추가
    try:
        subprocess.check_output([DEFAULT_JAVA, "-version"], stderr=subprocess.STDOUT)
        return {"status": "ok"}
    except: return {"status": "error"}

@eel.expose
def send_command_py(token, cmd):
    if not is_auth_verified(token):
        add_access_log("Execute Command", "blocked", f"Unauthorized: {cmd}")
        return
    if current_view_server and current_view_server in active_processes:
        p = active_processes[current_view_server]
        if p.poll() is None:
            try:
                p.stdin.write(cmd+"\n"); p.stdin.flush(); append_log(current_view_server, f"> {cmd}")
                add_access_log("Execute Command", "success", f"Server '{current_view_server}': {cmd}")
            except:
                add_access_log("Execute Command", "error", f"Command send fail: {cmd}")
                pass

@eel.expose
def trigger_backup_py(token, server_name):
    if not is_auth_verified(token):
        add_access_log("Backup Run", "blocked", "Unauthorized")
        return "❌ Unauthorized"
    t = threading.Thread(target=backup_server, args=(server_name,))
    t.start()
    add_access_log("Backup Run", "success", f"Server '{server_name}' backup started")
    return "Backup started"

def backup_server(server_name):
    try:
        server_dir = os.path.join(BASE_SERVERS_DIR, server_name)
        backup_root = os.path.join(BACKUP_ROOT_DIR, server_name)
        if not os.path.exists(backup_root):
            os.makedirs(backup_root)
            
        ts = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        zip_name = f"backup_{ts}.zip"
        zip_path = os.path.join(backup_root, zip_name)
        
        if current_view_server == server_name: eel.add_log_js(f"[SYSTEM] 백업 시작: {zip_name}")()
        
        with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as z:
            for r, d, f in os.walk(server_dir):
                if "backups" in d: d.remove("backups")
                for file in f:
                    fp = os.path.join(r, file)
                    try: z.write(fp, os.path.relpath(fp, server_dir))
                    except: pass
                    
        last_backup_times[server_name] = time.time()
        if current_view_server == server_name: eel.add_log_js("[SYSTEM] 백업 완료")()
    except Exception as e:
        if current_view_server == server_name: eel.add_log_js(f"[ERROR] 백업 실패: {e}")()
        
@eel.expose
def list_backups_py(token, server_name):
    if not is_auth_verified(token):
        add_access_log("Backup List", "blocked", "Unauthorized")
        return []
    backup_dir = os.path.join(BACKUP_ROOT_DIR, server_name)
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
    add_access_log("Backup List", "success", f"Server '{server_name}' {len(backups)} backups found")
    return backups

@eel.expose
def restore_backup_py(token, server_name, filename):
    if not is_auth_verified(token):
        add_access_log("Backup Restore", "blocked", "Unauthorized")
        return "❌ Unauthorized"
    t = threading.Thread(target=restore_server, args=(server_name, filename))
    t.start()
    add_access_log("Backup Restore", "start", f"Server '{server_name}' → {filename}")
    return "Restore started"

def restore_server(server_name, filename):
    try:
        server_dir = os.path.join(BASE_SERVERS_DIR, server_name)
        backup_path = os.path.join(BACKUP_ROOT_DIR, server_name, filename)
        
        if not os.path.exists(backup_path):
            if current_view_server == server_name: eel.add_log_js(f"[ERROR] 백업 파일 없음: {filename}")()
            return
        
        # 1. Extract to a temp dir first to count files
        import tempfile
        tmpdir = tempfile.mktemp()
        total_files = 0
        with zipfile.ZipFile(backup_path, 'r') as z:
            total_files = len(z.namelist())
        
        if total_files == 0:
            if current_view_server == server_name: eel.add_log_js("[ERROR] 백업 파일이 비어있음")()
            shutil.rmtree(tmpdir, ignore_errors=True)
            return
        
        # 2. Delete existing server files
        if os.path.exists(server_dir):
            if current_view_server == server_name: eel.add_log_js("[SYSTEM] 기존 서버 파일 삭제 중...")()
            eel.update_restore_progress_js(0, "Deleting old files...")()
            for item in os.listdir(server_dir):
                item_path = os.path.join(server_dir, item)
                try:
                    if os.path.isfile(item_path) or os.path.islink(item_path):
                        os.unlink(item_path)
                    elif os.path.isdir(item_path):
                        shutil.rmtree(item_path)
                except Exception as e:
                    if current_view_server == server_name: eel.add_log_js(f"[WARN] 삭제 실패 {item}: {e}")()
        
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
                    if current_view_server == server_name: eel.add_log_js(f"[WARN] 복원 실패 {entry}: {e}")()
                extracted += 1
                percent = int((extracted / total_files) * 100)
                filename_only = os.path.basename(entry) if entry else entry
                eel.update_restore_progress_js(percent, filename_only)()
        
        shutil.rmtree(tmpdir, ignore_errors=True)
        
        if current_view_server == server_name:
            eel.add_log_js(f"[SYSTEM] 복원 완료: {filename} ({total_files}개 파일)")()
            eel.showToast("복원 완료!", "success")
    except Exception as e:
        if current_view_server == server_name:
            eel.add_log_js(f"[ERROR] 복원 실패: {e}")()
            eel.showToast(f"복원 실패: {e}", "error")

@eel.expose
def open_folder_py(token, server_name, mode):
    if not is_auth_verified(token): return "❌ Unauthorized"
    if not server_name: return "❌ No Server Selected"
    
    if mode == "backup":
        path = os.path.join(BACKUP_ROOT_DIR, server_name)
    else:
        path = os.path.join(BASE_SERVERS_DIR, server_name)
        
    if not os.path.exists(path):
        try:
            os.makedirs(path)
        except:
            return "❌ Create Failed"
    try:
        if os.name == 'nt':
            os.startfile(path)
        elif sys.platform == 'darwin':
            subprocess.Popen(['open', path])
        else:
            subprocess.Popen(['xdg-open', path])
        return "✅ Opened"
    except Exception as e:
        return f"❌ Error: {e}"

@eel.expose
def get_public_ip_py(token):
    # IP 확인은 토큰 검증 없이도 가능하지만, 일관성을 위해 매개변수 유지
    try:
        return requests.get('https://api.ipify.org', timeout=3).text
    except:
        return "Unknown"

# ==========================================================
# [기능] 플러그인 관리 (Plugins)
# ==========================================================
@eel.expose
def get_plugin_list_py(token):
    if not is_auth_verified(token): return []
    if not current_view_server: return []
    
    plugins_dir = os.path.join(BASE_SERVERS_DIR, current_view_server, "plugins")
    if not os.path.exists(plugins_dir):
        try: os.makedirs(plugins_dir)
        except: return []
        
    plugin_list = []
    try:
        for file in os.listdir(plugins_dir):
            if file.endswith(".jar"):
                plugin_list.append({
                    "name": file,           
                    "filename": file,       
                    "enabled": True
                })
            elif file.endswith(".jar.disabled"):
                display_name = file.replace(".jar.disabled", ".jar")
                plugin_list.append({
                    "name": display_name,
                    "filename": file,
                    "enabled": False
                })
    except: pass
    
    return sorted(plugin_list, key=lambda x: x['name'])

@eel.expose
def toggle_plugin_py(token, filename, make_active):
    if not is_auth_verified(token): return "❌ Unauthorized"
    if not current_view_server: return "❌ No Server"
    plugins_dir = os.path.join(BASE_SERVERS_DIR, current_view_server, "plugins")
    old_path = os.path.join(plugins_dir, filename)
    
    if not os.path.exists(old_path): return "❌ File Not Found"
    
    try:
        if make_active:
            new_name = filename.replace(".jar.disabled", ".jar")
            new_path = os.path.join(plugins_dir, new_name)
            os.rename(old_path, new_path)
            return "✅ Enabled"
        else:
            new_name = filename + ".disabled"
            new_path = os.path.join(plugins_dir, new_name)
            os.rename(old_path, new_path)
            return "✅ Disabled"
    except Exception as e:
        return f"❌ Error: {e}"

@eel.expose
def delete_plugin_py(token, filename):
    if not is_auth_verified(token): return "❌ Unauthorized"
    if not current_view_server: return "❌ No Server"
    plugins_dir = os.path.join(BASE_SERVERS_DIR, current_view_server, "plugins")
    target_path = os.path.join(plugins_dir, filename)
    
    if not os.path.exists(target_path): return "❌ File Not Found"
    
    try:
        os.remove(target_path)
        return "✅ Deleted"
    except Exception as e:
        return f"❌ Error: {e}"

# ==========================================================
# [추가됨] 서버 상세 정보 (Server Info)
# ==========================================================
@eel.expose
def get_server_extended_info_py(token):
    if not is_auth_verified(token): return None
    if not current_view_server: return None
    
    server_path = os.path.join(BASE_SERVERS_DIR, current_view_server)
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
        playerdata_path = os.path.join(server_path, info["world_name"], "playerdata")
        if os.path.exists(playerdata_path):
            count = len([name for name in os.listdir(playerdata_path) if name.endswith('.dat')])
            info["player_count"] = count
    except: pass

    return info

# ==========================================================
# [추가 기능] 자바 버전 관리자 (Java Version Manager)
# ==========================================================

def load_global_java_setting():
    global DEFAULT_JAVA
    try:
        if os.path.exists(LAUNCHER_CONFIG_FILE):
            with open(LAUNCHER_CONFIG_FILE, 'r', encoding='utf-8') as f:
                conf = json.load(f)
                DEFAULT_JAVA = conf.get("global_java", "java")
    except: pass

@eel.expose
def scan_java_versions_py(token, target_path=None):
    if not is_auth_verified(token): return []
    java_list = []
    current_path = target_path if target_path else DEFAULT_JAVA
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

    search_paths = [
        r"C:\Program Files\Java",
        r"C:\Program Files (x86)\Java",
        r"C:\Program Files\Eclipse Adoptium",
        r"C:\Program Files\Zulu",
        r"C:\Program Files\Microsoft",
        r"C:\Program Files\BellSoft"
    ]

    for root_dir in search_paths:
        try:
            if os.path.exists(root_dir):
                for item in os.listdir(root_dir):
                    try:
                        full_path = os.path.join(root_dir, item, "bin", "java.exe")
                        if os.path.exists(full_path) and full_path != current_path:
                            ver = get_java_version_string(full_path)
                            if ver != "Unknown":
                                java_list.append({
                                    "path": full_path,
                                    "version": ver,
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
        result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=10)
        output = result.stderr
        for line in output.split('\n'):
            if "version" in line:
                return line.split('"')[1]
        return "Detected"
    except:
        return "Unknown"

@eel.expose
def set_global_java_py(token, new_path):
    if not is_auth_verified(token): return "❌ Unauthorized"
    if len(active_processes) > 0:
        return "⚠️ Running"

    try:
        config = {}
        if os.path.exists(LAUNCHER_CONFIG_FILE):
            with open(LAUNCHER_CONFIG_FILE, 'r', encoding='utf-8') as f:
                config = json.load(f)
        
        config["global_java"] = new_path
        
        with open(LAUNCHER_CONFIG_FILE, 'w', encoding='utf-8') as f:
            json.dump(config, f, indent=4)
            
        global DEFAULT_JAVA
        DEFAULT_JAVA = new_path
        return "✅ Saved"
    except Exception as e:
        return f"❌ Error: {e}"

@eel.expose
def check_any_server_running_py(token):
    if not is_auth_verified(token): return False
    return len(active_processes) > 0

@eel.expose
def kill_all_java_processes_py(token):
    if not is_auth_verified(token): return "❌ Unauthorized"
    count = 0
    try:
        if os.name == 'nt':
            os.system("taskkill /f /im java.exe")
            os.system("taskkill /f /im javaw.exe")
            return "✅ 모든 자바 프로세스를 종료 명령을 보냈습니다."
        else:
            for proc in psutil.process_iter(['pid', 'name']):
                if 'java' in proc.info['name'].lower():
                    proc.kill()
                    count += 1
            return f"✅ 자바 프로세스 {count}개를 종료했습니다."
    except Exception as e:
        return f"❌ 오류 발생: {e}"

@eel.expose
def restart_launcher_py(token):
    # 원격 설정 변경 후 서버 재바인딩을 위해 어플리케이션 자체를 재시작
    if not is_auth_verified(token): return False
    try:
        # 새로운 프로세스 실행
        subprocess.Popen([sys.executable] + sys.argv)
        # 현재 프로세스 종료
        os._exit(0)
    except:
        return False

def close_callback(route, websockets):
    pass

def create_image():
    width = 64
    height = 64
    image = Image.new('RGB', (width, height), (60, 166, 255))
    dc = ImageDraw.Draw(image)
    dc.rectangle((16, 16, 48, 48), fill=(255, 255, 255))
    return image

def quit_app(icon, item):
    icon.stop()
    for name, p in list(active_processes.items()):
        if p.poll() is None:
            try:
                p.stdin.write("stop\n")
                p.stdin.flush()
            except:
                pass
    for p in list(active_processes.values()):
        if p.poll() is None:
            try:
                p.wait(timeout=5)
            except:
                try: p.terminate()
                except: pass
    os._exit(0)

@eel.expose
def run_update_py(token):
    if not is_auth_verified(token): return "❌ Unauthorized"
    update_exe = os.path.join(AYA_BASE, "update.exe")
    if not os.path.exists(update_exe):
        return "❌ update.exe not found"
    try:
        subprocess.Popen([update_exe], shell=True)
        return "✅ Update started"
    except Exception as e:
        return f"❌ {e}"

def open_browser(icon, item):
    webbrowser.open(f'http://localhost:8000/index.html?token={LOCAL_TOKEN}')

def setup_tray():
    image = create_image()
    if os.path.exists("icon.ico"):
        try: image = Image.open("icon.ico")
        except: pass
        
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
            for name in list(active_processes.keys()):
                if active_processes[name].poll() is None:
                    try:
                        cp = os.path.join(BASE_SERVERS_DIR, name, "nene_config.json")
                        if os.path.exists(cp):
                            with open(cp, 'r', encoding='utf-8') as f:
                                conf = json.load(f)
                                if conf.get("auto_backup", False):
                                    iv = int(conf.get("backup_interval", 60)) * 60
                                    lst = last_backup_times.get(name, 0)
                                    if lst == 0: last_backup_times[name] = cur
                                    elif (cur - lst) >= iv: backup_server(name)
                    except: pass
        except: pass

if __name__ == "__main__":
    t = threading.Thread(target=system_monitor_thread)
    t.daemon = True
    t.start()
    
    t_tray = threading.Thread(target=setup_tray)
    t_tray.daemon = True
    t_tray.start()
    
    def deferred_open():
        time.sleep(0.5)
        webbrowser.open(f'http://localhost:8000/index.html?token={LOCAL_TOKEN}')
        
    t_open = threading.Thread(target=deferred_open)
    t_open.daemon = True
    t_open.start()
    
    # 런처가 구동될 때 최초로 원격 제어 사용 설정 상태를 읽음
    launcher_conf = get_launcher_config_py(LOCAL_TOKEN)
    is_remote_enabled = launcher_conf.get("remote_enabled", False)
    
    # [치명적 취약점 패치]: 원격 설정 상태에 따라 소켓 네트워크 리스너의 바인딩 주소를 명확히 대입
    # - remote_enabled 가 False 인 경우: 'localhost' (혹은 '127.0.0.1') 외부 패킷 수신이 물리적으로 불가능
    # - remote_enabled 가 True 인 경우: '0.0.0.0' 모든 네트워크 접근 허용
    host_ip = '0.0.0.0' if is_remote_enabled else '127.0.0.1'
    
    try: 
        eel.start('index.html', mode=False, port=8000, host=host_ip, block=True, close_callback=close_callback)
    except Exception as e:
        print(f"Eel Server Error: {e}")
        pass