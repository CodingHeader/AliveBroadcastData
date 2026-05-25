#!/bin/bash
echo "=== AliveBroadcastData 启动 ==="
cd "$(dirname "$0")/server" || exit 1

# 从 config.py 读取实际端口（默认12306）
PORT=$(grep -oP '^PORT\s*=\s*\K[0-9]+' config.py 2>/dev/null || echo "12306")

# 检查端口占用
if command -v lsof &> /dev/null; then
    if lsof -i :"$PORT" &> /dev/null; then
        echo "[警告] 端口 $PORT 已被占用"
        echo "请关闭占用进程后重试，或修改 server/config.py 中的 PORT"
        exit 1
    fi
elif command -v ss &> /dev/null; then
    if ss -tlnp 2>/dev/null | grep -q ":$PORT "; then
        echo "[警告] 端口 $PORT 已被占用"
        echo "请关闭占用进程后重试，或修改 server/config.py 中的 PORT"
        exit 1
    fi
fi

# 检查 Python
if ! command -v python3 &> /dev/null; then
    echo "[错误] 未找到 Python3，请安装 Python 3.x"
    exit 1
fi

# 检查 requirements.txt
if [ ! -f "requirements.txt" ]; then
    echo "[错误] 未找到 requirements.txt"
    echo "请确保 server/requirements.txt 存在"
    exit 1
fi

if [ ! -d "venv" ]; then echo "创建虚拟环境..."; python3 -m venv venv; fi
source venv/bin/activate
pip install -r requirements.txt -q

echo "启动服务 http://127.0.0.1:$PORT"
python main.py
