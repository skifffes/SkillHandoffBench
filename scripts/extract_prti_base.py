"""抽取论文中与 PRTI 基座模型/Table 2 相关的段落（Phase B1）。"""
import os
import re

SRC = os.path.join(os.environ.get("TEMP", "/tmp"), "rc_copy.txt")
OUT = os.path.join(os.environ.get("TEMP", "/tmp"), "prti_base.txt")
text = re.sub(r"\s+", " ", open(SRC, encoding="utf-8", errors="ignore").read())

chunks = []
for kw in ("Table 2", "base atomic policy", "0.5", "atomic post-training"):
    idxs = [m.start() for m in re.finditer(re.escape(kw), text)]
    chunks.append(f"\n===== {kw}: {len(idxs)} hits =====")
    seen, n = set(), 0
    for i in idxs:
        b = i // 1200
        if b in seen:
            continue
        seen.add(b)
        n += 1
        if n > 6:
            break
        chunks.append(f"\n--- hit {i} ---")
        chunks.append(text[max(0, i - 600):i + 900])

open(OUT, "w", encoding="utf-8").write("\n".join(chunks))
print("wrote", OUT, os.path.getsize(OUT))
