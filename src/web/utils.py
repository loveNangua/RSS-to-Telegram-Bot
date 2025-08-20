#  RSS to Telegram Bot
#  Copyright (C) 2021-2025  Rongrong <i@rong.moe>
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
from typing import Union, Optional, AnyStr, ClassVar, Iterable, Dict, Tuple, Type, Literal
from typing_extensions import Final
from enum import Enum, auto

import aiohttp
import aiohttp.abc
import asyncio
import email.utils
import feedparser
from contextlib import suppress
from dataclasses import dataclass
from datetime import datetime, timezone, timedelta
from ipaddress import ip_address, ip_network
from urllib.parse import urlparse
from multidict import CIMultiDictProxy
from propcache import cached_property

from .. import env, log
from ..i18n import i18n

logger = log.getLogger('RSStT.web')
PRIVATE_NETWORKS: Final = tuple(ip_network(ip_block) for ip_block in
                                ('127.0.0.0/8', '::1/128',
                                 # loopback is not a private network, list in here for convenience
                                 '169.254.0.0/16', 'fe80::/10',  # link-local address
                                 '10.0.0.0/8',  # class A private network
                                 '172.16.0.0/12',  # class B private networks
                                 '192.168.0.0/16',  # class C private networks
                                 'fc00::/7',  # ULA
                                 ))
sentinel = object()


