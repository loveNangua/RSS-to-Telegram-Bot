#!/usr/bin/env python3
"""测试RT去重逻辑"""
import re
import hashlib

def _normalize_content_for_similarity(content: str) -> str:
    """
    标准化内容用于相似度检测
    移除RT前缀、多余空格、特殊字符等，保留核心内容
    """
    if not content:
        return ''
    
    # 移除HTML标签（如<br>）
    content = re.sub(r'<[^>]+>', ' ', content)
    
    # 移除HTML实体（如&lt; &gt; &amp;）
    content = re.sub(r'&[a-z]+;', ' ', content)
    
    # 移除RT前缀和用户名（支持多种格式）
    # 格式1: "RT 用户名: 内容"
    content = re.sub(r'^RT\s+[^:]+:\s*', '', content, flags=re.IGNORECASE)
    # 格式2: "RT 用户名 内容"（没有冒号，RT后跟用户名和空格/换行）
    content = re.sub(r'^RT\s+\S+\s+', '', content, flags=re.IGNORECASE)
    
    # 移除多余的空格和换行
    content = re.sub(r'\s+', ' ', content).strip()
    
    # 移除URL（保留核心文本内容）
    content = re.sub(r'https?://\S+', '', content)
    
    # 移除@用户名（但保留核心内容）
    content = re.sub(r'@\w+', '', content)
    
    # 标准化标点符号
    content = re.sub(r'[,.!?;:…]+', '', content)
    
    return content.lower().strip()

# 测试案例
test_cases = [
    ("RT 小韩: 太可爱了🥳 我玩玩玩玩玩玩 完整视频在🚪视频号 #4i #四爱 #龟头责", "RT case"),
    ("太可爱了🥳 我玩玩玩玩玩玩 完整视频在🚪视频号 #4i #四爱 #龟头责", "Original case"),
    ("RT 小韩\n太可爱了🥳\n我玩玩玩玩玩玩\n\n完整视频在🚪视频号\n#4i #四爱 #龟头责", "RT with newlines"),
    ("太可爱了🥳\n我玩玩玩玩玩玩\n\n完整视频在🚪视频号\n#4i #四爱 #龟头责", "Original with newlines")
]

print("测试内容标准化和去重：\n")
print("-" * 80)

for content, label in test_cases:
    normalized = _normalize_content_for_similarity(content)
    hash_value = hashlib.md5(normalized.encode('utf-8')).hexdigest()[:12]
    
    print(f"Label: {label}")
    print(f"Original: {content[:50]}...")
    print(f"Normalized: {normalized}")
    print(f"Hash: {hash_value}")
    print("-" * 80)

# 测试实际RSS数据的情况
print("\n测试实际RSS数据：")
print("-" * 80)

# 模拟RSS条目
entry1 = {
    'title': 'RT 小韩: 太可爱了🥳 我玩玩玩玩玩玩 完整视频在🚪视频号 #4i #四爱 #龟头责',
    'summary': 'RT 小韩<br>太可爱了🥳<br>我玩玩玩玩玩玩<br><br>完整视频在🚪视频号<br>#4i #四爱 #龟头责<br>',
    'content': []
}

entry2 = {
    'title': '太可爱了🥳 我玩玩玩玩玩玩 完整视频在🚪视频号 #4i #四爱 #龟头责',
    'summary': '太可爱了🥳<br>我玩玩玩玩玩玩<br><br>完整视频在🚪视频号<br>#4i #四爱 #龟头责<br>',
    'content': []
}

def calculate_content_hash(entry):
    """计算条目的内容哈希"""
    title = entry.get('title', '') or ''
    summary = entry.get('summary', '') or ''
    
    # 先分别标准化每个字段
    normalized_title = _normalize_content_for_similarity(title)
    normalized_summary = _normalize_content_for_similarity(summary)
    
    # 合并标准化后的内容
    combined_normalized = f"{normalized_title} {normalized_summary}".strip()
    
    # 进一步清理合并后的内容
    combined_normalized = re.sub(r'\s+', ' ', combined_normalized).strip()
    
    if not combined_normalized or len(combined_normalized) < 10:
        return None
    
    return hashlib.md5(combined_normalized.encode('utf-8')).hexdigest()[:12]

hash1 = calculate_content_hash(entry1)
hash2 = calculate_content_hash(entry2)

print(f"Entry 1 (RT):")
print(f"  Title: {entry1['title'][:50]}...")
print(f"  Hash: {hash1}")
print()
print(f"Entry 2 (Original):")
print(f"  Title: {entry2['title'][:50]}...")
print(f"  Hash: {hash2}")
print()
print(f"是否相同哈希: {hash1 == hash2}")
print(f"应该被去重: {'是' if hash1 == hash2 else '否'}")
