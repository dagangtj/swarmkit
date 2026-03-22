#!/usr/bin/env python3
"""
SwarmKit 快速安装配置脚本
运行：python3 setup.py
"""
import json, os, subprocess, sys

print('=== SwarmKit 安装配置向导 ===')
print()

# 检查依赖
print('检查依赖...')
try:
    import paho.mqtt.client
    print('✅ paho-mqtt 已安装')
except ImportError:
    print('安装 paho-mqtt...')
    subprocess.check_call([sys.executable, '-m', 'pip', 'install', 'paho-mqtt'])
    print('✅ paho-mqtt 安装完成')

# 读取现有配置
config_path = os.path.join(os.path.dirname(__file__), 'capabilities.json')
with open(config_path) as f:
    config = json.load(f)

print()
print('配置节点身份（直接回车使用默认值）：')

agent_id = input(f'  节点ID [{config["agent_id"]}]: ').strip() or config['agent_id']
broker = input(f'  Broker IP [{config["broker"]}]: ').strip() or config['broker']
skills_input = input(f'  能力标签（逗号分隔）[{" ,".join(config["skills"])}]: ').strip()
skills = [s.strip() for s in skills_input.split(',')] if skills_input else config['skills']
username = input(f'  MQTT用户名 [{config["auth"]["username"]}]: ').strip() or config['auth']['username']
password = input('  MQTT密码: ').strip()

# 更新配置
config.update({
    'agent_id': agent_id,
    'broker': broker,
    'skills': skills,
    'auth': {'username': username, 'password': password}
})

with open(config_path, 'w') as f:
    json.dump(config, f, indent=2, ensure_ascii=False)

print()
print('✅ 配置已保存')
print()
print('启动SwarmKit：')
print('  python3 agent_sync.py')
print()
print('运行测试：')
print('  python3 test_integration.py')
