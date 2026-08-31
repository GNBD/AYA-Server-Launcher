import json
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent

DEFAULT_CONFIG_PATH = BASE_DIR / "config.json"

DEFAULTS = {
    "server_host": "127.0.0.1",
    "server_port": 42137,
    "client_id": "",
    "token": "",
    "ping_interval": 30,
    "ping_timeout": 90,
    "max_backoff": 60,
    "tunnels": [
        {
            "tunnel_id": "main",
            "target_host": "127.0.0.1",
            "target_port": 25565,
        }
    ],
}


def load_config(path=None) -> dict:
    data = dict(DEFAULTS)
    if path is None:
        path = DEFAULT_CONFIG_PATH
    p = Path(path)
    if p.exists():
        data.update(json.loads(p.read_text(encoding="utf-8")))
    return data


def save_config(config: dict, path=None) -> None:
    if path is None:
        path = DEFAULT_CONFIG_PATH
    Path(path).write_text(
        json.dumps(config, indent=2, ensure_ascii=False), encoding="utf-8"
    )