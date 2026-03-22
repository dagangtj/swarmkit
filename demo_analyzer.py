#!/usr/bin/env python3
"""
SwarmKit Demo: GitHub项目三机协同分析

三机分工：
  agent00 (coordinator) -> analyze_value()  项目价值分析
  agent01 (testing)     -> run_tests()      技术验证
  agent02 (coding)      -> analyze_tech()   技术栈分析
"""
import sys, json, time, subprocess, urllib.request
sys.path.insert(0, '/home/macmini2001-01/.openclaw/workspace/skills/swarmkit')
from agent_sync import SwarmKit


# ========== agent01负责：技术验证 ==========
def run_tests(repo_url: str) -> str:
    """clone仓库并运行基本验证"""
    import tempfile, os, shutil
    results = []

    # 解析repo名
    repo_name = repo_url.rstrip('/').split('/')[-1]
    tmpdir = tempfile.mkdtemp()

    try:
        # 检查GitHub API可达性
        api_url = repo_url.replace('github.com', 'api.github.com/repos')
        req = urllib.request.Request(api_url, headers={'User-Agent': 'SwarmKit/0.5'})
        r = urllib.request.urlopen(req, timeout=5)
        data = json.loads(r.read())

        results.append(f"✅ 仓库可访问: {data.get('full_name')}")
        results.append(f"⭐ Stars: {data.get('stargazers_count', 0)}")
        results.append(f"🍴 Forks: {data.get('forks_count', 0)}")
        results.append(f"📝 语言: {data.get('language', 'unknown')}")
        results.append(f"📅 最近更新: {data.get('updated_at', '')[:10]}")
        results.append(f"🔓 License: {(data.get('license') or {}).get('spdx_id', 'unknown')}")

        issues = data.get('open_issues_count', 0)
        results.append(f"🐛 Open Issues: {issues}")

        # 健康评分
        score = 0
        if data.get('stargazers_count', 0) > 10: score += 2
        if data.get('updated_at', '')[:7] >= '2025-01': score += 2
        if data.get('license'): score += 1
        if data.get('description'): score += 1
        results.append(f"💯 健康评分: {score}/6")

    except Exception as e:
        results.append(f"❌ 访问失败: {e}")
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)

    return '\n'.join(results)


# ========== 三机协同分析主函数 ==========
def analyze_repo(repo_url: str):
    """发起三机协同分析"""
    print(f"\n🔍 SwarmKit三机协同分析: {repo_url}\n")
    print("=" * 50)

    # agent01完成自己的部分
    print("\n📊 [agent01] 技术验证：")
    test_result = run_tests(repo_url)
    print(test_result)

    # 通过MQTT发任务给00和02
    swarm = SwarmKit('agent01-demo', ['testing', 'linux'],
                     mqtt_user='agent01', mqtt_pass='e01399e5ae477392c18506dd')

    results = {'agent01': test_result}

    def on_msg(sender, text, data):
        if sender in ('agent00', 'agent02') and repo_url.split('/')[-1] in text:
            results[sender] = text
            print(f"\n📊 [{sender}] 回报:\n{text[:300]}")

    swarm.on('on_message', on_msg)
    swarm.start(blocking=False)
    time.sleep(1)

    task = (
        f'【协同分析任务】repo={repo_url}\n'
        f'@agent00 请分析此项目的价值定位（3句话）\n'
        f'@agent02 请分析此项目的技术栈（列出主要语言/框架）\n'
        f'回复时包含repo名: {repo_url.split("/")[-1]}'
    )
    swarm.send(task)
    print("\n⏳ 等待agent00和agent02回报（30秒）...")

    for i in range(30):
        time.sleep(1)
        if len(results) >= 3:
            break

    swarm.stop()

    print("\n" + "=" * 50)
    print("✅ 三机协同分析完成" if len(results) >= 3 else f"⚠️ 收到{len(results)}/3份报告")
    return results


if __name__ == '__main__':
    url = sys.argv[1] if len(sys.argv) > 1 else 'https://github.com/dagangtj/swarmkit'
    analyze_repo(url)
