#  RSS to Telegram Bot
#  Copyright (C) 2021-2024  Rongrong <i@rong.moe>
#
#  This program is free software: you can redistribute it and/or modify
#  it under the terms of the GNU Affero General Public License as
#  published by the Free Software Foundation, either version 3 of the
#  License, or (at your option) any later version.
#
#  This program is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU Affero General Public License for more details.
#
#  You should have received a copy of the GNU Affero General Public License
#  along with this program.  If not, see <https://www.gnu.org/licenses/>.

from __future__ import annotations
from typing import Any, Union, Optional
from collections.abc import Iterable, Sequence

import asyncio
import re
import hashlib
from collections import defaultdict
from itertools import chain, repeat
from telethon import Button
from telethon.tl.types import KeyboardButtonCallback

try:
    from isal.isal_zlib import crc32
except ImportError:
    from zlib import crc32

from ... import db, log, env
from ...i18n import i18n

logger = log.getLogger('RSStT.command')

emptyButton = Button.inline(' ', data='null')


def parse_hashtags(text: str) -> list[str]:
    if '#' in text:
        return re.findall(r'(?<=#)[^\s#]+', text)
    return re.findall(r'\S+', text)


def construct_hashtags(tags: Union[Iterable[str], str]) -> str:
    if isinstance(tags, str):
        tags = parse_hashtags(tags)
    return '#' + ' #'.join(tags)


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


def filter_urls(urls: Optional[Iterable[str]]) -> tuple[str, ...]:
    return tuple(filter(lambda x: x.startswith('http://') or x.startswith('https://'), urls)) if urls else ()


# copied from command.utils
def escape_html(raw: Any) -> str:
    raw = str(raw)
    return raw.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')


