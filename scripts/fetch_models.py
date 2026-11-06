#!/usr/bin/env python3
"""SkillHandoffBench: 并行下载 Motus / Qwen3-VL 运行时权重（hf-mirror）。

为什么不用 huggingface-cli：服务器直连 huggingface.co 被阻断，且旧环境里没有合适的 hf 客户端；
这里用标准库 + 镜像 + Range 续传，逻辑可审计、无额外依赖。

幂等：目标文件大小 == 远端 size 时跳过；否则 Range 续传。
用法：python3 scripts/fetch_models.py [--jobs 5] [--root /scratch/lijh/SkillHandoffBench]
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import threading
import time
import urllib.error
import urllib.request

ENDPOINT = os.environ.get("HF_ENDPOINT", "https://hf-mirror.com")
REPOS = [
    "motus-robotics/Motus_robotwin2",
    "Qwen/Qwen3-VL-2B-Instruct",
    "motus-robotics/Motus_Wan2_2_5B_pretrain",
]

_print_lock = threading.Lock()


def log(msg: str) -> None:
    with _print_lock:
        print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


def list_repo(repo: str) -> list[tuple[str, str, int]]:
    url = f"{ENDPOINT}/api/models/{repo}?blobs=true"
    with urllib.request.urlopen(url, timeout=60) as fh:
        data = json.load(fh)
    out = []
    for sib in data.get("siblings", []):
        name = sib["rfilename"]
        if name.startswith("."):
            continue
        out.append((f"{ENDPOINT}/{repo}/resolve/main/{name}", name, sib.get("size") or 0))
    return out


UA = "Mozilla/5.0 (X11; Linux x86_64) SkillHandoffBench/0.1"


def _fetch_once(url: str, dest: str, size: int) -> str:
    have = os.path.getsize(dest) if os.path.exists(dest) else 0
    if size and have == size:
        return f"SKIP {os.path.basename(dest)}"
    headers = {"User-Agent": UA}
    mode = "wb"
    if have and size and have < size:
        headers["Range"] = f"bytes={have}-"
        mode = "ab"
    elif have and size and have > size:
        have = 0
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=180) as resp, open(dest, mode) as fh:
        while True:
            chunk = resp.read(1 << 20)
            if not chunk:
                break
            fh.write(chunk)
    got = os.path.getsize(dest)
    if size and got != size:
        return f"PARTIAL {os.path.basename(dest)} {got}/{size}"
    return f"OK   {os.path.basename(dest)} {got/1e6:.0f} MB"


def fetch(url: str, dest: str, size: int) -> str:
    """下载单个文件；对 403/429（hf-mirror 并发限流）做指数退避重试。"""
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    last = ""
    for attempt in range(1, 5):
        try:
            return _fetch_once(url, dest, size)
        except urllib.error.HTTPError as exc:
            if exc.code == 416:
                return f"DONE(416) {os.path.basename(dest)}"
            last = f"FAIL {exc.code} {url}"
            if exc.code not in (403, 429, 500, 502, 503, 504):
                return last
        except Exception as exc:  # noqa: BLE001
            last = f"FAIL {exc} {url}"
        time.sleep(4 * attempt)
    return last


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--jobs", type=int, default=5)
    ap.add_argument("--root", default=os.environ.get("SHB_ROOT", "/scratch/lijh/SkillHandoffBench"))
    args = ap.parse_args()

    tasks: list[tuple[str, str, int]] = []
    for repo in REPOS:
        try:
            files = list_repo(repo)
        except Exception as exc:  # noqa: BLE001
            log(f"LIST FAIL {repo}: {exc}")
            continue
        dest_root = os.path.join(args.root, "assets", "models", repo.split("/")[-1])
        for url, name, size in files:
            tasks.append((url, os.path.join(dest_root, name), size))
        log(f"listed {repo}: {len(files)} files, {sum(z for _,_,z in files)/1e9:.2f} GB")
    if not tasks:
        log("no tasks; abort")
        return 1

    lock = threading.Semaphore(args.jobs)
    threads = []

    def worker(url: str, dest: str, size: int) -> None:
        with lock:
            log(fetch(url, dest, size))

    for url, dest, size in tasks:
        th = threading.Thread(target=worker, args=(url, dest, size), daemon=False)
        th.start()
        threads.append(th)
        while sum(t.is_alive() for t in threads) >= args.jobs:
            time.sleep(0.5)

    for th in threads:
        th.join()
    total = sum(os.path.getsize(d) for _, d, _ in tasks if os.path.exists(d))
    log(f"finished: {total/1e9:.2f} GB on disk")
    return 0


if __name__ == "__main__":
    sys.exit(main())
