"""
钉钉流客户端实现
"""
import threading
import time
from typing import Dict, Any, Optional

from dingtalk_stream import DingTalkStreamClient
from dingtalk_stream import Credential
from loguru import logger

from app.config.settings import settings
from app.core.message_service import MessageService
from app.api.client.stream.message_handler import DingTalkChatbotHandler
from app.api.client.open.openapi_client import DingtalkClient


class DingTalkStreamManager:
    """增强版的钉钉流客户端管理器，带有健康监控功能"""

    def __init__(self, message_service: Optional[MessageService] = None):
        """
        使用改进的配置初始化流管理器

        Args:
            message_service: 用于处理消息的可选消息服务
        """
        self.stream_client = None
        self.message_service = message_service
        self.stop_event = threading.Event()
        self.reconnect_interval = 5  # 初始重连间隔（秒）
        self.max_reconnect_interval = 60  # 最大重连间隔（秒）
        self.client_thread = None
        self.health_monitor_thread = None
        self.handler = None

        # 健康监控设置
        self.health_check_interval = 60  # 秒
        self.connection_timeout = 300  # 5分钟无消息后认为连接已断开
        self.is_healthy = False

        # 连接统计信息
        self.stats = {
            "connection_attempts": 0,
            "successful_connections": 0,
            "reconnections": 0,
            "last_connection_time": 0,
            "uptime": 0
        }

    def start(self, message_service: Optional[MessageService] = None) -> None:
        """
        启动钉钉流客户端，包含重连逻辑和健康监控

        Args:
            message_service: 用于处理消息的消息服务
        """
        # 如果提供了消息服务，则更新
        if message_service:
            self.message_service = message_service

        if not self.message_service:
            raise ValueError("需要提供消息服务")

        # 创建消息处理器
        self.handler = DingTalkChatbotHandler(self.message_service)

        # 从设置中配置流主题
        stream_topic = settings.DINGTALK_STREAM_TOPIC
        logger.info(f"使用主题配置钉钉流: {stream_topic}")

        try:
            # 创建认证凭据
            credential = Credential(
                settings.DINGTALK_APP_KEY,
                settings.DINGTALK_APP_SECRET
            )

            logger.info("使用凭据创建钉钉流: {credential}")

            # 创建钉钉流客户端
            self.stream_client = DingTalkStreamClient(credential)

            # 注册聊天机器人消息的回调处理器
            self.stream_client.register_callback_handler(
                stream_topic,
                self.handler
            )
            logger.info(f"使用凭据创建钉钉流: app_key={settings.DINGTALK_APP_KEY}, app_secret={settings.DINGTALK_APP_SECRET}")
            logger.info(f"凭据对象: {credential}")

            # 在单独的线程中启动客户端
            self.client_thread = threading.Thread(
                target=self._start_client_with_reconnection,
                daemon=True,
                name="DingTalkStreamThread"
            )
            self.client_thread.start()

            # 在单独的线程中启动健康监控
            self.health_monitor_thread = threading.Thread(
                target=self._monitor_connection_health,
                daemon=True,
                name="DingTalkHealthMonitor"
            )
            self.health_monitor_thread.start()

            # 更新连接统计信息
            self.stats["last_connection_time"] = time.time()
            self.is_healthy = True

            logger.info(f"钉钉流客户端成功启动，主题: {stream_topic}")

        except Exception as e:
            logger.error(f"启动钉钉流客户端失败: {str(e)}", exc_info=True)
            raise

    def _start_client_with_reconnection(self) -> None:
        """启动客户端，包含失败时的自动重连"""
        reconnect_interval = self.reconnect_interval

        while not self.stop_event.is_set():
            try:
                self.stats["connection_attempts"] += 1
                logger.info(f"启动钉钉流客户端连接 (尝试 #{self.stats['connection_attempts']})...")

                # 启动流客户端
                self.stream_client.start_forever()

                # 如果执行到这里，说明客户端正常退出
                if self.stop_event.is_set():
                    logger.info("钉钉流客户端正常停止")
                    break

                logger.warning("钉钉流客户端意外退出")
                self.is_healthy = False

            except Exception as e:
                if self.stop_event.is_set():
                    break

                self.is_healthy = False
                logger.error(f"钉钉流客户端错误: {str(e)}", exc_info=True)

            # 只有在不停止时才重连
            if self.stop_event.is_set():
                break

            # 记录重连尝试
            self.stats["reconnections"] += 1

            # 重连的指数退避
            logger.info(f"{reconnect_interval} 秒后重连 (尝试 #{self.stats['reconnections']})...")
            if self.stop_event.wait(reconnect_interval):
                break

            # 增加重连间隔，但有上限
            reconnect_interval = min(reconnect_interval * 2, self.max_reconnect_interval)

    def _monitor_connection_health(self) -> None:
        """监控钉钉流连接的健康状态"""
        while not self.stop_event.is_set():
            try:
                # 获取最后接收消息的时间
                if self.handler:
                    last_message_time = self.handler.stats.get("last_message_time", 0)
                    current_time = time.time()

                    # 检查是否最近收到消息
                    if last_message_time > 0:
                        time_since_last_message = current_time - last_message_time

                        # 如果太久没有收到消息，连接可能已断开
                        if time_since_last_message > self.connection_timeout:
                            logger.warning(f"{time_since_last_message:.1f} 秒未收到消息，连接可能已断开")
                            self.is_healthy = False

                            # 通过停止和重启客户端强制重连
                            if self.stream_client and not self.stop_event.is_set():
                                logger.info("由于不活跃，强制重连")
                                try:
                                    # 停止当前客户端
                                    self.stream_client.stop()
                                except Exception as e:
                                    logger.error(f"停止无响应客户端时出错: {str(e)}")
                        else:
                            # 连接健康
                            self.is_healthy = True

                    # 更新运行时间统计
                    if self.is_healthy:
                        self.stats["uptime"] = current_time - self.stats["last_connection_time"]

            except Exception as e:
                logger.error(f"健康监控出错: {str(e)}")

            # 等待健康检查间隔
            if self.stop_event.wait(self.health_check_interval):
                break

    def stop(self) -> None:
        """优雅地停止钉钉流客户端"""
        if not self.stream_client:
            logger.warning("尝试停止不存在的钉钉流客户端")
            return

        logger.info("正在停止钉钉流客户端...")
        self.stop_event.set()

        try:
            # 停止客户端
            self.stream_client.stop()
            logger.info("已发送钉钉流客户端停止命令")
        except Exception as e:
            logger.error(f"停止流客户端时出错: {str(e)}")

        # 等待线程终止
        threads_to_join = []

        if self.client_thread and self.client_thread.is_alive():
            threads_to_join.append(("client", self.client_thread))

        if self.health_monitor_thread and self.health_monitor_thread.is_alive():
            threads_to_join.append(("health monitor", self.health_monitor_thread))

        # 使用超时连接所有线程
        for name, thread in threads_to_join:
            logger.debug(f"等待 {name} 线程终止...")
            thread.join(timeout=5)
            if thread.is_alive():
                logger.warning(f"{name} 线程未正常终止")

        # 重置客户端状态
        self.stream_client = None
        self.is_healthy = False

        # 记录最终统计信息
        logger.info(f"钉钉流客户端已停止。统计信息: {self.stats}")

    def get_status(self) -> Dict[str, Any]:
        """获取钉钉流客户端的当前状态"""
        status = {
            "is_connected": self.is_healthy,
            "manager_stats": self.stats,
            "handler_stats": self.handler.get_stats() if self.handler else {},
            "uptime_seconds": self.stats.get("uptime", 0),
            "message_rate": 0
        }

        # 计算消息速率（每分钟消息数）
        if self.handler and self.stats.get("uptime", 0) > 0:
            messages_processed = self.handler.stats.get("messages_processed", 0)
            uptime_minutes = self.stats.get("uptime", 0) / 60
            if uptime_minutes > 0:
                status["message_rate"] = messages_processed / uptime_minutes

        return status

__all__ = ["DingTalkStreamManager"] 