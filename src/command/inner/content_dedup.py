#!/usr/bin/env python3
"""
智能内容去重模块
使用多种策略进行内容去重，不依赖特定格式
"""

import re
import hashlib
from typing import Optional, Dict, Set, List, Tuple
from difflib import SequenceMatcher
import logging

logger = logging.getLogger('RSStT.dedup')


class ContentDeduplicator:
    """
    智能内容去重器
    支持多种去重策略：
    1. 精确匹配去重
    2. 相似度去重
    3. 核心内容去重
    """
    
    def __init__(self, similarity_threshold: float = 0.85):
        """
        :param similarity_threshold: 相似度阈值，超过此值认为是重复内容
        """
        self.similarity_threshold = similarity_threshold
        self._content_cache: Dict[str, str] = {}  # 缓存标准化后的内容
        self._hash_cache: Dict[str, str] = {}  # 缓存内容哈希
        
    @staticmethod
    def _extract_core_content(text: str) -> str:
        """
        提取文本的核心内容，去除所有可能的前缀、后缀和格式
        """
        if not text:
            return ''
            
        # 移除HTML标签和实体
        text = re.sub(r'<[^>]+>', ' ', text)
        text = re.sub(r'&[a-z]+;', ' ', text)
        
        # 策略1：移除各种RT/转发标记（更通用的模式）
        # 匹配 "RT @用户名:" "RT 用户名:" "RT 用户名" "转发自" 等
        text = re.sub(r'^(RT|转发|Retweet|Forward|via)[\s:@]*[^:：\s]*[:：]?\s*', '', text, flags=re.IGNORECASE)
        
        # 策略2：如果文本中有明显的分隔符（如多个换行后的内容），取主要内容
        # 处理 "RT 用户名\n实际内容" 这种格式
        lines = text.split('\n')
        if len(lines) > 1:
            # 如果第一行很短且包含RT/用户名等，跳过它
            if len(lines[0]) < 30 and re.search(r'(RT|@|转发|via)', lines[0], re.IGNORECASE):
                text = '\n'.join(lines[1:])
        
        # 移除URL
        text = re.sub(r'https?://\S+', '', text)
        text = re.sub(r'www\.\S+', '', text)
        text = re.sub(r't\.co/\S+', '', text)
        
        # 移除@提及
        text = re.sub(r'@[\w\u4e00-\u9fa5]+', '', text)
        
        # 移除话题标签但保留内容
        text = re.sub(r'#(\S+)', r'\1', text)
        
        # 移除多余的空白字符
        text = re.sub(r'\s+', ' ', text)
        
        # 移除标点符号（但保留表情）
        # 使用原始字符串和正确的转义
        text = re.sub(r'[,.!?;:"""''`~\-_=+\[\]{}()|/<>*&^%$#@\\]+', ' ', text)
        
        # 最终清理
        text = text.strip().lower()
        
        return text
    
    @staticmethod
    def _calculate_similarity(text1: str, text2: str) -> float:
        """
        计算两个文本的相似度
        """
        if not text1 or not text2:
            return 0.0
        
        # 使用SequenceMatcher计算相似度
        return SequenceMatcher(None, text1, text2).ratio()
    
    def _get_content_hash(self, text: str) -> str:
        """
        获取内容的哈希值（用于快速查找）
        """
        if text in self._hash_cache:
            return self._hash_cache[text]
        
        hash_val = hashlib.md5(text.encode('utf-8')).hexdigest()[:16]
        self._hash_cache[text] = hash_val
        return hash_val
    
    def _normalize_entry_content(self, entry: dict) -> str:
        """
        标准化RSS条目的内容
        """
        # 提取所有相关文本
        texts = []
        
        # 标题
        if title := entry.get('title', ''):
            texts.append(title)
        
        # 摘要
        if summary := entry.get('summary', ''):
            texts.append(summary)
        
        # 内容
        if contents := entry.get('content', []):
            for content in contents:
                if value := content.get('value', ''):
                    texts.append(value)
        
        # 合并所有文本
        combined = ' '.join(texts)
        
        # 提取核心内容
        core = self._extract_core_content(combined)
        
        return core
    
    def is_duplicate(self, entry: dict, seen_contents: Set[str]) -> Tuple[bool, str]:
        """
        检查条目是否为重复内容
        
        :param entry: RSS条目
        :param seen_contents: 已见过的内容集合
        :return: (是否重复, 内容哈希)
        """
        # 标准化内容
        normalized = self._normalize_entry_content(entry)
        
        # 如果内容太短，不进行去重
        if len(normalized) < 10:
            return False, ''
        
        # 计算哈希
        content_hash = self._get_content_hash(normalized)
        
        # 精确匹配检查
        if content_hash in seen_contents:
            logger.debug(f"Exact duplicate found: {entry.get('title', '')[:50]}")
            return True, content_hash
        
        # 相似度检查（对于已见内容）
        for seen_hash in seen_contents:
            if seen_hash in self._content_cache:
                seen_content = self._content_cache[seen_hash]
                similarity = self._calculate_similarity(normalized, seen_content)
                
                if similarity >= self.similarity_threshold:
                    logger.debug(
                        f"Similar content found (similarity: {similarity:.2f}): "
                        f"{entry.get('title', '')[:50]}"
                    )
                    return True, content_hash
        
        # 缓存这个内容
        self._content_cache[content_hash] = normalized
        
        return False, content_hash
    
    def deduplicate_entries(self, entries: List[dict]) -> List[dict]:
        """
        对条目列表进行去重
        
        :param entries: RSS条目列表
        :return: 去重后的条目列表
        """
        seen_contents = set()
        deduped_entries = []
        
        for entry in entries:
            is_dup, content_hash = self.is_duplicate(entry, seen_contents)
            
            if not is_dup:
                deduped_entries.append(entry)
                if content_hash:
                    seen_contents.add(content_hash)
        
        return deduped_entries


# 全局去重器实例
global_deduplicator = ContentDeduplicator(similarity_threshold=0.85)


def calculate_update_smart(old_hashes: Optional[List[str]], entries: List[dict]) -> Tuple[List[str], List[dict]]:
    """
    智能去重更新计算
    
    这是对原有 calculate_update 函数的增强版本
    """
    from zlib import crc32
    
    # 使用智能去重器过滤条目
    deduped_entries = global_deduplicator.deduplicate_entries(entries)
    
    # 构建基于GUID的哈希字典（保留原有逻辑）
    guid_hash_to_entry = {}
    
    for entry in deduped_entries:
        # 获取GUID标识符
        guid = (
            entry.get('guid') or 
            entry.get('link') or 
            entry.get('title') or 
            entry.get('summary') or
            (next(filter(None, map(lambda c: c.get('value'), entry.get('content', []))), ''))
        )
        
        if not guid:
            continue
        
        # 计算GUID哈希
        guid_hash = hex(crc32(guid.encode('utf-8')))[2:]
        guid_hash_to_entry[guid_hash] = entry
    
    # 与历史记录合并
    if old_hashes:
        for old_hash in old_hashes:
            if old_hash not in guid_hash_to_entry:
                guid_hash_to_entry[old_hash] = None
    
    new_hashes = list(guid_hash_to_entry.keys())
    updated_entries = [e for e in guid_hash_to_entry.values() if e is not None]
    
    return new_hashes, updated_entries
