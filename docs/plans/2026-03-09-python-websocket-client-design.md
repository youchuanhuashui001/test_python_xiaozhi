# WebSocket 客户端设计文档 (Python 异步版本)

## 1. 概述
本文档定义了运行在嵌入式 Linux (i.MX6ULL) 上的 WebSocket 客户端架构。该程序主要用于：
- 实时上报传感器数据。
- 接收并处理来自服务器的远程指令（控制 GPIO、配置网络等）。
- 在 PC 上进行功能原型设计，后续作为 C/C++ 实现的逻辑蓝图。

## 2. 系统架构

### 2.1 生产者-消费者模型
程序基于 Python `asyncio` 构建，核心分为三个并发协程：
1.  **Connection Manager (连接管理器)**: 
    - 管理 WebSocket 的连接、认证及心跳。
    - 负责指数退避重连机制。
2.  **Sensor Producer (数据采集器)**:
    - 模拟/读取硬件传感器数据。
    - 将数据封装为 JSON 并放入异步发送队列。
3.  **Command Consumer (指令处理器)**:
    - 监听 WebSocket 下行消息。
    - 将 JSON 指令路由至对应的硬件控制函数。

### 2.2 数据流设计
```text
[传感器] -> [JSON 封装] -> [发送队列] -> [WS 连接管理器] -> (网络) -> [Server]
[传感器] <- [控制函数] <- [路由分发器] <- [WS 连接管理器] <- (网络) <- [Server]
```

## 3. 通信协议定义 (JSON)

### 3.1 上行数据 (Uplink - Sensor Data)
```json
{
  "type": "telemetry",
  "device_id": "imx6ull-001",
  "timestamp": 1709971200,
  "payload": {
    "cpu_temp": 45.2,
    "mem_usage": 12.5,
    "status": "online"
  }
}
```

### 3.2 下行数据 (Downlink - Remote Command)
```json
{
  "type": "command",
  "cmd": "set_wifi",
  "params": {
    "ssid": "Home-WiFi",
    "psk": "password123"
  }
}
```

## 4. 关键特性实现方案

### 4.1 指令路由 (Dispatcher)
使用装饰器或字典映射模式，注册不同指令的处理函数：
```python
DISPATCHER = {
    "set_wifi": handle_wifi_config,
    "set_led": handle_led_control
}
```

### 4.2 鲁棒性与重连
- **检测策略**: WebSocket `pong` 超时、连接异常关闭、网络不可达。
- **重连策略**: 初始等待 2s，每次重连失败翻倍，最大等待 60s。

## 5. 测试与验证
- **Mock Server**: 提供一个简单的 Python WebSocket Server 脚本模拟云端环境。
- **日志记录**: 所有的通信包及连接状态变更均记录至标准输出或日志文件。
