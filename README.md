# Python WebSocket 客户端项目使用指南

本项目实现了一个基于 `asyncio` 和 `websockets` 的异步客户端，具备传感器数据模拟上报、远程指令接收处理以及自动重连（指数退避算法）功能。

## 1. 环境准备

项目使用 Python 虚拟环境隔离依赖。

### 1.1 安装依赖
如果您尚未配置环境，请运行以下命令：
```bash
# 创建虚拟环境
python3 -m venv venv

# 激活虚拟环境
source venv/bin/activate

# 安装依赖
pip install -r requirements.txt
```

---

## 2. 快速启动

建议开启两个终端窗口，分别运行服务器和客户端。

### 步骤 A：启动模拟服务器 (Mock Server)
在测试阶段，使用内置的模拟服务器来验证通信。
```bash
source venv/bin/activate
python3 mock_server.py
```
*   **功能**：监听 `ws://localhost:8765`。
*   **行为**：每当收到 `type: telemetry` 数据时，会自动下发一个 `set_led` 指令给客户端。

### 步骤 B：启动客户端 (Client)
```bash
source venv/bin/activate
python3 client.py
```
*   **功能**：连接服务器，开始上报数据。
*   **行为**：
    *   每 5 秒发送一次模拟传感器数据（CPU 温度、内存占用）。
    *   实时监听服务器指令并分发处理（如 LED 控制）。

---

## 3. 核心功能说明

### 3.1 自动重连机制
客户端具备健壮的连接管理逻辑：
*   **连接丢失**：当服务器关闭或网络中断时，客户端会捕获异常并尝试重连。
*   **指数退避**：重连间隔从 2s 开始，每次失败翻倍（4s, 8s...），最高间隔为 60s，以保护服务器免受冲击。
*   **自动恢复**：一旦服务器恢复在线，客户端将自动重连并继续工作。

### 3.2 传感器数据生产 (`sensor_producer`)
在 `client.py` 的 `sensor_producer` 协程中：
*   模拟产生包含 `device_id` 和 `timestamp` 的 JSON 消息。
*   数据通过 `asyncio.Queue` 异步发送，确保发送逻辑不会阻塞数据采集。

### 3.3 指令分发器 (`dispatch_command`)
客户端能够解析并执行服务器下发的 JSON 指令：
*   **`set_led`**: 模拟控制 LED 状态。
*   **`set_wifi`**: 模拟配置 WiFi 信息。
*   **扩展性**: 只需在 `dispatch_command` 方法中添加 `elif` 分支即可支持更多业务指令。

---

## 4. 常见问题 (FAQ)

**Q: 如何更改服务器地址？**
A: 在 `client.py` 的末尾修改 `WebSocketClient` 实例的初始化参数：
```python
client = WebSocketClient("ws://your-server-ip:port")
```

**Q: 客户端可以发送自定义数据吗？**
A: 可以。通过调用 `client.send_queue.put(your_data_dict)`，您可以从客户端的任何地方将消息推送到发送队列。

**Q: 如何停止程序？**
A: 在终端按 `Ctrl + C` 即可安全停止。

---

## 5. 项目结构说明
*   `client.py`: 核心客户端实现。
*   `mock_server.py`: 本地开发验证用的服务器脚本。
*   `requirements.txt`: 库依赖清单。
*   `tasks.md`: 开发进度清单。
*   `docs/plans/`: 包含详细的设计与实现计划文档。
