#!/usr/bin/env python3
"""01号机 MQTT 守护进程 v3 - 只收发+归档，不自动回复"""
import paho.mqtt.client as mqtt
import json, time, logging, signal, sys, os
from datetime import datetime

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [01] %(message)s',
    handlers=[logging.FileHandler('/tmp/mqtt_daemon_01.log'), logging.StreamHandler()]
)

BROKER, PORT = '100.96.208.18', 1883
USER, PASS = 'agent01', 'e01399e5ae477392c18506dd'
TOPIC = 'agent/chat'
ARCHIVE_DIR = os.path.expanduser('~/.openclaw/workspace/memory/mqtt')
os.makedirs(ARCHIVE_DIR, exist_ok=True)

def archive_message(sender, text, ts):
    date_str = datetime.fromtimestamp(ts).strftime('%Y-%m-%d')
    path = os.path.join(ARCHIVE_DIR, f'mqtt-chat-{date_str}.md')
    if not os.path.exists(path):
        with open(path, 'w', encoding='utf-8') as f:
            f.write(f'# MQTT团队对话归档 - {date_str}\n\n> 自动归档\n\n')
    time_str = datetime.fromtimestamp(ts).strftime('%H:%M:%S')
    with open(path, 'a', encoding='utf-8') as f:
        f.write(f'## [{time_str}] {sender}\n\n{text}\n\n---\n\n')

def on_connect(c, u, f, rc, p=None):
    if rc == 0:
        logging.info('已连接broker，订阅agent/chat [v3 纯收发+归档]')
        c.subscribe(TOPIC, qos=1)
    else:
        logging.error(f'连接失败 rc={rc}')

# TG同步：过滤不需要转发的发送者
TG_FILTER = {'AgentSync'}  # 不转发噪音
TG_FILTER_PREFIX = ('agent01',)  # 过滤agent01所有client_id前缀
TG_CHAT_ID = '-5122335253'
_seen = set()

def sync_to_tg(sender, text, ts):
    """通过cron唤醒agent发TG消息（写入待发队列文件）"""
    try:
        queue_dir = os.path.expanduser('~/.openclaw/workspace/memory/tg_queue')
        os.makedirs(queue_dir, exist_ok=True)
        entry = {'sender': sender, 'text': text[:300], 'ts': ts, 'chat_id': TG_CHAT_ID}
        fname = os.path.join(queue_dir, f'{int(ts*1000)}.json')
        with open(fname, 'w') as f:
            json.dump(entry, f, ensure_ascii=False)
        logging.info(f'[TG队列] 已加入: {sender}')
    except Exception as e:
        logging.error(f'[TG队列] 失败: {e}')

def on_message(c, u, msg):
    try:
        data = json.loads(msg.payload.decode())
        sender = data.get('from', '?')
        text = data.get('text', '')
        ts = data.get('ts', time.time())
        mtype = data.get('type', 'chat')
        logging.info(f'[收到] {sender}: {text[:80]}')
        archive_message(sender, text, ts)
        # 跳过自己发的ACK，避免循环
        if text == 'ACK': return
        # 对REMINDER消息自动发ACK，消除agent00的超时噪音
        if '[REMINDER]' in text and sender == 'AgentSync':
            ack = json.dumps({'from':'agent01','type':'ack','text':'ACK','ts':time.time()})
            c.publish(TOPIC, ack, qos=1)
            logging.info('[ACK] 已回复AgentSync REMINDER')
            return  # 不再进队列
        # TG同步：转发到群聊
        # 过滤噪音：presence、状态广播、已知节点消息不转发TG
        noise_keywords = ['已知节点', '在线。已知', 'agent00在线', 'agent01在线', 'agent02在线', '[REMINDER]']
        is_noise = any(kw in text for kw in noise_keywords)
        is_self = sender in TG_FILTER or any(sender.startswith(p) for p in TG_FILTER_PREFIX)
        if not is_self and mtype != 'presence' and not is_noise:
            msg_key = f'{sender}:{int(ts)}'
            if msg_key not in _seen:
                _seen.add(msg_key)
                if len(_seen) > 500: _seen.clear()
                sync_to_tg(sender, text, ts)
    except Exception as e:
        logging.error(f'处理失败: {e}')

def on_disconnect(c, u, d, rc=None, p=None):
    logging.warning('断开，自动重连...')

client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id='agent01-daemon')
client.username_pw_set(USER, PASS)
client.on_connect = on_connect
client.on_message = on_message
client.on_disconnect = on_disconnect

def shutdown(sig, frame):
    logging.info('退出')
    client.loop_stop()
    client.disconnect()
    sys.exit(0)

signal.signal(signal.SIGTERM, shutdown)
signal.signal(signal.SIGINT, shutdown)

logging.info('01守护进程v3启动 [纯收发+归档，无自动回复]')
client.connect_async(BROKER, PORT, 60)
client.loop_forever(retry_first_connection=True)
