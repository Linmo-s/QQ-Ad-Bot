import random
import asyncio
from datetime import datetime

from nonebot.log import logger
from nonebot.adapters.onebot.v11 import Bot, MessageSegment

from . import config


def _is_quiet_hours() -> bool:
    gs = config.plugin_config.global_settings
    now = datetime.now()
    hour = now.hour
    start, end = gs.quiet_hours_start, gs.quiet_hours_end
    if start < end:
        return start <= hour < end
    return hour >= start or hour < end


def _quiet_seconds_remaining() -> int:
    gs = config.plugin_config.global_settings
    now = datetime.now()
    start, end = gs.quiet_hours_start, gs.quiet_hours_end
    target = now.replace(hour=end, minute=0, second=0, microsecond=0)
    if start >= end:
        if now.hour >= start:
            target = target.replace(day=now.day + 1)
    elif now.hour < end:
        pass
    else:
        return 0
    delta = (target - now).total_seconds()
    return max(0, int(delta))


def _check_cooldown(group_id: int) -> int:
    group = config.get_group(group_id)
    if group is None or group.last_sent_time is None:
        return 0

    try:
        last = datetime.fromisoformat(group.last_sent_time)
    except (ValueError, TypeError):
        return 0

    elapsed = (datetime.now() - last).total_seconds()
    remaining = group.min_interval_seconds - int(elapsed)
    return max(0, remaining)


def _gauss_clamp(mu: float, sigma: float, lo: int, hi: int) -> int:
    val = random.gauss(mu, sigma)
    return max(lo, min(hi, int(round(val))))


async def delayed_send(bot: Bot, group_id: int):
    group = config.get_group(group_id)
    if group is None:
        return

    gs = config.plugin_config.global_settings

    try:
        # 检查静默时段
        if _is_quiet_hours():
            wait = _quiet_seconds_remaining()
            logger.info(f"群 {group_id} 处于静默时段，等待 {wait} 秒")
            await asyncio.sleep(wait)

        # 检查冷却间隔
        cooldown = _check_cooldown(group_id)
        if cooldown > 0:
            logger.info(f"群 {group_id} 冷却中，等待 {cooldown} 秒")
            await asyncio.sleep(cooldown)

        # 高斯分布打字延迟
        typing_mu = (gs.typing_duration_min + gs.typing_duration_max) / 2
        typing_sigma = (gs.typing_duration_max - gs.typing_duration_min) / 3
        typing_duration = _gauss_clamp(
            typing_mu, typing_sigma,
            gs.typing_duration_min, gs.typing_duration_max,
        )
        await asyncio.sleep(typing_duration)

        # 检查图片
        image_path = group.get_image_path()
        if not image_path.exists():
            logger.error(f"图片文件不存在: {image_path}")
            config.add_send_log(group_id, "error", f"图片不存在: {image_path}")
            return

        # 随机选择文本
        text = random.choice(group.text_messages) if group.text_messages else ""

        if group.split_send:
            # 拆分发送：先文字后图片
            if text:
                await bot.send_group_msg(
                    group_id=group_id,
                    message=MessageSegment.text(text),
                )
                await asyncio.sleep(random.uniform(1.0, 2.0))
            await bot.send_group_msg(
                group_id=group_id,
                message=MessageSegment.image(image_path),
            )
        else:
            message = MessageSegment.text(text) + MessageSegment.image(image_path)
            await bot.send_group_msg(group_id=group_id, message=message)

        # 更新状态
        config.update_last_sent(group_id)
        config.regenerate_message_limit(group_id)
        config.add_send_log(group_id, "success")
        logger.success(
            f"延迟发送成功，群 {group_id} (打字: {typing_duration}s, "
            f"下次数限: {group.message_limit})"
        )

    except Exception as e:
        logger.error(f"延迟发送失败，群 {group_id}：{e}")
        config.add_send_log(group_id, "error", str(e))
