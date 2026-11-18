# -*- coding: utf-8 -*-
"""闸 C 举证脚本：对着成片真跑一遍，不靠肉眼。

用法：
  py -3 scripts/verify.py                # 全部
  py -3 scripts/verify.py --video-only   # 只跑成片（不依赖图版/字体）
退出码即结论：0 = 全过。
"""
import os, sys, json, math, subprocess, tempfile, wave
import numpy as np
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)
import story as S

FAIL, OK = [], []
PROOF = os.path.join(ROOT, "proof")
os.makedirs(PROOF, exist_ok=True)
OUT = os.path.join(ROOT, "out", "yixian.mp4")

T_BODY = sum(s["dur"] for s in S.SHOTS)
T_TOTAL = T_BODY + S.ENDCARD


def check(name, cond, detail=""):
    (OK if cond else FAIL).append((name, detail))
    print(("  PASS  " if cond else "  FAIL  ") + name + ("   " + detail if detail else ""))
    return cond


def ffprobe(path):
    out = subprocess.check_output(["ffprobe", "-v", "error", "-print_format", "json",
                                   "-show_format", "-show_streams", path])
    return json.loads(out.decode("utf-8"))


def grab(path, t, size=None):
    with tempfile.TemporaryDirectory() as td:
        f = os.path.join(td, "f.png")
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-ss", f"{t:.3f}",
                        "-i", path, "-frames:v", "1", f], check=True)
        im = Image.open(f).convert("RGB")
    return im.resize(size, Image.LANCZOS) if size else im


def lum(im):
    return np.asarray(im.convert("L"), np.float32)


def gold_mask(arr):
    """金线/金箔：红高、绿中、蓝明显低，且整体够亮。"""
    r, g, b = arr[..., 0], arr[..., 1], arr[..., 2]
    return (r > 140) & (g > 95) & (r - b > 62) & (g - b > 35)


