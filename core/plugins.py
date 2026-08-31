import os
import eel
from . import state, security

@eel.expose
def get_plugin_list_py(token):
    if not security.is_auth_verified(token): return []
    if not state.current_view_server: return []

    plugins_dir = os.path.join(state.BASE_SERVERS_DIR, state.current_view_server, "plugins")
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
    if not security.is_auth_verified(token): return "❌ Unauthorized"
    if not state.current_view_server: return "❌ No Server"
    plugins_dir = os.path.join(state.BASE_SERVERS_DIR, state.current_view_server, "plugins")
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
    if not security.is_auth_verified(token): return "❌ Unauthorized"
    if not state.current_view_server: return "❌ No Server"
    plugins_dir = os.path.join(state.BASE_SERVERS_DIR, state.current_view_server, "plugins")
    target_path = os.path.join(plugins_dir, filename)

    if not os.path.exists(target_path): return "❌ File Not Found"

    try:
        os.remove(target_path)
        return "✅ Deleted"
    except Exception as e:
        return f"❌ Error: {e}"
