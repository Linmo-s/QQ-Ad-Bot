import sys
import json
import platform
import subprocess
from pathlib import Path

# 确保项目根目录在 sys.path 中
ROOT = Path(__file__).parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

CONFIG_PATH = ROOT / "massages_image_massage" / "data" / "config.json"

# NapCat 目录
NAPCAT_DIR = ROOT / "NapCat.Shell"


def _read_system_config():
    if not CONFIG_PATH.exists():
        return _default_system_config()
    try:
        data = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
        return data.get("system", _default_system_config())
    except Exception:
        return _default_system_config()


def _default_system_config():
    return {
        "host": "127.0.0.1",
        "port": 8080,
        "superusers": [],
        "log_level": "INFO",
    }


def _detect_launcher():
    """检测 NapCat.Shell 目录和 launcher.bat 是否存在"""
    if not NAPCAT_DIR.exists():
        return None
    ver = platform.version()
    major = int(ver.split('.')[0])
    if major >= 10:
        launcher = NAPCAT_DIR / "launcher-win10.bat"
        if launcher.exists():
            return launcher
    launcher = NAPCAT_DIR / "launcher.bat"
    return launcher if launcher.exists() else None


def _find_napcat_process():
    """通过 tasklist 查找 NapCatWinBootMain.exe 进程"""
    try:
        result = subprocess.run(
            ["tasklist", "/FI", "IMAGENAME eq NapCatWinBootMain.exe", "/NH"],
            capture_output=True, text=True, timeout=5,
        )
        return "NapCatWinBootMain.exe" in result.stdout
    except Exception:
        return False


def _generate_napcat_config(sys_cfg):
    qq_number = sys_cfg.get("napcat_qq_number", "")
    if not qq_number:
        return

    config_dir = NAPCAT_DIR / "config"
    config_dir.mkdir(parents=True, exist_ok=True)

    host = sys_cfg.get("host", "127.0.0.1")
    port = sys_cfg.get("port", 8080)

    onebot_config = {
        "network": {
            "httpServers": [],
            "httpClients": [],
            "websocketServers": [],
            "websocketClients": [{
                "name": "NoneBot2",
                "enable": True,
                "url": f"ws://{host}:{port}/onebot/v11/ws",
                "messagePostFormat": "array",
                "reportSelfMessage": False,
                "reconnectInterval": 5000,
                "token": "",
                "debug": False,
                "heartInterval": 30000,
            }],
        },
        "musicSignUrl": "",
        "enableLocalFile2Url": False,
        "parseMultMsg": False,
    }

    config_file = config_dir / f"onebot11_{qq_number}.json"
    config_file.write_text(
        json.dumps(onebot_config, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )


def get_napcat_status():
    """查询 NapCat 进程状态（通过 tasklist）"""
    if _find_napcat_process():
        return True, "运行中"
    return False, "未启动"


def start_napcat():
    """通过 launcher.bat 启动 NapCat"""
    launcher = _detect_launcher()
    if not launcher:
        return False, "未找到 NapCat，请确认 NapCat.Shell 目录存在"

    sys_cfg = _read_system_config()
    _generate_napcat_config(sys_cfg)

    qq_number = sys_cfg.get("napcat_qq_number", "")
    if qq_number:
        cmd = ["cmd", "/c", str(launcher), "-q", qq_number]
    else:
        cmd = ["cmd", "/c", str(launcher)]

    print(f"  正在启动 NapCat (QQ: {qq_number or '扫码登录'})...")
    # launcher.bat 会自动提权启动独立进程
    subprocess.Popen(cmd, cwd=str(NAPCAT_DIR))
    return True, "NapCat 已启动"


def stop_napcat():
    """通过 taskkill 终止 NapCatWinBootMain.exe 进程"""
    if not _find_napcat_process():
        return False, "NapCat 未在运行"
    try:
        subprocess.run(
            ["taskkill", "/F", "/IM", "NapCatWinBootMain.exe"],
            capture_output=True, timeout=10,
        )
        return True, "NapCat 已停止"
    except Exception as e:
        return False, f"停止失败: {e}"


def main():
    sys_cfg = _read_system_config()

    import nonebot
    from nonebot.adapters.onebot.v11 import Adapter as OneBotV11Adapter

    init_kwargs = {
        "driver": "~fastapi",
        "host": sys_cfg["host"],
        "port": sys_cfg["port"],
        "superusers": set(sys_cfg.get("superusers", [])),
        "log_level": sys_cfg.get("log_level", "INFO"),
    }

    conn = sys_cfg.get("onebot_connection", "reverse_ws")
    if conn == "forward_ws" and sys_cfg.get("onebot_ws_urls"):
        init_kwargs["onebot_ws_urls"] = set(sys_cfg["onebot_ws_urls"])
    if conn == "http_post" and sys_cfg.get("onebot_api_roots"):
        init_kwargs["onebot_api_roots"] = sys_cfg["onebot_api_roots"]

    nonebot.init(**init_kwargs)

    driver = nonebot.get_driver()
    driver.register_adapter(OneBotV11Adapter)

    nonebot.load_plugin("massages_image_massage")

    @driver.on_shutdown
    async def _shutdown():
        stop_napcat()

    print(f"\n{'='*50}")
    print(f"  QQ广告机器人已启动")
    print(f"  管理面板: http://{sys_cfg['host']}:{sys_cfg['port']}/adbot/")
    print(f"  默认密码: admin123 (首次登录请修改)")
    print(f"{'='*50}\n")

    nonebot.run()


if __name__ == "__main__":
    main()
