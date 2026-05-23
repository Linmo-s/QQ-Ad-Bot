import json
import random
import hashlib
from pathlib import Path
from typing import Dict, List, Optional
from datetime import datetime

from pydantic import BaseModel, Field


# 配置文件路径：插件目录下的 data/config.json
PLUGIN_DIR = Path(__file__).parent
DATA_DIR = PLUGIN_DIR / "data"
CONFIG_PATH = DATA_DIR / "config.json"

DEFAULT_TEXT_MESSAGE = "请通过管理面板配置广告文案"

DEFAULT_GROUPS = {}


class SystemConfig(BaseModel):
    host: str = "127.0.0.1"
    port: int = 8080
    superusers: List[str] = Field(default_factory=list)
    log_level: str = "INFO"
    onebot_connection: str = "reverse_ws"
    onebot_ws_urls: List[str] = Field(default_factory=lambda: ["ws://127.0.0.1:6700"])
    onebot_api_roots: Dict[str, str] = Field(default_factory=dict)
    panel_username: str = "admin"
    panel_password_hash: str = ""
    panel_initialized: bool = False
    napcat_path: str = ""
    napcat_qq_number: str = ""
    napcat_auto_start: bool = True

    def set_password(self, raw_password: str):
        self.panel_password_hash = hashlib.sha256(raw_password.encode()).hexdigest()

    def check_password(self, raw_password: str) -> bool:
        return self.panel_password_hash == hashlib.sha256(raw_password.encode()).hexdigest()


class GroupConfig(BaseModel):
    enabled: bool = True
    text_messages: List[str] = Field(default_factory=lambda: [DEFAULT_TEXT_MESSAGE])
    image_path: str = "resources/image/jd/jdt.jpg"
    message_limit: int = 8
    message_limit_min: int = 5
    message_limit_max: int = 15
    min_interval_seconds: int = 7200
    split_send: bool = False
    counter: int = 0
    last_sent_time: Optional[str] = None

    def get_image_path(self) -> Path:
        p = Path(self.image_path)
        if p.is_absolute():
            return p
        return PLUGIN_DIR.parent / p


class GlobalSettings(BaseModel):
    keywords: List[str] = Field(default_factory=lambda: ["场照", "接妆", "接单", "票代"])
    schedule_delay_min: int = 30
    schedule_delay_max: int = 90
    typing_duration_min: int = 3
    typing_duration_max: int = 6
    default_message_limit_min: int = 5
    default_message_limit_max: int = 15
    quiet_hours_start: int = 2
    quiet_hours_end: int = 7


class SendLogEntry(BaseModel):
    time: str
    group_id: int
    status: str
    message: str = ""


class PluginConfig(BaseModel):
    version: int = 1
    system: SystemConfig = Field(default_factory=SystemConfig)
    global_settings: GlobalSettings = Field(default_factory=GlobalSettings)
    groups: Dict[str, GroupConfig] = Field(default_factory=lambda: {})
    send_log: List[SendLogEntry] = Field(default_factory=list)


# 全局配置单例
plugin_config: Optional[PluginConfig] = None
_config_dirty = False


def load_config() -> PluginConfig:
    global plugin_config, _config_dirty

    DATA_DIR.mkdir(parents=True, exist_ok=True)

    if CONFIG_PATH.exists():
        try:
            data = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
            plugin_config = PluginConfig(**data)
        except Exception:
            plugin_config = _create_default_config()
    else:
        plugin_config = _create_default_config()
        save_config()

    _config_dirty = False
    return plugin_config


def _create_default_config() -> PluginConfig:
    cfg = PluginConfig(groups=DEFAULT_GROUPS)
    cfg.system.set_password("admin123")
    return cfg


def save_config():
    global _config_dirty

    if plugin_config is None:
        return

    DATA_DIR.mkdir(parents=True, exist_ok=True)

    tmp_path = CONFIG_PATH.with_suffix(".tmp")
    tmp_path.write_text(
        plugin_config.model_dump_json(indent=2, exclude_none=True),
        encoding="utf-8",
    )
    tmp_path.replace(CONFIG_PATH)
    _config_dirty = False


def mark_dirty():
    global _config_dirty
    _config_dirty = True


def flush_if_dirty():
    if _config_dirty:
        save_config()


def regenerate_message_limit(group_id: int) -> int:
    group = get_group(group_id)
    if group is None:
        return 8

    lo = max(group.message_limit_min, 5)
    hi = max(group.message_limit_max, lo)
    group.message_limit = random.randint(lo, hi)
    save_config()
    return group.message_limit


def increment_counter(group_id: int) -> int:
    group = get_group(group_id)
    if group is None:
        return 0
    group.counter += 1
    mark_dirty()
    return group.counter


def reset_counter(group_id: int):
    group = get_group(group_id)
    if group is None:
        return
    group.counter = 0
    save_config()


def get_group(group_id: int) -> Optional[GroupConfig]:
    if plugin_config is None:
        return None
    return plugin_config.groups.get(str(group_id))


def update_last_sent(group_id: int):
    group = get_group(group_id)
    if group is None:
        return
    group.last_sent_time = datetime.now().isoformat()
    save_config()


def add_send_log(group_id: int, status: str, message: str = ""):
    if plugin_config is None:
        return
    entry = SendLogEntry(
        time=datetime.now().isoformat(),
        group_id=group_id,
        status=status,
        message=message,
    )
    plugin_config.send_log.append(entry)
    if len(plugin_config.send_log) > 100:
        plugin_config.send_log = plugin_config.send_log[-100:]
    save_config()


def get_system_config() -> SystemConfig:
    if plugin_config is None:
        load_config()
    return plugin_config.system
