"""
Render Webhook 支持
用于保持 Render 服务活跃，避免 15 分钟无流量后暂停
"""

import os
import requests
import logging
from flask import Flask, request
import threading
import asyncio

logger = logging.getLogger(__name__)


class RenderWebhook:
    """Render Webhook 管理器"""
    
    def __init__(self):
        self.app = Flask(__name__)
        self.bot_token = None
        self.render_name = os.getenv('RENDER_NAME')
        self.webhook_url = None
        self.flask_thread = None
        
        # 设置 Flask 路由
        self._setup_routes()
    
    def _setup_routes(self):
        """设置 Flask 路由"""
        
        @self.app.route('/')
        def home():
            """首页路由"""
            return "RSS to Telegram Bot is running!"
        
        @self.app.route('/webhook', methods=['POST'])
        def webhook():
            """Telegram webhook 路由"""
            # 记录 webhook 调用
            logger.info("Received webhook call from Telegram")
            
            # 返回 OK 响应
            return 'ok'
        
        @self.app.route('/health')
        def health():
            """健康检查路由"""
            return {'status': 'ok', 'service': 'rss-to-telegram-bot'}
    
    def set_bot_token(self, token: str):
        """设置 bot token"""
        self.bot_token = token
        
        # 如果有 RENDER_NAME，设置 webhook
        if self.render_name and self.bot_token:
            self._set_webhook()
    
    def _set_webhook(self):
        """设置 Telegram webhook"""
        if not self.render_name or not self.bot_token:
            logger.warning("RENDER_NAME or bot_token not set, skipping webhook setup")
            return
        
        self.webhook_url = f"https://{self.render_name}.onrender.com/webhook"
        
        try:
            response = requests.post(
                f"https://api.telegram.org/bot{self.bot_token}/setWebhook",
                json={'url': self.webhook_url},
                timeout=10
            )
            
            if response.status_code == 200:
                result = response.json()
                if result.get('ok'):
                    logger.info(f"Webhook set successfully: {self.webhook_url}")
                else:
                    logger.error(f"Failed to set webhook: {result}")
            else:
                logger.error(f"Webhook request failed: {response.status_code} - {response.text}")
                
        except Exception as e:
            logger.error(f"Error setting webhook: {e}")
    
    def start_flask_server(self, port: int = 10000):
        """启动 Flask 服务器"""
        if self.flask_thread and self.flask_thread.is_alive():
            logger.warning("Flask server is already running")
            return
        
        def run_server():
            self.app.run(host='0.0.0.0', port=port, threaded=True)
        
        self.flask_thread = threading.Thread(target=run_server, daemon=True)
        self.flask_thread.start()
        logger.info(f"Flask server started on port {port}")
    
    def get_webhook_info(self):
        """获取 webhook 信息"""
        if not self.bot_token:
            return None
        
        try:
            response = requests.get(
                f"https://api.telegram.org/bot{self.bot_token}/getWebhookInfo",
                timeout=10
            )
            
            if response.status_code == 200:
                return response.json()
            return None
            
        except Exception as e:
            logger.error(f"Error getting webhook info: {e}")
            return None
    
    def delete_webhook(self):
        """删除 webhook"""
        if not self.bot_token:
            return
        
        try:
            response = requests.post(
                f"https://api.telegram.org/bot{self.bot_token}/deleteWebhook",
                timeout=10
            )
            
            if response.status_code == 200:
                logger.info("Webhook deleted successfully")
            else:
                logger.error(f"Failed to delete webhook: {response.text}")
                
        except Exception as e:
            logger.error(f"Error deleting webhook: {e}")


# 全局实例
render_webhook = RenderWebhook()