class YummyCookieJar(aiohttp.abc.AbstractCookieJar):
    """
    A cookie jar that acts as a DummyCookieJar in the initial state.
    Then it only switches to CookieJar when there is any cookie (``update_cookies`` is called).
    In our use case, it is common that the response does not contain any cookie, as we mostly fetch RSS feeds and
    multimedia files.
    As a result, the cookie jar is mostly empty, and the overhead of CookieJar, which is expensive, is unnecessary.
    So it is expected that YummyCookieJar will seldom switch to CookieJar, acting as a DummyCookieJar most of the time.

    See also https://github.com/aio-libs/aiohttp/issues/7583
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.__real_cookie_jar: aiohttp.abc.AbstractCookieJar = aiohttp.DummyCookieJar(*args, **kwargs)
        self.__init_args = args
        self.__init_kwargs = kwargs
        self.__is_dummy = True

    def update_cookies(self, *args, **kwargs):
        if self.__is_dummy:
            self.__real_cookie_jar = aiohttp.CookieJar(*self.__init_args, **self.__init_kwargs)
            self.__is_dummy = False
        return self.__real_cookie_jar.update_cookies(*args, **kwargs)

    def __iter__(self):
        return self.__real_cookie_jar.__iter__()

    def __len__(self) -> int:
        return self.__real_cookie_jar.__len__()

    def clear(self, *args, **kwargs):
        return self.__real_cookie_jar.clear(*args, **kwargs)

    def clear_domain(self, *args, **kwargs):
        return self.__real_cookie_jar.clear_domain(*args, **kwargs)

    def filter_cookies(self, *args, **kwargs):
        return self.__real_cookie_jar.filter_cookies(*args, **kwargs)

    @property
    def quote_cookie(self) -> bool:
        return self.__real_cookie_jar.quote_cookie


class ErrorType(Enum):
    """错误类型枚举"""
    UNKNOWN = auto()         # 未知错误
    TEMPORARY = auto()       # 临时错误（服务器临时不可用）
    PERMANENT = auto()       # 永久错误（资源不存在）
    RATE_LIMITED = auto()    # 限流错误
    CLIENT_ERROR = auto()    # 客户端错误
    AUTH_ERROR = auto()      # 认证错误
    NETWORK_ERROR = auto()   # 网络连接错误
    SERVER_ERROR = auto()    # 服务器错误


class ErrorClassifier:
    """HTTP状态码错误分类器"""
    
    # 状态码到错误类型的映射
    STATUS_TO_TYPE: Dict[int, ErrorType] = {
        400: ErrorType.CLIENT_ERROR,  # Bad Request
        401: ErrorType.AUTH_ERROR,    # Unauthorized
        403: ErrorType.AUTH_ERROR,    # Forbidden
        404: ErrorType.PERMANENT,     # Not Found
        408: ErrorType.TEMPORARY,     # Request Timeout
        429: ErrorType.RATE_LIMITED,  # Too Many Requests
        451: ErrorType.PERMANENT,     # Unavailable For Legal Reasons
        500: ErrorType.SERVER_ERROR,  # Internal Server Error
        502: ErrorType.TEMPORARY,     # Bad Gateway
        503: ErrorType.TEMPORARY,     # Service Unavailable
        504: ErrorType.TEMPORARY,     # Gateway Timeout
    }
    
    # Twitter特定处理映射
    TWITTER_STATUS_TO_TYPE: Dict[int, ErrorType] = {
        400: ErrorType.RATE_LIMITED,  # Twitter API通常在超出配额时返回400
        429: ErrorType.RATE_LIMITED,  # 对Twitter来说这是严重的限流
        404: ErrorType.PERMANENT,     # Twitter用户或内容不存在
    }
    
    @classmethod
    def classify(cls, status: int, is_twitter: bool = False) -> ErrorType:
        """根据状态码分类错误类型"""
        if is_twitter and status in cls.TWITTER_STATUS_TO_TYPE:
            return cls.TWITTER_STATUS_TO_TYPE[status]
        
        if status in cls.STATUS_TO_TYPE:
            return cls.STATUS_TO_TYPE[status]
        
        # 根据状态码范围分类
        if 400 <= status < 500:
            return ErrorType.CLIENT_ERROR
        elif 500 <= status < 600:
            return ErrorType.SERVER_ERROR
        
        return ErrorType.UNKNOWN
    
    @classmethod
    def get_retry_delay(cls, error_type: ErrorType, error_count: int, base_interval: int, is_twitter: bool = False) -> int:
        """根据错误类型获取建议的重试延迟（分钟）
        
        :param error_type: 错误类型
        :param error_count: 已经发生的错误次数
        :param base_interval: 基础检查间隔（分钟）
        :param is_twitter: 是否是Twitter订阅
        :return: 建议的延迟时间（分钟）
        """
        # 计算基本指数退避（标准的2的幂次方增长）
        exp_backoff = min(base_interval * (2 ** (error_count // 10)), 1440)  # 最大1天
        
        # 根据错误类型和Twitter特殊情况调整
        if error_type == ErrorType.RATE_LIMITED:
            if is_twitter:
                return max(60, exp_backoff)  # Twitter限流至少等待1小时
            return max(30, exp_backoff)  # 普通限流至少等待30分钟
            
        elif error_type == ErrorType.TEMPORARY:
            if is_twitter:
                return max(15, exp_backoff // 2)  # Twitter临时错误缩短等待
            return max(10, exp_backoff // 2)  # 临时错误缩短等待
            
        elif error_type == ErrorType.PERMANENT:
            if is_twitter:
                return min(1440, base_interval * 12)  # Twitter永久错误延长等待到12倍间隔
            return min(720, base_interval * 6)  # 永久错误延长等待到6倍间隔
            
        elif error_type == ErrorType.AUTH_ERROR:
            # 认证错误通常需要人工干预，延长检查间隔
            return min(1440, base_interval * 8)  # 认证错误延长到8倍间隔
            
        elif error_type == ErrorType.CLIENT_ERROR:
            # 客户端错误可能是临时的配置问题
            return max(base_interval * 2, exp_backoff // 2)  # 适度延长间隔
            
        elif error_type == ErrorType.NETWORK_ERROR:
            # 网络错误通常是临时的，但需要一些时间恢复
            return max(5, exp_backoff // 3)  # 网络错误快速重试，但至少等待5分钟
            
        # 默认使用标准指数退避
        return exp_backoff


class WebError(Exception):
    @staticmethod
    def _join_snips(sep: str, snips: Iterable[str]) -> str:
        return sep.join(filter(None, snips))

    def __init__(
            self,
            error_name: str,
            status: Union[int, str] = None,
            url: str = None,
            base_error: Exception = None,
            log_level: int = log.DEBUG,
            is_twitter: bool = False,
    ):
        super().__init__(error_name)
        self.error_name = error_name
        self.status = status
        self.url = url
        self.base_error = base_error
        self.is_twitter = is_twitter
        
        # 设置错误类型
        self.error_type = ErrorType.UNKNOWN
        if isinstance(status, int):
            self.error_type = ErrorClassifier.classify(status, is_twitter)
        elif isinstance(base_error, (asyncio.TimeoutError, ConnectionError, OSError, TimeoutError)):
            self.error_type = ErrorType.NETWORK_ERROR
        elif isinstance(base_error, aiohttp.ClientConnectorError):
            self.error_type = ErrorType.NETWORK_ERROR  
        elif isinstance(base_error, aiohttp.ClientError):
            # 其他aiohttp客户端错误，可能包含有用的状态码信息
            self.error_type = ErrorType.CLIENT_ERROR
            
        self.detail = self._join_snips(', ', (
            type(base_error).__name__ if base_error else None,
            status,
        ))
        reason = self._join_snips(', ', (
            error_name,
            self.detail,
        ))
        log_msg = self._join_snips(': ', (
            f'Fetch failed ({reason})',
            url,
        ))
        logger.log(
            log_level,
            log_msg,
            exc_info=base_error if log_level >= log.ERROR or env.DEBUG else None,
        )

    def i18n_message(self, lang: str = None) -> str:
        error_key = self.error_name.lower().replace(' ', '_')
        return self._join_snips(' ', (
            'ERROR:',
            i18n[lang][error_key],
            f'({self.detail})' if self.detail else None,
        ))
        
    def get_retry_delay(self, error_count: int, base_interval: int) -> int:
        """获取建议的重试延迟（分钟）"""
        return ErrorClassifier.get_retry_delay(
            error_type=self.error_type,
            error_count=error_count,
            base_interval=base_interval,
            is_twitter=self.is_twitter
        )

    def __str__(self) -> str:
        return self.i18n_message()


def rfc_2822_8601_to_datetime(time_str: Optional[str]) -> Optional[datetime]:
    """
    Some websites freakishly violate the standard and use RFC 8601 in HTTP headers, so we have to support both.
    :param time_str: Time string in RFC 2822 or 8601 format
    :return: datetime object, if valid
    """
    if not time_str:
        return None
    with suppress(ValueError):
        return email.utils.parsedate_to_datetime(time_str)
    with suppress(ValueError):
        return datetime.fromisoformat(time_str)
    return None


@dataclass
class WebResponse:
    AGE_REMAINING_CLAMP_MIN: ClassVar[int] = 0
    AGE_REMAINING_CLAMP_MAX: ClassVar[int] = 21600  # 6 hours

    url: str  # redirected url
    ori_url: str  # original url
    content: Optional[AnyStr]
    headers: CIMultiDictProxy[str]
    status: int
    reason: Optional[str]

    @cached_property
    def etag(self) -> Optional[str]:
        return self.headers.get('ETag') or None  # Prohibit empty string

    @cached_property
    def now(self) -> datetime:
        return datetime.now(timezone.utc)

    @cached_property
    def date(self) -> datetime:
        return rfc_2822_8601_to_datetime(self.headers.get('Date')) or self.now

    @cached_property
    def last_modified(self) -> datetime:
        return rfc_2822_8601_to_datetime(self.headers.get('Last-Modified')) or self.date

    @cached_property
    def max_age(self) -> Optional[int]:
        cache_control = self.headers.get('Cache-Control', '').lower()
        if not cache_control:
            return None
        elif 'no-cache' in cache_control or 'no-store' in cache_control:
            return 0
        elif max_age := cache_control.partition('max-age=')[2].partition(',')[0]:
            try:
                return int(max_age) if max_age else None
            except ValueError:
                return None
        return None

    @cached_property
    def age(self) -> Optional[int]:
        age = self.headers.get('Age')
        try:
            return int(age) if age else None
        except ValueError:
            return None

    @cached_property
    def age_remaining(self) -> Optional[int]:
        if self.max_age is None:
            return None
        else:
            age_remaining = self.max_age - (self.age or 0)
            if age_remaining < (clamp_min := self.AGE_REMAINING_CLAMP_MIN):
                return clamp_min
            elif age_remaining > (clamp_max := self.AGE_REMAINING_CLAMP_MAX):
                return clamp_max
            return age_remaining

    @cached_property
    def expires(self) -> Optional[datetime]:
        # max-age overrides Expires: https://developer.mozilla.org/en-US/docs/Web/HTTP/Headers/Expires
        if self.age_remaining is None:
            return rfc_2822_8601_to_datetime(self.headers.get('Expires'))
        elif self.age_remaining <= 0:
            return None
        else:
            return self.date + timedelta(seconds=self.age_remaining)


@dataclass
class WebFeed:
    url: str  # redirected url
    ori_url: str  # original url
    content: Optional[AnyStr] = None
    headers: Optional[CIMultiDictProxy[str]] = None
    status: int = -1
    reason: Optional[str] = None
    rss_d: Optional[feedparser.FeedParserDict] = None
    error: Optional[WebError] = None

    web_response: Optional[WebResponse] = None

    def calc_next_check_as_per_server_side_cache(self) -> Optional[datetime]:
        wr = self.web_response
        if wr is None:
            return None
        now = wr.now

        # defer next check as per Cloudflare cache
        # https://developers.cloudflare.com/cache/concepts/cache-responses/
        # https://developers.cloudflare.com/cache/how-to/edge-browser-cache-ttl/
        if self.headers.get('cf-cache-status') in {'HIT', 'MISS', 'EXPIRED', 'REVALIDATED'}:
            expires = wr.expires
            if expires and expires > now:
                return expires

        # defer next check as per RSSHub TTL (or Cache-Control max-age)
        # only apply when TTL > 5min,
        # as it is the default value of RSSHub and disabling cache won't change it in some legacy versions
        rss_d = self.rss_d
        if (
                rss_d.feed.get('generator') == 'RSSHub'
                and
                (updated_str := rss_d.feed.get('updated'))
        ):
            ttl_in_minute_str: str = rss_d.feed.get('ttl', '')
            ttl_in_second = (
                                int(ttl_in_minute_str) * 60
                                if ttl_in_minute_str.isdecimal()
                                else wr.max_age
                            ) or -1
            if ttl_in_second > 300:
                updated = rfc_2822_8601_to_datetime(updated_str)
                if updated and (next_check_time := updated + timedelta(seconds=ttl_in_second)) > now:
                    return next_check_time

        return None


def proxy_filter(url: str, parse: bool = True) -> bool:
    if not (env.PROXY_BYPASS_PRIVATE or env.PROXY_BYPASS_DOMAINS):
        return True

    hostname = urlparse(url).hostname if parse else url
    if env.PROXY_BYPASS_PRIVATE:
        with suppress(ValueError):  # if not an IP, continue
            ip_a = ip_address(hostname)
            is_private = any(ip_a in network for network in PRIVATE_NETWORKS)
            if is_private:
                return False
    if env.PROXY_BYPASS_DOMAINS:
        is_bypassed = any(hostname.endswith(domain) and (hostname == domain or hostname[-len(domain) - 1] == '.')
                          for domain in env.PROXY_BYPASS_DOMAINS)
        if is_bypassed:
            return False
    return True
