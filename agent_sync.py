#!/usr/bin/env python3
"""
SwarmKit v0.4 - 最终态
安装即入网 | 自动发现 | 自动分工 | TG同步
"""
import paho.mqtt.client as mqtt
import json, time, os, logging, threading, uuid, subprocess
from datetime import datetime

logging.basicConfig(level=logging.INFO, format='%(asctime)s [SwarmKit] %(message)s')

OPENCLAW_URL = os.environ.get('OPENCLAW_URL', 'http://localhost:18789')
TG_CHAT_ID = os.environ.get('TG_CHAT_ID', '-5122335253')

class SwarmKit:
    def __init__(self, agent_id, skills=None, broker='100.96.208.18', port=1883,
                 mqtt_user=None, mqtt_pass=None):
        self.agent_id = agent_id
        self.skills = skills or []
        self.broker = broker
        self.port = port
        self.registry = {}   # {agent_id: {skills, last_seen}}
        self.handlers = {}
        self._mqtt_ok = False
        self._lock = threading.Lock()

        # 归档
        self.archive_dir = os.path.expanduser('~/.swarmkit/archive')
        self.tg_queue = os.path.expanduser('~/.openclaw/workspace/memory/tg_queue')
        os.makedirs(self.archive_dir, exist_ok=True)
        os.makedirs(self.tg_queue, exist_ok=True)

        # MQTT
        self.client = mqtt.Client(
            mqtt.CallbackAPIVersion.VERSION2,
            client_id=f'swarmkit-{agent_id}-{uuid.uuid4().hex[:4]}'
        )
        if mqtt_user:
            self.client.username_pw_set(mqtt_user, mqtt_pass)
        self.client.on_connect = self._on_connect
        self.client.on_message = self._on_message
        self.client.on_disconnect = self._on_disconnect

        # 自动发现心跳
        self._presence_timer = None

    # ===== 连接 =====
    def _on_connect(self, c, u, f, rc, p=None):
        if rc == 0:
            self._mqtt_ok = True
            c.subscribe('swarm/chat', qos=1)
            c.subscribe('swarm/discover', qos=1)
            c.subscribe(f'swarm/{self.agent_id}/task', qos=1)
            c.subscribe('agent/chat', qos=1)  # 兼容旧topic
            self._announce_presence()
            self._start_presence_heartbeat()
            logging.info(f'已加入Swarm网络 agent_id={self.agent_id} skills={self.skills}')
        else:
            self._mqtt_ok = False

    def _on_disconnect(self, c, u, d, rc=None, p=None):
        self._mqtt_ok = False

    # ===== 自动发现 =====
    def _announce_presence(self):
        msg = json.dumps({
            'type': 'presence',
            'from': self.agent_id,
            'skills': self.skills,
            'ts': int(time.time())
        })
        self.client.publish('swarm/discover', msg, qos=1)

    def _start_presence_heartbeat(self):
        def heartbeat():
            while self._mqtt_ok:
                self._announce_presence()
                time.sleep(30)  # 每30秒广播一次
        t = threading.Thread(target=heartbeat, daemon=True)
        t.start()

    # ===== 消息处理 =====
    def _on_message(self, c, u, msg):
        try:
            data = json.loads(msg.payload.decode())
            sender = data.get('from', '?')
            mtype = data.get('type', 'chat')
            text = data.get('text', '')
            ts = data.get('ts', time.time())

            # 自动发现：更新注册表
            if mtype == 'presence':
                if sender != self.agent_id:
                    with self._lock:
                        self.registry[sender] = {
                            'skills': data.get('skills', []),
                            'last_seen': time.time()
                        }
                    logging.info(f'[发现] {sender} 能力:{data.get("skills",[])}')  
                return

            if sender == self.agent_id:
                return

            # 归档
            self._archive(sender, text, ts)

            # TG同步
            if sender not in {'AgentSync'} and mtype != 'presence':
                self._queue_tg(sender, text, ts)

            logging.info(f'[收到] {sender}: {text[:60]}')

            # 自动分工：任务派发
            if mtype == 'task':
                task_id = data.get('task_id', '?')
                logging.info(f'[任务] {task_id} from {sender}')
                if 'on_task' in self.handlers:
                    result = self.handlers['on_task'](sender, text, task_id)
                    if result:
                        self.send_result(result, to=sender, task_id=task_id)
                return

            # @点名
            if f'@{self.agent_id}' in text:
                if 'on_mention' in self.handlers:
                    self.handlers['on_mention'](sender, text)
                else:
                    self.send(f'@{sender} {self.agent_id}在线，收到。', to=sender)

            # 通用消息
            if 'on_message' in self.handlers:
                self.handlers['on_message'](sender, text, data)

        except Exception as e:
            logging.error(f'消息处理失败: {e}')

    # ===== 发送 =====
    def send(self, text, to='all', msg_type='chat', task_id=None):
        msg = json.dumps({
            'from': self.agent_id,
            'text': text,
            'to': to,
            'type': msg_type,
            'task_id': task_id,
            'ts': int(time.time())
        })
        if self._mqtt_ok:
            topic = 'swarm/chat' if to == 'all' else f'swarm/{to}/task' if msg_type == 'task' else f'swarm/{to}/task'
            self.client.publish('swarm/chat', msg, qos=1)  # 广播
            if to != 'all':
                self.client.publish(f'swarm/{to}/task', msg, qos=1)  # 点对点
        else:
            logging.warning('[外网模式] MQTT不可用，消息未发送')

    def send_task(self, task, to, task_id=None):
        """自动分工：派发任务给最优节点"""
        task_id = task_id or uuid.uuid4().hex[:8]
        # 如果to='auto'，自动选择有对应能力的节点
        if to == 'auto':
            to = self._best_agent_for(task)
        self.send(task, to=to, msg_type='task', task_id=task_id)
        logging.info(f'[派发任务] → {to} task_id={task_id}')
        return task_id

    def send_result(self, result, to, task_id=None):
        self.send(result, to=to, msg_type='result', task_id=task_id)

    def _best_agent_for(self, task):
        """简单关键词匹配找最优节点"""
        keywords = task.lower().split()
        best, best_score = self.agent_id, 0
        with self._lock:
            for aid, info in self.registry.items():
                score = sum(1 for k in keywords if any(k in s.lower() for s in info['skills']))
                if score > best_score:
                    best, best_score = aid, score
        return best

    # ===== 工具 =====
    def on(self, event, handler):
        self.handlers[event] = handler

    def find_by_skill(self, skill):
        with self._lock:
            return [aid for aid, info in self.registry.items()
                    if any(skill.lower() in s.lower() for s in info.get('skills', []))]

    def online_agents(self):
        now = time.time()
        with self._lock:
            return {aid: info for aid, info in self.registry.items()
                    if now - info['last_seen'] < 60}

    def mode(self):
        return '内网(MQTT)' if self._mqtt_ok else '外网(OpenClaw)'

    def _archive(self, sender, text, ts):
        date_str = datetime.fromtimestamp(ts).strftime('%Y-%m-%d')
        path = os.path.join(self.archive_dir, f'swarm-{date_str}.md')
        time_str = datetime.fromtimestamp(ts).strftime('%H:%M:%S')
        with open(path, 'a') as f:
            f.write(f'## [{time_str}] {sender}\n\n{text}\n\n---\n\n')

    def _queue_tg(self, sender, text, ts):
        entry = {'sender': sender, 'text': text[:300], 'ts': ts, 'chat_id': TG_CHAT_ID}
        fname = os.path.join(self.tg_queue, f'{int(ts*1000)}.json')
        with open(fname, 'w') as f:
            json.dump(entry, f, ensure_ascii=False)

    def start(self, blocking=True):
        try:
            self.client.connect_async(self.broker, self.port, 60)
        except Exception as e:
            logging.warning(f'MQTT连接失败: {e}')
        if blocking:
            self.client.loop_forever(retry_first_connection=True)
        else:
            self.client.loop_start()
            return self

    def stop(self):
        self.client.loop_stop()
        self.client.disconnect()


if __name__ == '__main__':
    import sys
    agent_id = sys.argv[1] if len(sys.argv) > 1 else 'agent01'
    skills_arg = sys.argv[2].split(',') if len(sys.argv) > 2 else ['general']

    swarm = SwarmKit(
        agent_id=agent_id,
        skills=skills_arg,
        mqtt_user='agent01',
        mqtt_pass='e01399e5ae477392c18506dd'
    )

    def on_task(sender, task, task_id):
        logging.info(f'执行任务: {task[:50]}')
        return f'{agent_id}已完成任务 task_id={task_id}'

    def on_mention(sender, text):
        agents = swarm.online_agents()
        swarm.send(f'@{sender} {agent_id}在线。已知节点: {list(agents.keys())}，当前模式: {swarm.mode()}')

    swarm.on('on_task', on_task)
    swarm.on('on_mention', on_mention)
    logging.info(f'SwarmKit v0.4 启动 | {agent_id} | 能力:{skills_arg}')
    swarm.start()
