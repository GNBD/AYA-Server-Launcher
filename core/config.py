import os
import json
import eel
from . import state, security, java

# ==========================================================
# [기본 언어 데이터]
# ==========================================================
DEFAULT_TRANSLATIONS = {
    "ko": {
        "title_launcher": "SERVER<br>LAUNCHER", "btn_new_server": "새 서버", "msg_select_server": "서버를 선택하세요",
        "tab_dashboard": "대시보드", "tab_env": "서버 관리", "tab_players": "플레이어 관리", "tab_broadcast": " 광고/공지", "tab_settings": "전체 설정", "tab_info": "ℹ 서버 정보", "tab_danger": " 위험 구간",
        "card_player": "Player", "card_status": "Status", "ph_cmd_input": "명령어 입력...", "btn_start": "서버 시작", "btn_stop": "서버 종료", "btn_restart": "재시작",
        "title_time": "⏰ 시간 제어", "env_morning": "아침", "env_noon": "점심", "env_evening": "저녁", "env_night": "밤",
        "title_weather": " 날씨 제어", "env_clear": "맑음", "env_rain": "비", "env_thunder": "폭풍우", "env_lock": "날씨 고정",
        "title_player_list": "접속자 목록", "btn_whitelist": "화이트리스트 관리", "btn_banlist": "차단 목록 관리", "btn_ip_banlist": "IP 차단 관리", "msg_no_players": "접속 중인 플레이어가 없습니다.",
        "title_broadcast": " 광고 / 공지 보내기", "desc_broadcast": "서버에 접속한 모든 플레이어에게 메시지를 띄웁니다.",
        "lbl_bc_title": " 화면 중앙 타이틀 (Title)", "desc_bc_title": "가장 크게 보이는 제목입니다.",
        "lbl_bc_subtitle": " 서브 타이틀 (Subtitle)", "desc_bc_subtitle": "타이틀 아래에 작게 나오는 설명입니다. (타이틀과 함께 보낼 때 사용)",
        "lbl_bc_actionbar": " 액션 바 (Actionbar)", "desc_bc_actionbar": "아이템 슬롯 위에 작게 뜨는 메시지입니다.",
        "btn_bc_send": "보내기 (Send)", "btn_bc_set": "설정 (Set)", "btn_bc_clear": "지우기",
        "btn_save_settings": " 설정 저장하기", "title_backup": " 백업 설정", "set_auto_backup": "자동 백업 활성화", "set_backup_interval": "백업 주기 (분)",
        "btn_backup_now": "지금 백업하기", "title_java": " Java 설정", "set_java_path": "실행 경로 (java.exe)", "msg_java_tip": "* 1.18 이상은 Java 17+, 그 이하는 Java 8 권장",
        "title_general": " 일반 설정", "set_motd": "서버 이름 (MOTD)", "set_server_port": "서버 포트", "set_server_ip": "서버 IP", "set_max_players": "최대 인원",
        "set_online_mode": "정품 인증 (Online Mode)", "set_white_list": "화이트리스트 사용", "set_enforce_whitelist": "화이트리스트 강제",
        "title_performance": " 성능 및 네트워크", "set_ram": "메모리 할당", "set_view_distance": "시야 거리", "set_simulation_distance": "연산 거리",
        "set_max_tick_time": "최대 틱 시간", "set_network_compression_threshold": "네트워크 압축 임계값", "set_rate_limit": "패킷 제한",
        "set_use_native_transport": "네이티브 전송 사용", "set_enable_status": "상태 표시 활성화", "set_broadcast_rcon_to_ops": "RCON 로그 방송", "set_broadcast_console_to_ops": "콘솔 로그 방송",
        "title_world": " 월드 및 생성", "set_level_name": "월드 폴더명", "set_level_seed": "월드 시드", "set_level_type": "월드 타입", "set_generator_settings": "생성기 설정",
        "set_max_world_size": "월드 최대 크기", "set_allow_nether": "네더(지옥) 허용", "set_generate_structures": "구조물 생성",
        "title_gameplay": " 게임 플레이", "set_gamemode": "기본 게임모드", "set_force_gamemode": "게임모드 강제", "set_difficulty": "난이도",
        "set_hardcore": "하드코어", "set_pvp": "PVP 허용", "set_allow_flight": "비행 허용", "set_spawn_monsters": "몬스터 스폰", "set_spawn_animals": "동물 스폰",
        "set_spawn_npcs": "NPC 스폰", "set_spawn_protection": "스폰 보호 구역", "set_enable_command_block": "커맨드 블록 허용", "set_player_idle_timeout": "잠수 추방 시간 (분)",
        "title_security": " 보안 및 기타", "set_op_permission_level": "OP 권한 레벨", "set_log_ips": "IP 기록", "set_enforce_secure_profile": "보안 프로필 강제",
        "set_prevent_proxy_connections": "프록시 연결 방지", "set_resource_pack": "리소스팩 URL", "set_require_resource_pack": "리소스팩 강제",
        "set_enable_rcon": "RCON 활성화", "set_rcon_port": "RCON 포트", "set_rcon_password": "RCON 비밀번호", "set_enable_query": "Query 활성화", "set_query_port": "Query 포트",
        "set_sync_chunk_writes": "청크 동기화 저장", "set_enable_jmx_monitoring": "JMX 모니터링", "set_entity_broadcast_range_percentage": "엔티티 방송 범위(%)",
        "set_max_chained_neighbor_updates": "최대 이웃 업데이트", "set_region_file_compression": "청크 압축 방식", "set_accepts_transfers": "서버 이동 허용",
        "set_bug_report_link": "버그 리포트 링크", "set_initial_enabled_packs": "초기 활성 팩", "set_initial_disabled_packs": "초기 비활성 팩", "set_debug": "디버그 모드",
        "title_folder_check": " 파일 위치 확인", "desc_folder_check": "서버 파일이나 백업 파일이 저장된 실제 폴더를 엽니다.", "btn_open_server_folder": " 서버 폴더 열기", "btn_open_backup_folder": " 백업 폴더 열기",
        "title_danger": " 서버 삭제 (Danger Zone)", "msg_danger": "현재 서버를 영구 삭제합니다. 복구할 수 없습니다.", "btn_delete_server": " 서버 영구 삭제",
        "modal_p_join": "접속 시간", "modal_p_status": "상태", "btn_whisper": " 귓속말 (Whisper)", "btn_tp": " 이동 (TP)",
        "act_op": "관리자 (OP)", "act_deop": "권한 해제 (DEOP)", "act_kick": "추방 (KICK)", "act_ban": "차단 (BAN)", "btn_close": "닫기",
        "modal_whisper_title": " 귓속말 보내기", "modal_tp_title": " 텔레포트 (TP)", "msg_tp_ask": "누구에게 이동하시겠습니까?", "msg_tp_empty": "이동할 상대가 없습니다.",
        "modal_ban_opt_title": " 차단 옵션 선택", "msg_ban_opt": "어떤 방식으로 차단하시겠습니까?", "btn_ban_name": "닉네임 차단 (Name Ban)", "btn_ban_ip": "IP 차단 (IP Ban)", "btn_ban_both": "둘 다 차단 (Both)",
        "btn_cancel": "취소", "btn_confirm": "확인", "btn_create": "생성", "btn_save": "저장", "btn_delete": "제거", "btn_add": "추가",
        "modal_confirm_title": " 실행 확인", "modal_list_title": "목록 관리", "ph_nickname": "닉네임 / IP 입력",
        "modal_new_title": " 새 서버 생성", "modal_new_name": "서버 이름", "modal_new_ver": "버전", "modal_setting_title": " 런처 설정", "modal_setting_lang": "언어 (Language)", "modal_setting_mirror": "미러 URL",
        "modal_del_title": " 정말 삭제하시겠습니까?", "modal_del_msg": "선택된 서버: ", "modal_eula_title": " EULA 동의", "msg_eula_content": "마인크래프트 서버를 생성하려면<br>Mojang의 EULA(최종 사용자 라이선스 계약)에<br>동의해야 합니다.",
        "btn_agree": "동의합니다", "btn_disagree": "거절", "msg_cannot_close": " 서버가 실행 중입니다! 먼저 서버를 종료해주세요.",
        "diff_peaceful": "평화로움", "diff_easy": "쉬움", "diff_normal": "보통", "diff_hard": "어려움",
        "modal_restart_title": " 서버 재시작 확인", "msg_restart_confirm": "정말 서버를 다시 시작하시겠습니까?<br>(종료 후 다시 시작됩니다)",
        "title_server_info": "ℹ 서버 정보", "info_created": "생성 일자", "info_source": "다운로드 출처", "info_size": "디스크 사용량", "info_java": "Java 버전/경로", "info_players": "방문한 플레이어 수",
        "remote_nav_btn": " 원격 연결 제어 관리", "remote_modal_title": " 원격 연결 (베타)", "remote_modal_desc": "타 PC나 모바일 웹브라우저에서 이 런처에 접속하여 원격으로 제어할 수 있도록 도와줍니다.", "remote_addr_label": "내 외부 원격 접속 주소",
        "remote_enable_label": "원격 제어 활성화", "remote_restart_needed": "(재시작 필요)", "remote_pw_label": "새 원격 비밀번호 설정", "remote_pw_placeholder": "새 비밀번호 입력 (빈 칸 입력 시 변경 없음)",
        "remote_pw_warning": "* 안전한 환경을 위해 비밀번호 설정을 권장합니다.", "restart_title": "런처 재시작 안내", "restart_desc": "원격 제어 설정 변경을 적용하기 위해 <b>프로그램을 재시작합니다.</b><br>확인 버튼을 누르거나 잠시 기다려 주세요.",
        "restart_btn_text": "확인 및 재시작", "security_warning_banner": "보안 경고: 원격 제어용 비밀번호가 설정되어 있지 않습니다!", "btn_go_to_settings": "비밀번호 설정하러 가기",
        "remote_lock_title": "원격 제어 잠금", "remote_lock_desc": "이 컴퓨터는 원격 제어 보안 모드가 켜져 있습니다.", "remote_auth_pw_label": "인증 비밀번호 입력", "remote_auth_pw_placeholder": "비밀번호를 입력하세요",
        "remote_remember_pw": "암호 기억하기 (비추천)", "btn_authenticate": "인증하기",
        "remote_ip_warning": " 주의: 외부 접속 주소와 비밀번호가 유출되면 타인이 이 서버를 제어할 수 있습니다. 신뢰할 수 없는 사람에게는 절대 주소를 공유하지 마세요!",
        "remote_enabled_banner": " 원격제어가 활성화되어 있습니다. 외부에서의 비인가 접근 등 혹시 모를 위험에 항상 주의하세요."
    },
    "en": {
        "title_launcher": "SERVER<br>LAUNCHER", "btn_new_server": "New Server", "msg_select_server": "Select a server",
        "tab_dashboard": "Dashboard", "tab_env": "Manage Server", "tab_players": "Manage Players", "tab_broadcast": " Broadcast", "tab_settings": "Settings", "tab_info": "ℹ Server Info", "tab_danger": " Danger Zone",
        "card_player": "Player", "card_status": "Status", "ph_cmd_input": "Enter command...", "btn_start": "Start Server", "btn_stop": "Stop Server", "btn_restart": "Restart",
        "title_time": "⏰ Time Control", "env_morning": "Morning", "env_noon": "Noon", "env_evening": "Evening", "env_night": "Night",
        "title_weather": " Weather Control", "env_clear": "Clear", "env_rain": "Rain", "env_thunder": "Thunder", "env_lock": "Lock Weather",
        "title_player_list": "Player List", "btn_whitelist": "Manage Whitelist", "btn_banlist": "Manage Banlist", "btn_ip_banlist": "Manage IP Bans", "msg_no_players": "No players online.",
        "title_broadcast": " Send Broadcast", "desc_broadcast": "Display a message to all players on the server.",
        "lbl_bc_title": " Title", "desc_bc_title": "Large text in the center of the screen.",
        "lbl_bc_subtitle": " Subtitle", "desc_bc_subtitle": "Small text under the title.",
        "lbl_bc_actionbar": " Actionbar", "desc_bc_actionbar": "Small message above the item slots.",
        "btn_bc_send": "Send", "btn_bc_set": "Set", "btn_bc_clear": "Clear",
        "btn_save_settings": " Save Settings", "title_backup": " Backup Settings", "set_auto_backup": "Enable Auto Backup", "set_backup_interval": "Backup Interval (min)",
        "btn_backup_now": "Backup Now", "title_java": " Java Settings", "set_java_path": "Executable Path (java.exe)", "msg_java_tip": "* Java 17+ for 1.18+, Java 8 for older versions",
        "title_general": " General Settings", "set_motd": "Server Name (MOTD)", "set_server_port": "Server Port", "set_server_ip": "Server IP", "set_max_players": "Max Players",
        "set_online_mode": "Online Mode", "set_white_list": "Whitelist", "set_enforce_whitelist": "Enforce Whitelist",
        "title_performance": " Performance & Network", "set_ram": "RAM Allocation", "set_view_distance": "View Distance", "set_simulation_distance": "Simulation Distance",
        "set_max_tick_time": "Max Tick Time", "set_network_compression_threshold": "Network Compression Threshold", "set_rate_limit": "Packet Rate Limit",
        "set_use_native_transport": "Use Native Transport", "set_enable_status": "Enable Status", "set_broadcast_rcon_to_ops": "Broadcast RCON to OPs", "set_broadcast_console_to_ops": "Broadcast Console to OPs",
        "title_world": " World Generation", "set_level_name": "Level Name", "set_level_seed": "Level Seed", "set_level_type": "Level Type", "set_generator_settings": "Generator Settings",
        "set_max_world_size": "Max World Size", "set_allow_nether": "Allow Nether", "set_generate_structures": "Generate Structures",
        "title_gameplay": " Gameplay", "set_gamemode": "Default Gamemode", "set_force_gamemode": "Force Gamemode", "set_difficulty": "Difficulty",
        "set_hardcore": "Hardcore", "set_pvp": "Allow PVP", "set_allow_flight": "Allow Flight", "set_spawn_monsters": "Spawn Monsters", "set_spawn_animals": "Spawn Animals",
        "set_spawn_npcs": "Spawn NPCs", "set_spawn_protection": "Spawn Protection", "set_enable_command_block": "Enable Command Blocks", "set_player_idle_timeout": "Idle Timeout (min)",
        "title_security": " Security & Misc", "set_op_permission_level": "OP Permission Level", "set_log_ips": "Log IPs", "set_enforce_secure_profile": "Enforce Secure Profile",
        "set_prevent_proxy_connections": "Prevent Proxy Connections", "set_resource_pack": "Resource Pack URL", "set_require_resource_pack": "Require Resource Pack",
        "set_enable_rcon": "Enable RCON", "set_rcon_port": "RCON Port", "set_rcon_password": "RCON Password", "set_enable_query": "Enable Query", "set_query_port": "Query Port",
        "set_sync_chunk_writes": "Sync Chunk Writes", "set_enable_jmx_monitoring": "JMX Monitoring", "set_entity_broadcast_range_percentage": "Entity Broadcast Range (%)",
        "set_max_chained_neighbor_updates": "Max Chained Neighbor Updates", "set_region_file_compression": "Region File Compression", "set_accepts_transfers": "Accept Transfers",
        "set_bug_report_link": "Bug Report Link", "set_initial_enabled_packs": "Initial Enabled Packs", "set_initial_disabled_packs": "Initial Disabled Packs", "set_debug": "Debug Mode",
        "title_folder_check": " Check Folder", "desc_folder_check": "Open the actual folder where server or backup files are saved.", "btn_open_server_folder": " Open Server Folder", "btn_open_backup_folder": " Open Backup Folder",
        "title_danger": " Delete Server (Danger Zone)", "msg_danger": "Permanently delete the current server. Cannot be undone.", "btn_delete_server": " Delete Server",
        "modal_p_join": "Joined At", "modal_p_status": "Status", "btn_whisper": " Whisper", "btn_tp": " TP",
        "act_op": "OP", "act_deop": "DEOP", "act_kick": "KICK", "act_ban": "BAN", "btn_close": "Close",
        "modal_whisper_title": " Send Whisper", "modal_tp_title": " 텔레포트 (TP)", "msg_tp_ask": "누구에게 이동하시겠습니까?", "msg_tp_empty": "이동할 상대가 없습니다.",
        "modal_ban_opt_title": " Ban Options", "msg_ban_opt": "How would you like to ban?", "btn_ban_name": "Name Ban", "btn_ban_ip": "IP Ban", "btn_ban_both": "Both",
        "btn_cancel": "Cancel", "btn_confirm": "Confirm", "btn_create": "Create", "btn_save": "Save", "btn_delete": "Delete", "btn_add": "Add",
        "modal_confirm_title": " Confirm Execution", "modal_list_title": "Manage List", "ph_nickname": "Enter Nickname / IP",
        "modal_new_title": " Create New Server", "modal_new_name": "Server Name", "modal_new_ver": "Version", "modal_setting_title": " 런처 설정", "modal_setting_lang": "Language", "modal_setting_mirror": "Mirror URL",
        "modal_del_title": " Are you sure?", "modal_del_msg": "Selected Server: ", "modal_eula_title": " EULA Agreement", "msg_eula_content": "To create a Minecraft server, you must agree to Mojang's EULA.",
        "btn_agree": "I Agree", "btn_disagree": "Decline", "msg_cannot_close": " Server is running! Please stop the server first.",
        "diff_peaceful": "Peaceful", "diff_easy": "Easy", "diff_normal": "Normal", "diff_hard": "Hard",
        "modal_restart_title": " Restart Confirmation", "msg_restart_confirm": "Are you sure you want to restart the server?\n(It will stop and start again)",
        "title_server_info": "ℹ Server Info", "info_created": "Created At", "info_source": "Source", "info_size": "Disk Usage", "info_java": "Java Ver/Path", "info_players": "Total Players Visitors",
        "remote_nav_btn": " Remote Access Management", "remote_modal_title": " Remote Access (Beta)", "remote_modal_desc": "Control this launcher remotely from other PCs or mobile browsers.", "remote_addr_label": "External Access Address",
        "remote_enable_label": "Enable Remote Control", "remote_restart_needed": "(Restart Required)", "remote_pw_label": "Set New Remote Password", "remote_pw_placeholder": "Enter new password (leave blank to keep current)",
        "remote_pw_warning": "* Password is highly recommended for security.", "restart_title": "Launcher Restarting", "restart_desc": "Applying remote settings... <b>The launcher will restart.</b><br>Please wait or click the button.",
        "restart_btn_text": "Confirm and Restart", "security_warning_banner": "Security Warning: Remote password is not set!", "btn_go_to_settings": "Go to Settings",
        "remote_lock_title": "Remote Access Locked", "remote_lock_desc": "This computer is in remote security mode.", "remote_auth_pw_label": "Enter Password", "remote_auth_pw_placeholder": "Enter your password",
        "remote_remember_pw": "Remember Password (Not Recommended)", "btn_authenticate": "Authenticate",
        "remote_ip_warning": " Caution: If your access address and password leak, others could control your server. Never share them with untrusted individuals!",
        "remote_enabled_banner": " Remote control is active. Always be cautious of unknown risks such as unauthorized access."
    }
}