# ---------------------------------------------------------------- 成片规格
def verify_container():
    print("\n[成片]")
    if not check("AC-0 成片存在", os.path.exists(OUT), OUT):
        return None
    info = ffprobe(OUT)
    v = [s for s in info["streams"] if s["codec_type"] == "video"][0]
    a = [s for s in info["streams"] if s["codec_type"] == "audio"]
    dur = float(info["format"]["duration"])
    size = os.path.getsize(OUT)

    check("AC-1 时长 60–240s（赛规 1–4 分钟）", 60 <= dur <= 240, f"{dur:.2f}s")
    check("AC-1b 时长与 story.py 一致（±0.15s）", abs(dur - T_TOTAL) <= 0.15,
          f"{dur:.2f}s / 脚本 {T_TOTAL:.2f}s")
    check("AC-2 1920×1080", v["width"] == 1920 and v["height"] == 1080,
          f'{v["width"]}×{v["height"]}')
    check("AC-3 H.264 / yuv420p", v["codec_name"] == "h264" and v["pix_fmt"] == "yuv420p",
          f'{v["codec_name"]} / {v["pix_fmt"]}')
    check("AC-4 文件 ≤ 400MB", size <= 400 * 1024 ** 2, f"{size / 1024 / 1024:.1f} MB")
    check("AC-5 有音轨", bool(a), f"{len(a)} 条" if a else "无")
    if a:
        check("AC-5b AAC / 48kHz / 立体声",
              a[0]["codec_name"] == "aac" and int(a[0]["sample_rate"]) == 48000
              and int(a[0]["channels"]) == 2,
              f'{a[0]["codec_name"]} {a[0]["sample_rate"]}Hz {a[0]["channels"]}ch')

    p = subprocess.run(["ffmpeg", "-hide_banner", "-nostats", "-i", OUT,
                        "-af", "ebur128=peak=true", "-f", "null", "-"],
                       capture_output=True, text=True)
    txt = p.stderr
    tail = txt[txt.rfind("Summary:"):]
    I = LRA = PK = None
    for line in tail.splitlines():
        s = line.strip()
        if s.startswith("I:"):
            I = float(s.split()[1])
        if s.startswith("LRA:"):
            LRA = float(s.split()[1])
        if s.startswith("Peak:"):
            PK = float(s.split()[1])
    check("AC-5c 响度 −22…−12 LUFS", I is not None and -22 <= I <= -12, f"{I} LUFS")
    check("AC-5d 真峰 ≤ −1.0 dBFS", PK is not None and PK <= -1.0, f"{PK} dBFS")
    check("AC-5e 响度范围 LRA 4–24 LU", LRA is not None and 4 <= LRA <= 24, f"{LRA} LU")
    return dict(dur=dur, size=size, I=I, LRA=LRA, PK=PK,
                vbr=int(v.get("bit_rate", 0)) // 1000)


# ---------------------------------------------------------------- 时间轴与字幕
def verify_timeline():
    print("\n[时间轴 / 字幕]")
    starts, acc = [], 0.0
    for s in S.SHOTS:
        starts.append(acc)
        acc += s["dur"]
    check("AC-6a 镜头起点连续", all(abs((starts[i] + S.SHOTS[i]["dur"]) - starts[i + 1]) < 1e-9
                                    for i in range(len(starts) - 1)))
    check("AC-6b 时长和 = 全片 − 片名卡", abs(acc - T_BODY) < 1e-9,
          f"{acc:.2f}s / {T_BODY:.2f}s")
    check("AC-6c 镜头数 ≥ 16", len(S.SHOTS) >= 16, f"{len(S.SHOTS)} 个")

    subs = []
    for i, s in enumerate(S.SHOTS):
        if not s.get("sub"):
            continue
        t0 = starts[i] + 0.9
        t1 = starts[i] + s["dur"] - 0.7
        subs.append((s["sub"], t0, t1))
    check("AC-7a 字幕条数 ≥ 15", len(subs) >= 15, f"{len(subs)} 条")
    bad = [(a[0], b[0]) for i, a in enumerate(subs) for b in subs[i + 1:]
           if a[1] < b[2] and b[1] < a[2]]
    check("AC-7b 字幕不重叠", not bad, str(bad[:2]))
    short = [(x[0], round(x[2] - x[1], 2)) for x in subs if x[2] - x[1] < 1.2]
    check("AC-7c 每条停留 ≥ 1.2s", not short, str(short[:3]))
    out = [x[0] for x in subs if x[2] > T_TOTAL or x[1] < 0]
    check("AC-7d 全部落在成片时间轴内", not out, str(out[:2]))
    long_line = [(x[0], len(x[0])) for x in subs if len(x[0]) > 34]
    check("AC-7e 单行 ≤ 34 字（1920 宽不折行）", not long_line, str(long_line[:2]))

    rep = os.path.join(ROOT, "build", "vo.json")
    if os.path.exists(rep):
        vo = json.load(open(rep, encoding="utf-8"))
        over = [(v["text"], v["vo"], v["slot"]) for v in vo if v["vo"] > v["slot"] + 0.4]
        check("AC-7f 配音不超槽 +0.4s", not over, str(over[:2]))
        check("AC-7g 配音条数 = 有字幕镜头数", len(vo) == len(subs),
              f'{len(vo)} / {len(subs)}')
        tight = [v["text"] for v in vo if v["slot"] - v["vo"] < 0.6]
        check("AC-7h 每条配音余量 ≥ 0.6s", not tight, str(tight[:2]))


def verify_sub_on_screen():
    print("\n[字幕真的上屏]")
    if not os.path.exists(OUT):
        return check("AC-8a 成片存在", False)
    starts, acc = [], 0.0
    for s in S.SHOTS:
        starts.append(acc)
        acc += s["dur"]
    picks = []
    for i, s in enumerate(S.SHOTS):
        if s.get("sub"):
            picks.append((i, s["sub"], starts[i] + s["dur"] / 2))
    hits = 0
    for i, txt, t in (picks[3], picks[9], picks[-2]):
        arr = np.asarray(grab(OUT, t), np.float32)
        band = arr[1080 - 150:1080 - 70, 200:1720]     # 字幕带（见 render.subtitle）
        hi = (band.max(axis=2) > 210).mean()
        ok = hi > 0.003
        hits += ok
        check(f"AC-8b 第 {i} 镜字幕上屏（{txt[:8]}…）", ok, f"高亮像素 {hi * 100:.2f}%")
    check("AC-8c 抽 3 镜字幕全部可见", hits == 3, f"{hits}/3")


# ---------------------------------------------------------------- 画面
def warm_mask(arr):
    """"看得见的暖亮"：线芯被放大与颗粒柔化后不一定满足严格金色，用暖亮判据。"""
    r, g, b = arr[..., 0], arr[..., 1], arr[..., 2]
    return (r > 100) & (r - b > 30)


def verify_picture():
    print("\n[画面：第一眼与图版]")
    if not os.path.exists(OUT):
        return check("AC-9a 成片存在", False)

    # 开场不能像"播放失败"：判据不是某个魔法阈值，而是**线在变长**
    # （0.5s < 1s < 2s < 3s 的暖亮像素数严格递增），且 1 秒时已经有一条看得见的线头。
    cnt = {}
    for t in (0.5, 1.0, 2.0, 3.0):
        cnt[t] = int(warm_mask(np.asarray(grab(OUT, t), np.float32)).sum())
    inc = all(cnt[b] > cnt[a] for a, b in ((0.5, 1.0), (1.0, 2.0), (2.0, 3.0)))
    check("AC-9b 开场线在长（0.5→1→2→3s 暖亮像素严格递增）", inc, str(list(cnt.values())))
    check("AC-9c 第 1.0s 已有看得见的线头（暖亮像素 ≥ 500）", cnt[1.0] >= 500,
          f"{cnt[1.0]} px")
    a1 = np.asarray(grab(OUT, 1.0), np.float32)
    check("AC-9d 第 1.0s 有亮点（max R ≥ 200）", a1[..., 0].max() >= 200,
          f"{a1[..., 0].max():.0f}")
    check("AC-9e 第 1.0s 画面非全黑（p99 ≥ 25）", np.percentile(lum(grab(OUT, 1.0)), 99) >= 25,
          f"{np.percentile(lum(grab(OUT, 1.0)), 99):.0f}")

    # 每个镜头中点都不能是废帧
    starts, acc = [], 0.0
    for s in S.SHOTS:
        starts.append(acc)
        acc += s["dur"]
    dark = []
    for i, s in enumerate(S.SHOTS):
        p99 = np.percentile(lum(grab(OUT, starts[i] + s["dur"] * 0.55)), 99)
        if p99 < 45:
            dark.append((i, s["plate"], round(float(p99), 1)))
    check("AC-10a 每镜中点帧 p99 ≥ 45（无废帧）", not dark, str(dark[:3]))

    # 金线转场：转场中点抽帧，金线像素要有存在感
    trans = []
    for i, s in enumerate(S.SHOTS):
        tr = s.get("trans") or {}
        if tr.get("kind") == "line" and i > 0:
            trans.append((i, starts[i] + float(tr["dur"]) * 0.55))
    miss = []
    for i, t in trans[:6]:
        g = gold_mask(np.asarray(grab(OUT, t), np.float32)).mean()
        if g < 0.0008:
            miss.append((i, round(float(g) * 100, 3)))
    check("AC-10b 线转场里金线真的在场（抽 6 处）", not miss, str(miss))

    # 片名卡
    e = T_BODY + 4.6
    arr = np.asarray(grab(OUT, e), np.float32)
    band = arr[240:840, 360:1560]
    bright = (band.max(axis=2) > 170).mean()
    check("AC-10c 片名卡有文字（亮像素 ≥ 0.5%）", bright >= 0.005, f"{bright * 100:.2f}%")

    # 图版覆盖
    used = [s["plate"] for s in S.SHOTS]
    miss_plate = [p for p in used
                  if not os.path.exists(os.path.join(ROOT, "assets", "plates", p + ".png"))]
    check("AC-10d 每个镜头都有图版文件", not miss_plate, str(miss_plate))
    unused = [p for p in S.PLATES if p not in used]
    check("AC-10e 没有闲图版（18 张全用到）", not unused, str(unused))
    check("AC-10f 图版张数 = 18", len(S.PLATES) == 18, f"{len(S.PLATES)}")


def window_bottom(shot):
    """复制 render.window 的几何，返回取样窗在最坏时刻的 (右下角比例)。"""
    z0, z1 = shot["cam"]["z"]
    c0, c1 = shot["cam"]["c"]
    worst_r = worst_b = 0.0
    for k in range(0, 21):
        p = k / 20
        e = p * p * (3 - 2 * p)
        z = min(z0, z1) + (max(z0, z1) - min(z0, z1)) * 0     # 取最宽的一端
        for zz in (z0, z1, min(z0, z1)):
            cw = S.PW / max(zz, 1.0)
            ch = cw * S.H / S.W
            if ch > S.PH * S.SAFE_BOTTOM:
                ch = S.PH * S.SAFE_BOTTOM
                cw = ch * S.W / S.H
            cx = (c0[0] + (c1[0] - c0[0]) * e) * S.PW
            cy = (c0[1] + (c1[1] - c0[1]) * e) * S.PH
            cx = min(max(cx, cw / 2), S.PW - cw / 2)
            cy = min(max(cy, ch / 2), S.PH * S.SAFE_BOTTOM - ch / 2)
            worst_r = max(worst_r, (cx + cw / 2) / S.PW)
            worst_b = max(worst_b, (cy + ch / 2) / S.PH)
    return worst_r, worst_b


def verify_watermark():
    print("\n[工具水印避让]")
    check("AC-11a SAFE_BOTTOM ≤ 水印上沿 0.940", S.SAFE_BOTTOM <= 0.940, f"{S.SAFE_BOTTOM}")
    worst = []
    for i, s in enumerate(S.SHOTS):
        r, b = window_bottom(s)
        worst.append((i, round(r, 3), round(b, 3)))
    bad = [w for w in worst if w[2] > S.SAFE_BOTTOM + 1e-6]
    check("AC-11b 所有取样窗下边界 ≤ SAFE_BOTTOM", not bad, str(bad[:3]))
    # 成片里直接量：水印位（x≥0.92,y≥0.94）对应的画面区域应当没有"文字状"高亮
    if os.path.exists(OUT):
        arr = np.asarray(grab(OUT, T_BODY - 3.0), np.float32)
        corner = arr[int(1080 * 0.94):, int(1920 * 0.92):]
        hi = (corner.max(axis=2) > 150).mean()
        check("AC-11c 成片右下角无高亮水印残留", hi < 0.02, f"{hi * 100:.2f}%")


# ---------------------------------------------------------------- 声音
def verify_audio():
    print("\n[声音]")
    if not os.path.exists(OUT):
        return check("AC-12a 成片存在", False)
    with tempfile.TemporaryDirectory() as td:
        w = os.path.join(td, "a.wav")
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", OUT,
                        "-vn", "-ac", "1", "-ar", "16000", w], check=True)
        with wave.open(w) as f:
            sr = f.getframerate()
            x = np.frombuffer(f.readframes(f.getnframes()), dtype=np.int16).astype(np.float32) / 32768
    win = int(0.25 * sr)
    n = len(x) // win
    rms = np.array([np.sqrt((x[i * win:(i + 1) * win] ** 2).mean() + 1e-12) for i in range(n)])
    db = 20 * np.log10(rms + 1e-9)
    silent = db < -55
    # 最长连续静音
    run = best = 0
    for s in silent:
        run = run + 1 if s else 0
        best = max(best, run)
    check("AC-12b 无 > 3s 的静音段", best * 0.25 <= 3.0, f"最长 {best * 0.25:.2f}s")
    check("AC-12c 有对白级动态（p95 − p20 ≥ 8 dB）",
          np.percentile(db, 95) - np.percentile(db, 20) >= 8,
          f"{np.percentile(db, 95) - np.percentile(db, 20):.1f} dB")

    rep = os.path.join(ROOT, "build", "vo.json")
    if os.path.exists(rep):
        vo = json.load(open(rep, encoding="utf-8"))
        low = []
        for v in vo:
            t0 = v["t0"] + 0.25
            t1 = t0 + min(1.2, v["vo"] - 0.3)
            if t1 <= t0:
                continue
            seg = x[int(t0 * sr):int(t1 * sr)]
            if len(seg) < 100:
                continue
            lv = 20 * np.log10(np.sqrt((seg ** 2).mean()) + 1e-9)
            if lv < -34:
                low.append((v["shot"], round(float(lv), 1)))
        check("AC-12d 每条旁白处都有声音（≥ −34 dBFS）", not low, str(low[:3]))


