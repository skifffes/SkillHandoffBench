#!/usr/bin/env bash
# SkillHandoffBench: 下载 RoboTwin2 资产与 Motus 运行时权重（只写 SHB 自己的目录，不碰 Simulate）。
# 设计：hf-mirror.com 镜像（服务器直连 huggingface.co 被阻断，实测 hf-mirror 可达）。
# 幂等：curl -C - 断点续传；已完成的文件会被跳过。
# 用法：bash scripts/fetch_assets.sh [assets|models|all]
set -uo pipefail

ROOT="${SHB_ROOT:-/scratch/lijh/SkillHandoffBench}"
DL="$ROOT/assets/_downloads"
MODELS="$ROOT/assets/models"
LOGD="$ROOT/logs"
export HF_ENDPOINT="${HF_ENDPOINT:-https://hf-mirror.com}"
mkdir -p "$DL" "$MODELS" "$LOGD"

say() { printf '[%s] %s\n' "$(date +%H:%M:%S)" "$*"; }

# dl <url> <outfile>
dl() {
  local url="$1" out="$2"
  mkdir -p "$(dirname "$out")"
  if [ -f "$out" ]; then
    # 若远端有 Content-Length 则比较；简化：仅当文件非空且 curl 返回 416 时视为完成
    :
  fi
  curl -L --fail --retry 5 --retry-delay 5 --connect-timeout 30 -C - -o "$out" "$url" \
    && say "OK   $(basename "$out") ($(du -h "$out" | cut -f1))" \
    || say "FAIL $url"
}

# 用 HF API 列出 repo 文件，逐个下载（跳过纯文本小文件里的大仓库元数据）
list_repo() {  # <type:models|datasets> <repo>
  local type="$1" repo="$2"
  curl -s "$HF_ENDPOINT/api/$type/$repo?blobs=true" \
    | "${SHB_PY:-/scratch/lijh/simulate_vla/venv/bin/python}" -c '
import json,sys
d=json.load(sys.stdin)
for s in d.get("siblings",[]):
    n=s["rfilename"]
    if n.startswith("."): continue
    print("%d\t%s" % ((s.get("size") or 0), n))
'
}

fetch_assets() {
  say "=== RoboTwin2 assets (≈14.9 GB) -> $DL ==="
  local base="$HF_ENDPOINT/datasets/TianxingChen/RoboTwin2.0/resolve/main"
  for f in background_texture.zip embodiments.zip objects.zip; do
    dl "$base/$f" "$DL/$f" &
  done
  wait
  say "=== unzip assets -> $ROOT/third_party/RoboCombine/assets ==="
  local A="$ROOT/third_party/RoboCombine/assets"
  mkdir -p "$A"
  for f in background_texture embodiments objects; do
    if [ -f "$DL/$f.zip" ]; then
      say "unzip $f.zip"
      unzip -q -o "$DL/$f.zip" -d "$A" 2>&1 | tail -2
    fi
  done
  ls -la "$A"
}

fetch_models() {
  say "=== Motus_robotwin2 (16.0 GB) ==="
  list_repo models motus-robotics/Motus_robotwin2 | while IFS=$'\t' read -r size name; do
    dl "$HF_ENDPOINT/motus-robotics/Motus_robotwin2/resolve/main/$name" "$MODELS/motus_robotwin2/$name"
  done
  say "=== Qwen3-VL-2B-Instruct (4.3 GB) ==="
  list_repo models Qwen/Qwen3-VL-2B-Instruct | while IFS=$'\t' read -r size name; do
    dl "$HF_ENDPOINT/Qwen/Qwen3-VL-2B-Instruct/resolve/main/$name" "$MODELS/Qwen3-VL-2B-Instruct/$name"
  done
  say "=== Motus_Wan2_2_5B_pretrain (10.0 GB) ==="
  list_repo models motus-robotics/Motus_Wan2_2_5B_pretrain | while IFS=$'\t' read -r size name; do
    dl "$HF_ENDPOINT/motus-robotics/Motus_Wan2_2_5B_pretrain/resolve/main/$name" "$MODELS/Motus_Wan2_2_5B_pretrain/$name"
  done
}

case "${1:-all}" in
  assets) fetch_assets ;;
  models) fetch_models ;;
  all) fetch_assets; fetch_models ;;
  *) echo "usage: $0 [assets|models|all]"; exit 2 ;;
esac
say "done"
