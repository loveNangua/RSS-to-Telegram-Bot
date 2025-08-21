#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
简化版内容去重测试 - 不依赖完整项目环境
"""

import re
import hashlib
from typing import Optional, Sequence, Iterable
from itertools import repeat

try:
    from isal.isal_zlib import crc32
except ImportError:
    from zlib import crc32

def _normalize_content_for_similarity(content: str) -> str:
    """
    标准化内容用于相似度检测
    移除RT前缀、多余空格、特殊字符等，保留核心内容
    """
    if not content:
        return ''
    
    # 移除RT前缀和用户名
    content = re.sub(r'^RT\s+[^:]+:\s*', '', content, flags=re.IGNORECASE)
    
    # 移除多余的空格和换行
    content = re.sub(r'\s+', ' ', content).strip()
    
    # 移除URL（保留核心文本内容）
    content = re.sub(r'https?://\S+', '', content)
    
    # 移除@用户名（但保留核心内容）
    content = re.sub(r'@\w+', '', content)
    
    # 标准化标点符号
    content = re.sub(r'[,.!?;:…]+', '', content)
    
    return content.lower().strip()


def _calculate_content_hash(entry: dict) -> Optional[str]:
    """
    计算条目的内容哈希（用于相似度检测）
    基于标准化后的标题和描述内容
    """
    # 提取关键内容字段
    title = entry.get('title', '') or ''
    summary = entry.get('summary', '') or ''
    
    # 获取内容的第一个值
    content_value = ''
    content_list = entry.get('content', [])
    if content_list:
        content_value = next(filter(None, map(lambda c: c.get('value', ''), content_list)), '')
    
    # 先分别标准化每个字段，然后合并（避免字段间干扰）
    normalized_title = _normalize_content_for_similarity(title)
    normalized_summary = _normalize_content_for_similarity(summary)
    normalized_content = _normalize_content_for_similarity(content_value)
    
    # 合并标准化后的内容（使用统一的分隔符）
    combined_normalized = f"{normalized_title} {normalized_summary} {normalized_content}".strip()
    
    # 进一步清理合并后的内容
    combined_normalized = re.sub(r'\s+', ' ', combined_normalized).strip()
    
    if not combined_normalized or len(combined_normalized) < 10:  # 内容太短，不进行相似度检测
        return None
    
    # 使用MD5生成内容哈希（更适合相似度检测）
    return hashlib.md5(combined_normalized.encode('utf-8')).hexdigest()[:12]  # 只取前12位，节省空间


def calculate_update(old_hashes: Optional[Sequence[str]], entries: Sequence[dict]) \
        -> tuple[Iterable[str], Iterable[dict]]:
    """
    计算需要更新的RSS条目，支持双重去重：
    1. 基于GUID的精确去重（原有机制）
    2. 基于内容的相似度去重（新增机制）
    """
    # 第一阶段：构建基于GUID的哈希字典（原有逻辑）
    guid_hash_to_entry = {}
    content_hashes_seen = set()  # 用于内容去重
    
    for entry in entries:
        # 获取GUID标识符（优先级：guid > link > title > summary > content）
        guid = (
            entry.get('guid') or entry.get('link') or entry.get('title') or entry.get('summary')
            or (
                # the first non-empty content.value
                next(filter(None, map(lambda content: content.get('value'), entry.get('content', []))), '')
            )
        )
        
        if not guid:
            continue
            
        # 计算GUID哈希（原有机制）
        guid_hash = hex(crc32(guid.encode('utf-8')))[2:]
        
        # 计算内容哈希（新增机制）
        content_hash = _calculate_content_hash(entry)
        
        # 跳过重复内容（基于内容相似度）
        if content_hash and content_hash in content_hashes_seen:
            # 内容重复，跳过这个条目
            continue
            
        # 记录这个条目
        guid_hash_to_entry[guid_hash] = entry
        if content_hash:
            content_hashes_seen.add(content_hash)
    
    # 第二阶段：与历史记录合并（原有逻辑）
    if old_hashes:
        # 将历史哈希添加到字典中（值为None表示已处理过）
        for old_hash in old_hashes:
            if old_hash not in guid_hash_to_entry:
                guid_hash_to_entry[old_hash] = None
    
    # 第三阶段：生成结果
    new_hashes = guid_hash_to_entry.keys()
    updated_entries = filter(None, guid_hash_to_entry.values())
    
    return new_hashes, updated_entries


def test_duplicate_detection():
    """测试重复内容检测功能"""
    
    # 模拟茶百道账户的重复内容情况
    test_entries = [
        {
            'guid': 'https://twitter.com/bbwwoai/status/1958166401648148915',
            'link': 'https://x.com/bbwwoai/status/1958166401648148915',
            'title': '#四爱 #第四爱 #4i #iiii #pegging 感谢来自@xuan040221 一芝奈奈，投稿的视频。 爽到扭曲挣扎的身体，说明了一切。',
            'summary': '#四爱 #第四爱 #4i #iiii #pegging 感谢来自@xuan040221 一芝奈奈，投稿的视频。 爽到扭曲挣扎的身体，说明了一切。',
            'pubDate': 'Wed, 20 Aug 2025 13:57:05 GMT',
            'author': '茶百道'
        },
        {
            'guid': 'https://twitter.com/bbwwoai/status/1958326280832885141',
            'link': 'https://x.com/bbwwoai/status/1958326280832885141',
            'title': 'RT 茶百道: #四爱 #第四爱 #4i #iiii #pegging 感谢来自@xuan040221 一芝奈奈，投稿的视频。 爽到扭曲挣扎的身体，说明了一切。',
            'summary': 'RT 茶百道: #四爱 #第四爱 #4i #iiii #pegging 感谢来自@xuan040221 一芝奈奈，投稿的视频。 爽到扭曲挣扎的身体，说明了一切。',
            'pubDate': 'Wed, 20 Aug 2025 13:57:05 GMT',
            'author': '茶百道'
        },
        {
            'guid': 'https://twitter.com/bbwwoai/status/1957799538514883082',
            'link': 'https://x.com/bbwwoai/status/1957799538514883082',
            'title': '#四爱 #第四爱 #4i #iiii #pegging 感谢来自 @molishang17 暴戾恣睢 @hexagon_wowo 蜗蜗今天喝橙汁了吗 投稿的视频。 骚狗就喜欢在落地窗前被凿是吧，连拉珠都爆出水了！',
            'summary': '#四爱 #第四爱 #4i #iiii #pegging 感谢来自 @molishang17 暴戾恣睢 @hexagon_wowo 蜗蜗今天喝橙汁了吗 投稿的视频。 骚狗就喜欢在落地窗前被凿是吧，连拉珠都爆出水了！',
            'pubDate': 'Tue, 19 Aug 2025 13:39:18 GMT',
            'author': '茶百道'
        }
    ]
    
    print("=== 内容去重测试 ===\n")
    
    print("1. 测试内容标准化功能：")
    for i, entry in enumerate(test_entries[:2]):  # 只测试前两个（重复的）
        normalized = _normalize_content_for_similarity(entry['title'])
        content_hash = _calculate_content_hash(entry)
        print(f"   条目 {i+1}:")
        print(f"   原始标题: {entry['title']}")
        print(f"   标准化后: '{normalized}'")
        print(f"   内容哈希: {content_hash}")
        print()
    
    print("2. 测试去重机制：")
    old_hashes = []  # 模拟没有历史记录的情况
    new_hashes, updated_entries = calculate_update(old_hashes, test_entries)
    
    updated_entries_list = list(updated_entries)
    print(f"   输入条目数: {len(test_entries)}")
    print(f"   去重后条目数: {len(updated_entries_list)}")
    print(f"   去除的重复条目数: {len(test_entries) - len(updated_entries_list)}")
    print()
    
    print("3. 保留的条目：")
    for i, entry in enumerate(updated_entries_list):
        print(f"   条目 {i+1}: {entry['guid']}")
        title_preview = entry['title'][:80] + ('...' if len(entry['title']) > 80 else '')
        print(f"   标题: {title_preview}")
        print()
    
    print("4. 性能评估：")
    import time
    
    # 测试大量条目的处理性能
    large_test_entries = test_entries * 100  # 300个条目
    
    start_time = time.time()
    new_hashes, updated_entries = calculate_update([], large_test_entries)
    end_time = time.time()
    
    updated_count = len(list(updated_entries))
    processing_time = end_time - start_time
    
    print(f"   处理 {len(large_test_entries)} 个条目用时: {processing_time:.4f} 秒")
    print(f"   去重后剩余: {updated_count} 个条目")
    print(f"   平均每个条目处理时间: {processing_time/len(large_test_entries)*1000:.2f} 毫秒")
    
    return len(updated_entries_list) == 2  # 应该去掉1个重复条目，保留2个

def test_edge_cases():
    """测试边缘情况"""
    
    print("\n=== 边缘情况测试 ===\n")
    
    # 1. 内容太短的情况
    short_entries = [
        {
            'guid': 'test1',
            'title': '短',
            'summary': '内容'
        },
        {
            'guid': 'test2', 
            'title': '也很短',
            'summary': '的内容'
        }
    ]
    
    print("1. 短内容测试：")
    new_hashes, updated_entries = calculate_update([], short_entries)
    updated_count = len(list(updated_entries))
    print(f"   短内容条目数: {len(short_entries)}")
    print(f"   保留条目数: {updated_count}")
    print(f"   说明: 内容太短不进行相似度检测，只使用GUID去重")
    
    # 2. 空内容的情况
    empty_entries = [
        {
            'guid': 'empty1',
            'title': '',
            'summary': ''
        },
        {
            'guid': 'empty2',
            'title': None,
            'summary': None
        }
    ]
    
    print("\n2. 空内容测试：")
    new_hashes, updated_entries = calculate_update([], empty_entries)
    updated_count = len(list(updated_entries))
    print(f"   空内容条目数: {len(empty_entries)}")
    print(f"   保留条目数: {updated_count}")
    print(f"   说明: 空内容跳过相似度检测，只使用GUID去重")

if __name__ == "__main__":
    print("RSS-to-Telegram-Bot 内容去重机制测试")
    print("=" * 50)
    
    success = test_duplicate_detection()
    test_edge_cases()
    
    print(f"\n测试结果: {'✅ 通过' if success else '❌ 失败'}")
    print("\n解决方案特点：")
    print("• ✅ 高性能：基于MD5哈希的快速比较")
    print("• ✅ 智能标准化：移除RT前缀、用户名、URL等噪音")
    print("• ✅ 向后兼容：保留原有GUID去重机制")
    print("• ✅ 空间效率：只存储12位哈希值")
    print("• ✅ 鲁棒性：处理短内容和空内容的边缘情况")
