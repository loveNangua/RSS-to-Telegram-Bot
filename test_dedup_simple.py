#!/usr/bin/env python3
"""直接测试去重逻辑"""
import re
import hashlib
from difflib import SequenceMatcher

def extract_core_content(text):
    """提取文本的核心内容"""
    if not text:
        return ''
    
    # 移除HTML标签和实体
    text = re.sub(r'<[^>]+>', ' ', text)
    text = re.sub(r'&[a-z]+;', ' ', text)
    
    # 移除各种RT/转发标记
    text = re.sub(r'^(RT|转发|Retweet|Forward|via)[\s:@]*[^:：\s]*[:：]?\s*', '', text, flags=re.IGNORECASE)
    
    # 处理多行格式
    lines = text.split('\n')
    if len(lines) > 1:
        if len(lines[0]) < 30 and re.search(r'(RT|@|转发|via)', lines[0], re.IGNORECASE):
            text = '\n'.join(lines[1:])
    
    # 移除URL和@
    text = re.sub(r'https?://\S+', '', text)
    text = re.sub(r'@[\w\u4e00-\u9fa5]+', '', text)
    
    # 移除话题标签但保留内容
    text = re.sub(r'#(\S+)', r'\1', text)
    
    # 清理
    text = re.sub(r'\s+', ' ', text)
    text = re.sub(r'[,.!?;:"""''`~\-_=+\[\]{}()|\\/<>*&^%$#@]+', ' ', text)
    
    return text.strip().lower()

# 测试案例
test_cases = [
    ("RT 小韩: 太可爱了🥳 我玩玩玩玩玩玩 完整视频在🚪视频号 #4i #四爱 #龟头责", "RT with colon"),
    ("太可爱了🥳 我玩玩玩玩玩玩 完整视频在🚪视频号 #4i #四爱 #龟头责", "Original"),
    ("RT 小韩<br>太可爱了🥳<br>我玩玩玩玩玩玩<br>完整视频在🚪视频号<br>#4i #四爱 #龟头责", "RT with br tag"),
    ("RT 小狗质检员: 逃不掉就只能乖乖掰开屁股被打啦 #spank", "RT 小狗质检员 with colon"),
    ("RT 小狗质检员<br>逃不掉就只能乖乖掰开屁股被打啦 #spank", "RT 小狗质检员 without colon"),
    ("逃不掉就只能乖乖掰开屁股被打啦 #spank", "Original spank"),
    ("RT 小狗质检员 逃不掉就只能乖乖掰开屁股被打啦 #spank", "RT with space only"),
    ("转发自 @某用户: 这是完全不同的内容 #test", "Different content 1"),
    ("这是完全不同的内容 #test", "Different content 2"),
]

print("测试核心内容提取:")
print("=" * 80)

results = {}
for text, label in test_cases:
    core = extract_core_content(text)
    hash_val = hashlib.md5(core.encode('utf-8')).hexdigest()[:12]
    
    print(f"\n标签: {label}")
    print(f"原文: {text[:60]}...")
    print(f"核心: {core}")
    print(f"哈希: {hash_val}")
    
    # 查找相同的核心内容
    for prev_label, (prev_core, prev_hash) in results.items():
        if prev_hash == hash_val:
            print(f"  ✅ 与 '{prev_label}' 内容相同 (将被去重)")
            break
        else:
            similarity = SequenceMatcher(None, core, prev_core).ratio()
            if similarity > 0.85:
                print(f"  ⚠️ 与 '{prev_label}' 高度相似 ({similarity:.2%})")
    
    results[label] = (core, hash_val)

print("\n" + "=" * 80)
print("去重结果统计:")
unique_hashes = set(h for _, h in results.values())
print(f"原始条目数: {len(test_cases)}")
print(f"唯一内容数: {len(unique_hashes)}")
print(f"将去重数量: {len(test_cases) - len(unique_hashes)}")
