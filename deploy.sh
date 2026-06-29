#!/bin/bash
# 新媒体数据平台 - 快速部署脚本
# 用法: bash deploy.sh

set -e

echo "========================================"
echo "新媒体数据平台 - 快速部署"
echo "========================================"

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
DEPLOY_DIR="$SCRIPT_DIR/../newmedia-deploy"

# 1. 同步文件到部署目录
echo ""
echo "[1/3] 同步文件到部署目录..."
cp -r "$SCRIPT_DIR/public/"* "$DEPLOY_DIR/"
echo "  ✅ 文件同步完成"

# 2. 推送到 GitHub
echo ""
echo "[2/3] 推送到 GitHub..."
cd "$DEPLOY_DIR"
git add -A
if git diff --cached --quiet; then
    echo "  ⏭️ 没有变更，跳过提交"
else
    git commit -m "update: $(date +%Y-%m-%d_%H:%M)"
    git push
    echo "  ✅ GitHub 推送完成"
fi

# 3. 提示
echo ""
echo "[3/3] 部署完成！"
echo "  📦 CloudStudio: 需要手动部署或等待自动任务"
echo "  🌐 GitHub Pages: https://wufrancis16-sketch.github.io/newmedia"
echo ""
echo "========================================"
