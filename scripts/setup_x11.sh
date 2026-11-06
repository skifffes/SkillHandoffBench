#!/usr/bin/env bash
# SkillHandoffBench: 在用户空间补齐 SAPIEN 需要的 X11 运行库（不需要 root）。
#
# 为什么：sapien 3.0.0b1 的 pysapien 直接链 libX11.so.6，而本机是 **纯 headless**
# CentOS 7（/usr/lib64 里没有任何 libX*）。我们不改系统，只把 CentOS 7.9 官方 RPM
# 解包到 $ROOT/envs/xlib，然后通过 LD_LIBRARY_PATH 注入。
#
# 版本注意：libX11 在 vault 里 `os/` 只有 1.6.7-2，1.6.7-5 在 `updates/`。
# 脚本对每个包按 os → updates 的顺序尝试（先探测 HTTP 200）。
#
# 用法：bash scripts/setup_x11.sh
set -uo pipefail
ROOT="${SHB_ROOT:-/scratch/lijh/SkillHandoffBench}"
DEST="$ROOT/envs/xlib"
WORK="$ROOT/envs/_rpm"
BASE="https://mirrors.aliyun.com/centos-vault/7.9.2009"
mkdir -p "$DEST" "$WORK"
say() { printf '[%s] %s\n' "$(date +%H:%M:%S)" "$*"; }

PKGS="
libX11-1.6.7-5.el7_9.x86_64.rpm
libXau-1.0.8-2.1.el7.x86_64.rpm
libXdmcp-1.1.2-6.el7.x86_64.rpm
libxcb-1.13-1.el7.x86_64.rpm
libXext-1.3.3-3.el7.x86_64.rpm
libXrender-0.9.10-1.el7.x86_64.rpm
libXfixes-5.0.3-1.el7.x86_64.rpm
libXrandr-1.5.1-2.el7.x86_64.rpm
libXcursor-1.1.15-1.el7.x86_64.rpm
libXinerama-1.1.3-2.1.el7.x86_64.rpm
libXi-1.7.9-1.el7.x86_64.rpm
libSM-1.2.2-2.el7.x86_64.rpm
libICE-1.0.9-9.el7.x86_64.rpm
"

fetch() {  # pkg -> path or fail
  local pkg="$1" repo url code
  for repo in os updates; do
    url="$BASE/$repo/x86_64/Packages/$pkg"
    code=$(curl -s -o /dev/null -w '%{http_code}' --max-time 20 "$url")
    if [ "$code" = "200" ]; then
      curl -sL --fail --retry 3 -o "$WORK/$pkg" "$url" && echo "$WORK/$pkg" && return 0
    fi
  done
  return 1
}

for pkg in $PKGS; do
  if f=$(fetch "$pkg"); then
    say "got $pkg"
    ( cd "$DEST" && rpm2cpio "$f" | cpio -idm --quiet 2>/dev/null ) && say "extract $pkg"
  else
    say "FAIL $pkg"
  fi
done

echo "--- libs in $DEST/usr/lib64 ---"
ls -1 "$DEST/usr/lib64" 2>/dev/null | head -30
