"""CPU 单测：protocol lock 校验脚本的核心逻辑（不联网、不需要 GPU）。

跑法：python -m pytest tests/test_protocol_lock.py -q
或：  python tests/test_protocol_lock.py
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPT = os.path.join(ROOT, "scripts", "check_protocol_lock.py")


def run_checker(root: str):
    return subprocess.run(
        [sys.executable, SCRIPT, "--root", root],
        capture_output=True, text=True, timeout=120,
    )


class TestProtocolLock(unittest.TestCase):
    def test_real_repo_passes(self):
        """真实仓库应当全部 PASS（若失败，说明锁文件与代码已不一致）。"""
        r = run_checker(ROOT)
        self.assertEqual(r.returncode, 0, msg=r.stdout + r.stderr)
        self.assertIn("0 failed", r.stdout)

    def test_detects_tampered_spec(self):
        """篡改 spec 的 episodes 默认值必须被检出。"""
        with tempfile.TemporaryDirectory() as tmp:
            repo = os.path.join(tmp, "third_party", "RoboCombine")
            for sub in ("handoff_eval/specs", "task_config"):
                os.makedirs(os.path.join(repo, sub), exist_ok=True)
            os.makedirs(os.path.join(tmp, "configs"), exist_ok=True)
            # 复制真实锁文件与必要文件
            import shutil
            shutil.copy(os.path.join(ROOT, "configs", "robocombine_public_protocol_lock.yaml"),
                        os.path.join(tmp, "configs"))
            src_spec = os.path.join(ROOT, "third_party", "RoboCombine", "handoff_eval", "specs", "robocombine.json")
            shutil.copy(src_spec, os.path.join(repo, "handoff_eval", "specs"))
            shutil.copy(os.path.join(ROOT, "third_party", "RoboCombine", "task_config", "robocombine_eval.yml"),
                        os.path.join(repo, "task_config"))
            # 篡改 episodes 默认值
            spec_path = os.path.join(repo, "handoff_eval", "specs", "robocombine.json")
            d = json.load(open(spec_path, encoding="utf-8"))
            d["default_episodes"] = 7
            json.dump(d, open(spec_path, "w", encoding="utf-8"))
            r = run_checker(tmp)
            self.assertNotEqual(r.returncode, 0, msg=r.stdout)
            self.assertIn("spec 默认 episodes = 5", r.stdout)
            self.assertIn("FAIL", r.stdout)

    def test_detects_missing_command_flag(self):
        """command.sh 缺 --clear_cache false 必须被检出。"""
        with tempfile.TemporaryDirectory() as tmp:
            repo = os.path.join(tmp, "third_party", "RoboCombine")
            for sub in ("handoff_eval/specs", "task_config"):
                os.makedirs(os.path.join(repo, sub), exist_ok=True)
            os.makedirs(os.path.join(tmp, "configs"), exist_ok=True)
            task_dir = os.path.join(tmp, "results", "paper_table1", "x", "tasks", "t")
            os.makedirs(task_dir, exist_ok=True)
            import shutil
            shutil.copy(os.path.join(ROOT, "configs", "robocombine_public_protocol_lock.yaml"),
                        os.path.join(tmp, "configs"))
            shutil.copy(os.path.join(ROOT, "third_party", "RoboCombine", "handoff_eval", "specs", "robocombine.json"),
                        os.path.join(repo, "handoff_eval", "specs"))
            shutil.copy(os.path.join(ROOT, "third_party", "RoboCombine", "task_config", "robocombine_eval.yml"),
                        os.path.join(repo, "task_config"))
            with open(os.path.join(task_dir, "command.sh"), "w", encoding="utf-8") as fh:
                fh.write("python script/eval_policy.py --episode_num 20\n")  # 缺 --clear_cache false
            r = run_checker(tmp)
            self.assertNotEqual(r.returncode, 0, msg=r.stdout)
            self.assertIn("--clear_cache false", r.stdout)


if __name__ == "__main__":
    unittest.main(verbosity=2)
