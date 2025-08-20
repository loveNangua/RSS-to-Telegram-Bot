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
# 不导入 twitter_scheduler 以避免任何可能的阻塞


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
    
    # 极简版本 - 不访问任何 scheduler 对象
    # 直接显示静态信息
    is_running = "N/A"  # 无法检查状态
    main_task_status = "Check manually"  # 需要手动检查
    
    # 不再访问 feeds 或任何可能大的数据结构
    total_feeds = "Check with /twitter_queue"  # 提示用其他命令查看
    active_slots = "N/A"
    
    # 格式化状态信息
    status_icon = "❔"  # 未知状态图标
    current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    # 使用简化的方式处理翻译，避免复杂的字典访问
    is_chinese = lang == 'zh-Hans'
    
    # 直接显示状态
    status_display = "请手动检查" if is_chinese else "Check manually"
    
    # 不访问 scheduler 的任何数据属性，使用静态值
    slot_count = 12  # 固定值
    max_feeds_per_slot = 10  # 固定值
    slot_interval_minutes = 15.0  # 固定值
    total_cycle_minutes = 180.0  # 固定值
    
    # 构建状态文本，使用直接的字符串而不是复杂的翻译查找
    title = "Twitter 调度器状态" if is_chinese else "Twitter Scheduler Status"
    scheduler_label = "调度器" if is_chinese else "Scheduler"
    current_time_label = "当前时间" if is_chinese else "Current Time"
    config_label = "配置" if is_chinese else "Configuration"
    total_feeds_label = "订阅源总数" if is_chinese else "Total Twitter Feeds"
    time_slots_label = "时间槽数量" if is_chinese else "Time Slots"
    max_feeds_label = "每个时间槽最多订阅源数" if is_chinese else "Max Feeds per Slot"
    active_slots_label = "活跃时间槽" if is_chinese else "Active Slots"
    slot_interval_label = "时间槽间隔" if is_chinese else "Slot Interval"
    minutes_label = "分钟" if is_chinese else "minutes"
    full_cycle_label = "完整周期" if is_chinese else "Full Cycle"
    
    status_text = f"""
<b>{title}</b>

{status_icon} <b>{scheduler_label}: {status_display}</b>
🕐 <b>{current_time_label}:</b> {current_time}

<b>{config_label}:</b>
📊 {total_feeds_label}: {total_feeds}
🎰 {time_slots_label}: {slot_count}
📦 {max_feeds_label}: {max_feeds_per_slot}
✅ {active_slots_label}: {active_slots}
⏱️ {slot_interval_label}: {slot_interval_minutes:.1f} {minutes_label}
🔄 {full_cycle_label}: {total_cycle_minutes:.1f} {minutes_label}
"""
    
    # 添加说明
    note_text = "注：由于性能优化，不再实时检查调度器状态" if is_chinese else "Note: Status check disabled for performance"
    status_text += f"\n\nℹ️ <i>{note_text}</i>"
    
    await event.respond(status_text, parse_mode='html')