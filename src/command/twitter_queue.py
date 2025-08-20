"""
Twitter 队列状态命令
查看 Twitter 订阅队列的当前状态
"""

from typing import Optional
from telethon import types
from datetime import datetime

from .. import env
from ..command.types import *
from ..command.utils import command_gatekeeper
from ..i18n import i18n
from ..scheduler.twitter_sub_queue import twitter_sub_queue


@command_gatekeeper(only_manager=False)
async def cmd_twitter_queue(
        event: TypeEventMsgHint,
        args: str = '',
        *_,
        lang: Optional[str] = None,
        **__,
):
    """查看 Twitter 订阅队列状态
    
    用法:
    /twitter_queue - 显示基本状态
    /twitter_queue detailed - 显示详细订阅列表
    /twitter_queue history - 显示处理历史
    """
    
    # 只有管理员可以使用此命令
    if event.chat_id not in env.MANAGER:
        await event.respond("This command is only available for bot managers.")
        return
    
    # 解析参数
    show_detailed = args.lower() in ['detailed', 'detail', 'full']
    show_history = args.lower() in ['history', 'hist']
    
    # 获取队列状态
    status = twitter_sub_queue.get_queue_status()
    
    # 获取翻译
    _ = i18n[lang]
    
    if show_detailed or show_history:
        # 获取订阅详情
        limit = 20  # 默认显示20条
        details = twitter_sub_queue.get_subscription_details(limit)
        
        # 格式化详细状态
        status_text = f"""
<b>{_['twitter_subscription_queue_status']} - {_['detailed_view']}</b>

📊 {_['queue_size']}: {status['queue_size']}
🔄 {_['processing_status']}: {_['yes'] if status['processing'] else _['no']}
📋 {_['history_size']}: {status['history_size']}

<b>{_['status_summary']}:</b>
🟡 {_['queued']}: {status['status_counts'].get('queued', 0)}
🔵 {_['processing_status']}: {status['status_counts'].get('processing', 0)}
✅ {_['success']}: {status['status_counts'].get('success', 0)}
❌ {_['failed']}: {status['status_counts'].get('failed', 0)}

<b>{_['subscription_details']}:</b>
"""
        
        # 添加订阅详情
        for i, sub in enumerate(details[:10], 1):  # 最多显示10个
            status_icon = {
                'queued': '⏳',
                'processing': '🔄',
                'success': '✅',
                'failed': '❌'
            }.get(sub['status'], '❓')
            
            # 格式化时间
            added_time = sub['added_time'].strftime('%m-%d %H:%M') if sub['added_time'] else 'N/A'
            
            status_text += f"""
{i}. {status_icon} <b>{sub['title'] or sub['feed_url'][:50]}...</b>
   {_['status']}: {sub['status']}
   {_['user']}: {sub['user_id']}
   {_['added']}: {added_time}"""
            
            if sub['error_message']:
                status_text += f"\n   {_['error']}: {sub['error_message'][:50]}..."
            
            status_text += "\n"
        
        if len(details) > 10:
            status_text += f"\n{_['and_more'].format(count=len(details) - 10)}"
        
    else:
        # 基本状态视图
        status_text = f"""
<b>{_['twitter_subscription_queue_status']}</b>

📊 {_['queue_size']}: {status['queue_size']}
🔄 {_['processing_status']}: {_['yes'] if status['processing'] else _['no']}
⏱️ {_['delay_within_group']}: {status['delay_within_group']}s
⏱️ {_['delay_between_groups']}: {status['delay_between_groups'] // 60} {_['minutes']}
📦 {_['group_size']}: {status['group_size']}
🔢 {_['max_concurrent_checks']}: {status['max_concurrent_initial_checks']}

<b>{_['status_summary']}:</b>
🟡 {_['queued']}: {status['status_counts'].get('queued', 0)}
🔵 {_['processing_status']}: {status['status_counts'].get('processing', 0)}
✅ {_['success']}: {status['status_counts'].get('success', 0)}
❌ {_['failed']}: {status['status_counts'].get('failed', 0)}

💡 {_['use_detailed_cmd']}
"""
    
    await event.respond(status_text, parse_mode='html')