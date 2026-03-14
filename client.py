import asyncio
import websockets
import json
import time
import logging
import os
import struct

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger("WS-Client")

class WebSocketClient:
    def __init__(self, hostname, port, path, device_id, client_id):
        self.uri = f"wss://{hostname}:{port}{path}"
        self.device_id = device_id
        self.client_id = client_id
        self.send_queue = None
        self.is_running = True
        self.session_id = None
        self.is_listening = False
        self.is_playing_tts = False
        self.opus_file_path = "output.opus"

    async def connect(self):
        if self.send_queue is None:
            self.send_queue = asyncio.Queue()
        
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
                async with websockets.connect(self.uri, extra_headers=headers) as websocket:
                    logger.info("网络连接成功，开始握手...")
                    
                    if await self.perform_handshake(websocket):
                        logger.info(f"握手成功！会话 ID: {self.session_id}")
                        
                        # 运行处理协程
                        await asyncio.gather(
                            self.send_handler(websocket),
                            self.recv_handler(websocket),
                            self.interaction_logic() 
                        )
                    else:
                        logger.error("握手验证失败，准备重连...")
                        
            except Exception as e:
                logger.error(f"连接或运行异常: {e}。将在 {retry_delay}秒后重试...")
                await asyncio.sleep(retry_delay)
                retry_delay = min(retry_delay * 2, 60)

    async def perform_handshake(self, websocket):
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
            logger.info(f"发送握手: {json.dumps(hello_msg)}")
            await websocket.send(json.dumps(hello_msg))
            response_str = await asyncio.wait_for(websocket.recv(), timeout=10.0)
            response = json.loads(response_str)
            if response.get("type") == "hello":
                self.session_id = response.get("session_id")
                return True
            return False
        except Exception as e:
            logger.error(f"握手失败: {e}")
            return False

    async def interaction_logic(self):
        """控制交互流程，减少空闲时间"""
        await asyncio.sleep(0.1) # 短暂等待
        await self.start_listening()
        await self.audio_producer()

    async def start_listening(self):
        if not self.session_id:
            return
        
        listen_msg = {
            "session_id": str(self.session_id),
            "type": "listen",
            "state": "start",
            "mode": "auto"
        }
        logger.info(f"发送指令: {json.dumps(listen_msg)}")
        await self.send_queue.put(json.dumps(listen_msg))
        self.is_listening = True

    async def send_handler(self, websocket):
        try:
            while True:
                data = await self.send_queue.get()
                await websocket.send(data)
                self.send_queue.task_done()
        except Exception as e:
            logger.error(f"发送异常: {e}")

    async def recv_handler(self, websocket):
        try:
            async for message in websocket:
                if isinstance(message, str):
                    data = json.loads(message)
                    logger.info(f"收到 JSON: {data}")
                    self.dispatch_command(data)
                else:
                    # 处理音频
                    pass
        except Exception as e:
            logger.error(f"接收异常: {e}")

    async def audio_producer(self):
        """解析 Ogg 文件并发送真正的 Opus Packets"""
        if not os.path.exists(self.opus_file_path):
            logger.error(f"未找到音频文件: {self.opus_file_path}")
            return

        logger.info(f"开始解析并发送音频: {self.opus_file_path}")
        
        try:
            with open(self.opus_file_path, "rb") as f:
                # 这是一个极其简化的 Ogg 解析逻辑，用于提取数据包
                page_count = 0
                while self.is_listening and self.is_running:
                    header = f.read(27)
                    if not header: break
                    if header[:4] != b"OggS": 
                        logger.error("非法 Ogg 格式")
                        break
                    
                    segments_count = header[26]
                    segment_table = f.read(segments_count)
                    
                    # 每一个包的数据长度可能跨越多个 segment
                    packet_data = b""
                    for size in segment_table:
                        packet_data += f.read(size)
                        if size < 255:
                            # 这是一个包的结尾
                            page_count += 1
                            # 跳过前两页（OpusID 和 OpusTags）
                            if page_count > 2:
                                if packet_data:
                                    await self.send_queue.put(packet_data)
                                    # 按照 60ms 间隔发送
                                    await asyncio.sleep(0.06)
                            packet_data = b""
                            
                logger.info("音频文件发送结束")
                self.is_listening = False
                await self.send_queue.put(json.dumps({
                    "session_id": str(self.session_id),
                    "type": "listen",
                    "state": "stop"
                }))
                
        except Exception as e:
            logger.error(f"音频发送过程异常: {e}")

    def dispatch_command(self, data):
        msg_type = data.get("type")
        if msg_type == "stt":
            logger.info(f"[ASR]: {data.get('text')}")
        elif msg_type == "tts":
            state = data.get("state")
            if state == "start":
                self.is_playing_tts = True
                self.is_listening = False
                logger.info("--- 服务端开始推送 TTS ---")
            elif state == "stop":
                self.is_playing_tts = False
                logger.info("--- TTS 结束 ---")
        elif msg_type == "error":
            logger.error(f"服务端报错: {data.get('message')}")

    async def start(self):
        await self.connect()

if __name__ == "__main__":
    client = WebSocketClient(
        hostname="api.tenclass.net",
        port=443,
        path="/xiaozhi/v1/",
        device_id="00:11:22:33:44:55",
        client_id="uuid-1234-5678-90ab"
    )
    asyncio.run(client.start())
