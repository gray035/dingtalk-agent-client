# main.py
"""
钉钉 MCP 服务器入口
"""
import os
import sys
import signal
import asyncio
import multiprocessing
from contextlib import AsyncExitStack
from loguru import logger

from app.config.settings import settings
from app.core.mcp_server import mcp
from app.api.auth import get_auth
from app.api.client.open.openapi_client import DingtalkClient
from app.api.client.stream.stream_client import DingTalkStreamManager
from app.core.message_service import MessageService


def configure_logging():
    """Configure logging with enhanced settings"""
    # Remove default handler
    logger.remove()
    
    # Add colored console handler with better formatting
    logger.add(
        sys.stderr,
        format="<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
        level="INFO"
    )
    
    # Add file handler for persistent logs
    log_dir = "logs"
    os.makedirs(log_dir, exist_ok=True)
    logger.add(
        os.path.join(log_dir, "app_{time:YYYY-MM-DD}.log"),
        rotation="12:00",  # New file at noon
        retention="7 days",  # Keep logs for 7 days
        compression="zip",  # Compress old log files
        level="DEBUG"
    )


def start_mcp_server():
    """Start the MCP server in a separate process"""
    try:
        logger.info("Starting MCP server...")
        mcp.run(transport="stdio")
    except Exception as e:
        logger.error(f"Failed to start MCP server: {str(e)}", exc_info=True)
        sys.exit(1)


class ApplicationContext:
    """Application context to manage resources and lifecycle"""
    
    def __init__(self):
        self.dingtalk_client = None
        self.message_service = None
        self.stream_manager = None
        self.mcp_process = None
        self.exit_stack = AsyncExitStack()
        self.shutdown_event = asyncio.Event()
    
    async def initialize(self):
        """Initialize all application components"""
        logger.info("Initializing application context...")
        
        # Start the MCP server in a separate process
        self.mcp_process = multiprocessing.Process(
            target=start_mcp_server,
            name="MCPServerProcess"
        )
        self.mcp_process.daemon = True
        self.mcp_process.start()
        logger.info(f"MCP server process started with PID: {self.mcp_process.pid}")
        
        # Create the DingTalk client
        try:
            auth = get_auth()
            self.dingtalk_client = DingtalkClient(auth)
            logger.info("DingTalk client created successfully")
        except Exception as e:
            logger.error(f"Failed to create DingTalk client: {str(e)}", exc_info=True)
            await self.shutdown()
            sys.exit(1)
        
        # Create the message service
        self.message_service = MessageService(self.dingtalk_client)
        logger.info("Message service created")
        
        # Start the DingTalk Stream manager
        try:
            self.stream_manager = DingTalkStreamManager(self.message_service)
            self.stream_manager.start()
            logger.info("DingTalk Stream manager started")
        except Exception as e:
            logger.error(f"Failed to start DingTalk Stream manager: {str(e)}", exc_info=True)
            await self.shutdown()
            sys.exit(1)
    
    async def monitor_health(self):
        """Monitor the health of application components"""
        check_interval = 60  # seconds
        
        while not self.shutdown_event.is_set():
            try:
                # Check stream manager health if available
                if self.stream_manager:
                    status = self.stream_manager.get_status()
                    if not status["is_connected"]:
                        logger.warning("DingTalk Stream connection is unhealthy")
                    else:
                        msg_count = status.get("handler_stats", {}).get("messages_processed", 0)
                        msg_rate = status.get("message_rate", 0)
                        logger.info(f"Health check: Stream connected, messages: {msg_count}, rate: {msg_rate:.2f}/min")
                
                # Check MCP server health
                if self.mcp_process and not self.mcp_process.is_alive():
                    logger.error("MCP server process died unexpectedly, restarting...")
                    # Restart MCP server
                    self.mcp_process = multiprocessing.Process(
                        target=start_mcp_server,
                        name="MCPServerProcess"
                    )
                    self.mcp_process.daemon = True
                    self.mcp_process.start()
                    logger.info(f"MCP server process restarted with PID: {self.mcp_process.pid}")
            
            except Exception as e:
                logger.error(f"Error in health monitoring: {str(e)}", exc_info=True)
            
            # Wait for the next check or shutdown
            try:
                await asyncio.wait_for(
                    self.shutdown_event.wait(),
                    timeout=check_interval
                )
                break  # Exit if shutdown event is set
            except asyncio.TimeoutError:
                # Continue health checks
                pass
    
    async def shutdown(self):
        """Gracefully shut down all application components"""
        logger.info("Shutting down application...")
        
        # Signal shutdown to other tasks
        self.shutdown_event.set()
        
        # Stop the DingTalk Stream manager
        if self.stream_manager:
            try:
                logger.info("Stopping DingTalk Stream manager...")
                self.stream_manager.stop()
                logger.info("DingTalk Stream manager stopped")
            except Exception as e:
                logger.error(f"Error stopping DingTalk Stream manager: {str(e)}")
        
        # Close the message service
        if self.message_service:
            try:
                logger.info("Closing message service...")
                self.message_service.close()
                logger.info("Message service closed")
            except Exception as e:
                logger.error(f"Error closing message service: {str(e)}")
        
        # Terminate the MCP server process
        if self.mcp_process and self.mcp_process.is_alive():
            try:
                logger.info("Shutting down MCP server process...")
                self.mcp_process.terminate()
                self.mcp_process.join(timeout=5)
                if self.mcp_process.is_alive():
                    logger.warning("MCP server did not terminate gracefully, forcing...")
                    self.mcp_process.kill()
                logger.info("MCP server process shut down")
            except Exception as e:
                logger.error(f"Error shutting down MCP server process: {str(e)}")
        
        # Exit the application
        logger.info("Shutdown complete")


async def main():
    """Main function to run the DingTalk message processor"""
    # Configure logging
    configure_logging()
    
    # Print application banner
    logger.info("=" * 60)
    logger.info("DingTalk Message Processor - Starting")
    logger.info("=" * 60)
    
    # Create and initialize application context
    app_context = ApplicationContext()
    
    # Set up signal handlers
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(
            sig,
            lambda: asyncio.create_task(app_context.shutdown())
        )
    
    try:
        # Initialize all components
        await app_context.initialize()
        
        # Start health monitoring
        monitor_task = asyncio.create_task(app_context.monitor_health())
        
        # Keep the application running until shutdown
        logger.info("Application started and ready to process messages")
        await app_context.shutdown_event.wait()
        
        # Wait for monitor task to complete
        await monitor_task
    
    except KeyboardInterrupt:
        logger.info("Application interrupted by user")
    except Exception as e:
        logger.error(f"Unhandled exception in main: {str(e)}", exc_info=True)
    finally:
        # Ensure proper shutdown
        await app_context.shutdown()


if __name__ == "__main__":
    asyncio.run(main())