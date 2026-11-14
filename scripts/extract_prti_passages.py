"""从缓存的论文文本中抽取 PRTI 相关段落（Phase B1 审计用，只读）。"""
import os
import re

SRC = os.path.join(os.environ.get("TEMP", "/tmp"), "rc_copy.txt")
OUT = os.path.join(os.environ.get("TEMP", "/tmp"), "prti_passages.txt")

text = open(SRC, encoding="utf-8", errors="ignore").read()
text = re.sub(r"\s+", " ", text)

chunks = [f"LEN {len(text)}"]
for kw in ("Pose Robust Task Initialization", "PRTI"):
    idxs = [m.start() for m in re.finditer(re.escape(kw), text)]
    chunks.append(f"\n===== {kw}: {len(idxs)} hits =====")
    seen, n = set(), 0
    for i in idxs:
        bucket = i // 900
        if bucket in seen:
            continue
        seen.add(bucket)
        n += 1
        if n > 16:
            break
        chunks.append(f"\n--- hit {i} ---")
        chunks.append(text[max(0, i - 700):i + 1100])

open(OUT, "w", encoding="utf-8").write("\n".join(chunks))
print("wrote", OUT, os.path.getsize(OUT), "bytes")
