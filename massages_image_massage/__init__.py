from nonebot.plugin import PluginMetadata
from nonebot import get_driver
from nonebot.log import logger

from . import config
from . import handler  # noqa: F401  注册消息监听
from . import sender   # noqa: F401  注册发送函数

__plugin_meta__ = PluginMetadata(
    name="关键词计数图文延迟发送",
    description="每群收到指定数量关键词消息后，随机延迟发送图文，增强防检测",
    usage="通过 Web 面板管理，访问 /adbot/",
)

driver = get_driver()


@driver.on_startup
async def _startup():
    cfg = config.load_config()

    try:
        from nonebot.drivers.fastapi import Driver as FastAPIDriver
        if isinstance(driver, FastAPIDriver):
            from .web import router
            driver.server_app.include_router(router)
            logger.info(
                f"管理面板已启动: http://{cfg.system.host}:{cfg.system.port}/adbot/"
            )
    except ImportError:
        logger.warning("FastAPI 驱动未安装，Web 面板不可用")
