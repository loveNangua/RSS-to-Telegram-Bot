"""
Twitter RSSHub 订阅时间槽调度器
用于避免同时发送过多请求到 Twitter API
"""

import asyncio
import hashlib
import time
from typing import Dict, List, Optional, Set
import logging

logger = logging.getLogger(__name__)


class DynamicTwitterScheduler:
    """动态 Twitter 订阅调度器"""
    
    def __init__(self):
        self.slot_count = 6  # 固定6个时间槽
        self.slot_duration = 15 * 60  # 每个槽15分钟（秒）
        self.min_interval = 30  # 最小检查间隔（秒）
        
        # 存储
        self.feeds: Dict[int, Dict] = {}  # feed_id -> feed_info
        self.slot_assignments: Dict[int, List[int]] = {}  # slot_id -> [feed_ids]
        self.slot_tasks: Dict[int, Optional[asyncio.Task]] = {}  # slot_id -> task
        
        # 初始化槽分配
        self._init_slots()
        
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
        
        # 平均分配到各个槽
        for i, feed_id in enumerate(sorted_feed_ids):
            slot_id = i % self.slot_count
            position_in_slot = i // self.slot_count
            
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
    
    async def start_slot_task(self, slot_id: int, check_callback):
        """启动时间槽任务"""
        if slot_id not in range(self.slot_count):
            return
            
        # 取消现有任务
        if self.slot_tasks[slot_id]:
            self.slot_tasks[slot_id].cancel()
        
        # 创建新任务
        self.slot_tasks[slot_id] = asyncio.create_task(
            self._slot_worker(slot_id, check_callback)
        )
        
        logger.info(f"Started slot task for slot {slot_id}")
    
    async def _slot_worker(self, slot_id: int, check_callback):
        """时间槽工作进程"""
        logger.info(f"Slot worker {slot_id} started")
        
        while True:
            cycle_start = time.time()
            feeds_in_slot = self.slot_assignments[slot_id].copy()
            
            if not feeds_in_slot:
                # 没有订阅，等待一个完整周期
                await asyncio.sleep(self.slot_duration * self.slot_count)
                continue
            
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
                    await check_callback(feed_id, self.feeds[feed_id]['url'])
                except Exception as e:
                    logger.error(f"Error checking feed {feed_id}: {e}")
            
            # 计算等待时间
            cycle_duration = time.time() - cycle_start
            total_cycle_time = self.slot_duration * self.slot_count
            wait_time = total_cycle_time - cycle_duration
            
            if wait_time > 0:
                await asyncio.sleep(wait_time)
    
    async def stop_all(self):
        """停止所有时间槽任务"""
        for slot_id in range(self.slot_count):
            if self.slot_tasks[slot_id]:
                self.slot_tasks[slot_id].cancel()
                try:
                    await self.slot_tasks[slot_id]
                except asyncio.CancelledError:
                    pass
        logger.info("All slot tasks stopped")
    
    def get_stats(self) -> Dict:
        """获取调度器统计信息"""
        stats = {
            'total_feeds': len(self.feeds),
            'slot_count': self.slot_count,
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


# 全局调度器实例
twitter_scheduler = DynamicTwitterScheduler()