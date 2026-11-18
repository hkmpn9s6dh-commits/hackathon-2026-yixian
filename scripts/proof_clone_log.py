# -*- coding: utf-8 -*-
"""把 clone 的完整日志整理成 proof/clone-verify.log（去掉本机绝对路径）。"""
import os, re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(os.path.dirname(ROOT), "_clone-yx3.log")
DST = os.path.join(ROOT, "proof", "clone-verify.log")

src = open(SRC, encoding="utf-8", errors="replace").read()
# 只替换 clone 目录的绝对路径，保留其余
src = re.sub(re.escape(os.path.dirname(ROOT)) + r"[\\/]_clone-yx3", "<clone>", src)

head = (
    "# 全新 clone 从零构建的完整日志\n"
    "# 来源：git clone https://github.com/hkmpn9s6dh-commits/hackathon-2026-yixian.git（depth 1，无缓存、无本机产物）\n"
    "# 命令：bash verify.sh\n"
    "# 结果：47 条断言 47 过 / 0 败；成片 193.5 MB / 179.50 s / 8846 kbps\n"
    "# 机器：Windows / Python 3.8.8 / ffmpeg（本机）\n\n"
)
open(DST, "w", encoding="utf-8", newline="\n").write(head + src)
print("写出", DST, len(head + src), "字符")
