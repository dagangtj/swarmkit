#!/usr/bin/env python3
"""
SwarmKit OpenClaw Bridge
让OpenClaw AI通过TG消息参与SwarmKit协作
无需额外进程，天然集成

工作原理：
1. 任务发布到MQTT + TG群聊
2. 各机器AI看到TG消息，用OpenClaw回复
3. 回复通过TG→MQTT桥接回SwarmKit
4. 形成闭环
"""
import paho.mqtt.client as mqtt
import json, time, os, logging
from datetime import datetime

logging.basicConfig(level=logging.INFO, format='%(asctime)s [Bridge] %(message)s')

BROKER = '100.96.208.18'
MQTT_USER = 'agent01'
MQTT_PASS = 'e01399e5ae477392c18506dd'
TG_CHAT_ID = '-5122335253'

# TG→MQTT桥接：把TG群聊里AI的回复同步回MQTT
# MQTT→TG桥接：把MQTT任务推送到TG群聊供AI处理

class OpenClawBridge:
    def __init__(self):
        self.client = mqtt.Client(
            mqtt.CallbackAPIVersion.VERSION2,
            client_id='swarmkit-bridge'
        )
        self.client.username_pw_set(MQTT_USER, MQTT_PASS)
        self.client.on_connect = self._on_connect
        self.client.on_message = self._on_message
        self.tg_queue = os.path.expanduser('~/.openclaw/workspace/memory/tg_queue')
        os.makedirs(self.tg_queue, exist_ok=True)
        self._seen = set()

    def _on_connect(self, c, u, f, rc, p=None):
        if rc == 0:
            logging.info('Bridge已连接')
            c.subscribe('swarm/chat', qos=1)
            c.subscribe('swarm/task', qos=1)
            c.subscribe('agent/chat', qos=1)

    def _on_message(self, c, u, msg):
        try:
            data = json.loads(msg.payload.decode())
            sender = data.get('from', '?')
            text = data.get('text', '')
            ts = data.get('ts', time.time())
            mtype = data.get('type', 'chat')

            if sender in {'AgentSync', 'swarmkit-bridge'}: return
            if mtype == 'presence': return

            key = f'{sender}:{int(ts)}'
            if key in self._seen: return
            self._seen.add(key)
            if len(self._seen) > 500: self._seen.clear()

            # 推送到TG队列供OpenClaw处理
            entry = {
                'sender': sender,
                'text': text[:300],
                'ts': ts,
                'chat_id': TG_CHAT_ID,
                'type': mtype
            }
            fname = os.path.join(self.tg_queue, f'{int(ts*1000)}.json')
            with open(fname, 'w') as f:
                json.dump(entry, f, ensure_ascii=False)

        except Exception as e:
            logging.error(f'处理失败: {e}')

    def publish_task(self, task_text, from_agent='bridge', task_id=None):
        """发布任务到MQTT"""
        import uuid
        task_id = task_id or uuid.uuid4().hex[:8]
        msg = json.dumps({
            'from': from_agent,
            'text': task_text,
            'type': 'task',
            'task_id': task_id,
            'ts': int(time.time())
        })
        self.client.publish('swarm/chat', msg, qos=1)
        self.client.publish('agent/chat', msg, qos=1)
        return task_id

    def start(self, blocking=True):
        self.client.connect_async(BROKER, 1883, 60)
        if blocking:
            self.client.loop_forever(retry_first_connection=True)
        else:
            self.client.loop_start()
            return self

    def stop(self):
        self.client.loop_stop()
        self.client.disconnect()


if __name__ == '__main__':
    bridge = OpenClawBridge()
    logging.info('SwarmKit OpenClaw Bridge启动')
    bridge.start()
