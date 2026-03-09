import asyncio
import websockets
import json
import time
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("WS-Client")

class WebSocketClient:
    def __init__(self, uri):
        self.uri = uri
        self.send_queue = None
        self.is_running = True

    async def connect(self):
        if self.send_queue is None:
            self.send_queue = asyncio.Queue()
        retry_delay = 2
        while self.is_running:
            try:
                logger.info(f"Connecting to {self.uri}...")
                async with websockets.connect(self.uri) as websocket:
                    logger.info("Connected successfully")
                    retry_delay = 2 # 重置重连延迟
                    
                    # 运行发送、接收和传感器模拟协程
                    await asyncio.gather(
                        self.send_handler(websocket),
                        self.recv_handler(websocket),
                        self.sensor_producer()
                    )
            except Exception as e:
                logger.error(f"Connection failed: {e}. Retrying in {retry_delay}s...")
                await asyncio.sleep(retry_delay)
                retry_delay = min(retry_delay * 2, 60) # 指数退避

    async def send_handler(self, websocket):
        while True:
            msg = await self.send_queue.get()
            await websocket.send(json.dumps(msg))
            self.send_queue.task_done()

    async def recv_handler(self, websocket):
        async for message in websocket:
            data = json.loads(message)
            logger.info(f"Received command: {data}")
            self.dispatch_command(data)

    async def sensor_producer(self):
        """模拟读取传感器并放入队列"""
        while self.is_running:
            data = {
                "type": "telemetry",
                "device_id": "imx6ull-001",
                "timestamp": int(time.time()),
                "payload": {"cpu_temp": 45.0, "mem_usage": 10.2}
            }
            logger.info(f"Sending telemetry: {data['payload']}")
            await self.send_queue.put(data)
            await asyncio.sleep(5) # 每5秒采集一次

    def dispatch_command(self, data):
        """指令分发"""
        cmd = data.get("cmd")
        params = data.get("params")
        if cmd == "set_led":
            logger.info(f"LED Control: Setting LED to {params.get('status')}")
        elif cmd == "set_wifi":
            logger.info(f"WiFi Config: SSID={params.get('ssid')}")
        else:
            logger.warning(f"Unknown command: {cmd}")

    async def start(self):
        await self.connect()

if __name__ == "__main__":
    client = WebSocketClient("ws://localhost:8765")
    try:
        asyncio.run(client.start())
    except KeyboardInterrupt:
        pass
