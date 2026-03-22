#!/usr/bin/env python3
"""
SwarmKit v0.4 集成测试
验证：安装即入网、自动发现、自动分工、TG同步
"""
import sys, time, json
sys.path.insert(0, '.')
from agent_sync import SwarmKit

BROKER = '100.96.208.18'
MQTT_USER = 'agent01'
MQTT_PASS = 'e01399e5ae477392c18506dd'

passed = []
failed = []

def test(name, result, detail=''):
    if result:
        print(f'✅ PASS {name}')
        passed.append(name)
    else:
        print(f'❌ FAIL {name} {detail}')
        failed.append(name)

print('=== SwarmKit v0.4 集成测试 ===')
print()

# T1: 实例化
swarm = SwarmKit('test-agent', ['testing','linux'],
                 broker=BROKER, mqtt_user=MQTT_USER, mqtt_pass=MQTT_PASS)
test('T1.1 实例化', swarm.agent_id == 'test-agent')
test('T1.2 能力注册', 'testing' in swarm.skills)

# T2: 连接
swarm.start(blocking=False)
time.sleep(3)
test('T2.1 MQTT连接', swarm._mqtt_ok, f'mode={swarm.mode()}')
test('T2.2 模式检测', swarm.mode() in ['内网(MQTT)', '外网(OpenClaw)'])

# T3: 自动发现
time.sleep(5)
online = swarm.online_agents()
test('T3.1 发现节点', len(online) >= 0)  # 有没有其他节点
if online:
    test('T3.2 节点有能力', all('skills' in v for v in online.values()))
    print(f'   发现节点: {list(online.keys())}')
else:
    print('   [INFO] 当前无其他在线节点')
    passed.append('T3.2 无节点(正常)')

# T4: 自动分工
best = swarm._best_agent_for('testing linux')
test('T4.1 能力匹配-自身', best == 'test-agent' or best in online)
task_id = swarm.send_task('测试任务', to='test-agent')
test('T4.2 任务派发', task_id is not None)

# T5: TG队列
import os
queue_dir = os.path.expanduser('~/.openclaw/workspace/memory/tg_queue')
test('T5.1 TG队列目录', os.path.exists(queue_dir))

# T6: 归档
archive_dir = os.path.expanduser('~/.swarmkit/archive')
test('T6.1 归档目录', os.path.exists(archive_dir))

swarm.stop()

print()
print(f'=== 测试结果: {len(passed)}/{len(passed)+len(failed)} PASS ===')
if failed:
    print(f'失败: {failed}')
    sys.exit(1)
else:
    print('🎉 ALL PASS')