# ==========================================================
# [기능] 시스템 초기화
# ==========================================================
@eel.expose
def init_system_py(token):
    if not security.is_auth_verified(token): return

    if not os.path.exists(state.BASE_SERVERS_DIR): os.makedirs(state.BASE_SERVERS_DIR)
    if not os.path.exists(state.BACKUP_ROOT_DIR): os.makedirs(state.BACKUP_ROOT_DIR)
    first_run = False
    if not os.path.exists(state.LAUNCHER_CONFIG_FILE):
        first_run = True
        with open(state.LAUNCHER_CONFIG_FILE, 'w', encoding='utf-8') as f:
            json.dump({
                "version": state.AYA_VERSION,
                "language": "ko",
        "mirror_url": "https://fill.papermc.io/v3/projects/paper",
                "remote_enabled": False
            }, f, indent=4)
    if not os.path.exists(state.LANG_DIR): os.makedirs(state.LANG_DIR)

    java.load_global_java_setting()

    for lang_code, default_data in DEFAULT_TRANSLATIONS.items():
        lang_file = os.path.join(state.LANG_DIR, f"{lang_code}.json")
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
    authenticated = security.is_auth_verified(token)

    if not authenticated:
        try:
            if os.path.exists(state.LAUNCHER_CONFIG_FILE):
                with open(state.LAUNCHER_CONFIG_FILE, 'r', encoding='utf-8') as f:
                    full_conf = json.load(f)
                    return {
                        "remote_enabled": full_conf.get("remote_enabled", False),
                        "ui_mode": full_conf.get("ui_mode", "browser"),
                        "is_authenticated": False
                    }
        except: pass
        return {"remote_enabled": False, "is_authenticated": False}

    if os.path.exists(state.LAUNCHER_CONFIG_FILE):
        try:
            with open(state.LAUNCHER_CONFIG_FILE, 'r', encoding='utf-8') as f:
                conf = json.load(f)
                conf["remote_key_exists"] = os.path.exists(state.REMOTE_KEY_FILE)
                conf["is_authenticated"] = True
                return conf
        except: pass
    return {
        "language": "ko",
                "mirror_url": "https://fill.papermc.io/v3/projects/paper",
        "remote_enabled": False,
        "ui_mode": "browser",
        "remote_key_exists": os.path.exists(state.REMOTE_KEY_FILE),
        "is_authenticated": True
    }

@eel.expose
def save_launcher_config_py(token, data):
    if not security.is_auth_verified(token): return "❌ Unauthorized"
    try:
        current = {}
        if os.path.exists(state.LAUNCHER_CONFIG_FILE):
            with open(state.LAUNCHER_CONFIG_FILE, 'r', encoding='utf-8') as f:
                current = json.load(f)
        current.update(data)
        with open(state.LAUNCHER_CONFIG_FILE, 'w', encoding='utf-8') as f: json.dump(current, f, indent=4)
        return "✅ 저장 완료"
    except: return "❌ 실패"

@eel.expose
def get_available_languages_py(token):
    langs = []
    if os.path.exists(state.LANG_DIR):
        for f in sorted(os.listdir(state.LANG_DIR)):
            if f.endswith('.json'):
                code = f[:-5]
                langs.append({"code": code, "name": code})
    return langs

@eel.expose
def get_translation_py(token, lang_code):
    file_path = os.path.join(state.LANG_DIR, f"{lang_code}.json")
    if os.path.exists(file_path):
        try:
            with open(file_path, 'r', encoding='utf-8') as f: return json.load(f)
        except: pass
    return DEFAULT_TRANSLATIONS.get(lang_code, {})
