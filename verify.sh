#!/usr/bin/env bash
# 一条命令把这部片子从头验一遍。全新 clone 只需要 python + ffmpeg + pip install -r requirements.txt
set -euo pipefail
cd "$(dirname "$0")"

PY=${PY:-py -3}
command -v py >/dev/null 2>&1 || PY=python3

echo "== 0. 依赖 =="
$PY - <<'EOF'
import importlib.util, sys
need = ["numpy", "PIL", "fontTools", "edge_tts"]
miss = [m for m in need if importlib.util.find_spec(m) is None]
if miss:
    sys.exit("缺依赖：" + ", ".join(miss) + "\n  pip install -r requirements.txt")
print("依赖齐")
EOF
command -v ffmpeg >/dev/null 2>&1 || { echo "缺 ffmpeg（PATH 里找不到）"; exit 1; }

echo "== 1. 图版与字体 =="
$PY - <<'EOF'
import os, sys
sys.path.insert(0, ".")
import story as S
miss = [k for k in S.PLATES if not os.path.exists(f"assets/plates/{k}.png")]
if miss:
    sys.exit("缺图版：" + ", ".join(miss))
for f in ["NotoSerifSC-VF.ttf", "MaShanZheng.ttf"]:
    if not os.path.exists(f"assets/fonts/{f}"):
        sys.exit("缺字体 " + f)
print(f"图版 {len(S.PLATES)} 张、字体 2 套")
EOF

echo "== 2. 分镜表与 story.py 是否一致 =="
$PY scripts/gen_shots.py --check

echo "== 3. 成片 =="
if [ ! -f out/yixian.mp4 ]; then
  echo "   out/yixian.mp4 不存在，现在从头构建（约 40 分钟，4 进程并行）"
  $PY scripts/build.py
fi

echo "== 4. 闸 C 逐条 =="
$PY scripts/verify.py

echo "== 5. 证据帧 =="
$PY scripts/stills.py

echo
echo "全部通过。"
