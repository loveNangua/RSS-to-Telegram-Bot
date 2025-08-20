"""
Twitter 调度器状态命令
查看 Twitter 时间槽调度器的当前状态
"""

from typing import Optional
from telethon import types
from datetime import datetime

from .. import env
from ..command.types import *
from ..command.utils import command_gatekeeper
from ..i18n import i18n
from ..scheduler.twitter_scheduler import twitter_scheduler


@command_gatekeeper(only_manager=False)
async def cmd_twitter_scheduler_status(
        event: TypeEventMsgHint,
        *_,
        lang: Optional[str] = None,
        **__,
):
    """查看 Twitter 调度器状态"""
    
    # 只有管理员可以使用此命令
    if event.chat_id not in env.MANAGER:
        await event.respond("This command is only available for bot managers.")
        return
    
    # 获取调度器状态
    stats = twitter_scheduler.get_stats()
    
    # 检查调度器是否在运行
    is_running = False
    main_task_status = "Not Started"
    
    if hasattr(twitter_scheduler, 'main_task') and twitter_scheduler.main_task:
        if not twitter_scheduler.main_task.done():
            is_running = True
            main_task_status = "Running"
        elif twitter_scheduler.main_task.cancelled():
            main_task_status = "Cancelled"
        else:
            main_task_status = "Stopped"
    
    # 获取翻译
    _ = i18n[lang]
    
    # 格式化状态信息
    status_icon = "🟢" if is_running else "🔴"
    current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    status_text = f"""
<b>Twitter Scheduler Status</b>

{status_icon} <b>Scheduler: {main_task_status}</b>
🕐 <b>Current Time:</b> {current_time}

<b>Configuration:</b>
📊 Total Twitter Feeds: {stats['total_feeds']}
🎰 Time Slots: {stats['slot_count']} slots
📦 Max Feeds per Slot: {stats['max_feeds_per_slot']}
✅ Active Slots: {stats['active_slots']}
⏱️ Slot Interval: {stats['slot_interval_minutes']:.1f} minutes
🔄 Full Cycle Time: {stats['total_cycle_minutes']:.1f} minutes
"""
    
    # 添加槽详情
    if stats['active_slots'] > 0:
        status_text += "\n\n<b>Active Slot Details:</b>"
        for slot_id, slot_info in stats['slots'].items():
            if slot_info['feed_count'] > 0:
                interval_min = slot_info['interval'] / 60
                status_text += f"\n• Slot {slot_id}: {slot_info['feed_count']} feeds (check every {interval_min:.1f} min)"
    else:
        status_text += "\n\n⚠️ <b>No active slots - no Twitter feeds configured</b>"
    
    # 添加说明
    if not is_running and stats['total_feeds'] > 0:
        status_text += "\n\n❗ <b>Scheduler is not running but feeds are configured!</b>"
        status_text += "\n💡 The scheduler should start automatically on the next periodic task."
    elif is_running and stats['total_feeds'] == 0:
        status_text += "\n\n⚠️ <b>Scheduler is running but no feeds to check.</b>"
    elif is_running:
        status_text += "\n\n✅ <b>Scheduler is running normally.</b>"
    
    await event.respond(status_text, parse_mode='html')