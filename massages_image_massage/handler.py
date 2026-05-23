import random
from datetime import datetime, timedelta

from nonebot import on_message
from nonebot.adapters.onebot.v11 import Bot, GroupMessageEvent
from nonebot.typing import T_State
from nonebot_plugin_apscheduler import scheduler
from nonebot.log import logger

from . import config, sender

message_listener = on_message()


@message_listener.handle()
async def handle_group_message(bot: Bot, event: GroupMessageEvent, state: T_State):
    if config.plugin_config is None:
        return

    group_id = event.group_id
    group = config.get_group(group_id)

    if group is None or not group.enabled:
        return

    gs = config.plugin_config.global_settings
    message_text = event.get_plaintext()
    if not any(kw in message_text for kw in gs.keywords):
        return

    count = config.increment_counter(group_id)
    logger.debug(f"群 {group_id} 关键词计数: {count}/{group.message_limit}")

    if count >= group.message_limit:
        config.reset_counter(group_id)
        delay_seconds = random.randint(gs.schedule_delay_min, gs.schedule_delay_max)
        run_time = datetime.now() + timedelta(seconds=delay_seconds)

        scheduler.add_job(
            sender.delayed_send,
            "date",
            run_date=run_time,
            args=[bot, group_id],
            id=f"delayed_send_{group_id}_{run_time.timestamp()}",
            replace_existing=True,
            misfire_grace_time=120,
        )
        logger.info(f"群 {group_id} 达到触发条件，将在 {delay_seconds} 秒后发送")
