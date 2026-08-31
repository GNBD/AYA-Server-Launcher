import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

import webview

from client.api import ClientApi
from shared.web import ApiHttpServer


def _resource_path(rel) -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys._MEIPASS) / rel
    return Path(__file__).resolve().parent / rel


GUI_DIR = _resource_path("client/gui")


def main():
    api = ClientApi()
    http = ApiHttpServer(api, GUI_DIR)
    port = http.start()
    window = webview.create_window(
        "AYANAT",
        url=http.url,
        width=460,
        height=600,
        min_size=(400, 500),
    )
    webview.start(debug=False)
    try:
        api.disconnect()
    except Exception:
        pass
    http.stop()


if __name__ == "__main__":
    main()
