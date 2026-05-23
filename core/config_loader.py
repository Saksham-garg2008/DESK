import json
import os
from pathlib import Path


BASE_DIR = Path(__file__).parent.parent
CONFIG_DIR = BASE_DIR / "config"


def _load(filename: str) -> dict:
    path = CONFIG_DIR / filename
    if not path.exists():
        return {}
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _save(filename: str, data: dict) -> None:
    path = CONFIG_DIR / filename
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


def load_app_config() -> dict:
    return _load("app.json")


def save_app_config(data: dict) -> None:
    _save("app.json", data)


def load_agents_config() -> dict:
    return _load("agents.json")


def save_agents_config(data: dict) -> None:
    _save("agents.json", data)


def load_keys_config() -> dict:
    return _load("keys.json")


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
