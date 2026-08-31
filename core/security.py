import datetime
import json
import time
import hashlib
import eel
from . import state

# ==========================================================
# [보안] WebSocket 클라이언트 IP 추적
# Eel의 _process_message를 후킹하여 클라이언트 IP 캡처
# ==========================================================
original_process_message = eel._process_message

def patched_process_message(message, ws):
    try:
        environ = ws.environ if hasattr(ws, 'environ') else {}
        state._client_ip_local.value = environ.get('REMOTE_ADDR', 'unknown')
    except:
        state._client_ip_local.value = 'unknown'
    return original_process_message(message, ws)

eel._process_message = patched_process_message

def get_client_ip():
    return getattr(state._client_ip_local, 'value', 'unknown')

# ==========================================================
# [보안 검증 헬퍼 함수]
# 개발자 도구(F12) 우회 및 무력화 방지를 위한 서버 측 2차 권한 검증
# ==========================================================
def is_auth_verified(token):
    # 1. 로컬 토큰 확인
    if token == state.LOCAL_TOKEN:
        return True
    # 2. 인증된 세션 토큰 확인
    return token in state.authenticated_sessions

# ==========================================================
# [접속 기록 로그]
# ==========================================================
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
    state.access_logs.append(entry)
    try:
        with open(state.ACCESS_LOG_FILE, 'a', encoding='utf-8') as f:
            f.write(json.dumps(entry, ensure_ascii=False) + '\n')
    except:
        pass
