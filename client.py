import asyncio
import websockets
import json
import time
import logging
import os
import struct
import random

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger("WS-Client")

# Ogg 标准 CRC32 表 (非反转多项式 0x04C11DB7)
_OGG_CRC_TABLE = [0] * 256
for i in range(256):
    r = i << 24
    for _ in range(8):
        if r & 0x80000000:
            r = (r << 1) ^ 0x04c11db7
        else:
            r <<= 1
    _OGG_CRC_TABLE[i] = r & 0xffffffff

def ogg_crc32(data):
    """计算 Ogg 页面所需的 CRC32 校验码"""
    crc = 0
    for b in data:
        crc = ((crc << 8) ^ _OGG_CRC_TABLE[((crc >> 24) ^ b) & 0xff]) & 0xffffffff
    return crc

class WebSocketClient:
    def __init__(self, hostname, port, path, device_id, client_id):
        self.uri = f"wss://{hostname}:{port}{path}"
        self.device_id = device_id
        self.client_id = client_id
        self.send_queue = None
        self.is_running = True
        self.is_listening = False
        self.is_playing_tts = False
        self.opus_file_path = "output.opus"
        
        # 文件保存路径
        self.tts_raw_path = "received_tts.opus"
        self.tts_ogg_path = "received_tts_playable.ogg"
        self.raw_file = None
        self.ogg_file = None
        
        # Ogg 封装状态
        self.ogg_serial = random.randint(0, 0xFFFFFFFF)
        self.ogg_page_num = 0
        self.ogg_granule_pos = 0

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
                        
            except websockets.exceptions.ConnectionClosed:
                logger.warning("服务器主动断开了连接")
                break # 根据需求，可以是 break 或继续 retry
            except Exception as e:
                if not self.is_running: break
                logger.error(f"连接异常: {e}。将在 {retry_delay}秒后重试...")
                self._close_files()
                await asyncio.sleep(retry_delay)
                retry_delay = min(retry_delay * 2, 60)
        
        self._close_files()
        logger.info("WebSocket 客户端已完全停止。")

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
        """控制交互流程"""
        await asyncio.sleep(0.1)
        await self.start_listening()
        await self.audio_producer()

    async def start_listening(self):
        if not self.session_id: return
        listen_msg = {
            "session_id": str(self.session_id),
            "type": "listen",
            "state": "start",
            "mode": "auto"
        }
        logger.info(f"发送指令: {json.dumps(listen_msg)}")
        await self.send_queue.put(json.dumps(listen_msg))
        self.is_listening = True

    def close_audio_channel(self):
        """主动断开连接，回到空闲状态"""
        logger.info("正在主动关闭音频通道并断开连接...")
        self.is_running = False
        self.is_listening = False
        # 如果有正在进行的发送任务，可以在这里清理

    async def send_handler(self, websocket):
        try:
            while self.is_running:
                data = await self.send_queue.get()
                await websocket.send(data)
                self.send_queue.task_done()
        except Exception as e:
            if self.is_running:
                logger.error(f"发送异常: {e}")

    async def recv_handler(self, websocket):
        try:
            async for message in websocket:
                if not self.is_running: break
                if isinstance(message, str):
                    data = json.loads(message)
                    logger.info(f"收到 JSON: {data}")
                    self.dispatch_command(data)
                else:
                    if self.is_playing_tts:
                        if self.raw_file: self.raw_file.write(message)
                        if self.ogg_file:
                            self.ogg_granule_pos += 2880 # 60ms @ 48kHz
                            page = self._create_ogg_page([message])
                            self.ogg_file.write(page)
        except Exception as e:
            if self.is_running:
                logger.error(f"接收异常: {e}")

    def _create_ogg_page(self, packets, header_type=0):
        segment_table = b""
        payload = b""
        for p in packets:
            l = len(p)
            while l >= 255:
                segment_table += b"\xff"
                l -= 255
            segment_table += bytes([l])
            payload += p
        
        # 4sBBQIIIB: Magic, Ver(0), Type, Granule, Serial, Seq, CRC(0), Segments
        # Header 长度固定 27 字节
        header = bytearray(struct.pack("<4sBBQIIIB", 
            b"OggS", 0, header_type, self.ogg_granule_pos,
            self.ogg_serial, self.ogg_page_num, 0, len(segment_table)
        ))
        self.ogg_page_num += 1
        page = header + segment_table + payload
        
        # 使用 Ogg 标准 CRC32 填充
        crc = ogg_crc32(page)
        struct.pack_into("<I", page, 22, crc)
        return page

    def _init_files(self, sample_rate):
        try:
            self.raw_file = open(self.tts_raw_path, "wb")
            self.ogg_file = open(self.tts_ogg_path, "wb")
            self.ogg_page_num = 0
            self.ogg_granule_pos = 0
            
            # OpusHead (19字节)
            # Format: 8s(Magic), B(Ver), B(Chan), H(PreSkip), I(Rate), h(Gain), B(Map)
            opus_head = struct.pack("<8sBBHIhB", 
                b"OpusHead", 1, 1, 0, sample_rate, 0, 0
            )
            self.ogg_file.write(self._create_ogg_page([opus_head], header_type=0x02))
            
            # OpusTags
            vendor = b"Gemini-Client"
            opus_tags = b"OpusTags" + struct.pack("<I", len(vendor)) + vendor + struct.pack("<I", 0)
            self.ogg_file.write(self._create_ogg_page([opus_tags]))
        except Exception as e:
            logger.error(f"初始化文件失败: {e}")

    def _close_files(self):
        if self.raw_file:
            self.raw_file.close()
            self.raw_file = None
        if self.ogg_file:
            self.ogg_file.close()
            self.ogg_file = None
            logger.info(f"TTS 已保存为: {self.tts_raw_path} 和 {self.tts_ogg_path}")

    async def audio_producer(self):
        if not os.path.exists(self.opus_file_path): return
        try:
            with open(self.opus_file_path, "rb") as f:
                page_count = 0
                while self.is_listening and self.is_running:
                    header = f.read(27)
                    if not header: break
                    segments_count = header[26]
                    segment_table = f.read(segments_count)
                    packet_data = b""
                    for size in segment_table:
                        packet_data += f.read(size)
                        if size < 255:
                            page_count += 1
                            if page_count > 2 and packet_data:
                                await self.send_queue.put(packet_data)
                                await asyncio.sleep(0.06)
                            packet_data = b""
                self.is_listening = False
                if self.is_running:
                    await self.send_queue.put(json.dumps({"session_id": str(self.session_id), "type": "listen", "state": "stop"}))
        except Exception as e:
            if self.is_running:
                logger.error(f"音频发送异常: {e}")

    def dispatch_command(self, data):
        msg_type = data.get("type")
        if msg_type == "tts":
            state = data.get("state")
            if state == "start":
                self.is_playing_tts = True
                self.is_listening = False
                sr = data.get("sample_rate", 24000)
                logger.info(f"--- 开始保存 TTS ({sr}Hz) ---")
                self._init_files(sr)
            elif state == "stop":
                self.is_playing_tts = False
                self._close_files()
                # 交互完成，根据文档要求，设备可以调用 CloseAudioChannel 断开连接
                # 这里为了演示，执行断开逻辑
                # self.close_audio_channel() 
        elif msg_type == "stt":
            logger.info(f"[ASR]: {data.get('text')}")
        elif msg_type == "llm":
            logger.info(f"[LLM]: {data.get('text')} ({data.get('emotion')})")

    async def start(self):
        await self.connect()

if __name__ == "__main__":
    client = WebSocketClient(
        hostname="api.tenclass.net", port=443, path="/xiaozhi/v1/",
        device_id="00:11:22:33:44:55", client_id="uuid-1234-5678-90ab"
    )
    try:
        asyncio.run(client.start())
    except KeyboardInterrupt:
        client.close_audio_channel()
        logger.info("客户端正在关闭...")