# ---------------------------------------------------------------- 字体
def verify_fonts():
    print("\n[字体]")
    from fontTools.ttLib import TTFont
    use = {"serif": [], "brush": []}
    use["serif"] += [s["sub"] for s in S.SHOTS if s.get("sub")]
    use["serif"] += [S.SUBTITLE, "AIGC 生成画面 · 程序化运镜与合成"]
    use["brush"] += [S.TITLE]
    files = {"serif": "NotoSerifSC-VF.ttf", "brush": "MaShanZheng.ttf"}
    for kind, texts in use.items():
        p = os.path.join(ROOT, "assets", "fonts", files[kind])
        if not check(f"AC-13a 字体存在 {files[kind]}", os.path.exists(p)):
            continue
        f = TTFont(p)
        cmap = set()
        for t in f["cmap"].tables:
            cmap |= set(t.cmap.keys())
        need = set("".join(texts))
        miss = sorted(ch for ch in need if ord(ch) not in cmap)
        check(f"AC-13b {files[kind]} 缺字 = 0（{len(need)} 字）", not miss, "".join(miss))
    check("AC-13c 字体许可随包",
          os.path.exists(os.path.join(ROOT, "assets", "fonts", "LICENSE.md")))


def main():
    args = sys.argv[1:]
    video_only = "--video-only" in args
    info = verify_container()
    verify_timeline()
    if not video_only:
        verify_sub_on_screen()
        verify_picture()
        verify_watermark()
        verify_audio()
        verify_fonts()
    print(f"\n合计：{len(OK)} 过 / {len(FAIL)} 败")
    with open(os.path.join(PROOF, "verify.log"), "w", encoding="utf-8") as f:
        for n, d in OK:
            f.write(f"PASS  {n}  {d}\n")
        for n, d in FAIL:
            f.write(f"FAIL  {n}  {d}\n")
    if info:
        json.dump(info, open(os.path.join(PROOF, "container.json"), "w", encoding="utf-8"),
                  ensure_ascii=False, indent=1)
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
