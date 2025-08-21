#!/usr/bin/env python3
"""测试智能去重系统"""
import sys
sys.path.insert(0, 'src')

from command.inner.content_dedup import ContentDeduplicator

# 创建去重器
dedup = ContentDeduplicator(similarity_threshold=0.85)

# 测试数据 - 模拟各种RT格式
test_entries = [
    # 案例1: RT with colon
    {
        'title': 'RT 小韩: 太可爱了🥳 我玩玩玩玩玩玩 完整视频在🚪视频号 #4i #四爱 #龟头责',
        'summary': 'RT 小韩<br>太可爱了🥳<br>我玩玩玩玩玩玩<br><br>完整视频在🚪视频号<br>#4i #四爱 #龟头责',
        'link': 'https://example.com/1'
    },
    # 案例2: Original
    {
        'title': '太可爱了🥳 我玩玩玩玩玩玩 完整视频在🚪视频号 #4i #四爱 #龟头责',
        'summary': '太可爱了🥳<br>我玩玩玩玩玩玩<br><br>完整视频在🚪视频号<br>#4i #四爱 #龟头责',
        'link': 'https://example.com/2'
    },
    # 案例3: RT without colon (新格式)
    {
        'title': 'RT 小狗质检员: 逃不掉就只能乖乖掰开屁股被打啦 #spank',
        'summary': 'RT 小狗质检员<br>逃不掉就只能乖乖掰开屁股被打啦 #spank<br>其他更多内容更新在视频号🚪',
        'link': 'https://example.com/3'
    },
    # 案例4: Original of case 3
    {
        'title': '逃不掉就只能乖乖掰开屁股被打啦 #spank',
        'summary': '逃不掉就只能乖乖掰开屁股被打啦 #spank<br>其他更多内容更新在视频号🚪',
        'link': 'https://example.com/4'
    },
    # 案例5: 转发自 format
    {
        'title': '转发自 用户A：这是一条测试内容',
        'summary': '转发自 用户A<br>这是一条测试内容',
        'link': 'https://example.com/5'
    },
    # 案例6: Original of case 5
    {
        'title': '这是一条测试内容',
        'summary': '这是一条测试内容',
        'link': 'https://example.com/6'
    },
    # 案例7: Via format
    {
        'title': 'via @someone: Important news today',
        'summary': 'via @someone<br>Important news today',
        'link': 'https://example.com/7'
    },
    # 案例8: Original of case 7
    {
        'title': 'Important news today',
        'summary': 'Important news today',
        'link': 'https://example.com/8'
    },
    # 案例9: 完全不同的内容（不应该被去重）
    {
        'title': '今天天气真好',
        'summary': '今天天气真好，适合出去玩',
        'link': 'https://example.com/9'
    },
    # 案例10: 另一个不同的内容
    {
        'title': '明天要下雨了',
        'summary': '明天要下雨了，记得带伞',
        'link': 'https://example.com/10'
    }
]

print("=" * 80)
print("测试智能去重系统")
print("=" * 80)

# 进行去重
deduped = dedup.deduplicate_entries(test_entries)

print(f"\n原始条目数: {len(test_entries)}")
print(f"去重后条目数: {len(deduped)}")
print(f"去除的重复数: {len(test_entries) - len(deduped)}")

print("\n保留的条目:")
for i, entry in enumerate(deduped, 1):
    print(f"{i}. {entry['title'][:50]}... (link: {entry['link']})")

print("\n被去重的条目:")
deduped_links = {e['link'] for e in deduped}
for entry in test_entries:
    if entry['link'] not in deduped_links:
        print(f"- {entry['title'][:50]}... (link: {entry['link']})")

print("\n" + "=" * 80)
print("测试结果分析:")
print("-" * 40)

# 验证预期结果
expected_deduped_count = 5  # 应该保留5个唯一内容
if len(deduped) == expected_deduped_count:
    print(f"✅ 去重效果正确！保留了 {expected_deduped_count} 个唯一内容")
else:
    print(f"❌ 去重可能有问题，预期保留 {expected_deduped_count} 个，实际保留 {len(deduped)} 个")

# 检查是否正确识别了各种RT格式
rt_formats = ['RT', '转发', 'via']
print("\n各种转发格式处理:")
for fmt in rt_formats:
    originals = [e for e in test_entries if fmt.lower() not in e['title'].lower()]
    rts = [e for e in test_entries if fmt.lower() in e['title'].lower()]
    if rts:
        print(f"- {fmt} 格式: 找到 {len(rts)} 个转发，应该与原文去重")
