import json
import os
from pathlib import Path


BASE_DIR = Path(__file__).parent.parent
CONFIG_DIR = BASE_DIR / "config"

# Default app.json content — used when file is missing or corrupt
_DEFAULT_APP_CONFIG = {
    "version": "2.0.0",
    "compute_mode": "high",
    "theme": "medium_grey",
    "response_length": "standard",
    "last_active_agent": None,
    "window": {
        "width": 1200,
        "height": 800,
        "sidebar_width": 52
    }
}


def _load(filename: str) -> dict:
    path = CONFIG_DIR / filename
    if not path.exists():
        return {}
    try:
        content = path.read_text(encoding="utf-8").strip()
        if not content:
            return {}
        return json.loads(content)
    except (json.JSONDecodeError, Exception):
        return {}


def _save(filename: str, data: dict) -> None:
    CONFIG_DIR.mkdir(exist_ok=True)
    path = CONFIG_DIR / filename
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


def load_app_config() -> dict:
    data = _load("app.json")
    if not data:
        # File was missing or corrupt — restore defaults and save
        _save("app.json", _DEFAULT_APP_CONFIG)
        return dict(_DEFAULT_APP_CONFIG)
    return data


def save_app_config(data: dict) -> None:
    _save("app.json", data)


def load_agents_config() -> dict:
    data = _load("agents.json")
    if not data:
        return {"agents": {}}
    return data


def save_agents_config(data: dict) -> None:
    _save("agents.json", data)


def load_keys_config() -> dict:
    data = _load("keys.json")
    if not data:
        return {"keys": {}}
    return data


def save_keys_config(data: dict) -> None:
    _save("keys.json", data)


def load_models_config() -> dict:
    return _load("models.json")


def get_agent_config(agent_name: str) -> dict:
    agents = load_agents_config()
    return agents.get("agents", {}).get(agent_name, {})


def set_agent_config(agent_name: str, config: dict) -> None:
    agents = load_agents_config()
    if "agents" not in agents:
        agents["agents"] = {}
    agents["agents"][agent_name] = config
    save_agents_config(agents)


def delete_agent_config(agent_name: str) -> None:
    agents = load_agents_config()
    if "agents" in agents and agent_name in agents["agents"]:
        del agents["agents"][agent_name]
        save_agents_config(agents)


def get_key(backend: str) -> str:
    keys = load_keys_config()
    return keys.get("keys", {}).get(backend, "")


def set_key(backend: str, value: str) -> None:
    keys = load_keys_config()
    if "keys" not in keys:
        keys["keys"] = {}
    keys["keys"][backend] = value
    save_keys_config(keys)


def get_app_setting(key: str, default=None):
    config = load_app_config()
    return config.get(key, default)


def set_app_setting(key: str, value) -> None:
    config = load_app_config()
    config[key] = value
    save_app_config(config)