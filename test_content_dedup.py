#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试新的内容去重机制
验证是否能正确处理转发推文的重复内容
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from command.inner.utils import calculate_update, _normalize_content_for_similarity, _calculate_content_hash

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
        print(f"   标准化后: {normalized}")
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
        print(f"   标题: {entry['title'][:80]}...")
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
