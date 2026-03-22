#!/usr/bin/env python3
"""Agent00 MQTT Client - Mac Mini版本"""
import paho.mqtt.client as mqtt
import json, time, sys

BROKER = '100.96.208.18'
PORT = 1883
USER = 'agent00'
PASS = 'your_password_here'  # 请替换为实际密码
TOPIC = 'agent/chat'

def on_connect(client, userdata, flags, rc, properties=None):
    if rc == 0:
        print(f'✅ [{USER}] 已连接到broker')
        client.subscribe(TOPIC, qos=1)
        print(f'✅ 已订阅 {TOPIC}')
        # 发送就绪消息
        msg = json.dumps({
            'from': USER,
            'text': '00就绪',
            'ts': time.time()
        })
        client.publish(TOPIC, msg, qos=1)
        print('✅ 就绪消息已发送')
    else:
        print(f'❌ 连接失败: {rc}')

def on_message(client, userdata, msg):
    try:
        data = json.loads(msg.payload.decode())
        sender = data.get('from', '?')
        text = data.get('text', '')
        ts = data.get('ts', 0)
        
        # 只处理发给自己的消息
        if f'@{USER}' in text or 'agent00' in text.lower():
            print(f'📨 [{time.strftime("%H:%M:%S")}] 收到@{sender}: {text[:60]}')
            # 这里可以调用AI处理并回复
            reply = json.dumps({
                'from': USER,
                'text': f'00收到: {text[:30]}',
                'ts': time.time()
            })
            client.publish(TOPIC, reply, qos=1)
            print(f'📤 已回复')
    except Exception as e:
        print(f'处理错误: {e}')

def on_disconnect(client, userdata, rc, properties=None):
    print('⚠️ 断开连接，自动重连...')

# 创建客户端
client = mqtt.Client(
    mqtt.CallbackAPIVersion.VERSION2,
    client_id=USER,
    clean_session=True
)
client.username_pw_set(USER, PASS)
client.on_connect = on_connect
client.on_message = on_message
client.on_disconnect = on_disconnect

print(f'🚀 {USER} MQTT客户端启动...')
print(f'   Broker: {BROKER}:{PORT}')
print(f'   Topic: {TOPIC}')

# 连接并运行
client.connect(BROKER, PORT, 60)
client.loop_forever(retry_first_connection=True)
