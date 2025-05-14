"""
DingTalk Stream Client Manager

This module provides a robust implementation of DingTalk's streaming API client with:
- Automatic reconnection handling
- Health monitoring
- Connection statistics tracking
- Graceful shutdown
"""

import threading
import time
from typing import Dict, Any, Optional
from dataclasses import dataclass

from dingtalk_stream import DingTalkStreamClient, Credential
from loguru import logger

from app.core.message_service import MessageService
from app.config.settings import settings
from .callback_handler import DingTalkChatbotHandler


@dataclass
class ConnectionStats:
    """Connection statistics data class for monitoring client health"""
    connection_attempts: int = 0
    successful_connections: int = 0
    reconnections: int = 0
    last_connection_time: float = 0
    uptime: float = 0
    last_message_time: float = 0
    messages_processed: int = 0


class DingTalkStreamManager:
    """Enhanced DingTalk Stream Client Manager with health monitoring capabilities"""

    def __init__(self, message_service: Optional[MessageService] = None):
        """
        Initialize the stream manager with improved configuration
        
        Args:
            message_service: Optional message service for processing messages
        """
        self.stream_client = None
        self.message_service = message_service
        self.stop_event = threading.Event()
        self.reconnect_interval = 5  # Initial reconnect interval (seconds)
        self.max_reconnect_interval = 60  # Maximum reconnect interval (seconds)
        self.client_thread = None
        self.health_monitor_thread = None
        self.handler = None

        # Health monitoring settings
        self.health_check_interval = 60  # seconds
        self.connection_timeout = 300  # 5 minutes without messages considered disconnected
        self.is_healthy = False

        # Connection statistics
        self.stats = ConnectionStats()

    def start(self, message_service: Optional[MessageService] = None) -> None:
        """
        启动钉钉流客户端，包含重连逻辑和健康监控

        Args:
            message_service: 用于处理消息的消息服务
        """
        if message_service:
            self.message_service = message_service

        if not self.message_service:
            raise ValueError("需要提供消息服务")

        try:
            self._initialize_client()
            self._start_monitoring_threads()
            self._update_connection_stats()
        except Exception as e:
            logger.error(f"启动钉钉流客户端失败: {str(e)}", exc_info=True)
            raise

    def _initialize_client(self) -> None:
        """初始化钉钉流客户端"""
        self.handler = DingTalkChatbotHandler(self.message_service)
        stream_topic = settings.DINGTALK_STREAM_TOPIC
        
        credential = Credential(
            settings.DINGTALK_APP_KEY,
            settings.DINGTALK_APP_SECRET
        )

        self.stream_client = DingTalkStreamClient(credential)
        self.stream_client.register_callback_handler(stream_topic, self.handler)
        

    def _start_monitoring_threads(self) -> None:
        """启动监控线程"""
        self.client_thread = threading.Thread(
            target=self._start_client_with_reconnection,
            daemon=True,
            name="DingTalkStreamThread"
        )
        self.client_thread.start()

        self.health_monitor_thread = threading.Thread(
            target=self._monitor_connection_health,
            daemon=True,
            name="DingTalkHealthMonitor"
        )
        self.health_monitor_thread.start()

    def _update_connection_stats(self) -> None:
        """更新连接统计信息"""
        self.stats.last_connection_time = time.time()
        self.is_healthy = True

    def _start_client_with_reconnection(self) -> None:
        """启动客户端，包含失败时的自动重连"""
        reconnect_interval = self.reconnect_interval

        while not self.stop_event.is_set():
            try:
                self.stats.connection_attempts += 1
                logger.info(f"启动钉钉流客户端连接 (尝试 #{self.stats.connection_attempts})...")

                self.stream_client.start_forever()

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

            if self.stop_event.is_set():
                break

            self.stats.reconnections += 1
            logger.info(f"{reconnect_interval} 秒后重连 (尝试 #{self.stats.reconnections})...")
            
            if self.stop_event.wait(reconnect_interval):
                break

            reconnect_interval = min(reconnect_interval * 2, self.max_reconnect_interval)

    def _monitor_connection_health(self) -> None:
        """监控钉钉流连接的健康状态"""
        while not self.stop_event.is_set():
            try:
                if self.handler:
                    last_message_time = self.handler.stats.get("last_message_time", 0)
                    current_time = time.time()

                    if last_message_time > 0:
                        time_since_last_message = current_time - last_message_time

                        if time_since_last_message > self.connection_timeout:
                            logger.warning(f"{time_since_last_message:.1f} 秒未收到消息，连接可能已断开")
                            self.is_healthy = False
                            self._force_reconnect()
                        else:
                            self.is_healthy = True

                    if self.is_healthy:
                        self.stats.uptime = current_time - self.stats.last_connection_time

            except Exception as e:
                logger.error(f"健康监控出错: {str(e)}")

            if self.stop_event.wait(self.health_check_interval):
                break

    def _force_reconnect(self) -> None:
        """强制重连客户端"""
        if self.stream_client and not self.stop_event.is_set():
            logger.info("由于不活跃，强制重连")
            try:
                self.stream_client.stop()
            except Exception as e:
                logger.error(f"停止无响应客户端时出错: {str(e)}")

    def stop(self) -> None:
        """优雅地停止钉钉流客户端"""
        if not self.stream_client:
            logger.warning("尝试停止不存在的钉钉流客户端")
            return

        logger.info("正在停止钉钉流客户端...")
        self.stop_event.set()

        try:
            self.stream_client.close()
            logger.info("已发送钉钉流客户端关闭命令")
        except Exception as e:
            logger.error(f"关闭钉钉流客户端时出错: {str(e)}")
        finally:
            self._join_threads()
            self._reset_client_state()

    def _join_threads(self) -> None:
        """等待所有线程结束"""
        if self.client_thread and self.client_thread.is_alive():
            self.client_thread.join(timeout=5)
        if self.health_monitor_thread and self.health_monitor_thread.is_alive():
            self.health_monitor_thread.join(timeout=5)

    def _reset_client_state(self) -> None:
        """重置客户端状态"""
        self.stream_client = None
        self.handler = None
        self.is_healthy = False

    def get_status(self) -> Dict[str, Any]:
        """获取客户端状态"""
        return {
            "is_healthy": self.is_healthy,
            "uptime": self.stats.uptime,
            "connection_attempts": self.stats.connection_attempts,
            "reconnections": self.stats.reconnections,
            "messages_processed": self.stats.messages_processed,
            "last_message_time": self.stats.last_message_time
        }

    def _calculate_message_rate(self) -> float:
        """计算消息处理速率"""
        if self.stats.uptime > 0:
            return self.stats.messages_processed / self.stats.uptime
        return 0.0


__all__ = ["DingTalkStreamManager"] 