import os
import secrets
import shutil
import time
from pathlib import Path
from typing import Dict, Optional

from fastapi import APIRouter, Request, Response, Depends, HTTPException, UploadFile, File
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse

from . import config

router = APIRouter(prefix="/adbot")

# 简单 token 认证
_tokens: Dict[str, float] = {}
TOKEN_TTL = 86400  # 24h


def _cleanup_tokens():
    now = time.time()
    expired = [t for t, ts in _tokens.items() if now - ts > TOKEN_TTL]
    for t in expired:
        del _tokens[t]


def _validate_token(request: Request) -> bool:
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        return False
    token = auth[7:]
    if token not in _tokens:
        return False
    if time.time() - _tokens[token] > TOKEN_TTL:
        del _tokens[token]
        return False
    return True


def require_auth(request: Request):
    if not _validate_token(request):
        raise HTTPException(status_code=401, detail="未登录或登录已过期")


# HTML 面板
TEMPLATE_PATH = Path(__file__).parent / "templates" / "index.html"


@router.get("/", response_class=HTMLResponse)
async def dashboard():
    if not TEMPLATE_PATH.exists():
        return HTMLResponse("<h1>模板文件不存在</h1>", status_code=500)
    return HTMLResponse(TEMPLATE_PATH.read_text(encoding="utf-8"))


# 登录
@router.post("/api/login")
async def login(request: Request):
    body = await request.json()
    username = body.get("username", "")
    password = body.get("password", "")

    sys_cfg = config.plugin_config.system
    if username != sys_cfg.panel_username or not sys_cfg.check_password(password):
        return JSONResponse({"ok": False, "msg": "用户名或密码错误"}, 401)

    _cleanup_tokens()
    token = secrets.token_hex(32)
    _tokens[token] = time.time()

    return {"ok": True, "token": token, "initialized": sys_cfg.panel_initialized}


# 系统配置
@router.get("/api/system")
async def get_system(request: Request, _=Depends(require_auth)):
    sys_cfg = config.plugin_config.system
    return {
        "host": sys_cfg.host,
        "port": sys_cfg.port,
        "superusers": sys_cfg.superusers,
        "log_level": sys_cfg.log_level,
        "onebot_connection": sys_cfg.onebot_connection,
        "onebot_ws_urls": sys_cfg.onebot_ws_urls,
        "onebot_api_roots": sys_cfg.onebot_api_roots,
        "panel_username": sys_cfg.panel_username,
        "panel_initialized": sys_cfg.panel_initialized,
        "napcat_path": sys_cfg.napcat_path,
        "napcat_qq_number": sys_cfg.napcat_qq_number,
        "napcat_auto_start": sys_cfg.napcat_auto_start,
    }


@router.post("/api/system")
async def update_system(request: Request, _=Depends(require_auth)):
    body = await request.json()
    sys_cfg = config.plugin_config.system

    if "host" in body:
        sys_cfg.host = body["host"]
    if "port" in body:
        sys_cfg.port = int(body["port"])
    if "superusers" in body:
        sys_cfg.superusers = [str(s) for s in body["superusers"]]
    if "log_level" in body:
        sys_cfg.log_level = body["log_level"]
    if "onebot_connection" in body:
        sys_cfg.onebot_connection = body["onebot_connection"]
    if "onebot_ws_urls" in body:
        sys_cfg.onebot_ws_urls = body["onebot_ws_urls"]
    if "onebot_api_roots" in body:
        sys_cfg.onebot_api_roots = body["onebot_api_roots"]
    if "panel_initialized" in body:
        sys_cfg.panel_initialized = body["panel_initialized"]
    if "napcat_path" in body:
        sys_cfg.napcat_path = body["napcat_path"]
    if "napcat_qq_number" in body:
        sys_cfg.napcat_qq_number = str(body["napcat_qq_number"])
    if "napcat_auto_start" in body:
        sys_cfg.napcat_auto_start = body["napcat_auto_start"]

    config.save_config()
    return {"ok": True, "msg": "系统配置已保存，部分设置需要重启后生效"}


@router.post("/api/system/password")
async def change_password(request: Request, _=Depends(require_auth)):
    body = await request.json()
    old_pw = body.get("old_password", "")
    new_pw = body.get("new_password", "")

    sys_cfg = config.plugin_config.system
    if not sys_cfg.check_password(old_pw):
        return JSONResponse({"ok": False, "msg": "旧密码错误"}, 400)

    if len(new_pw) < 6:
        return JSONResponse({"ok": False, "msg": "新密码至少6位"}, 400)

    sys_cfg.set_password(new_pw)
    config.save_config()
    return {"ok": True, "msg": "密码修改成功"}


@router.post("/api/system/restart")
async def restart_bot(request: Request, _=Depends(require_auth)):
    config.save_config()
    os._exit(0)


# 插件配置
@router.get("/api/config")
async def get_config(request: Request, _=Depends(require_auth)):
    return config.plugin_config.model_dump(mode="json")


