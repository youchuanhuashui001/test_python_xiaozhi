# Python WebSocket 客户端实现计划

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 实现一个基于 `asyncio` 的 Python WebSocket 客户端，能够上报传感器数据并处理远程指令。

**Architecture:** 采用生产者-消费者模型，使用三个核心协程：连接管理器（含重连逻辑）、传感器数据发送器、远程指令接收器。

**Tech Stack:** Python 3, `websockets` 库, `asyncio`。

---

### Task 1: 环境准备与依赖安装

**Files:**
- Create: `requirements.txt`

**Step 1: 创建 requirements.txt**

```text
websockets==12.0
```

**Step 2: 安装依赖**

Run: `pip install -r requirements.txt`
Expected: 成功安装 websockets 库。

**Step 3: Commit**

```bash
git add requirements.txt
git commit -m "chore: add websocket dependencies"
```

---

### Task 2: 实现模拟服务器 (Mock Server)

用于在本地 PC 上测试客户端的连接和通信。

**Files:**
- Create: `mock_server.py`

**Step 1: 编写模拟服务器代码**

```python
import asyncio
import websockets
import json

async def handler(websocket):
    print(f"Client connected: {websocket.remote_address}")
    try:
        async for message in websocket:
            data = json.loads(message)
            print(f"Received from client: {data}")
            
            # 收到 telemetry 后，模拟发送一个控制指令
            if data.get("type") == "telemetry":
                response = {
                    "type": "command",
                    "cmd": "set_led",
                    "params": {"status": "on"}
                }
                await websocket.send(json.dumps(response))
                print(f"Sent command to client: {response}")
    except websockets.ConnectionClosed:
        print("Client disconnected")

async def main():
    async with websockets.serve(handler, "localhost", 8765):
        print("Mock Server running on ws://localhost:8765")
        await asyncio.Future()  # run forever

if __name__ == "__main__":
    asyncio.run(main())
```

**Step 2: 验证服务器运行**

Run: `python3 mock_server.py` (后台运行或另开终端)
Expected: 输出 "Mock Server running on ws://localhost:8765"

**Step 3: Commit**

```bash
git add mock_server.py
git commit -m "feat: add mock websocket server for testing"
```

---

### Task 3: 实现客户端核心 (Connection Manager)

实现基础的连接和重连逻辑。

**Files:**
- Create: `client.py`

**Step 1: 编写带重连逻辑的客户端框架**

```python
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
        self.send_queue = asyncio.Queue()
        self.is_running = True

    async def connect(self):
        retry_delay = 2
        while self.is_running:
            try:
                logger.info(f"Connecting to {self.uri}...")
                async with websockets.connect(self.uri) as websocket:
                    logger.info("Connected successfully")
                    retry_delay = 2 # 重置重连延迟
                    
                    # 运行发送和接收协程
                    await asyncio.gather(
                        self.send_handler(websocket),
                        self.recv_handler(websocket)
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
            # 这里后续会调用指令分发器

    async def start(self):
        await self.connect()

if __name__ == "__main__":
    client = WebSocketClient("ws://localhost:8765")
    try:
        asyncio.run(client.start())
    except KeyboardInterrupt:
        pass
```

**Step 2: 运行测试**

1. 启动 `mock_server.py`
2. 运行 `python3 client.py`
Expected: 客户端显示 "Connected successfully"。关闭服务器后，客户端显示 "Connection failed" 并开始重连。

**Step 3: Commit**

```bash
git add client.py
git commit -m "feat: add websocket client with reconnection logic"
```

---

### Task 4: 实现传感器模拟与指令分发

完善业务逻辑。

**Files:**
- Modify: `client.py`

**Step 1: 添加数据产生和指令处理逻辑**

在 `WebSocketClient` 中添加 `sensor_producer` 和 `command_dispatcher`。

```python
# 修改 client.py 中的类方法
    async def sensor_producer(self):
        """模拟读取传感器并放入队列"""
        while self.is_running:
            data = {
                "type": "telemetry",
                "device_id": "imx6ull-001",
                "timestamp": int(time.time()),
                "payload": {"cpu_temp": 45.0, "mem_usage": 10.2}
            }
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

    # 修改 connect 中的 gather
    # await asyncio.gather(
    #     self.send_handler(websocket),
    #     self.recv_handler(websocket),
    #     self.sensor_producer()
    # )
```

**Step 2: 验证全流程**

1. 运行 `mock_server.py`
2. 运行 `client.py`
Expected: 客户端每5秒发送一次数据，并收到服务器回复的 `set_led` 指令并打印日志。

**Step 3: Commit**

```bash
git add client.py
git commit -m "feat: implement sensor producer and command dispatcher"
```