def formatting_time(days: int = 0, hours: int = 0, minutes: int = 0, seconds: int = 0, long: bool = False) -> str:
    days = days + hours // 24 + minutes // (24 * 60) + seconds // (24 * 60 * 60)
    hours = (hours + minutes // 60 + seconds // (60 * 60)) % 24
    minutes = (minutes + seconds // 60) % 60
    seconds %= 60
    return (
            (f'{days}d' if days > 0 or long else '')
            + (f'{hours}h' if hours > 0 or long else '')
            + (f'{minutes}min' if minutes > 0 or long else '')
            + (f'{seconds}s' if seconds > 0 or long else '')
    )


def arrange_grid(to_arrange: Iterable, columns: int = 8, rows: int = 13) -> tuple[tuple[Any, ...], ...]:
    """
    :param to_arrange: `Iterable` containing objects to arrange
    :param columns: 1-based, telegram limit: 8 (row 1-12), 4 (row 13)
    :param rows: 1-based, telegram limit: 13
    :return: grid (2D tuple) with objects arranged
    """
    if rows <= 0 or columns <= 0:
        raise ValueError('Invalid grid size')
    to_arrange = list(to_arrange)
    counts = min(len(to_arrange), rows * columns)
    columns = min(columns, len(to_arrange))
    return tuple(
        tuple(to_arrange[i:i + columns]) for i in range(0, counts, columns)
    ) if counts > 0 else ()


def get_lang_buttons(callback=str, current_lang: str = None, tail: str = '') \
        -> tuple[tuple[tuple[KeyboardButtonCallback, ...], ...], tuple[str, ...]]:
    def push(n_: int):
        if len(carry) >= n_:
            lang_n_per_row[n_].extend(carry)
            carry.clear()

    lang_n_per_row = defaultdict(list)
    carry = []
    for n in sorted(i18n.lang_n_per_row.keys(), reverse=True):
        for lang in i18n.lang_n_per_row[n]:
            if lang == current_lang:
                continue
            push(n)
            carry.append(lang)
        push(n)
        lang_n_per_row[n].sort()
    push(1)

    buttons = tuple(
        tuple(map(
            lambda l: Button.inline(i18n[l]['lang_native_name'], data=f'{callback}={l}{tail}'),
            lang_n_per_row[n][i:i + n]
        ))
        for n in sorted(lang_n_per_row.keys(), reverse=True)
        for i in range(0, len(lang_n_per_row[n]), n)
    )
    langs = tuple(chain.from_iterable(lang_n_per_row.values()))
    return buttons, langs


async def get_sub_list_by_page(user_id: int, page_number: int, size: int, desc: bool = True, *args, **kwargs) \
        -> tuple[int, int, list[db.Sub], int]:
    """
    :param user_id: user id
    :param page_number: page number (1-based)
    :param size: page size
    :param desc: descending order
    :param args: args for `Sub.filter`
    :param kwargs: kwargs for `Sub.filter`
    :return: (page_count, page_number, subs_page, total_count)
    """
    if page_number <= 0:
        # raise IndexError('Page number must be positive.')
        page_number = 1

    sub_count = await db.Sub.filter(user=user_id, *args, **kwargs).count()
    if sub_count == 0:
        return 0, 0, [], 0

    page_count = (sub_count - 1) // size + 1
    page_number = min(page_number, page_count)

    offset = (page_number - 1) * size
    page = await db.Sub.filter(user=user_id, *args, **kwargs) \
        .order_by('-id' if desc else 'id') \
        .limit(size) \
        .offset(offset) \
        .prefetch_related('feed')
    return page_number, page_count, page, sub_count


def get_page_buttons(page_number: int,
                     page_count: int,
                     get_page_callback: str,
                     total_count: Optional[int] = None,
                     display_cancel: bool = False,
                     lang: Optional[str] = None,
                     tail: str = '') -> list[Button]:
    page_number = min(page_number, page_count)
    page_info = f'{page_number} / {page_count}' + (f' ({total_count})' if total_count else '')
    return [
        Button.inline(f'< {i18n[lang]["previous_page"]}', data=f'{get_page_callback}|{page_number - 1}{tail}')
        if page_number > 1
        else emptyButton,

        Button.inline(f'{page_info} | {i18n[lang]["cancel"]}', data='cancel')
        if display_cancel
        else Button.inline(page_info, data='null'),

        Button.inline(f'{i18n[lang]["next_page"]} >', data=f'{get_page_callback}|{page_number + 1}{tail}')
        if page_number < page_count
        else emptyButton,
    ]


async def get_sub_choosing_buttons(user_id: int,
                                   page_number: int,
                                   callback: str,
                                   get_page_callback: Optional[str],
                                   callback_contain_page_num: bool = True,
                                   lang: Optional[str] = None,
                                   rows: int = 12,
                                   columns: int = 1,
                                   tail: str = '',
                                   *args, **kwargs) -> Optional[tuple[tuple[KeyboardButtonCallback, ...], ...]]:
    """
    :param user_id: user id
    :param page_number: page number (1-based)
    :param callback: callback data header
    :param get_page_callback: callback data header for getting another page
    :param callback_contain_page_num: callback data should be followed by current page number or not?
    :param lang: language code
    :param rows: the number of rows
    :param columns: the number of columns
    :param args: args for `list_sub`
    :param kwargs: kwargs for `list_sub`
    :param tail: callback data tail
    :return: ReplyMarkup
    """
    if page_number <= 0:
        raise IndexError('Page number must be positive.')

    size = columns * rows
    page_number, page_count, page, sub_count = \
        await get_sub_list_by_page(user_id=user_id, page_number=page_number, size=size, *args, **kwargs)

    if page_count == 0:
        return None

    buttons_to_arrange = tuple(Button.inline(_sub.title or _sub.feed.title,
                                             data=f'{callback}={_sub.id}'
                                                  + (f'|{page_number}' if callback_contain_page_num else '')
                                                  + tail)
                               for _sub in page)
    buttons = arrange_grid(to_arrange=buttons_to_arrange, columns=columns, rows=rows)

    page_buttons = get_page_buttons(page_number=page_number,
                                    page_count=page_count,
                                    get_page_callback=get_page_callback,
                                    total_count=sub_count,
                                    display_cancel=True,
                                    lang=lang,
                                    tail=tail)

    return buttons + (tuple(page_buttons),) if page_buttons else buttons


async def update_interval(feed: Union[db.Feed, db.Sub, int]):
    if isinstance(feed, int):
        feed = await db.Feed.get_or_none(id=feed)
    elif isinstance(feed, db.Sub):
        sub = feed
        if not isinstance(sub.feed, db.Feed):
            await sub.fetch_related('feed')
        feed = sub.feed

    if feed is None:
        return
    
    # Twitter 调度器处理
    from ..scheduler.twitter_scheduler import twitter_scheduler
    if twitter_scheduler.is_twitter_feed(feed.link):
        # Twitter 订阅由调度器管理，不更新 interval
        logger.debug(f"Twitter feed {feed.id} is managed by scheduler, skipping interval update")
        return

    default_interval = db.EffectiveOptions.default_interval
    curr_interval = feed.interval or default_interval
    set_to_default = False

    sub_exist = await feed.subs.all().exists()
    if not sub_exist:  # no sub subs the feed, del the feed
        await feed.delete()
        db.effective_utils.EffectiveTasks.delete(feed.id)
        return
    intervals = await feed.subs.filter(state=1, interval__not_isnull=True).values_list('interval', flat=True)
    intervals += await feed.subs.filter(state=1, interval__isnull=True, user__interval__not_isnull=True) \
        .values_list('user__interval', flat=True)
    some_using_default = await feed.subs.filter(state=1, interval__isnull=True, user__interval__isnull=True).exists()
    if not intervals and not some_using_default:  # no active sub subs the feed, deactivate the feed
        if feed.state == 1:
            feed.state = 0
            feed.error_count = 0
            feed.next_check_time = None
            await feed.save()
        db.effective_utils.EffectiveTasks.delete(feed.id)
        return
    new_interval = min(intervals) if intervals else None
    if (new_interval is None or default_interval < new_interval) and some_using_default:
        new_interval = default_interval
        set_to_default = True

    feed_update_flag = False
    if new_interval != curr_interval or (set_to_default and feed.interval is not None):
        feed.interval = None if set_to_default else new_interval
        feed_update_flag = True
    if feed.state != 1:
        feed.state = 1
        feed.error_count = 0
        feed.next_check_time = None
        feed_update_flag = True
    if feed_update_flag:
        await feed.save()
    if db.effective_utils.EffectiveTasks.get_interval(feed.id) != new_interval:
        db.effective_utils.EffectiveTasks.update(feed.id, new_interval)


async def list_sub(user_id: int, *args, **kwargs) -> list[db.Sub]:
    return await db.Sub.filter(user=user_id, *args, **kwargs).prefetch_related('feed')


async def count_sub(user_id: int, *args, **kwargs) -> int:
    return await db.Sub.filter(user=user_id, *args, **kwargs).count()


async def have_subs(user_id: int) -> bool:
    return await db.Sub.filter(user=user_id).exists()


async def check_sub_limit(user_id: int, force_count_current: bool = False) -> tuple[bool, int, int, bool]:
    """
    :return: exceeded (bool), current count (int), limit (int), is default limit (bool)
    """
    curr_count: int = -1
    limit: int = -1
    is_default_limit: bool = False
    if user_id not in env.MANAGER:
        # noinspection PyTypeChecker
        limit: Optional[int] = await db.User.get_or_none(id=user_id).values_list('sub_limit', flat=True)
        if limit is None:
            limit: int = (db.EffectiveOptions.user_sub_limit
                          if user_id > 0
                          else db.EffectiveOptions.channel_or_group_sub_limit)
            is_default_limit = True

    if force_count_current or limit >= 0:
        curr_count = await count_sub(user_id)

    return curr_count >= limit >= 0, curr_count, limit, is_default_limit


async def activate_feed(feed: db.Feed) -> db.Feed:
    if feed.state == 1:
        return feed

    feed.state = 1
    feed.error_count = 0
    feed.next_check_time = None
    await feed.save()
    await update_interval(feed)
    return feed


async def deactivate_feed(feed: db.Feed) -> db.Feed:
    db.effective_utils.EffectiveTasks.delete(feed.id)

    subs = await feed.subs.all()
    if not subs:
        await feed.delete()
        return feed

    feed.state = 0
    feed.error_count = 0
    feed.next_check_time = None
    await feed.save()
    await asyncio.gather(
        *(activate_or_deactivate_sub(sub.user_id, sub, activate=False, _update_interval=False) for sub in subs)
    )

    return feed


async def activate_or_deactivate_sub(user_id: int, sub: Union[db.Sub, int], activate: bool,
                                     _update_interval: bool = True) -> Optional[db.Sub]:
    """
    :param user_id: user id
    :param sub: `db.Sub` or sub id
    :param activate: activate the sub if `Ture`, deactivate if `False`
    :param _update_interval: update interval or not?
    :return: the updated sub, `None` if the sub does not exist
    """
    if isinstance(sub, int):
        sub = await db.Sub.get_or_none(id=sub, user_id=user_id)
        if not sub:
            return None
    elif sub.user_id != user_id:
        return None

    sub.state = 1 if activate else 0
    await sub.save()
    if not isinstance(sub.feed, db.Feed):
        await sub.fetch_related('feed')

    feed = sub.feed
    if activate and feed.state != 1:
        await activate_feed(feed)
    elif _update_interval:
        await update_interval(feed)

    return sub


async def activate_or_deactivate_all_subs(user_id: int, activate: bool) -> tuple[Optional[db.Sub], ...]:
    """
    :param user_id: user id
    :param activate: activate all subs if `Ture`, deactivate if `False`
    :return: the updated sub, `None` if the sub does not exist
    """
    subs = await list_sub(user_id, state=0 if activate else 1)
    tasks = []
    feeds_to_update = []
    for sub in subs:
        sub.state = 1 if activate else 0
        feed = sub.feed
        if activate and sub.feed.state != 1:
            feed.state = 1
            feed.error_count = 0
            feed.next_check_time = None
            feeds_to_update.append(feed)
        tasks.append(update_interval(feed))
    await db.Sub.bulk_update(subs, ['state'])
    if feeds_to_update:
        await db.Feed.bulk_update(feeds_to_update, ['state', 'error_count', 'next_check_time'])
    for task in tasks:
        env.loop.create_task(task)
    return tuple(subs)
