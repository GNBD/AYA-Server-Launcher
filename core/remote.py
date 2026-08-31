import os
import time
import json
import hashlib
import secrets
import eel
from . import state, security, config

@eel.expose
def save_remote_setting_py(token, enabled, raw_password):
    if not security.is_auth_verified(token): return "❌ Unauthorized"
    try:
        cfg = config.get_launcher_config_py(token)
        cfg["remote_enabled"] = enabled

        try:
            current = {}
            if os.path.exists(state.LAUNCHER_CONFIG_FILE):
                with open(state.LAUNCHER_CONFIG_FILE, 'r', encoding='utf-8') as f:
                    current = json.load(f)
            current.update(cfg)
            with open(state.LAUNCHER_CONFIG_FILE, 'w', encoding='utf-8') as f:
                json.dump(current, f, indent=4)
        except:
            return "❌ 저장 실패"

        if raw_password and raw_password.strip() != "":
            hashed_pw = hashlib.sha256(raw_password.encode('utf-8')).hexdigest()
            with open(state.REMOTE_KEY_FILE, 'w', encoding='utf-8') as f:
                f.write(hashed_pw)

        if not enabled:
            try:
                eel.remote_refresh_js()()
            except:
                pass

        action = "Remote Disable" if not enabled else "Remote Config Change"
        security.add_access_log(action, "success")
        return "✅ Remote config saved"
    except Exception as e:
        security.add_access_log("Remote Config Change", "error", str(e))
        return f"❌ Error: {e}"

@eel.expose
def get_access_logs_py(token):
    if not security.is_auth_verified(token): return []
    logs = []
    try:
        if os.path.exists(state.ACCESS_LOG_FILE):
            with open(state.ACCESS_LOG_FILE, 'r', encoding='utf-8') as f:
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
    security.add_access_log("Page Access", "blocked", "Unauthenticated session")
    return "ok"

@eel.expose
def verify_remote_password_py(token, raw_password):
    now = time.time()
    client_ip = security.get_client_ip()
    failed_attempts_per_ip = state.failed_attempts_per_ip

    if client_ip not in failed_attempts_per_ip:
        failed_attempts_per_ip[client_ip] = []
    attempts = [t for t in failed_attempts_per_ip[client_ip] if now - t < 300]
    failed_attempts_per_ip[client_ip] = attempts
    remaining = max(0, 5 - len(attempts))

    if len(attempts) >= 5:
        security.add_access_log("Password Auth", "blocked", "IP blocked (5+ attempts)")
        return {"success": False, "remaining": 0, "token": None}

    cfg = config.get_launcher_config_py(token)
    if not cfg.get("remote_enabled", False):
        return {"success": False, "remaining": remaining, "token": None}

    if not os.path.exists(state.REMOTE_KEY_FILE):
        security.add_access_log("Password Auth", "fail", "Password file not found")
        return {"success": False, "remaining": remaining, "token": None}

    try:
        with open(state.REMOTE_KEY_FILE, 'r', encoding='utf-8') as f:
            stored_hashed = f.read().strip()

        input_hashed = hashlib.sha256(raw_password.encode('utf-8')).hexdigest()
        success = (input_hashed == stored_hashed)
        if success:
            new_token = secrets.token_hex(16)
            state.authenticated_sessions[new_token] = True
            security.add_access_log("Password Auth", "success", "Remote access authenticated")
            return {"success": True, "remaining": remaining, "token": new_token}
        failed_attempts_per_ip[client_ip].append(now)
        remaining = max(0, 5 - len(failed_attempts_per_ip[client_ip]))
        security.add_access_log("Password Auth", "fail", f"Wrong password (attempts left: {remaining})")
        return {"success": False, "remaining": remaining, "token": None}
    except:
        security.add_access_log("Password Auth", "error", "Auth exception")
        return {"success": False, "remaining": remaining, "token": None}
