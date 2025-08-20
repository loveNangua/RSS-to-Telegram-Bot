"""
Twitter 调度器状态命令
查看 Twitter 时间槽调度器的当前状态
"""

from typing import Optional
from telethon import types

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
    
    # 获取翻译
    _ = i18n[lang]
    
    # 格式化状态信息
    status_text = f"""
<b>{_['twitter_scheduler_status']}</b>

📊 {_['total_feeds']}: {stats['total_feeds']}
🕐 {_['time_slots']}: {stats['slot_count']} ({_['max_feeds_per_slot']} {stats['max_feeds_per_slot']} {_['feeds']} per slot)
✅ {_['active_slots']}: {stats['active_slots']}
⏱️ {_['slot_interval']}: {stats['slot_interval_minutes']:.1f} {_['minutes']}
🔄 {_['full_cycle']}: {stats['total_cycle_minutes']:.1f} {_['minutes']}

<b>{_['slot_details']}:</b>
"""
    
    for slot_id, slot_info in stats['slots'].items():
        if slot_info['feed_count'] > 0:
            status_text += f"\nSlot {slot_id}: {slot_info['feed_count']} {_['feeds']}"
            if slot_info['feed_count'] > 0:
                interval = slot_info['interval']
                status_text += f" ({_['check_every']} {interval:.1f}{_['seconds']})"
    
    await event.respond(status_text, parse_mode='html')