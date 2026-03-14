import asyncio
import websockets
import json
import time
import logging
import ssl

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("WS-Client")

class WebSocketClient:
    def __init__(self, hostname, port, path, device_id, client_id):
        self.uri = f"wss://{hostname}:{port}{path}"
        self.device_id = device_id
        self.client_id = client_id
        self.send_queue = None
        self.is_running = True
        self.session_id = None
        self.audio_params = None

    async def connect(self):
        if self.send_queue is None:
            self.send_queue = asyncio.Queue()

        # 构造请求头
        headers = {
            "Authorization": "Bearer test-token",
            "Protocol-Version": "1",
            "Device-Id": self.device_id,
            "Client-Id": self.client_id
        }

        retry_delay = 2
        while self.is_running:
            try:
                logger.info(f"正在连接到 {self.uri} ...")
                # api.tenclass.net 使用 443 端口，需要 SSL
                async with websockets.connect(self.uri, extra_headers=headers) as websocket:
                    logger.info("网络连接成功，开始握手...")

                    # 1. 发起握手
                    if await self.perform_handshake(websocket):
                        logger.info(f"握手成功！会话 ID: {self.session_id}")
                        retry_delay = 2 # 重置重连延迟

                        # 2. 运行发送、接收和遥测模拟协程
                        await asyncio.gather(
                            self.send_handler(websocket),
                            self.recv_handler(websocket),
                            self.sensor_producer()
                        )
                    else:
                        logger.error("握手验证失败，准备重连...")

            except Exception as e:
                logger.error(f"连接或运行异常: {e}。将在 {retry_delay}秒后重试...")
                await asyncio.sleep(retry_delay)
                retry_delay = min(retry_delay * 2, 60) # 指数退避

    async def perform_handshake(self, websocket):
        """执行握手协议"""
        hello_msg = {
            "type": "hello",
            "version": 1,
            "transport": "websocket",
            "audio_params": {
                "format": "opus",
                "sample_rate": 16000,
                "channels": 1,
                "frame_duration": 60
            }
        }

        try:
            # 发送 hello
            logger.info("发送握手消息 (hello)...")
            await websocket.send(json.dumps(hello_msg))

            # 等待回复，超时时间 10 秒
            logger.info("等待服务端响应 (超时 10s)...")
            response_str = await asyncio.wait_for(websocket.recv(), timeout=10.0)
            response = json.loads(response_str)

            # 验证响应
            if response.get("type") == "hello" and response.get("transport") == "websocket":
                self.session_id = response.get("session_id")
                self.audio_params = response.get("audio_params")
                logger.info(f"服务端已就绪，音频参数: {self.audio_params}")
                return True
            else:
                logger.warning(f"握手响应不匹配: {response}")
                return False

        except asyncio.TimeoutError:
            logger.error("握手超时：10秒内未收到服务端回复")
            return False
        except Exception as e:
            logger.error(f"握手过程出错: {e}")
            return False

    async def send_handler(self, websocket):
        """发送队列中的消息"""
        try:
            while True:
                msg = await self.send_queue.get()
                await websocket.send(json.dumps(msg))
                self.send_queue.task_done()
        except Exception as e:
            logger.error(f"发送处理器异常: {e}")

    async def recv_handler(self, websocket):
        """接收服务端指令"""
        try:
            async for message in websocket:
                data = json.loads(message)
                logger.info(f"收到指令: {data}")
                self.dispatch_command(data)
        except Exception as e:
            logger.error(f"接收处理器异常: {e}")

    async def sensor_producer(self):
        """模拟传感器数据发送"""
        while self.is_running:
            # 仅在握手成功后发送遥测数据
            if self.session_id:
                data = {
                    "type": "telemetry",
                    "session_id": self.session_id,
                    "timestamp": int(time.time()),
                    "payload": {"status": "running", "uptime": int(time.perf_counter())}
                }
                logger.info(f"发送遥测数据，Uptime: {data['payload']['uptime']}s")
                await self.send_queue.put(data)
            await asyncio.sleep(10) # 每10秒发送一次

    def dispatch_command(self, data):
        """指令分发逻辑"""
        cmd = data.get("cmd")
        if cmd == "ping":
            asyncio.create_task(self.send_queue.put({"type": "pong", "timestamp": int(time.time())}))
        else:
            logger.debug(f"收到未知或无需处理的指令: {cmd}")

    async def start(self):
        await self.connect()

if __name__ == "__main__":
    # 配置设备参数
    MAC_ADDR = "00:11:22:33:44:55"
    CLIENT_UUID = "uuid-1234-5678-90ab"

    client = WebSocketClient(
        hostname="api.tenclass.net",
        port=443,
        path="/xiaozhi/v1/",
        device_id=MAC_ADDR,
        client_id=CLIENT_UUID
    )

    try:
        asyncio.run(client.start())
    except KeyboardInterrupt:
        logger.info("客户端已停止")
