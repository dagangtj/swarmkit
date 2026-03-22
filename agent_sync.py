#!/usr/bin/env python3
"""
SwarmKit v0.3 - 双模式AI协作网络
内网：MQTT直连（低延迟，局域网）
外网：OpenClaw sessions_send（跨网络，全球可达）
自动选择最优通道，用户无感知

类比：智能家居
  内网 = 设备直连
  外网 = 云服务器中转
"""
import paho.mqtt.client as mqtt
import json, time, os, logging, threading, requests
from datetime import datetime

logging.basicConfig(level=logging.INFO, format='%(asctime)s [SwarmKit] %(message)s')

class SwarmKit:
    def __init__(self, agent_id, skills=None, broker='100.96.208.18', port=1883,
                 openclaw_url=None, openclaw_token=None):
        self.agent_id = agent_id
        self.skills = skills or []
        self.broker = broker
        self.port = port
        self.openclaw_url = openclaw_url or os.environ.get('OPENCLAW_URL', 'http://localhost:18789')
        self.openclaw_token = openclaw_token or os.environ.get('OPENCLAW_TOKEN', '')
        self.registry = {}
        self.handlers = {}
        self._mqtt_ok = False
        self._lock = threading.Lock()

        # 归档目录
        self.archive_dir = os.path.expanduser('~/.swarmkit/archive')
        os.makedirs(self.archive_dir, exist_ok=True)

        # MQTT客户端（内网模式）
        self.client = mqtt.Client(
            mqtt.CallbackAPIVersion.VERSION2,
            client_id=f'swarmkit-{agent_id}'
        )
        self.client.on_connect = self._on_connect
        self.client.on_message = self._on_message
        self.client.on_disconnect = self._on_disconnect

    # ===== 内网模式（MQTT）=====
    def _on_connect(self, c, u, f, rc, p=None):
        if rc == 0:
            self._mqtt_ok = True
            logging.info(f'[内网模式] 已连接MQTT broker {self.broker}')
            c.subscribe('swarm/chat', qos=1)
            c.subscribe(f'swarm/{self.agent_id}/inbox', qos=1)
            c.subscribe('swarm/discover', qos=1)
            self._broadcast_presence()
        else:
            self._mqtt_ok = False
            logging.warning(f'[内网模式] 连接失败 rc={rc}，将使用外网模式')

    def _on_disconnect(self, c, u, d, rc=None, p=None):
        self._mqtt_ok = False
        logging.warning('[内网模式] 断开连接，切换到外网模式')

    def _on_message(self, c, u, msg):
        try:
            data = json.loads(msg.payload.decode())
            sender = data.get('from', '?')
            mtype = data.get('type', 'chat')

            if mtype == 'presence' and sender != self.agent_id:
                self.registry[sender] = {
                    'skills': data.get('skills', []),
                    'last_seen': time.time()
                }
                logging.info(f'[发现节点] {sender} 能力: {data.get("skills", [])}')
                return

            if sender == self.agent_id:
                return

            text = data.get('text', '')
            self._archive(sender, text, data.get('ts', time.time()))
            logging.info(f'[收到-内网] {sender}: {text[:60]}')

            if f'@{self.agent_id}' in text:
                if 'on_mention' in self.handlers:
                    self.handlers['on_mention'](sender, text)

            if 'on_message' in self.handlers:
                self.handlers['on_message'](sender, text, data)

        except Exception as e:
            logging.error(f'消息处理失败: {e}')

    def _broadcast_presence(self):
        msg = {
            'type': 'presence',
            'from': self.agent_id,
            'skills': self.skills,
            'ts': int(time.time())
        }
        self.client.publish('swarm/discover', json.dumps(msg), qos=1)

    # ===== 外网模式（OpenClaw sessions_send）=====
    def _send_via_openclaw(self, text, to='all'):
        """外网模式：通过OpenClaw Gateway转发消息"""
        try:
            url = f'{self.openclaw_url}/api/sessions/send'
            payload = {
                'label': to if to != 'all' else None,
                'message': f'[SwarmKit/{self.agent_id}] {text}'
            }
            headers = {'Authorization': f'Bearer {self.openclaw_token}'}
            r = requests.post(url, json=payload, headers=headers, timeout=5)
            if r.status_code == 200:
                logging.info(f'[外网模式] 消息已发送到 {to}')
                return True
            else:
                logging.warning(f'[外网模式] 发送失败 {r.status_code}')
                return False
        except Exception as e:
            logging.error(f'[外网模式] 请求失败: {e}')
            return False

    # ===== 统一发送接口（自动选择通道）=====
    def send(self, text, to='all', msg_type='message', task_id=None):
        """自动选择最优通道：内网优先，外网备用"""
        msg = {
            'from': self.agent_id,
            'text': text,
            'to': to,
            'type': msg_type,
            'task_id': task_id,
            'ts': int(time.time())
        }

        if self._mqtt_ok:
            # 内网模式：MQTT直连
            topic = 'swarm/chat' if to == 'all' else f'swarm/{to}/inbox'
            self.client.publish(topic, json.dumps(msg), qos=1)
            logging.info(f'[内网模式] 发送到 {to}')
        else:
            # 外网模式：OpenClaw转发
            logging.info(f'[外网模式] MQTT不可用，切换到OpenClaw')
            self._send_via_openclaw(text, to)

    def send_task(self, task, to, task_id=None):
        """派发任务（A2A兼容）"""
        import uuid
        task_id = task_id or str(uuid.uuid4())[:8]
        self.send(task, to=to, msg_type='task', task_id=task_id)
        return task_id

    def send_result(self, result, to, task_id=None):
        """返回任务结果（A2A兼容）"""
        self.send(result, to=to, msg_type='result', task_id=task_id)

    # ===== 工具方法 =====
    def on(self, event, handler):
        self.handlers[event] = handler

    def find_by_skill(self, skill):
        return [aid for aid, info in self.registry.items() if skill in info.get('skills', [])]

    def mode(self):
        return '内网(MQTT)' if self._mqtt_ok else '外网(OpenClaw)'

    def _archive(self, sender, text, ts):
        date_str = datetime.fromtimestamp(ts).strftime('%Y-%m-%d')
        path = os.path.join(self.archive_dir, f'swarm-{date_str}.md')
        if not os.path.exists(path):
            with open(path, 'w') as f:
                f.write(f'# SwarmKit归档 - {date_str}\n\n')
        time_str = datetime.fromtimestamp(ts).strftime('%H:%M:%S')
        with open(path, 'a') as f:
            f.write(f'## [{time_str}] {sender}\n\n{text}\n\n---\n\n')

    def start(self, blocking=True):
        try:
            self.client.connect_async(self.broker, self.port, 60)
        except Exception as e:
            logging.warning(f'MQTT连接失败，使用外网模式: {e}')
        if blocking:
            self.client.loop_forever(retry_first_connection=True)
        else:
            self.client.loop_start()

    def stop(self):
        self.client.loop_stop()
        self.client.disconnect()


if __name__ == '__main__':
    swarm = SwarmKit(
        agent_id='agent01',
        skills=['testing', 'linux', 'monitoring']
    )

    def on_mention(sender, text):
        swarm.send(f'@{sender} 01号机收到，当前模式：{swarm.mode()}')

    swarm.on('on_mention', on_mention)
    logging.info(f'SwarmKit v0.3 启动，当前模式：{swarm.mode()}')
    swarm.start()
