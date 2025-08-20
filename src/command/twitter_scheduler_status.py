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


@command_gatekeeper(only_manager=True)
async def cmd_twitter_scheduler_status(
        event: TypeEventMsgHint,
        *_,
        lang: Optional[str] = None,
        **__,
):
    """查看 Twitter 调度器状态"""
    import asyncio
    
    # 立即 yield 控制权，避免阻塞
    await asyncio.sleep(0)
    
    # 极简版本 - 只显示最基本的信息
    # 检查调度器是否在运行
    is_running = False
    main_task_status = "Unknown"
    
    try:
        if hasattr(twitter_scheduler, 'main_task') and twitter_scheduler.main_task:
            if not twitter_scheduler.main_task.done():
                is_running = True
                main_task_status = "Running"
            elif twitter_scheduler.main_task.cancelled():
                main_task_status = "Cancelled"
            else:
                main_task_status = "Stopped"
        else:
            main_task_status = "Not Started"
    except:
        pass  # 忽略任何错误
    
    # 不再访问 feeds 或任何可能大的数据结构
    total_feeds = "Check with /twitter_queue"  # 提示用其他命令查看
    active_slots = "N/A"
    
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
    
    # 不访问 scheduler 的任何数据属性，使用静态值
    slot_count = 12  # 固定值
    max_feeds_per_slot = 10  # 固定值
    slot_interval_minutes = 15.0  # 固定值
    total_cycle_minutes = 180.0  # 固定值
    
    status_text = f"""
<b>{_['twitter_scheduler_status'] if 'twitter_scheduler_status' in _ else 'Twitter Scheduler Status'}</b>

{status_icon} <b>{"调度器" if lang == 'zh-Hans' else "Scheduler"}: {status_display}</b>
🕐 <b>{"当前时间" if lang == 'zh-Hans' else "Current Time"}:</b> {current_time}

<b>{"配置" if lang == 'zh-Hans' else "Configuration"}:</b>
📊 {_['total_feeds'] if 'total_feeds' in _ else 'Total Twitter Feeds'}: {total_feeds}
🎰 {_['time_slots'] if 'time_slots' in _ else 'Time Slots'}: {slot_count}
📦 {_['max_feeds_per_slot'] if 'max_feeds_per_slot' in _ else 'Max Feeds per Slot'}: {max_feeds_per_slot}
✅ {_['active_slots'] if 'active_slots' in _ else 'Active Slots'}: {active_slots}
⏱️ {_['slot_interval'] if 'slot_interval' in _ else 'Slot Interval'}: {slot_interval_minutes:.1f} {_['minutes'] if 'minutes' in _ else 'minutes'}
🔄 {_['full_cycle'] if 'full_cycle' in _ else 'Full Cycle'}: {total_cycle_minutes:.1f} {_['minutes'] if 'minutes' in _ else 'minutes'}
"""
    
    # 添加简单的状态说明
    if is_running:
        running_normally_text = "调度器运行正常。" if lang == 'zh-Hans' else "Scheduler is running normally."
        status_text += f"\n\n✅ <b>{running_normally_text}</b>"
    
    await event.respond(status_text, parse_mode='html')