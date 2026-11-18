# PROOF —《一线》证据索引

> 一句话：**每一条验收都有一条命令能跑出来。** 想自己验：`bash verify.sh`。

## 一、成片

| 项 | 值 | 怎么来的 |
| --- | --- | --- |
| 文件 | `out/yixian.mp4` | `py -3 scripts/build.py` |
| 时长 | 179.50 s（2 分 59.5 秒） | ffprobe，与 `story.py` 推导值一致（AC-1b） |
| 画幅/帧率 | 1920×1080 / 24fps | ffprobe（AC-2） |
| 编码 | H.264 High / yuv420p + AAC 192k 48kHz 立体声 | ffprobe（AC-3/5b） |
| 帧数 | 4308 | `story.py` |
| 镜头 | 20 + 片名卡 6s | `docs/03-SHOTS.md`（脚本生成） |
| 图版 | 18 张，全部用到 | AC-10e/f |

## 二、脚本自证

| 证据 | 命令 |
| --- | --- |
| 40+ 条断言逐条 PASS/FAIL | `py -3 scripts/verify.py` → `proof/verify.log` |
| 容器摘要 | `proof/container.json` |
| 分镜表与代码一致 | `py -3 scripts/gen_shots.py --check` |
| 20 镜联系表 | `proof/contact-sheet.jpg` |
| 线转场 6 连拍 | `proof/transition-strip.jpg` |

## 三、闸 D（第一眼）

见 `docs/07-GATE-D.md`。判据与结果都记在那里，包括**没过线的轮次**。

## 四、全新 clone

`proof/clone-verify.log`：从 `git clone` 开始，只照 README 跑 `bash verify.sh`，
它会从头重建成片（约 40 分钟）再跑全部断言。
