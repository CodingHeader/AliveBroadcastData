import subprocess
import sys
import os
import time

# Change to server directory
os.chdir(r"E:\Code\AliveBroadcastData\server")

# Start uvicorn as detached process
proc = subprocess.Popen(
    [sys.executable, "-m", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "12306", "--reload"],
    stdout=subprocess.PIPE,
    stderr=subprocess.PIPE,
    stdin=subprocess.DEVNULL,
    creationflags=subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.DETACHED_PROCESS
)

print(f"Server started with PID: {proc.pid}")

# Wait a bit and check if still running
time.sleep(3)

if proc.poll() is None:
    print("Server is running")
else:
    print("Server exited with code:", proc.returncode)
    stdout, stderr = proc.communicate()
    print("STDOUT:", stdout.decode() if stdout else "None")
    print("STDERR:", stderr.decode() if stderr else "None")