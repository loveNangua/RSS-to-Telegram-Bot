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
    
    # 状态文本映射
    status_text_map = {
        "Running": "运行中" if lang == 'zh-Hans' else "Running",
        "Not Started": "未启动" if lang == 'zh-Hans' else "Not Started",
        "Cancelled": "已取消" if lang == 'zh-Hans' else "Cancelled",
        "Stopped": "已停止" if lang == 'zh-Hans' else "Stopped"
    }
    status_display = status_text_map.get(main_task_status, main_task_status)
    
    status_text = f"""
<b>{_['twitter_scheduler_status'] if 'twitter_scheduler_status' in _ else 'Twitter Scheduler Status'}</b>

{status_icon} <b>{"调度器" if lang == 'zh-Hans' else "Scheduler"}: {status_display}</b>
🕐 <b>{"当前时间" if lang == 'zh-Hans' else "Current Time"}:</b> {current_time}

<b>{"配置" if lang == 'zh-Hans' else "Configuration"}:</b>
📊 {_['total_feeds'] if 'total_feeds' in _ else 'Total Twitter Feeds'}: {stats['total_feeds']}
🎰 {_['time_slots'] if 'time_slots' in _ else 'Time Slots'}: {stats['slot_count']}
📦 {_['max_feeds_per_slot'] if 'max_feeds_per_slot' in _ else 'Max Feeds per Slot'}: {stats['max_feeds_per_slot']}
✅ {_['active_slots'] if 'active_slots' in _ else 'Active Slots'}: {stats['active_slots']}
⏱️ {_['slot_interval'] if 'slot_interval' in _ else 'Slot Interval'}: {stats['slot_interval_minutes']:.1f} {_['minutes'] if 'minutes' in _ else 'minutes'}
🔄 {_['full_cycle'] if 'full_cycle' in _ else 'Full Cycle'}: {stats['total_cycle_minutes']:.1f} {_['minutes'] if 'minutes' in _ else 'minutes'}
"""
    
    # 添加槽详情
    if stats['active_slots'] > 0:
        slot_details_title = _['slot_details'] if 'slot_details' in _ else 'Active Slot Details'
        status_text += f"\n\n<b>{slot_details_title}:</b>"
        for slot_id, slot_info in stats['slots'].items():
            if slot_info['feed_count'] > 0:
                interval_min = slot_info['interval'] / 60
                feeds_text = _['feeds'] if 'feeds' in _ else 'feeds'
                check_every_text = _['check_every'] if 'check_every' in _ else 'check every'
                min_text = "分钟" if lang == 'zh-Hans' else "min"
                status_text += f"\n• Slot {slot_id}: {slot_info['feed_count']} {feeds_text} ({check_every_text} {interval_min:.1f} {min_text})"
    else:
        no_active_text = "无活跃时间槽 - 未配置 Twitter 订阅源" if lang == 'zh-Hans' else "No active slots - no Twitter feeds configured"
        status_text += f"\n\n⚠️ <b>{no_active_text}</b>"
    
    # 添加说明
    if not is_running and stats['total_feeds'] > 0:
        not_running_text = "调度器未运行但已配置订阅源！" if lang == 'zh-Hans' else "Scheduler is not running but feeds are configured!"
        auto_start_text = "调度器应该会在下一次周期任务时自动启动。" if lang == 'zh-Hans' else "The scheduler should start automatically on the next periodic task."
        status_text += f"\n\n❗ <b>{not_running_text}</b>"
        status_text += f"\n💡 {auto_start_text}"
    elif is_running and stats['total_feeds'] == 0:
        no_feeds_text = "调度器正在运行但没有订阅源需要检查。" if lang == 'zh-Hans' else "Scheduler is running but no feeds to check."
        status_text += f"\n\n⚠️ <b>{no_feeds_text}</b>"
    elif is_running:
        running_normally_text = "调度器运行正常。" if lang == 'zh-Hans' else "Scheduler is running normally."
        status_text += f"\n\n✅ <b>{running_normally_text}</b>"
    
    await event.respond(status_text, parse_mode='html')