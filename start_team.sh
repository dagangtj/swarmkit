#!/bin/bash
# SwarmKit 三机启动脚本
# 在各自机器上运行对应命令

AGENT_ID=${1:-"agent"}
SKILLS=${2:-"general"}
BROKER=${3:-"100.96.208.18"}

echo "🚀 SwarmKit 启动"
echo "  agent_id: $AGENT_ID"
echo "  skills:   $SKILLS"
echo "  broker:   $BROKER"
echo ""

# 检查依赖
if ! python3 -c "import paho.mqtt" 2>/dev/null; then
    echo "安装 paho-mqtt..."
    pip install paho-mqtt --quiet || pip3 install paho-mqtt --quiet
fi

# 启动
exec python3 "$(dirname "$0")/agent_sync.py" "$AGENT_ID" "$SKILLS"
