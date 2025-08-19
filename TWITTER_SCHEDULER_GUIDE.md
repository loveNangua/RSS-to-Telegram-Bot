# Twitter 时间槽调度 + Render Webhook 使用指南

## 功能说明

### 1. Twitter 时间槽调度
自动将 Twitter RSSHub 订阅分配到 6 个时间槽，避免同时发送过多请求到 Twitter API。

### 2. Render Webhook 支持
通过设置 Telegram webhook，利用 Telegram 的流量保持 Render 服务活跃，避免 15 分钟无流量后暂停。

## 环境变量设置

### Render 部署
```bash
# 设置 Render 服务名称
export RENDER_NAME=your-service-name

# 设置 Bot Token
export TOKEN=your-bot-token

# 其他必要的环境变量
export API_ID=your-api-id
export API_HASH=your-api-hash
export DATABASE_URL=your-database-url
```

## 工作原理

### Twitter 调度器
- 自动检测 Twitter RSSHub 订阅（包含 `/twitter/` 的 URL）
- 将订阅平均分配到 6 个时间槽
- 每个时间槽 15 分钟，槽内订阅串行检查
- 自动适应订阅数量变化

### Render Webhook
- 启动时自动设置 Telegram webhook
- Flask 服务器监听 `/webhook` 路由
- Telegram 发送消息时触发 webhook，保持服务活跃

## 使用示例

### 1. 正常使用
```bash
# 添加 Twitter 订阅（自动应用时间槽调度）
/sub https://rsshub.app/twitter/user/username

# 添加普通订阅（不受影响）
/sub https://example.com/feed.xml
```

### 2. 查看调度信息
启动时会自动打印调度信息：
```
Twitter scheduler initialized with 120 feeds
Twitter scheduler stats: {
    'total_feeds': 120,
    'slot_count': 6,
    'slots': {
        0: {'feed_count': 20, 'interval': 45.0},
        1: {'feed_count': 20, 'interval': 45.0},
        2: {'feed_count': 20, 'interval': 45.0},
        3: {'feed_count': 20, 'interval': 45.0},
        4: {'feed_count': 20, 'interval': 45.0},
        5: {'feed_count': 20, 'interval': 45.0}
    }
}
```

### 3. Webhook 设置
成功设置 webhook 会显示：
```
Webhook set successfully: https://your-service-name.onrender.com/webhook
```

## 注意事项

1. **Twitter 订阅的间隔设置会被忽略**，由调度器自动管理
2. **普通订阅不受影响**，按原有方式工作
3. **Render webhook 仅在设置了 RENDER_NAME 时启用**
4. **Flask 服务器运行在端口 10000**，确保 Render 配正确认

## 故障排除

### Twitter 订阅不更新
1. 检查日志中的调度器信息
2. 确认订阅 URL 包含 `/twitter/`
3. 查看 Monitor 模块的错误日志

### Webhook 不工作
1. 确认 RENDER_NAME 环境变量已设置
2. 检查 Flask 服务器是否启动
3. 使用 `/getWebhookInfo` 命令查看 webhook 状态

### Render 服务仍然暂停
1. 确认 webhook 设置成功
2. 检查 Render 的服务状态
3. 确保端口 10000 可以访问