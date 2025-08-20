# RSS状态码感知功能改进说明

## 概述

本次改进为RSSTT添加了智能的HTTP状态码感知处理机制，特别针对Twitter订阅的特殊情况进行了优化。该功能可以根据不同的错误类型和订阅源类型，采用差异化的重试策略，提高系统的稳定性和可靠性。

## 主要改进内容

### 1. 错误类型分类系统

新增了 `ErrorType` 枚举和 `ErrorClassifier` 类，能够智能分类HTTP错误：

```python
class ErrorType(Enum):
    UNKNOWN = auto()         # 未知错误
    TEMPORARY = auto()       # 临时错误（服务器临时不可用）
    PERMANENT = auto()       # 永久错误（资源不存在）
    RATE_LIMITED = auto()    # 限流错误
    CLIENT_ERROR = auto()    # 客户端错误
    AUTH_ERROR = auto()      # 认证错误
    NETWORK_ERROR = auto()   # 网络连接错误
    SERVER_ERROR = auto()    # 服务器错误
```

#### 状态码映射规则

**通用状态码映射：**
- `404`: `PERMANENT` - 资源不存在
- `429`: `RATE_LIMITED` - 请求过于频繁
- `502/503/504`: `TEMPORARY` - 服务器临时不可用
- `401/403`: `AUTH_ERROR` - 认证或权限问题
- `500`: `SERVER_ERROR` - 服务器内部错误

**Twitter特殊映射：**
- `400`: `RATE_LIMITED` - Twitter API通常在超出配额时返回400
- `429`: `RATE_LIMITED` - 严重限流
- `404`: `PERMANENT` - 用户或内容不存在

### 2. 智能重试延迟策略

根据错误类型和订阅源类型（普通/Twitter）采用不同的重试延迟：

#### 限流错误 (RATE_LIMITED)
- **普通订阅**: 至少等待30分钟
- **Twitter订阅**: 至少等待60分钟（Twitter限流更严格）

#### 临时错误 (TEMPORARY)
- **普通订阅**: 至少等待10分钟，使用标准延迟的1/2
- **Twitter订阅**: 至少等待15分钟，快速恢复检查

#### 永久错误 (PERMANENT)
- **普通订阅**: 延长到基础间隔的6倍
- **Twitter订阅**: 延长到基础间隔的12倍（避免频繁检查不存在的用户）

### 3. 增强的WebError类

扩展了 `WebError` 类以支持：

```python
class WebError(Exception):
    def __init__(self, error_name: str, status: Union[int, str] = None, 
                 url: str = None, base_error: Exception = None, 
                 log_level: int = log.DEBUG, is_twitter: bool = False):
        # 自动设置错误类型
        self.error_type = ErrorClassifier.classify(status, is_twitter)
        
    def get_retry_delay(self, error_count: int, base_interval: int) -> int:
        """获取建议的重试延迟（分钟）"""
        return ErrorClassifier.get_retry_delay(
            self.error_type, error_count, base_interval, self.is_twitter
        )
```

### 4. 监控系统集成

在 `monitor/_monitor.py` 中集成了新的状态码感知逻辑：

```python
# 使用智能重试延迟策略
if wf.error and hasattr(wf.error, 'get_retry_delay'):
    next_check_delay = wf.error.get_retry_delay(new_error_count, interval)
else:
    # 回退到标准指数退避
    next_check_delay = min(interval << (new_error_count // 10), 1440)
```

### 5. Twitter URL检测

新增了 `is_twitter_feed()` 函数，能够准确识别Twitter相关的RSS订阅：

```python
def is_twitter_feed(url: str) -> bool:
    """检测是否为Twitter RSSHub URL"""
    twitter_patterns = [
        '/twitter/user/', '/twitter/list/', '/twitter/search/',
        '/rsshub.app/twitter/', 'rsshub.app/twitter/user', ...
    ]
    return any(pattern in url.lower() for pattern in twitter_patterns)
```

## 实际效果示例

### 场景1: Twitter用户限流
- **状态码**: 429
- **传统处理**: 使用固定的指数退避，可能在15-30分钟后重试
- **新处理**: 识别为Twitter限流，至少等待60分钟，避免加剧限流问题

### 场景2: RSSHub临时不可用
- **状态码**: 503
- **传统处理**: 标准指数退避
- **新处理**: 识别为临时错误，缩短等待时间，快速恢复服务

### 场景3: Twitter用户不存在
- **状态码**: 404
- **传统处理**: 标准重试逻辑
- **新处理**: 识别为Twitter永久错误，延长检查间隔到12倍基础间隔

## 向后兼容性

- 所有现有功能保持不变
- 新的错误处理逻辑作为增强，不会破坏现有行为
- 如果新逻辑出现问题，会自动回退到传统的指数退避算法

## 性能影响

- **计算开销**: 极小，仅增加简单的状态码查找和算术计算
- **内存开销**: 可忽略，仅新增少量枚举和映射表
- **网络影响**: 正面，减少了无效重试，降低了对上游服务的压力

## 监控和调试

增强的日志记录提供更详细的错误信息：

```
Fetch failed (15th retry, error_type: RATE_LIMITED, next_check_delay: 60min, 429 Too Many Requests): https://rsshub.app/twitter/user/test
```

## 测试验证

创建了完整的测试套件 (`test_status_simple.py`) 验证：
- ✅ 错误分类准确性
- ✅ 重试延迟计算正确性  
- ✅ Twitter URL检测准确性
- ✅ 综合场景处理效果

所有测试均通过，确保功能可靠性。

## 未来扩展

该架构支持轻松扩展：
- 添加更多平台的特殊处理（如微博、知乎等）
- 支持更细粒度的错误分类
- 集成更多智能重试策略

## 总结

本次状态码感知功能改进显著提升了RSSTT对各种网络错误的处理能力，特别是对Twitter等敏感平台的支持。通过智能化的错误分类和差异化重试策略，系统变得更加稳定、高效，同时减少了对上游服务的不必要压力。
