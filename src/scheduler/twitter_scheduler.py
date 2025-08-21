"""
Twitter RSSHub 订阅时间槽调度器
用于避免同时发送过多请求到 Twitter API
串行执行版本：增加槽数，减少每槽订阅数，槽间15分钟间隔
"""

import asyncio
import hashlib
import time
from typing import Dict, List, Optional, Set
import logging

logger = logging.getLogger(__name__)


class DynamicTwitterScheduler:
    """串行 Twitter 订阅调度器"""
    
    def __init__(self):
        self.slot_count = 12  # 增加到12个时间槽
        self.slot_duration = 15 * 60  # 每个槽15分钟（秒）
        self.slot_interval = 15 * 60  # 槽间间隔15分钟（串行执行）
        self.min_interval = 30  # 最小检查间隔（秒）
        self.max_feeds_per_slot = 10  # 每个槽最多10个订阅
        
        # 存储
        self.feeds: Dict[int, Dict] = {}  # feed_id -> feed_info
        self.slot_assignments: Dict[int, List[int]] = {}  # slot_id -> [feed_ids]
        self.slot_tasks: Dict[int, Optional[asyncio.Task]] = {}  # slot_id -> task
        self.main_task: Optional[asyncio.Task] = None  # 串行主任务
        self.check_callback = None  # 检查回调函数
        
        # 初始化槽分配
        self._init_slots()
        
        # 存储本周期更新的订阅源
        self.cycle_updated_feeds: List[tuple] = []  # [(feed_title, feed_url, entry_count)]
        
    def _init_slots(self):
        """初始化时间槽"""
        for i in range(self.slot_count):
            self.slot_assignments[i] = []
            self.slot_tasks[i] = None
    
    def is_twitter_feed(self, feed_url: str) -> bool:
        """检测是否为 Twitter RSSHub URL"""
        twitter_patterns = [
            '/twitter/user/',
            '/twitter/list/',
            '/twitter/search/',
            '/rsshub.app/twitter/',
            'rsshub.app/twitter/user',
            'rsshub.app/twitter/list',
            'rsshub.app/twitter/search',
        ]
        url_lower = feed_url.lower()
        return any(pattern in url_lower for pattern in twitter_patterns)
    
    async def add_feed(self, feed_id: int, feed_url: str):
        """添加新的 Twitter 订阅"""
        if not self.is_twitter_feed(feed_url):
            return False
            
        if feed_id in self.feeds:
            logger.warning(f"Feed {feed_id} already exists in scheduler")
            return True
        
        # 添加到存储
        self.feeds[feed_id] = {
            'url': feed_url,
            'slot_id': None,
            'position': None,
            'added_time': time.time()
        }
        
        # 重新平衡
        await self._rebalance_slots()
        
        logger.info(f"Added Twitter feed {feed_id} to scheduler")
        return True
    
    async def remove_feed(self, feed_id: int):
        """移除订阅"""
        if feed_id not in self.feeds:
            return
            
        feed_info = self.feeds[feed_id]
        slot_id = feed_info.get('slot_id')
        
        # 从槽中移除
        if slot_id is not None and slot_id in self.slot_assignments:
            if feed_id in self.slot_assignments[slot_id]:
                self.slot_assignments[slot_id].remove(feed_id)
        
        # 删除记录
        del self.feeds[feed_id]
        
        # 重新平衡
        await self._rebalance_slots()
        
        logger.info(f"Removed Twitter feed {feed_id} from scheduler")
    
    async def _rebalance_slots(self):
        """重新平衡所有订阅到时间槽"""
        # 清空现有分配
        self._init_slots()
        
        if not self.feeds:
            return
        
        # 按订阅ID排序，确保稳定性
        sorted_feed_ids = sorted(self.feeds.keys())
        
        # 计算需要的槽数
        required_slots = (len(self.feeds) + self.max_feeds_per_slot - 1) // self.max_feeds_per_slot
        required_slots = min(required_slots, self.slot_count)  # 不超过最大槽数
        
        # 分配订阅到槽
        for i, feed_id in enumerate(sorted_feed_ids):
            if i < required_slots * self.max_feeds_per_slot:
                # 前面的槽填满
                slot_id = i // self.max_feeds_per_slot
                position_in_slot = i % self.max_feeds_per_slot
            else:
                # 超出的部分平均分配到各个槽
                slot_id = i % required_slots
                position_in_slot = len(self.slot_assignments[slot_id])
            
            # 更新分配
            self.feeds[feed_id]['slot_id'] = slot_id
            self.feeds[feed_id]['position'] = position_in_slot
            self.slot_assignments[slot_id].append(feed_id)
        
        # 打印分配情况（调试用）
        for slot_id in range(self.slot_count):
            count = len(self.slot_assignments[slot_id])
            if count > 0:
                interval = self.get_slot_interval(slot_id)
                logger.info(f"Slot {slot_id}: {count} feeds, interval: {interval:.1f}s")
    
    def get_slot_interval(self, slot_id: int) -> float:
        """计算特定时间槽内的检查间隔"""
        feeds_in_slot = len(self.slot_assignments[slot_id])
        
        if feeds_in_slot == 0:
            return self.slot_duration
        
        # 计算间隔，确保在15分钟内完成
        interval = self.slot_duration / feeds_in_slot
        
        # 设置最小间隔
        return max(interval, self.min_interval)
    
    def get_feed_check_info(self, feed_id: int) -> Optional[Dict]:
        """获取订阅的检查信息"""
        if feed_id not in self.feeds:
            return None
            
        feed_info = self.feeds[feed_id]
        slot_id = feed_info['slot_id']
        position = feed_info['position']
        
        if slot_id is None or position is None:
            return None
        
        # 计算时间槽开始时间（相对于周期开始）
        slot_start = slot_id * self.slot_duration
        
        # 计算在槽内的偏移
        slot_interval = self.get_slot_interval(slot_id)
        offset = position * slot_interval
        
        return {
            'slot_id': slot_id,
            'slot_start': slot_start,
            'offset': offset,
            'interval': slot_interval,
            'absolute_time': slot_start + offset
        }
    
    async def start_scheduler(self, check_callback):
        """启动串行调度器"""
        self.check_callback = check_callback
        
        # 取消所有现有任务
        await self.stop_all()
        
        # 启动串行主任务
        self.main_task = asyncio.create_task(self._serial_worker())
        logger.info("Started serial Twitter scheduler")
    
    async def _serial_worker(self):
        """串行工作进程"""
        logger.info("Serial scheduler started")
        
        while True:
            # 获取所有有订阅的槽
            active_slots = []
            for slot_id in range(self.slot_count):
                if self.slot_assignments[slot_id]:
                    active_slots.append(slot_id)
            
            if not active_slots:
                # 没有订阅，等待一段时间
                await asyncio.sleep(60)
                continue
            
            # 串行处理每个槽
            for slot_id in active_slots:
                await self._process_slot(slot_id)
                
                # 槽间等待15分钟（除了最后一个槽）
                if slot_id != active_slots[-1]:
                    logger.info(f"Slot {slot_id} completed, waiting {self.slot_interval/60:.1f} minutes...")
                    await asyncio.sleep(self.slot_interval)
            
            # 所有槽完成后，输出更新报告
            await self._output_cycle_report()
            
            # 等待一段时间再开始下一轮
            logger.info("All slots completed, starting new cycle...")
            await asyncio.sleep(60)  # 1分钟后开始新一轮
    
    async def _process_slot(self, slot_id: int):
        """处理单个时间槽"""
        logger.info(f"Processing slot {slot_id}")
        feeds_in_slot = self.slot_assignments[slot_id].copy()
        
        if not feeds_in_slot:
            return
        
        # 获取槽内间隔
        slot_interval = self.get_slot_interval(slot_id)
        
        # 处理槽内每个订阅
        for i, feed_id in enumerate(feeds_in_slot):
            if feed_id not in self.feeds:
                continue
            
            # 等待到检查时间
            if i > 0:
                await asyncio.sleep(slot_interval)
            
            try:
                # 执行检查回调
                if self.check_callback:
                    await self.check_callback(feed_id, self.feeds[feed_id]['url'])
            except Exception as e:
                logger.error(f"Error checking feed {feed_id}: {e}")
        
        logger.info(f"Slot {slot_id} completed")
    
    async def start_slot_task(self, slot_id: int, check_callback):
        """启动时间槽任务（向后兼容）"""
        if slot_id == 0:  # 只有第一个槽的调用会启动调度器
            await self.start_scheduler(check_callback)
        logger.debug(f"Ignoring start_slot_task for slot {slot_id} - using serial scheduler")
    
    async def start_all_slots(self, check_callback):
        """启动所有时间槽任务（使用串行调度器）"""
        await self.start_scheduler(check_callback)
    
    async def stop_all(self):
        """停止所有时间槽任务"""
        # 停止主任务
        if self.main_task:
            self.main_task.cancel()
            try:
                await self.main_task
            except asyncio.CancelledError:
                pass
        
        # 停止所有槽任务
        for slot_id in range(self.slot_count):
            if self.slot_tasks[slot_id]:
                self.slot_tasks[slot_id].cancel()
                try:
                    await self.slot_tasks[slot_id]
                except asyncio.CancelledError:
                    pass
        logger.info("All scheduler tasks stopped")
    
    def get_stats(self) -> Dict:
        """获取调度器统计信息"""
        # 计算活跃槽数
        active_slots = sum(1 for slot_id in range(self.slot_count) if self.slot_assignments[slot_id])
        
        # 计算完整周期时间
        if active_slots > 0:
            total_cycle_time = active_slots * self.slot_interval + (active_slots - 1) * 60  # 槽间间隔15分钟 + 1分钟缓冲
        else:
            total_cycle_time = 0
        
        stats = {
            'total_feeds': len(self.feeds),
            'slot_count': self.slot_count,
            'active_slots': active_slots,
            'max_feeds_per_slot': self.max_feeds_per_slot,
            'slot_interval_minutes': self.slot_interval / 60,
            'total_cycle_minutes': total_cycle_time / 60,
            'slots': {}
        }
        
        for slot_id in range(self.slot_count):
            feeds_count = len(self.slot_assignments[slot_id])
            interval = self.get_slot_interval(slot_id)
            stats['slots'][slot_id] = {
                'feed_count': feeds_count,
                'interval': interval,
                'feeds': self.slot_assignments[slot_id]
            }
        
        return stats
    
    def record_update(self, feed_title: str, feed_url: str, entry_count: int):
        """记录订阅源更新"""
        self.cycle_updated_feeds.append((feed_title, feed_url, entry_count))
    
    async def _output_cycle_report(self):
        """输出本周期的更新报告"""
        if self.cycle_updated_feeds:
            update_count = len(self.cycle_updated_feeds)
            total_entries = sum(count for _, _, count in self.cycle_updated_feeds)
            
            # 检查系统语言
            try:
                from .. import env, db
                is_chinese = env.MANAGER and db.effective_utils.EffectiveOptions.default_lang == 'zh-Hans'
            except:
                is_chinese = False
            
            if is_chinese:
                logger.info("="*30)
                logger.info("📢 Twitter RSS 更新报告")
                logger.info(f"更新的订阅源数量: {update_count}")
                logger.info(f"新文章总数: {total_entries}")
                logger.info("更新详情:")
                
                for title, link, entry_count in sorted(self.cycle_updated_feeds, key=lambda x: x[2], reverse=True):
                    logger.info(f"  • {title}: {entry_count} 篇新文章")
                    logger.info(f"    {link}")
                
                logger.info("="*30)
            else:
                logger.info("="*30)
                logger.info("📢 Twitter RSS Update Report")
                logger.info(f"Total feeds updated: {update_count}")
                logger.info(f"Total new entries: {total_entries}")
                logger.info("Update details:")
                
                for title, link, entry_count in sorted(self.cycle_updated_feeds, key=lambda x: x[2], reverse=True):
                    entry_text = "new entry" if entry_count == 1 else "new entries"
                    logger.info(f"  • {title}: {entry_count} {entry_text}")
                    logger.info(f"    {link}")
                
                logger.info("="*30)
        else:
            # 没有更新
            try:
                from .. import env, db
                is_chinese = env.MANAGER and db.effective_utils.EffectiveOptions.default_lang == 'zh-Hans'
            except:
                is_chinese = False
            
            if is_chinese:
                logger.info("本周期没有检测到 Twitter 订阅更新")
            else:
                logger.info("No Twitter feed updates detected in this cycle")
        
        # 清空下一周期
        self.cycle_updated_feeds.clear()


# 全局调度器实例
twitter_scheduler = DynamicTwitterScheduler()
