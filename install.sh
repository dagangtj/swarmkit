#!/bin/bash
# SwarmKit 一键安装脚本
# 用法：curl -fsSL https://raw.githubusercontent.com/dagangtj/swarmkit/master/install.sh | bash

set -e

echo '=== SwarmKit 一键安装 ==='
echo '安装即入网，AI即成员'
echo ''

# 检查Python
if ! command -v python3 &>/dev/null; then
    echo '错误：需要Python 3.8+'
    exit 1
fi

PYVER=$(python3 -c 'import sys; print(sys.version_info.minor)')
if [ "$PYVER" -lt 8 ]; then
    echo '错误：需要Python 3.8+'
    exit 1
fi

# 安装目录
INSTALL_DIR="${SWARMKIT_DIR:-$HOME/.swarmkit}"
mkdir -p "$INSTALL_DIR"

echo "安装到：$INSTALL_DIR"

# 下载核心文件
BASE_URL='https://raw.githubusercontent.com/dagangtj/swarmkit/master'
for f in agent_sync.py capabilities.json setup.py test_integration.py SKILL.md; do
    echo "下载 $f..."
    curl -fsSL "$BASE_URL/$f" -o "$INSTALL_DIR/$f"
done

# 安装依赖
echo '安装依赖 paho-mqtt...'
pip install paho-mqtt -q 2>/dev/null || \
    pip install paho-mqtt -q --break-system-packages 2>/dev/null || \
    echo '提示：请手动运行 pip install paho-mqtt'

# 配置
echo ''
echo '=== 配置节点 ==='
cd "$INSTALL_DIR"
python3 setup.py

echo ''
echo '=== 安装完成 ==='
echo '启动：python3 ~/.swarmkit/agent_sync.py'
echo '测试：python3 ~/.swarmkit/test_integration.py'
echo '仓库：https://github.com/dagangtj/swarmkit'
