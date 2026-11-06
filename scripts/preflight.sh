#!/usr/bin/env bash
# SkillHandoffBench 只读环境自检：不下载、不安装、不训练、不改任何已有文件。
# 用法：
#   bash scripts/preflight.sh              # 只检查本地
#   bash scripts/preflight.sh --server     # 通过 ssh 检查服务器（需要 SSH 密钥或 sshpass）
set -u

say() { printf '%s\n' "$*"; }
hr() { say "------------------------------------------------------------"; }

hr
say "== 1. 本地仓库/工作区 =="
if command -v git >/dev/null 2>&1; then
  git -C "$(dirname "$0")/.." rev-parse --short HEAD 2>/dev/null || say "NOT_A_GIT_REPO"
  git -C "$(dirname "$0")/.." status --short 2>/dev/null | head -20
else
  say "git: MISSING"
fi

hr
say "== 2. 目录结构 =="
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
for d in docs configs scripts results third_party; do
  if [ -d "$ROOT/$d" ]; then say "OK   $d"; else say "MISS $d"; fi
done
if [ -d "$ROOT/third_party/RoboCombine" ]; then
  say "OK   third_party/RoboCombine  ($(git -C "$ROOT/third_party/RoboCombine" rev-parse --short HEAD 2>/dev/null || echo 'no-git'))"
else
  say "MISS third_party/RoboCombine  -> Phase 0C 待执行（git clone）"
fi

hr
say "== 3. 本地配置 =="
[ -f "$ROOT/configs/resources.local.env" ] && say "OK   configs/resources.local.env（凭据，未入库）" \
  || say "MISS configs/resources.local.env -> cp configs/resources.example.env 并填值"

hr
say "== 4. 服务器（可选） =="
if [ "${1:-}" = "--server" ]; then
  HOST="${SHB_SSH_HOST:-222.29.51.96}"
  USER="${SHB_SSH_USER:-lijh}"
  ssh -o BatchMode=yes -o ConnectTimeout=8 "$USER@$HOST" '
    echo "host: $(hostname)  $(date)";
    echo "python3.10: $(/scratch/lijh/simulate_vla/venv/bin/python -V 2>&1)";
    echo "python3.11: $(/scratch/lijh/exp40/openpi/.venv/bin/python -V 2>&1)";
    echo "disk:"; df -h /scratch | tail -1;
    echo "gpu:"; nvidia-smi --query-gpu=index,name,memory.total,memory.used,utilization.gpu \
      --format=csv,noheader | head -5;
    echo "openpi assets:"; ls /scratch/lijh/.cache/openpi/openpi-assets/checkpoints/ 2>/dev/null;
    echo "robocombine:"; ls -d /scratch/lijh/SkillHandoffBench/third_party/RoboCombine 2>/dev/null \
      || echo "MISSING (待 clone)";
  ' 2>&1 || say "SSH 失败：检查密钥/密码（密码模式请用 sshpass 或旧项目 server/remote.py）"
else
  say "跳过（加 --server 检查服务器）"
fi

hr
say "preflight 完成（只读，无副作用）"
