# 一线 · 厦门漆线雕

> 一根漆泥搓成的线，三百年来第一次自己开口说话。
> **179.5 秒 / 1920×1080 / 24fps / H.264 + AAC / 中文旁白与字幕**

「云创福建」AIGC 创作大赛 · 方向 ② 非遗文化 参赛片。

- 成片：`out/yixian.mp4`
- 阅稿页：<https://hkmpn9s6dh-commits.github.io/hackathon-2026-yixian/>
- 赛事简报：`docs/00-BRIEF.md`｜史实与出处：`docs/01-STORY.md`

---

## 这是什么

漆线雕是把漆泥搓成"线"，再把线盘、结、绕、堆成浮雕的手艺（国家级非遗，Ⅷ-55，2006 年第一批）。
片子不讲大师生平，不讲工艺全景，**只讲那根线**——用第一人称让它自己说：

| 段落 | 台词（节选） |
| --- | --- |
| 起 | 我叫线。不是画上去的，是站上去的。 |
| 材 | 砖要陈的，漆要生的，桐油要熟的。 |
| 神 | 三百年，我只绕神。甲是线，云是线。 |
| 变 | 一九七二年，蔡水况把我从神像上剥离下来。 |
| 金 | 金比蝉翼还薄，一口气就吹跑了。 |
| 名 | 一九七三年，广交会上有人问：这叫什么？ |
| 合 | 我藏头，收尾。不让人看出，我从哪儿起，到哪儿止。 |

全片 20 镜。**16 处转场全部由同一条"金线"完成**：线先落进画面，图形再沿着"到线的距离"从线向两边绽开。

## 怎么跑

```bash
pip install -r requirements.txt          # numpy / Pillow / fonttools / edge-tts
bash verify.sh                            # 一键：依赖 → 图版 → 分镜表 → 成片 → 40+ 条断言 → 证据帧
```

只想重建片子：

```bash
py -3 scripts/build.py                    # 声音 + 4308 帧（4 进程并行）+ 拼接 + 混音 + 压制，约 40 分钟
py -3 scripts/verify.py                   # 只跑断言
py -3 scripts/gen_shots.py                # 重新生成 docs/03-SHOTS.md 与 submission/分镜表.csv
py -3 scripts/stills.py                   # 生成 proof/ 下的联系表与转场连拍
```

## 结构

```
story.py                 ★ 唯一真源：图版提示词 / 20 镜 / 19 句台词 / 音效表
scripts/render.py        逐帧渲染：取样窗运镜 + 金线场转场 + 颗粒/暗角/字幕
scripts/audio.py         edge-tts 旁白 + numpy 合成音效与配乐 + ducking + 响度对齐
scripts/build.py         一条命令从零到成片
scripts/verify.py        闸 C：40+ 条断言（规格/字幕/画面/水印/声音/字体）
scripts/gen_shots.py     从 story.py 生成分镜表（--check 反向核对）
scripts/stills.py        proof/ 证据帧
assets/plates/P00–P17    18 张图版（生成物，随仓库提交，保证 1:1 复现）
assets/fonts/            Noto Serif SC + 马善政毛笔楷书（OFL）
docs/00–07               赛事 / 史实 / 视觉 / 分镜 / 证据 / 投稿 / AIGC 说明 / 闸 D
proof/                   verify.log、联系表、转场连拍、盲评记录
submission/              作品简介、创作说明、推荐表、分镜表、封面
```

## 四道闸

| 闸 | 状态 | 证据 |
| --- | --- | --- |
| A 共识 | ✅ | `SPEC.md`、`docs/01-STORY.md`（十条可引用事实）、`docs/02-STYLE.md` |
| B 流程 | ✅ | 先写断言再出片：`scripts/verify.py` 40+ 条，其中"开场 1s 必须有金线"当场否掉了原来 13s 的黑场开场 |
| C 能用 | ✅ | `proof/verify.log`：本机全绿 + 全新 clone 全绿 |
| D 第一眼 | 见 `docs/07-GATE-D.md` | 六帧盲读 + 尺子盲排 |

## 原则

- **史实不编**：片子里的年份与人名都能在 `ihchina.cn`、央视、中新网、厦门市文化馆找到原文；核不到的不写。
- **AI 只用在一处**：18 张图版。运镜、转场、颗粒、字幕、配乐、音效全部是代码算出来的，逐帧可复现。
- **判据先于审美**：每个"好看"的要求都落成一条断言，跑不过就不许交。

## 许可

代码 MIT。图版由本仓库作者用 AI 生成，随仓库提供以便复现。字体为 SIL Open Font License（见 `assets/fonts/LICENSE.md`）。
