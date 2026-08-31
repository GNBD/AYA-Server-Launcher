import eel
from . import state, security, tunnel_api

# ClientApi는 내부에 asyncio 루프 스레드를 가지므로 최초 사용 시 1회만 생성
_api = None

def get_api():
    global _api
    if _api is None:
        _api = tunnel_api.ClientApi()
    return _api

def _guard(token):
    return security.is_auth_verified(token)

# ==========================================================
# [터널] 릴레이 서버 연결 / 로그인 / 터널 제어
# (client/ClientApi 기능을 그대로 노출, 함수명은 런처 규약에 맞춰 *_py)
# ==========================================================
@eel.expose
def tunnel_get_last_host_py(token):
    if not _guard(token): return {"success": False, "error": "Unauthorized"}
    return get_api().get_last_host()

@eel.expose
def tunnel_save_last_host_py(token, host):
    if not _guard(token): return {"success": False, "error": "Unauthorized"}
    return get_api().save_last_host(host)

@eel.expose
def tunnel_connect_py(token, server_host=None, server_port=None):
    if not _guard(token): return {"success": False, "error": "Unauthorized"}
    return get_api().connect(server_host, server_port)

@eel.expose
def tunnel_login_py(token, username, password):
    if not _guard(token): return {"success": False, "error": "Unauthorized"}
    return get_api().login(username, password)

@eel.expose
def tunnel_disconnect_py(token):
    if not _guard(token): return {"success": False, "error": "Unauthorized"}
    return get_api().disconnect()

@eel.expose
def tunnel_start_background_tasks_py(token):
    if not _guard(token): return {"success": False, "error": "Unauthorized"}
    return get_api().start_background_tasks()

@eel.expose
def tunnel_open_tunnel_py(token, target_host, target_port, proto="tcp"):
    if not _guard(token): return {"success": False, "error": "Unauthorized"}
    return get_api().open_tunnel(target_host, target_port, proto)

@eel.expose
def tunnel_close_tunnel_py(token):
    if not _guard(token): return {"success": False, "error": "Unauthorized"}
    return get_api().close_tunnel()

@eel.expose
def tunnel_get_status_py(token):
    if not _guard(token): return {"success": False, "error": "Unauthorized"}
    return get_api().get_status()

@eel.expose
def tunnel_get_tunnel_info_py(token):
    if not _guard(token): return {"success": False, "error": "Unauthorized"}
    return get_api().get_tunnel_info()

@eel.expose
def tunnel_change_password_py(token, old_password, new_password):
    if not _guard(token): return {"success": False, "error": "Unauthorized"}
    return get_api().change_password(old_password, new_password)

@eel.expose
def tunnel_get_connections_py(token):
    if not _guard(token): return {"success": False, "error": "Unauthorized"}
    return get_api().get_connections()

@eel.expose
def tunnel_kick_connection_py(token, conn_id):
    if not _guard(token): return {"success": False, "error": "Unauthorized"}
    return get_api().kick_connection(conn_id)
