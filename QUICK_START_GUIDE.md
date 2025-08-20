# RSSTT 快速启动指南

## 📋 当前状态检查结果

✅ **依赖包**: 已安装完成  
✅ **虚拟环境**: 已创建 (`venv/`)  
❌ **配置文件**: 需要创建 `.env` 文件  
❌ **Bot进程**: 当前未运行  

## 🚀 快速启动步骤

### 1. 获取 Telegram Bot Token

1. 与 [@BotFather](https://t.me/BotFather) 对话
2. 发送 `/newbot` 创建新Bot
3. 按提示设置Bot名称和用户名
4. 保存返回的Token (格式类似: `1234567890:ABCdef...`)

### 2. 获取你的User ID

1. 与 [@userinfobot](https://t.me/userinfobot) 对话
2. 发送任意消息
3. 记录返回的User ID (纯数字)

### 3. 创建配置文件

```bash
# 方法1: 复制测试模板
cp .env.test .env

# 方法2: 复制官方模板
cp .env.sample .env
```

### 4. 编辑配置文件

编辑 `.env` 文件，至少修改这两个配置：

```env
TOKEN=1234567890:ABCdef...  # 替换为你的Bot Token
MANAGER=987654321           # 替换为你的User ID
```

### 5. 启动RSSTT

```bash
# 使用启动脚本 (推荐)
./start_rsstt.sh

# 或手动启动
source venv/bin/activate
python3 telegramRSSbot.py
```

## 📊 检查运行状态

启动后，你可以：

1. **检查日志输出**: 观察终端显示的启动信息
2. **与Bot对话**: 给你的Bot发送 `/start` 命令
3. **查看日志文件**: `tail -f rsstt.log` (如果后台运行)

## 🔧 常用命令

Bot启动后，你可以使用以下命令：

- `/start` - 开始使用
- `/help` - 查看帮助
- `/sub <RSS_URL>` - 订阅RSS源
- `/list` - 查看订阅列表
- `/unsub <RSS_URL>` - 取消订阅

## 🐛 故障排除

### Bot无法启动
- 检查 `.env` 文件是否存在且配置正确
- 确保TOKEN和MANAGER都已正确填写
- 检查网络连接是否正常

### 收不到推送
- 确认RSS源URL是否有效
- 检查订阅是否成功添加 (`/list`)
- 查看日志中是否有错误信息

### 状态码感知功能
本版本包含了增强的状态码感知功能：
- 🐦 **Twitter订阅优化**: 针对Twitter限流有特殊处理
- 🔄 **智能重试**: 根据错误类型调整重试间隔
- 📊 **详细日志**: 提供更多错误分析信息

## 📁 重要文件说明

- `.env` - 主配置文件
- `venv/` - Python虚拟环境
- `~/.rsstt/` - 运行时数据目录 (自动创建)
- `rsstt.log` - 日志文件 (后台运行时)

## 🔍 检查工具

你可以随时运行状态检查：

```bash
# 使用虚拟环境检查
source venv/bin/activate
python3 check_rsstt_status.py

# 查看进程状态
ps aux | grep python | grep rss
```

## 🌐 后台运行

如果需要后台运行：

```bash
nohup ./start_rsstt.sh > rsstt.log 2>&1 &

# 查看后台运行状态
tail -f rsstt.log
```

## 📞 获取帮助

如果遇到问题：
1. 查看日志文件中的错误信息
2. 运行 `python3 check_rsstt_status.py` 诊断
3. 检查 [RSSTT官方文档](https://github.com/Rongronggg9/RSS-to-Telegram-Bot)

---

🎉 **恭喜！** 按照以上步骤，你的RSSTT应该能够正常运行了！