@router.post("/api/config/global")
async def update_global(request: Request, _=Depends(require_auth)):
    body = await request.json()
    gs = config.plugin_config.global_settings

    if "keywords" in body:
        gs.keywords = body["keywords"]
    if "schedule_delay_min" in body:
        gs.schedule_delay_min = int(body["schedule_delay_min"])
    if "schedule_delay_max" in body:
        gs.schedule_delay_max = int(body["schedule_delay_max"])
    if "typing_duration_min" in body:
        gs.typing_duration_min = int(body["typing_duration_min"])
    if "typing_duration_max" in body:
        gs.typing_duration_max = int(body["typing_duration_max"])
    if "default_message_limit_min" in body:
        gs.default_message_limit_min = int(body["default_message_limit_min"])
    if "default_message_limit_max" in body:
        gs.default_message_limit_max = int(body["default_message_limit_max"])
    if "quiet_hours_start" in body:
        gs.quiet_hours_start = int(body["quiet_hours_start"])
    if "quiet_hours_end" in body:
        gs.quiet_hours_end = int(body["quiet_hours_end"])

    config.save_config()
    return {"ok": True}


@router.post("/api/config/groups/{group_id}")
async def update_group(group_id: int, request: Request, _=Depends(require_auth)):
    body = await request.json()
    gid = str(group_id)

    if gid not in config.plugin_config.groups:
        config.plugin_config.groups[gid] = config.GroupConfig(
            text_messages=[config.DEFAULT_TEXT_MESSAGE],
            message_limit=config.plugin_config.global_settings.default_message_limit_min,
        )

    group = config.plugin_config.groups[gid]

    if "enabled" in body:
        group.enabled = body["enabled"]
    if "text_messages" in body:
        group.text_messages = body["text_messages"]
    if "image_path" in body:
        group.image_path = body["image_path"]
    if "message_limit_min" in body:
        group.message_limit_min = max(5, int(body["message_limit_min"]))
    if "message_limit_max" in body:
        group.message_limit_max = max(group.message_limit_min, int(body["message_limit_max"]))
    if "min_interval_seconds" in body:
        group.min_interval_seconds = int(body["min_interval_seconds"])
    if "split_send" in body:
        group.split_send = body["split_send"]

    config.save_config()
    return {"ok": True}


@router.delete("/api/config/groups/{group_id}")
async def delete_group(group_id: int, _=Depends(require_auth)):
    gid = str(group_id)
    if gid in config.plugin_config.groups:
        del config.plugin_config.groups[gid]
        config.save_config()
        return {"ok": True}
    return JSONResponse({"ok": False, "msg": "群组不存在"}, 404)


# 状态
@router.get("/api/status")
async def get_status(_=Depends(require_auth)):
    groups = {}
    for gid, g in config.plugin_config.groups.items():
        groups[gid] = {
            "enabled": g.enabled,
            "counter": g.counter,
            "message_limit": g.message_limit,
            "last_sent_time": g.last_sent_time,
        }
    return {"groups": groups}


@router.get("/api/logs")
async def get_logs(_=Depends(require_auth)):
    return {"logs": [l.model_dump() for l in config.plugin_config.send_log]}


@router.get("/api/connection-status")
async def connection_status(_=Depends(require_auth)):
    from nonebot import get_driver
    driver = get_driver()

    bots = {}
    for bot_id, bot in driver._bots.items():
        bots[bot_id] = {
            "adapter": type(bot.adapter).__name__,
            "self_id": bot.self_id,
        }

    sys_cfg = config.plugin_config.system
    conn_type = sys_cfg.onebot_connection
    conn_labels = {
        "reverse_ws": "反向 WebSocket",
        "forward_ws": "正向 WebSocket",
        "http_post": "HTTP POST",
    }

    ws_url = f"ws://{sys_cfg.host}:{sys_cfg.port}/onebot/v11/ws"

    return {
        "connected": len(bots) > 0,
        "bots": bots,
        "connection_type": conn_labels.get(conn_type, conn_type),
        "hint": (
            f"请在 QQ 协议端（如 NapCat/Lagrange）配置反向 WebSocket 连接到: {ws_url}"
            if conn_type == "reverse_ws"
            else f"NoneBot 将主动连接到: {sys_cfg.onebot_ws_urls}"
            if conn_type == "forward_ws"
            else "请在 QQ 协议端配置 HTTP POST 推送到 NoneBot"
        ),
    }


# NapCat 进程管理
@router.get("/api/napcat-status")
async def napcat_status_api(_=Depends(require_auth)):
    import bot as bot_module
    running, msg = bot_module.get_napcat_status()
    found = bot_module._detect_launcher() is not None
    return {
        "running": running,
        "msg": msg,
        "found": found,
    }


@router.post("/api/napcat-start")
async def napcat_start_api(_=Depends(require_auth)):
    import bot as bot_module
    ok, msg = bot_module.start_napcat()
    return {"ok": ok, "msg": msg}


@router.post("/api/napcat-stop")
async def napcat_stop_api(_=Depends(require_auth)):
    import bot as bot_module
    ok, msg = bot_module.stop_napcat()
    return {"ok": ok, "msg": msg}


# ── NapCat WebUI 代理辅助函数 ──────────────────────────────────

