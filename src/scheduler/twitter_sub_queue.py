"""
Twitter 订阅队列管理器
用于处理渐进式订阅，避免一次性添加多个 Twitter 订阅时触发 API 限制
"""

import asyncio
import logging
import time
from typing import List, Dict, Optional
from collections import deque
from dataclasses import dataclass

from .. import log
from ..db import Sub, Feed

logger = log.getLogger('RSStT.twitter.queue')


@dataclass
class QueuedSubscription:
    """队列中的订阅信息"""
    user_id: int
    feed_url: str
    title: Optional[str] = None
    interval: Optional[int] = None
    silent: bool = False
    subtitle: str = ""


class TwitterSubscriptionQueue:
    """Twitter 订阅队列管理器"""
    
    def __init__(self):
        self.queue: deque[QueuedSubscription] = deque()
        self.processing = False
        self.processing_task: Optional[asyncio.Task] = None
        self.delay_between_groups = 15 * 60  # 组间延迟（15分钟）
        self.delay_within_group = 30  # 组内延迟（30秒）
        self.group_size = 10  # 每组订阅数量
        self.max_concurrent_initial_checks = 3  # 最大并发初始检查数
        
    def is_twitter_feed(self, url: str) -> bool:
        """检查是否为 Twitter RSSHub 订阅"""
        return '/twitter/' in url.lower()
    
    def add_to_queue(self, sub: QueuedSubscription):
        """添加订阅到队列"""
        if not self.is_twitter_feed(sub.feed_url):
            return False  # 非 Twitter 订阅不加入队列
            
        self.queue.append(sub)
        logger.info(f"Added Twitter subscription to queue: {sub.feed_url} (user: {sub.user_id})")
        
        # 如果没有在处理，启动处理
        if not self.processing:
            self.start_processing()
            
        return True
    
    def start_processing(self):
        """开始处理队列"""
        if self.processing_task and not self.processing_task.done():
            return
            
        self.processing = True
        self.processing_task = asyncio.create_task(self._process_queue())
    
    async def _process_queue(self):
        """处理订阅队列"""
        logger.info(f"Starting Twitter subscription queue processing with {len(self.queue)} items")
        
        group_count = 0
        
        while self.queue:
            group_count += 1
            logger.info(f"Processing group {group_count} of Twitter subscriptions")
            
            # 处理一组订阅
            processed_in_group = 0
            while processed_in_group < self.group_size and self.queue:
                # 获取下一批订阅（最多 max_concurrent_initial_checks 个）
                batch = []
                batch_size = min(self.max_concurrent_initial_checks, len(self.queue), self.group_size - processed_in_group)
                
                for _ in range(batch_size):
                    if self.queue:
                        batch.append(self.queue.popleft())
                
                if not batch:
                    break
                
                # 并发处理这一批
                logger.info(f"Processing batch of {len(batch)} Twitter subscriptions in group {group_count}")
                tasks = []
                
                for sub in batch:
                    task = asyncio.create_task(self._process_single_subscription(sub))
                    tasks.append(task)
                
                # 等待这批完成
                await asyncio.gather(*tasks, return_exceptions=True)
                processed_in_group += len(batch)
                
                # 如果组内还有更多订阅，等待组内延迟
                if processed_in_group < self.group_size and self.queue:
                    logger.info(f"Waiting {self.delay_within_group}s before next batch in group {group_count}...")
                    await asyncio.sleep(self.delay_within_group)
            
            # 如果还有更多订阅，等待组间延迟
            if self.queue:
                logger.info(f"Group {group_count} completed. Waiting {self.delay_between_groups // 60} minutes before next group...")
                await asyncio.sleep(self.delay_between_groups)
        
        self.processing = False
        logger.info("Twitter subscription queue processing completed")
    
    async def _process_single_subscription(self, sub: QueuedSubscription):
        """处理单个订阅"""
        try:
            logger.info(f"Processing Twitter subscription: {sub.feed_url}")
            
            # 导入必要的模块
            from ..command.inner.utils import update_interval
            from ..monitor import Monitor
            from ..command.inner.sub import sub as inner_sub
            from ..i18n import i18n
            
            # 使用现有的 sub 函数来创建订阅，这样可以保持一致性
            result = await inner_sub(sub.user_id, (sub.feed_url, sub.title) if sub.title else sub.feed_url)
            
            if result and result.get('sub'):
                # 订阅成功
                logger.info(f"Successfully created Twitter subscription: {sub.feed_url}")
                
                # 发送成功通知（如果不是静默模式）
                if not sub.silent:
                    try:
                        from .. import env
                        bot = env.bot
                        success_msg = (
                            f'<b>{i18n["en"]["sub_successful"]}</b>\n'
                            f'<a href="{result["sub"].feed.link}">'
                            f'{result["sub"].title or result["sub"].feed.title}</a>'
                        )
                        await bot.send_message(sub.user_id, success_msg, parse_mode='html')
                    except Exception as e:
                        logger.warning(f"Failed to send success notification: {e}")
            else:
                # 订阅失败
                error_msg = result.get('msg', 'Unknown error') if result else 'Unknown error'
                logger.error(f"Failed to create Twitter subscription {sub.feed_url}: {error_msg}")
                
                # 发送失败通知
                if not sub.silent:
                    try:
                        from .. import env
                        bot = env.bot
                        await bot.send_message(sub.user_id, f"Failed to subscribe to {sub.feed_url}: {error_msg}")
                    except Exception as e:
                        logger.warning(f"Failed to send failure notification: {e}")
            
            logger.info(f"Processed Twitter subscription: {sub.feed_url}")
            
        except Exception as e:
            logger.error(f"Error processing Twitter subscription {sub.feed_url}: {e}")
    
    def get_queue_status(self) -> Dict:
        """获取队列状态"""
        return {
            'queue_size': len(self.queue),
            'processing': self.processing,
            'delay_between_groups': self.delay_between_groups,
            'delay_within_group': self.delay_within_group,
            'group_size': self.group_size,
            'max_concurrent_initial_checks': self.max_concurrent_initial_checks
        }


# 全局实例
twitter_sub_queue = TwitterSubscriptionQueue()