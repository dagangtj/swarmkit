#!/usr/bin/env python3
"""
SwarmKit v0.1 - AI协作网络核心模块
安装即入网，AI即成员
"""
import paho.mqtt.client as mqtt
import json, time, os, logging
from datetime import datetime

logging.basicConfig(level=logging.INFO, format='%(asctime)s [SwarmKit] %(message)s')

class SwarmKit:
    def __init__(self, agent_id, skills=None, broker='100.96.208.18', port=1883):
        self.agent_id = agent_id
        self.skills = skills or []
        self.broker = broker
        self.port = port
        self.registry = {}  # 已发现的节点
        self.handlers = {}  # 消息处理器
        self.archive_dir = os.path.expanduser('~/.swarmkit/archive')
        os.makedirs(self.archive_dir, exist_ok=True)

        self.client = mqtt.Client(
            mqtt.CallbackAPIVersion.VERSION2,
            client_id=f'swarmkit-{agent_id}'
        )
        self.client.on_connect = self._on_connect
        self.client.on_message = self._on_message

    def _on_connect(self, c, u, f, rc, p=None):
        if rc == 0:
            logging.info(f'[{self.agent_id}] 已连接SwarmKit网络')
            c.subscribe('swarm/chat', qos=1)       # 公共频道
            c.subscribe(f'swarm/{self.agent_id}/inbox', qos=1)  # 专属收件箱
            c.subscribe('swarm/discover', qos=1)   # 节点发现
            # 广播上线+能力
            self._broadcast_presence()
        else:
            logging.error(f'连接失败 rc={rc}')

    def _broadcast_presence(self):
        msg = {
            'type': 'presence',
            'from': self.agent_id,
            'skills': self.skills,
            'ts': int(time.time())
        }
        self.client.publish('swarm/discover', json.dumps(msg), qos=1)
        logging.info(f'已广播能力: {self.skills}')

    def _on_message(self, c, u, msg):
        try:
            data = json.loads(msg.payload.decode())
            sender = data.get('from', '?')
            mtype = data.get('type', 'chat')

            # 节点发现
            if mtype == 'presence' and sender != self.agent_id:
                self.registry[sender] = {
                    'skills': data.get('skills', []),
                    'last_seen': time.time()
                }
                logging.info(f'发现节点: {sender} 能力: {data.get("skills", [])}')
                return

            if sender == self.agent_id:
                return

            text = data.get('text', '')
            logging.info(f'[收到] {sender}: {text[:60]}')
            self._archive(sender, text, data.get('ts', time.time()))

            # @点名检测
            if f'@{self.agent_id}' in text:
                logging.info(f'被@点名，触发响应')
                if 'on_mention' in self.handlers:
                    self.handlers['on_mention'](sender, text)

            # 通用消息处理
            if 'on_message' in self.handlers:
                self.handlers['on_message'](sender, text, data)

        except Exception as e:
            logging.error(f'消息处理失败: {e}')

    def _archive(self, sender, text, ts):
        date_str = datetime.fromtimestamp(ts).strftime('%Y-%m-%d')
        path = os.path.join(self.archive_dir, f'swarm-{date_str}.md')
        if not os.path.exists(path):
            with open(path, 'w') as f:
                f.write(f'# SwarmKit对话归档 - {date_str}\n\n')
        time_str = datetime.fromtimestamp(ts).strftime('%H:%M:%S')
        with open(path, 'a') as f:
            f.write(f'## [{time_str}] {sender}\n\n{text}\n\n---\n\n')

    def send(self, text, to='all', msg_type='message', task_id=None):
        """发送消息，兼容A2A协议消息格式"""
        msg = {
            'from': self.agent_id,
            'text': text,
            'to': to,
            'type': msg_type,           # message/task/status/result (A2A兼容)
            'task_id': task_id,         # 任务追踪ID (A2A兼容)
            'ts': int(time.time())
        }
        topic = 'swarm/chat' if to == 'all' else f'swarm/{to}/inbox'
        self.client.publish(topic, json.dumps(msg), qos=1)

    def send_task(self, task, to, task_id=None):
        """发送任务请求（A2A task模式）"""
        import uuid
        task_id = task_id or str(uuid.uuid4())[:8]
        self.send(task, to=to, msg_type='task', task_id=task_id)
        return task_id

    def send_result(self, result, to, task_id=None):
        """发送任务结果（A2A result模式）"""
        self.send(result, to=to, msg_type='result', task_id=task_id)

    def on(self, event, handler):
        self.handlers[event] = handler

    def find_by_skill(self, skill):
        return [aid for aid, info in self.registry.items() if skill in info.get('skills', [])]

    def start(self, blocking=True):
        self.client.connect_async(self.broker, self.port, 60)
        if blocking:
            self.client.loop_forever(retry_first_connection=True)
        else:
            self.client.loop_start()

    def stop(self):
        self.client.loop_stop()
        self.client.disconnect()


if __name__ == '__main__':
    # 示例：01号机加入SwarmKit
    swarm = SwarmKit(
        agent_id='agent01',
        skills=['testing', 'linux', 'monitoring', 'hosting']
    )

    def on_mention(sender, text):
        swarm.send(f'@{sender} 01号机收到点名，正在处理...')

    swarm.on('on_mention', on_mention)
    logging.info('SwarmKit启动...')
    swarm.start()
