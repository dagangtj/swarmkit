#!/usr/bin/env python3
"""
Windows快速加入SwarmKit网络
02号机一键运行此脚本即可完成三机联调
"""
import paho.mqtt.client as mqtt
import json, time

BROKER = '100.96.208.18'
PORT = 1883

# 02号机的认证信息（请填入正确密码）
AGENT_ID = 'agent02'
USER = 'agent02'
PASS = ''  # 请填入02的MQTT密码

received = []

def on_connect(c, u, f, rc, p=None):
    if rc == 0:
        print(f'[连接成功] 已加入SwarmKit网络')
        c.subscribe('agent/chat', qos=1)
        # 广播上线
        msg = json.dumps({'from': AGENT_ID, 'text': 'agent02在线，三机联调测试', 'ts': int(time.time())})
        c.publish('agent/chat', msg, qos=1)
        print('[已广播] agent02上线消息已发出')
    else:
        print(f'[连接失败] rc={rc}，请检查密码')

def on_message(c, u, msg):
    try:
        data = json.loads(msg.payload.decode())
        sender = data.get('from', '?')
        text = data.get('text', '')[:60]
        print(f'[收到] {sender}: {text}')
        received.append(sender)
    except Exception as e:
        print(f'解析失败: {e}')

client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id=f'swarmkit-{AGENT_ID}')
if PASS:
    client.username_pw_set(USER, PASS)
client.on_connect = on_connect
client.on_message = on_message

print(f'正在连接 {BROKER}:{PORT}...')
client.connect(BROKER, PORT, 60)
client.loop_start()
time.sleep(10)
client.loop_stop()
client.disconnect()

print(f'\n=== 测试结果 ===')
print(f'收到来自: {set(received)}')
if 'agent01' in received:
    print('✅ 02-01 互通 PASS')
if 'agent00' in received:
    print('✅ 02-00 互通 PASS')
if not received:
    print('❌ 未收到任何消息，请检查网络和密码')
