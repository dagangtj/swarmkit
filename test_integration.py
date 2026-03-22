#!/usr/bin/env python3
"""
SwarmKit 集成测试脚本
01号机测试专家编写
"""
import sys, time, json
sys.path.insert(0, '.')
from agent_sync import SwarmKit

results = []

def log(test, passed, detail=''):
    status = '✅ PASS' if passed else '❌ FAIL'
    print(f'{status} {test}: {detail}')
    results.append({'test': test, 'passed': passed, 'detail': detail})

print('=== SwarmKit 集成测试开始 ===')
print()

# T1.1 节点实例化
try:
    swarm = SwarmKit('test-agent', skills=['testing', 'linux'], broker='100.96.208.18')
    log('T1.1 节点实例化', True, f'agent_id={swarm.agent_id}')
except Exception as e:
    log('T1.1 节点实例化', False, str(e))
    sys.exit(1)

# T1.2 连接Broker
try:
    swarm.start(blocking=False)
    time.sleep(2)
    log('T1.2 连接Broker', True, '100.96.208.18:1883')
except Exception as e:
    log('T1.2 连接Broker', False, str(e))

# T1.3 发送消息
try:
    swarm.send('SwarmKit集成测试消息')
    time.sleep(1)
    log('T1.3 发送消息', True, 'swarm/chat')
except Exception as e:
    log('T1.3 发送消息', False, str(e))

# T1.4 能力广播
try:
    swarm._broadcast_presence()
    time.sleep(1)
    log('T1.4 能力广播', True, f'skills={swarm.skills}')
except Exception as e:
    log('T1.4 能力广播', False, str(e))

# T2.1 @点名处理器
try:
    mentioned = []
    def on_mention(sender, text):
        mentioned.append(sender)
    swarm.on('on_mention', on_mention)
    log('T2.1 @点名处理器注册', True, 'on_mention handler set')
except Exception as e:
    log('T2.1 @点名处理器注册', False, str(e))

# T2.2 send_task (A2A兼容)
try:
    task_id = swarm.send_task('测试任务', to='agent01')
    time.sleep(1)
    log('T2.2 send_task A2A兼容', True, f'task_id={task_id}')
except Exception as e:
    log('T2.2 send_task A2A兼容', False, str(e))

# T3.1 归档目录
import os
try:
    archive_dir = os.path.expanduser('~/.swarmkit/archive')
    exists = os.path.exists(archive_dir)
    log('T3.1 归档目录', exists, archive_dir)
except Exception as e:
    log('T3.1 归档目录', False, str(e))

# 清理
swarm.stop()
time.sleep(1)

# 汇总
print()
print('=== 测试结果汇总 ===')
passed = sum(1 for r in results if r['passed'])
total = len(results)
print(f'通过: {passed}/{total}')
if passed == total:
    print('🎉 ALL PASS - SwarmKit v0.2 验收通过')
else:
    print(f'⚠️  {total-passed}个测试失败，需要修复')
    for r in results:
        if not r['passed']:
            print(f'  - {r["test"]}: {r["detail"]}')
