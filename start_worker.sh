#!/bin/bash
# SwarmKit Worker 一键启动脚本
# 用法: bash start_worker.sh <agent_id> <skills>
# 例：bash start_worker.sh agent00 coordinator,decision_maker

AGENT_ID=${1:-agent00}
SKILLS=${2:-coordinator}
DIR="$(cd "$(dirname "$0")" && pwd)"

echo "[SwarmKit] 启动 $AGENT_ID (skills: $SKILLS)"

# 检查依赖
if ! python3 -c "import paho.mqtt" 2>/dev/null; then
    echo "安装依赖..."
    pip3 install paho-mqtt -q
fi

# 停止旧的AgentSync进程（治本）
if pgrep -f 'agentsync\|agent_sync\|mqtt_daemon' > /dev/null 2>&1; then
    echo "[SwarmKit] 停止旧进程..."
    pkill -f 'agentsync' 2>/dev/null
    pkill -f 'AgentSync' 2>/dev/null
    sleep 1
fi

# 启动SwarmKit worker
cat > /tmp/swarmkit_worker_${AGENT_ID}.py << PYEOF
import sys, time, logging
sys.path.insert(0, '${DIR}')
from agent_sync import SwarmKit

logging.basicConfig(level=logging.INFO, format='%(asctime)s [${AGENT_ID}] %(message)s')

swarm = SwarmKit('${AGENT_ID}', '${SKILLS}'.split(','),
                 mqtt_user='agent01', mqtt_pass='e01399e5ae477392c18506dd')

def on_task(sender, task, task_id):
    logging.info(f'执行任务: {task[:80]}')
    import platform
    result = f'${AGENT_ID}完成: {task[:60]}'
    return result

swarm.on('on_task', on_task)
logging.info('SwarmKit worker已启动，等待任务...')
swarm.start(blocking=True)
PYEOF

nohup python3 /tmp/swarmkit_worker_${AGENT_ID}.py >> /tmp/swarmkit_${AGENT_ID}.log 2>&1 &
echo $! > /tmp/swarmkit_${AGENT_ID}.pid
echo "[SwarmKit] $AGENT_ID 已启动 PID=$(cat /tmp/swarmkit_${AGENT_ID}.pid)"
echo "日志: tail -f /tmp/swarmkit_${AGENT_ID}.log"
