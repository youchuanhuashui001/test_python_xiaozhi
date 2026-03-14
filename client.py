import asyncio
import websockets
import json
import time
import logging
import os
import struct
import zlib
import random

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
        
        # 文件路径
        self.tts_raw_path = "received_tts.opus"
        self.tts_ogg_path = "received_tts_playable.ogg"
        self.raw_file = None
        self.ogg_file = None
        
        # Ogg 状态
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
                        await asyncio.gather(
                            self.send_handler(websocket),
                            self.recv_handler(websocket),
                            self.interaction_logic() 
                        )
                    else:
                        logger.error("握手验证失败，准备重连...")
                        
            except Exception as e:
                logger.error(f"连接或运行异常: {e}。将在 {retry_delay}秒后重试...")
                self._close_files()
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
                    if self.is_playing_tts:
                        if self.raw_file:
                            self.raw_file.write(message)
                        if self.ogg_file:
                            # 24000Hz 下，每帧通常是 20ms, 40ms 或 60ms
                            # 如果服务端返回 60ms，则 granule 增加 24000 * 0.06 = 1440
                            # 但 Ogg Opus 规范要求 granule 总是基于 48000Hz 计数
                            self.ogg_granule_pos += 2880 # 60ms at 48k
                            page = self._create_ogg_page([message])
                            self.ogg_file.write(page)
        except Exception as e:
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
        header = bytearray(struct.pack("<4sBBQIIIB", 
            b"OggS", 0, header_type, self.ogg_granule_pos,
            self.ogg_serial, self.ogg_page_num, 0, len(segment_table)
        ))
        self.ogg_page_num += 1
        page = header + segment_table + payload
        crc = zlib.crc32(page) & 0xffffffff
        struct.pack_into("<I", page, 22, crc)
        return page

    def _init_files(self, sample_rate):
        try:
            self.raw_file = open(self.tts_raw_path, "wb")
            self.ogg_file = open(self.tts_ogg_path, "wb")
            self.ogg_page_num = 0
            self.ogg_granule_pos = 0
            
            # 1. OpusHead (必须正好 19 字节)
            # Format: 8s (Magic), B (Ver), B (Channels), H (Pre-skip), I (Rate), H (Gain), B (Mapping)
            opus_head = struct.pack("<8sBBHIHB", 
                b"OpusHead", 
                1,               # version
                1,               # channels
                0,               # pre-skip
                sample_rate, 
                0,               # output gain
                0                # mapping family
            )
            # BOS 页面标志为 0x02
            self.ogg_file.write(self._create_ogg_page([opus_head], header_type=0x02))
            
            # 2. OpusTags
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
            logger.info(f"TTS 已保存: {self.tts_raw_path} 和 {self.tts_ogg_path}")

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
                await self.send_queue.put(json.dumps({"session_id": str(self.session_id), "type": "listen", "state": "stop"}))
        except Exception as e:
            logger.error(f"发送音频异常: {e}")

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
        elif msg_type == "stt":
            logger.info(f"[ASR]: {data.get('text')}")
        elif msg_type == "llm":
            logger.info(f"[LLM]: {data.get('text')} ({data.get('emotion')})")

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
