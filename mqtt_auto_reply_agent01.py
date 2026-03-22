#!/usr/bin/env python3
"""Agent01 MQTT Auto-Reply Client - 自动回复版本"""
import paho.mqtt.client as mqtt
import json, time

BROKER = '100.96.208.18'
PORT = 1883
USER = 'agent01'
PASS = 'e01399e5ae477392c18506dd'
TOPIC = 'agent/chat'

def on_connect(client, userdata, flags, rc, properties=None):
    if rc == 0:
        print(f'✅ [{USER}] 自动回复客户端已连接')
        client.subscribe(TOPIC, qos=1)
        client.publish(TOPIC, json.dumps({
            'from': USER, 'text': '01自动回复客户端就绪', 'ts': time.time()
        }), qos=1)
    else:
        print(f'❌ 连接失败: {rc}')

def on_message(client, userdata, msg):
    try:
        data = json.loads(msg.payload.decode())
        sender = data.get('from', '?')
        text = data.get('text', '')
        
        if sender == USER:
            return
            
        print(f'📨 [{time.strftime("%H:%M:%S")}] 来自@{sender}: {text[:60]}')
        
        reply_text = None
        
        # 检查是否@自己
        if f'@{USER}' in text or 'agent01' in text.lower():
            if '状态' in text or '运行' in text:
                reply_text = '状态汇报：正常运行'
            elif '就绪' in text:
                reply_text = '01就绪'
            elif '测试' in text:
                reply_text = '01收到测试'
            elif '回复' in text and 'agent01' in text:
                reply_text = 'agent01'
            else:
                reply_text = f'01收到: {text[:20]}'
        
        if reply_text:
            reply = json.dumps({
                'from': USER,
                'text': reply_text,
                'ts': time.time()
            })
            client.publish(TOPIC, reply, qos=1)
            print(f'📤 自动回复: {reply_text}')
            
    except Exception as e:
        print(f'错误: {e}')

client = mqtt.Client(
    mqtt.CallbackAPIVersion.VERSION2,
    client_id=f'{USER}-auto-reply',
    clean_session=True
)
client.username_pw_set(USER, PASS)
client.on_connect = on_connect
client.on_message = on_message

print(f'🚀 {USER} 自动回复客户端启动...')
client.connect(BROKER, PORT, 60)
client.loop_forever(retry_first_connection=True)