def _get_napcat_webui_base() -> str:
    """从 webui.json 读取 NapCat WebUI 地址"""
    import json
    webui_config = Path("NapCat.Shell") / "config" / "webui.json"
    if webui_config.exists():
        try:
            data = json.loads(webui_config.read_text(encoding="utf-8"))
            port = data.get("port", 6099)
            host = data.get("host", "127.0.0.1")
            if host in ("::", "0.0.0.0"):
                host = "127.0.0.1"
            return f"http://{host}:{port}"
        except Exception:
            pass
    return "http://127.0.0.1:6099"


def _get_napcat_webui_token() -> str:
    """从 webui.json 读取 NapCat WebUI token"""
    import json
    webui_config = Path("NapCat.Shell") / "config" / "webui.json"
    if webui_config.exists():
        try:
            data = json.loads(webui_config.read_text(encoding="utf-8"))
            return data.get("token", "")
        except Exception:
            pass
    return ""


_napcat_credential = {"token": "", "credential": "", "expires": 0}


async def _get_napcat_credential() -> Optional[str]:
    """获取或刷新 NapCat WebUI 认证凭证（缓存1小时）"""
    import hashlib
    import httpx

    now = time.time()
    if _napcat_credential["credential"] and now < _napcat_credential["expires"] - 300:
        return _napcat_credential["credential"]

    token = _get_napcat_webui_token()
    if not token:
        return None

    password_hash = hashlib.sha256((token + ".napcat").encode()).hexdigest()
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            resp = await client.post(
                f"{_get_napcat_webui_base()}/auth/login",
                json={"hash": password_hash},
            )
            data = resp.json()
            if data.get("code") == 0:
                cred = data["data"]["Credential"]
                _napcat_credential["token"] = token
                _napcat_credential["credential"] = cred
                _napcat_credential["expires"] = now + 3600
                return cred
    except Exception:
        pass
    return None


async def _call_napcat_webui(path: str) -> dict:
    """调用 NapCat WebUI API"""
    import httpx

    cred = await _get_napcat_credential()
    if not cred:
        return {"code": -1, "msg": "NapCat WebUI 认证失败"}
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(
                f"{_get_napcat_webui_base()}{path}",
                headers={"Authorization": cred},
            )
            return resp.json()
    except Exception as e:
        return {"code": -1, "msg": str(e)}


# ── 二维码相关接口 ────────────────────────────────────────────

@router.get("/api/napcat-qrcode")
async def napcat_qrcode(_=Depends(require_auth)):
    import bot as bot_module
    qrcode_path = bot_module.NAPCAT_DIR / "cache" / "qrcode.png"
    if qrcode_path.exists():
        return FileResponse(str(qrcode_path), media_type="image/png")
    return JSONResponse({"ok": False, "msg": "二维码未生成"}, 404)


@router.get("/api/napcat-qrcode-status")
async def napcat_qrcode_status(_=Depends(require_auth)):
    """返回二维码文件状态（用于前端检测文件是否被 NapCat 重新生成）"""
    import bot as bot_module
    from nonebot import get_driver

    qrcode_path = bot_module.NAPCAT_DIR / "cache" / "qrcode.png"
    file_exists = qrcode_path.exists()
    file_mtime = qrcode_path.stat().st_mtime if file_exists else None
    connected = len(get_driver()._bots) > 0

    return {"isLogin": connected, "qrFileExists": file_exists, "qrFileMtime": file_mtime}


@router.get("/api/napcat-login-status")
async def napcat_login_status(_=Depends(require_auth)):
    """检查登录状态，同时查询 NapCat WebUI 获取 loginError"""
    from nonebot import get_driver

    connected = len(get_driver()._bots) > 0
    login_error = ""

    result = await _call_napcat_webui("/QQLogin/CheckLoginStatus")
    if result.get("code") == 0:
        login_error = result.get("data", {}).get("loginError", "")

    return {"isLogin": connected, "loginError": login_error}


@router.post("/api/napcat-refresh-qrcode")
async def napcat_refresh_qrcode(_=Depends(require_auth)):
    """代理调用 NapCat WebUI 刷新二维码，回退到删除文件"""
    result = await _call_napcat_webui("/QQLogin/RefreshQRcode")
    if result.get("code") == 0:
        return {"ok": True}
    # NapCat WebUI 不可达时回退：删除文件让 NapCat 自行重新生成
    import bot as bot_module
    qrcode_path = bot_module.NAPCAT_DIR / "cache" / "qrcode.png"
    if qrcode_path.exists():
        qrcode_path.unlink()
    return {"ok": True, "fallback": True}


# 图片上传
@router.post("/api/upload-image")
async def upload_image(file: UploadFile = File(...), _=Depends(require_auth)):
    if not file.filename:
        return JSONResponse({"ok": False, "msg": "无文件名"}, 400)

    resources_dir = config.PLUGIN_DIR.parent / "resources" / "images"
    resources_dir.mkdir(parents=True, exist_ok=True)

    safe_name = Path(file.filename).name
    dest = resources_dir / safe_name

    content = await file.read()
    dest.write_bytes(content)

    rel_path = f"resources/images/{safe_name}"
    return {"ok": True, "path": rel_path}
