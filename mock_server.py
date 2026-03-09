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
