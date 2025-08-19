"""
Twitter 队列状态命令
查看 Twitter 订阅队列的当前状态
"""

from typing import Optional
from telethon import types

from .. import env
from ..command.types import *
from ..command.utils import command_gatekeeper
from ..i18n import i18n
from ..scheduler.twitter_sub_queue import twitter_sub_queue


@command_gatekeeper(only_manager=False)
async def cmd_twitter_queue(
        event: TypeEventMsgHint,
        *_,
        lang: Optional[str] = None,
        **__,
):
    """查看 Twitter 订阅队列状态"""
    
    # 只有管理员可以使用此命令
    if event.chat_id not in env.MANAGER:
        await event.respond("This command is only available for bot managers.")
        return
    
    # 获取队列状态
    status = twitter_sub_queue.get_queue_status()
    
    # 格式化状态信息
    status_text = f"""
<b>Twitter Subscription Queue Status</b>

📊 Queue Size: {status['queue_size']}
🔄 Processing: {'Yes' if status['processing'] else 'No'}
⏱️ Delay Between Subs: {status['delay_between_subs']}s
🔢 Max Concurrent Checks: {status['max_concurrent_initial_checks']}
"""
    
    await event.respond(status_text, parse_mode='html')