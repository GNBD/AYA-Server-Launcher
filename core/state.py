import os
import secrets
import threading

# ==========================================================
# [공용 상태/상수] 모든 모듈이 공유하는 전역 변수 모음
# (원래 launcher.py 최상단 전역 변수들을 한 곳으로 모음)
# ==========================================================

AYA_VERSION = "4.2.3"
AYA_BASE = "AYA_data"
DEFAULT_JAVA = "java"
BASE_SERVERS_DIR = os.path.join(AYA_BASE, "servers")
BACKUP_ROOT_DIR = os.path.join(AYA_BASE, "backup")
CONFIG_DIR = os.path.join(AYA_BASE, "config")
LAUNCHER_CONFIG_FILE = os.path.join(CONFIG_DIR, "launcher_config.json")
REMOTE_KEY_FILE = os.path.join(CONFIG_DIR, "launcher_remote.key")
ACCESS_LOG_FILE = os.path.join(CONFIG_DIR, "access.log")
LANG_DIR = os.path.join(AYA_BASE, "languages")

DETAIL_PLUGIN_DIR = os.path.join(AYA_BASE, "Detail plugin")
DETAIL_LANG_DIR = os.path.join(DETAIL_PLUGIN_DIR, "languages")

# 로컬 접속 전용 일회성 보안 토큰
LOCAL_TOKEN = secrets.token_hex(16)

# 런타임 상태 (함수 간 공유, state.X 형태로 접근)
authenticated_sessions = {}          # token -> id mapping
failed_attempts_per_ip = {}          # IP별 타임스탬프 목록 (Rate Limiting)
access_logs = []                     # 메모리상 접속 기록

active_processes = {}                # 서버 이름 -> Popen
server_logs = {}                     # 서버 이름 -> 로그 리스트
current_view_server = None           # 현재 선택된 서버
server_players = {}                   # 서버 이름 -> 플레이어 정보
last_backup_times = {}               # 서버 이름 -> 마지막 백업 시각

# WebSocket 클라이언트 IP 추적용 스레드 로컬 저장소
_client_ip_local = threading.local()
