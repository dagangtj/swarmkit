#!/usr/bin/env python3
"""
SwarmKit TG同步层 - 人类旁观模块
监听swarm/chat，自动转发到Telegram群聊
主人无需干预，AI运作过程实时可见
"""
import paho.mqtt.client as mqtt
import json, time, os, logging, requests
from datetime import datetime

logging.basicConfig(level=logging.INFO, format='%(asctime)s [TGSync] %(message)s')

# 配置
BROKER = '100.96.208.18'
PORT = 1883
USER = 'agent01'
PASS = 'e01399e5ae477392c18506dd'

# OpenClaw Gateway（用于发TG消息）
OPENCLAW_URL = os.environ.get('OPENCLAW_URL', 'http://localhost:18789')
OPENCLAW_TOKEN = os.environ.get('OPENCLAW_TOKEN', '')
TG_CHAT_ID = os.environ.get('TG_CHAT_ID', '-5122335253')  # indeals2001群

# 过滤：不转发的发送者
FILTER_SENDERS = {'AgentSync'}  # 过滤超时提醒等噪音

# 消息缓冲（避免重复转发）
seen_messages = set()

def send_to_tg(text):
    """通过OpenClaw Gateway发送TG消息"""
    try:
        url = f'{OPENCLAW_URL}/api/message/send'
        payload = {
            'channel': 'telegram',
            'to': TG_CHAT_ID,
            'message': text
        }
        headers = {}
        if OPENCLAW_TOKEN:
            headers['Authorization'] = f'Bearer {OPENCLAW_TOKEN}'
        r = requests.post(url, json=payload, headers=headers, timeout=5)
        if r.status_code in (200, 201):
            logging.info(f'TG转发成功')
            return True
        else:
            logging.warning(f'TG转发失败: {r.status_code} {r.text[:100]}')
            return False
    except Exception as e:
        logging.error(f'TG转发异常: {e}')
        return False

def format_for_tg(sender, text, ts):
    """格式化消息供人类阅读"""
    time_str = datetime.fromtimestamp(ts).strftime('%H:%M:%S')
    # 截断超长消息
    if len(text) > 300:
        text = text[:300] + '...'
    return f'🤖 [{time_str}] {sender}\n{text}'

def on_connect(c, u, f, rc, p=None):
    if rc == 0:
        logging.info('TG同步层已连接，开始监听swarm/chat')
        c.subscribe('swarm/chat', qos=1)
        c.subscribe('agent/chat', qos=1)  # 同时监听旧topic
    else:
        logging.error(f'连接失败 rc={rc}')

def on_message(c, u, msg):
    try:
        data = json.loads(msg.payload.decode())
        sender = data.get('from', '?')
        text = data.get('text', '')
        ts = data.get('ts', time.time())
        mtype = data.get('type', 'chat')

        # 过滤噪音
        if sender in FILTER_SENDERS:
            return
        if mtype == 'presence':
            return

        # 去重
        msg_key = f'{sender}:{ts}'
        if msg_key in seen_messages:
            return
        seen_messages.add(msg_key)
        if len(seen_messages) > 1000:
            seen_messages.clear()

        logging.info(f'[收到] {sender}: {text[:60]}')
        tg_text = format_for_tg(sender, text, ts)
        send_to_tg(tg_text)

    except Exception as e:
        logging.error(f'处理失败: {e}')

client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id='swarmkit-tgsync')
client.username_pw_set(USER, PASS)
client.on_connect = on_connect
client.on_message = on_message

if __name__ == '__main__':
    logging.info('SwarmKit TG同步层启动')
    logging.info(f'目标群聊: {TG_CHAT_ID}')
    client.connect_async(BROKER, PORT, 60)
    client.loop_forever(retry_first_connection=True)
