import subprocess
import time
import os
import signal

def test_websocket_flow():
    print("Starting integration test...")
    
    # 1. Start mock server in background
    server_process = subprocess.Popen(
        ["python3", "mock_server.py"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True
    )
    time.sleep(2) # Wait for server to start
    
    # 2. Start client in background
    client_process = subprocess.Popen(
        ["python3", "client.py"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True
    )
    
    # 3. Wait for some communication
    print("Waiting for communication (10 seconds)...")
    time.sleep(10)
    
    # 4. Terminate both
    os.kill(client_process.pid, signal.SIGINT)
    os.kill(server_process.pid, signal.SIGINT)
    
    client_out, client_err = client_process.communicate()
    server_out, server_err = server_process.communicate()
    
    # 5. Verify client logs
    print("\n--- Client Output ---")
    print(client_out)
    
    success = (
        "Connected successfully" in client_out and
        "Sending telemetry" in client_out and
        "LED Control: Setting LED to on" in client_out
    )
    
    if success:
        print("\nSUCCESS: Integration test passed!")
    else:
        print("\nFAILURE: Integration test failed!")
        exit(1)

if __name__ == "__main__":
    test_websocket_flow()
