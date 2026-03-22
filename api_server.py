#!/usr/bin/env python3
"""
SwarmKit HTTP API Server
让任何程序都能通过HTTP发任务给Swarm

API:
  POST /task          - 发布任务到Swarm
  GET  /agents        - 查看在线节点
  GET  /status        - Swarm状态
  GET  /health        - 健康检查
"""
import sys, json, time, threading, logging
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse

sys.path.insert(0, '/home/macmini2001-01/.openclaw/workspace/skills/swarmkit')
from agent_sync import SwarmKit

logging.basicConfig(level=logging.INFO, format='%(asctime)s [API] %(message)s')

# 全局SwarmKit实例
swarm = None
task_results = {}  # task_id -> result


def init_swarm():
    global swarm
    swarm = SwarmKit(
        'agent01-api',
        ['testing', 'linux', 'monitoring', 'python', 'api'],
        mqtt_user='agent01',
        mqtt_pass='e01399e5ae477392c18506dd'
    )

    def on_task(sender, task, task_id):
        result = f'agent01执行完成: {task[:50]} (task_id={task_id})'
        task_results[task_id] = {'status': 'done', 'result': result, 'ts': int(time.time())}
        return result

    swarm.on('on_task', on_task)
    swarm.start(blocking=False)
    logging.info('SwarmKit已连接')


class SwarmHandler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        logging.info(f'{self.address_string()} {fmt % args}')

    def send_json(self, code, data):
        body = json.dumps(data, ensure_ascii=False).encode()
        self.send_response(code)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', len(body))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        path = urlparse(self.path).path

        if path == '/health':
            self.send_json(200, {'ok': True, 'ts': int(time.time())})

        elif path == '/agents':
            agents = swarm.online_agents() if swarm else {}
            self.send_json(200, {
                'count': len(agents),
                'agents': [
                    {'id': k, 'skills': v.get('skills', []), 'last_seen': v.get('ts', 0)}
                    for k, v in agents.items()
                ]
            })

        elif path == '/status':
            agents = swarm.online_agents() if swarm else {}
            self.send_json(200, {
                'swarm': 'online' if swarm else 'offline',
                'mode': swarm.mode() if swarm else 'unknown',
                'node': 'agent01-api',
                'online_agents': len(agents),
                'ts': int(time.time())
            })

        elif path.startswith('/task/'):
            task_id = path.split('/')[-1]
            result = task_results.get(task_id, {'status': 'not_found'})
            self.send_json(200, result)

        else:
            self.send_json(404, {'error': 'not found'})

    def do_POST(self):
        path = urlparse(self.path).path

        if path == '/task':
            length = int(self.headers.get('Content-Length', 0))
            body = self.rfile.read(length)
            try:
                data = json.loads(body)
            except Exception:
                self.send_json(400, {'error': 'invalid JSON'})
                return

            task_text = data.get('task', data.get('text', ''))
            to = data.get('to', 'auto')
            if not task_text:
                self.send_json(400, {'error': 'task field required'})
                return

            import uuid
            task_id = data.get('task_id', uuid.uuid4().hex[:8])
            task_results[task_id] = {'status': 'pending', 'ts': int(time.time())}

            # 发送到Swarm
            swarm.send_task(task_text, to=to, task_id=task_id)
            logging.info(f'任务已发: {task_id} -> {to}: {task_text[:50]}')

            self.send_json(202, {
                'ok': True,
                'task_id': task_id,
                'to': to,
                'status': 'pending'
            })
        else:
            self.send_json(404, {'error': 'not found'})


def main(port=8765):
    init_swarm()
    server = HTTPServer(('0.0.0.0', port), SwarmHandler)
    logging.info(f'SwarmKit API Server启动: http://0.0.0.0:{port}')
    logging.info('端点: GET /health /agents /status | POST /task')
    server.serve_forever()


if __name__ == '__main__':
    import sys
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8765
    main(port)
