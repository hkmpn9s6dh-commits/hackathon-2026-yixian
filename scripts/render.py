# -*- coding: utf-8 -*-
"""逐帧渲染《一线》。

核心只有一件事：**画面由一根线长出来**。
  · bloom  —— 线先落在画面里，图形从线向两边「绽」开
  · wipe   —— 线在画面里走，走过的顺序就是画面显影的顺序
所有转场都由同一条「金线」完成，没有淡入淡出、没有推拉划像。

用法：
  py -3 scripts/render.py build/video.mp4 [--from 0 --to 1000]
分段渲染（本机经验：整段跑在回合结束时会被回收）：
  1000 帧一段，段与段用 -c copy 拼。
"""
import os, sys, math, subprocess
import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
import story as S

W, H, FPS = S.W, S.H, S.FPS
PW, PH = S.PW, S.PH
N = int(round((sum(s["dur"] for s in S.SHOTS) + S.ENDCARD) * FPS))

PLATE_DIR = os.path.join(ROOT, "assets", "plates")
FONT_SERIF = os.path.join(ROOT, "assets", "fonts", "NotoSerifSC-VF.ttf")
FONT_BRUSH = os.path.join(ROOT, "assets", "fonts", "MaShanZheng.ttf")

GOLD = (214, 170, 92)
GOLD_HI = (255, 232, 178)


# ---------------------------------------------------------------- 小工具
def clamp(x, a, b):
    return a if x < a else (b if x > b else x)


def lerp(a, b, t):
    return a + (b - a) * t


def ease_io(x):
    x = clamp(x, 0.0, 1.0)
    return x * x * (3 - 2 * x)


def ease_out(x):
    x = clamp(x, 0.0, 1.0)
    return 1 - (1 - x) ** 3


def smoothstep(a, b, x):
    t = np.clip((x - a) / (b - a + 1e-9), 0, 1)
    return t * t * (3 - 2 * t)


# ---------------------------------------------------------------- 字体
_FONTS = {}
_CACHE = {}


def font(size, name="serif", weight=600):
    key = (size, name, weight)
    if key in _FONTS:
        return _FONTS[key]
    path = FONT_BRUSH if name == "brush" else FONT_SERIF
    f = ImageFont.truetype(path, size)
    if name == "serif":
        try:
            f.set_variation_by_axes([weight])
        except Exception:
            pass
    _FONTS[key] = f
    return f


# ---------------------------------------------------------------- 图版
_PLATES = {}
_VIG = None
_GRAIN = []


def plate(key):
    if key not in _PLATES:
        p = os.path.join(PLATE_DIR, key + ".png")
        _PLATES[key] = Image.open(p).convert("RGB")
    return _PLATES[key]


def vignette():
    global _VIG
    if _VIG is None:
        yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
        cx, cy = W / 2, H / 2
        r = np.sqrt(((xx - cx) / (W * 0.62)) ** 2 + ((yy - cy) / (H * 0.62)) ** 2)
        v = np.clip(1.06 - 0.42 * np.clip(r, 0, 1.6) ** 2.1, 0.42, 1.0)
        _VIG = v.astype(np.float32)
    return _VIG


def grain(i):
    if not _GRAIN:
        rng = np.random.default_rng(20261118)
        for _ in range(6):
            _GRAIN.append(rng.normal(0, 1, (H // 2, W // 2)).astype(np.float32))
    g = _GRAIN[i % len(_GRAIN)]
    return np.repeat(np.repeat(g, 2, axis=0), 2, axis=1)


# ---------------------------------------------------------------- 取样窗
def window(shot, p):
    """返回图版上的取样矩形 (l, t, r, b)，已做安全区约束。"""
    z0, z1 = shot["cam"]["z"]
    c0, c1 = shot["cam"]["c"]
    e = ease_io(p)
    z = lerp(z0, z1, e)
    cx = lerp(c0[0], c1[0], e) * PW
    cy = lerp(c0[1], c1[1], e) * PH
    cw = PW / max(z, 1.0)
    ch = cw * H / W
    if ch > PH * S.SAFE_BOTTOM:          # 不可能同时满足时，先保不进水印
        ch = PH * S.SAFE_BOTTOM
        cw = ch * W / H
    cx = clamp(cx, cw / 2, PW - cw / 2)
    cy = clamp(cy, ch / 2, PH * S.SAFE_BOTTOM - ch / 2)
    return (cx - cw / 2, cy - ch / 2, cx + cw / 2, cy + ch / 2)


def shot_image(shot, local_t):
    p = clamp(local_t / shot["dur"], 0.0, 1.0)
    box = window(shot, p)
    im = plate(shot["plate"]).crop(box).resize((W, H), Image.LANCZOS)
    # 极轻的呼吸，避免整帧死板
    b = 1.0 + 0.012 * math.sin(local_t * 0.9 + 0.7)
    if abs(b - 1.0) > 1e-4:
        im = Image.fromarray(np.clip(np.asarray(im, np.float32) * b, 0, 255).astype(np.uint8))
    return im


# ---------------------------------------------------------------- 路径
def curve_pts(kind, n=520):
    """归一化坐标下的路径点，返回 (n,2) float32。"""
    t = np.linspace(0, 1, n, dtype=np.float32)
    if kind == "sweep":                     # 一根微微下垂的横线（与 P01 里那根线对齐）
        x = 0.02 + 0.96 * t
        y = 0.486 + 0.012 * np.sin(np.pi * x)
    elif kind == "wave":                    # 水波
        x = 0.03 + 0.94 * t
        y = 0.50 + 0.085 * np.sin(2 * np.pi * 2.5 * t + 0.6) * (0.75 + 0.25 * t)
    elif kind == "coil":                    # 盘线：一圈套一圈
        th = 2 * np.pi * 2.1 * t
        r = 0.055 + 0.40 * t
        x = 0.50 + r * np.cos(th - 1.2) * 1.25
        y = 0.50 + r * np.sin(th - 1.2) * 0.78
    elif kind == "diag":
        x = 0.04 + 0.92 * t
        y = 0.92 - 0.80 * t
    elif kind == "stair":                   # 甲片：一级一级往右上
        seg = 7
        u = t * seg
        k = np.floor(u)
        f = u - k
        x = 0.03 + 0.94 * (k + np.minimum(f * 1.0, 1.0)) / seg
        y = 0.86 - 0.72 * (k + (f > 0.5)) / seg
    elif kind == "dragon":                  # 龙身：三个转折
        x = 0.04 + 0.92 * t
        y = 0.52 + 0.20 * np.sin(2 * np.pi * 1.45 * t + 0.4) * np.clip(np.sin(np.pi * t), 0, 1) ** 0.4
    else:
        x = 0.03 + 0.94 * t
        y = 0.5 * np.ones_like(t)
    return np.stack([x, y], 1).astype(np.float32)


def arclen(pts):
    d = np.linalg.norm(np.diff(pts, axis=0), axis=1)
    s = np.concatenate([[0], np.cumsum(d)])
    return s / s[-1], float(s[-1])


_FIELDS = {}
GW, GH = 480, 270          # 场分辨率（再双线性放大）


def field(kind):
    """返回 (smap, dmap)：沿路径的弧长参数 0-1、到路径的距离（归一化到长边）。"""
    if kind in _FIELDS:
        return _FIELDS[kind]
    pts = curve_pts(kind)
    sn, _ = arclen(pts)
    gx = (np.arange(GW, dtype=np.float32) + 0.5) / GW
    gy = (np.arange(GH, dtype=np.float32) + 0.5) / GH
    GX, GY = np.meshgrid(gx, gy)
    P = np.stack([GX.ravel(), GY.ravel()], 1)
    best_d = np.full(len(P), 1e9, np.float32)
    best_s = np.zeros(len(P), np.float32)
    for i in range(len(pts) - 1):
        a = pts[i]
        b = pts[i + 1]
        ab = b - a
        L2 = float(ab @ ab) + 1e-12
        tt = np.clip(((P - a) @ ab) / L2, 0, 1)
        proj = a + tt[:, None] * ab
        dd = np.linalg.norm(P - proj, axis=1)
        m = dd < best_d
        best_d[m] = dd[m]
        best_s[m] = sn[i] + (sn[i + 1] - sn[i]) * tt[m]
    smap = best_s.reshape(GH, GW)
    dmap = best_d.reshape(GH, GW)
    smap = np.asarray(Image.fromarray(smap, "F").resize((W, H), Image.BILINEAR), np.float32)
    dmap = np.asarray(Image.fromarray(dmap, "F").resize((W, H), Image.BILINEAR), np.float32)
    _FIELDS[kind] = (smap, dmap)
    return _FIELDS[kind]


# ---------------------------------------------------------------- 金线
def thread_layer(kind, head=None, upto=None, alpha=1.0, width=3.4, glow=1.0):
    """画线（半分辨率绘制 + 模糊后放大，省一半以上时间）。"""
    SC = 2
    w2, h2 = W // SC, H // SC
    pts = curve_pts(kind, 900)
    sn, _ = arclen(pts)
    if upto is not None:
        head = upto
    ov = Image.new("RGB", (w2, h2), (0, 0, 0))
    d = ImageDraw.Draw(ov)
    if head is not None:
        m = sn <= head
        if not m.any():
            return None
        pts = pts[m]
    xy = [(float(x) * w2, float(y) * h2) for x, y in pts]
    if len(xy) >= 2:
        d.line(xy, fill=GOLD, width=max(1, int(width * 2.2 / SC * 2) // 2 + 1), joint="curve")
        d.line(xy, fill=GOLD_HI, width=max(1, int(width * 0.8 / SC) + 1), joint="curve")
    elif len(xy) == 1:
        d.ellipse([xy[0][0] - 1, xy[0][1] - 1, xy[0][0] + 1, xy[0][1] + 1], fill=GOLD_HI)
    if head is not None and len(xy) >= 1:
        hx, hy = xy[-1]
        for r, k in ((15, 0.22), (7, 0.42), (3, 0.80)):
            d.ellipse([hx - r, hy - r, hx + r, hy + r], fill=tuple(int(c * k) for c in GOLD_HI))
    arr = np.asarray(ov, np.float32)
    if glow > 0:
        g = np.asarray(ov.filter(ImageFilter.GaussianBlur(4.5)), np.float32)
        arr = arr + g * (1.15 * glow)
    im = Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8)).resize((W, H), Image.BILINEAR)
    return np.asarray(im, np.float32) * alpha


def screen_add(base, add):
    """相加混合（金线发光），保留暗部。"""
    if add is None:
        return base
    b = np.asarray(base, np.float32)
    out = 255.0 - (255.0 - b) * (255.0 - np.clip(add, 0, 255)) / 255.0
    return Image.fromarray(np.clip(out, 0, 255).astype(np.uint8))


# ---------------------------------------------------------------- 转场
def reveal(prev_im, cur_im, kind, p, mode="bloom"):
    """p: 0-1 进度。返回合成图与线层要叠加的 head。"""
    smap, dmap = field(kind)
    if mode == "bloom":
        R = 0.58 * ease_out(p)
        a = 1.0 - smoothstep(R - 0.10, R + 0.02, dmap)
    else:
        head = 1.02 * ease_io(p) - 0.01
        a = 1.0 - smoothstep(head - 0.05, head + 0.005, smap)
    a = a[..., None]
    out = np.asarray(cur_im, np.float32) * a + np.asarray(prev_im, np.float32) * (1 - a)
    return Image.fromarray(np.clip(out, 0, 255).astype(np.uint8)), a[..., 0]


# ---------------------------------------------------------------- 文字
def text_layer(lines, size, name="serif", fill=(236, 228, 212), weight=600,
               tracking=0.0, shadow=True):
    """多行居中文字，返回 (RGB 图层, alpha 图层)。"""
    f = font(size, name, weight)
    im = Image.new("RGB", (W, H), (0, 0, 0))
    d = ImageDraw.Draw(im)
    lh = int(size * 1.55)
    y0 = H // 2 - lh * (len(lines) - 1) // 2
    if tracking <= 0:
        for i, ln in enumerate(lines):
            bb = d.textbbox((0, 0), ln, font=f)
            x = (W - (bb[2] - bb[0])) // 2 - bb[0]
            d.text((x, y0 + i * lh - size * 0.62), ln, font=f, fill=fill)
    else:
        for i, ln in enumerate(lines):
            widths = [d.textlength(ch, font=f) for ch in ln]
            tw = sum(widths) + tracking * (len(ln) - 1)
            x = (W - tw) / 2
            for ch, cw in zip(ln, widths):
                d.text((x, y0 + i * lh - size * 0.62), ch, font=f, fill=fill)
                x += cw + tracking
    ar = np.asarray(im, np.float32)
    alpha = np.clip(ar.max(axis=2) / max(fill[0], 1), 0, 1)
    if shadow:
        sh = np.asarray(im.filter(ImageFilter.GaussianBlur(6)), np.float32)
        ar = np.clip(ar + sh * 0.55, 0, 255)
    return ar, alpha


def blend_text(frame_arr, ar, alpha, op=1.0):
    a = (alpha * op)[..., None]
    src = 255.0 - (255.0 - frame_arr) * (255.0 - np.clip(ar, 0, 255)) / 255.0
    return frame_arr * (1 - a) + src * a


def subtitle(text):
    """返回 (文字覆盖, 投影覆盖) 两张全幅 alpha。白字 + 2px 黑描边 + 柔投影。"""
    if not text:
        return None
    if text in _CACHE:
        return _CACHE[text]
    size = 46
    f = font(size, "serif", 500)
    probe = ImageDraw.Draw(Image.new("L", (8, 8)))
    bb = probe.textbbox((0, 0), text, font=f, stroke_width=2)
    tw, th = bb[2] - bb[0], bb[3] - bb[1]
    m = 18
    small = Image.new("L", (tw + 2 * m, th + 2 * m), 0)
    ImageDraw.Draw(small).text((m - bb[0], m - bb[1]), text, font=f,
                               fill=255, stroke_width=2, stroke_fill=255)
    a_small = np.asarray(small, np.float32) / 255.0
    sh_small = np.asarray(small.filter(ImageFilter.GaussianBlur(7)), np.float32) / 255.0
    a = np.zeros((H, W), np.float32)
    sh = np.zeros((H, W), np.float32)
    x0 = (W - a_small.shape[1]) // 2
    y0 = H - 100 - a_small.shape[0]
    a[y0:y0 + a_small.shape[0], x0:x0 + a_small.shape[1]] = a_small
    sh[y0:y0 + sh_small.shape[0], x0:x0 + sh_small.shape[1]] = sh_small
    _CACHE[text] = (a, sh)
    return a, sh


# ---------------------------------------------------------------- 时间轴
def timeline():
    """把 SHOTS + 片名卡摊成 [(t0, t1, shot_index)] 与每个镜头的绝对起点。"""
    segs = []
    t = 0.0
    for i, s in enumerate(S.SHOTS):
        segs.append((t, t + s["dur"], i))
        t += s["dur"]
    return segs, t


SEGS, T_BODY = timeline()
T_TOTAL = T_BODY + S.ENDCARD


def which_shot(t):
    for t0, t1, i in SEGS:
        if t < t1:
            return i, t - t0
    return len(S.SHOTS) - 1, S.SHOTS[-1]["dur"]


def sub_at(t):
    """字幕：进入镜头后 0.9s 起，留到镜头结束前 0.7s。"""
    i, lt = which_shot(t)
    s = S.SHOTS[i]
    if not s.get("sub"):
        return None, 0.0
    a = clamp((lt - 0.9) / 0.6, 0, 1) * clamp((s["dur"] - 0.7 - lt) / 0.5, 0, 1)
    return s["sub"], a


# ---------------------------------------------------------------- 单帧
def frame_at(t, fi):
    i, lt = which_shot(t)
    shot = S.SHOTS[i]
    prev_shot = S.SHOTS[i - 1] if i > 0 else None

    # 基础层
    cur = shot_image(shot, lt)
    if i == 0:
        base = Image.new("RGB", (W, H), (0, 0, 0))
    else:
        base = shot_image(prev_shot, prev_shot["dur"] + lt)   # 上一镜继续走，不冻帧

    # 转场
    tr = shot.get("trans") or {}
    tw = float(tr.get("dur") or 0)
    thread = None
    if tr.get("kind") == "line" and tw > 0 and lt < tw:
        p = lt / tw
        base, mask = reveal(base, cur, tr["curve"], p,
                            tr.get("mode", "bloom"))
        fade = 1.0 - ease_io(clamp((p - 0.55) / 0.45, 0, 1))
        if tr.get("mode", "bloom") == "bloom":
            thread = thread_layer(tr["curve"], alpha=fade * 0.92, width=3.0)
        else:
            thread = thread_layer(tr["curve"], upto=1.02 * ease_io(p),
                                  alpha=fade * 0.45, width=1.7, glow=0.55)
    else:
        base = cur

    arr = np.asarray(base, np.float32)

    # 开场的线：自己长出来（第一帧就要有东西在动，别让观众以为播放失败）
    if i == 0:
        g0, g1 = 0.15, 6.4
        if lt >= g0:
            head = ease_io(clamp((lt - g0) / (g1 - g0), 0, 1)) * 1.02
            arr = np.asarray(screen_add(Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8)),
                                        thread_layer("sweep", upto=head)), np.float32)

    if thread is not None:
        arr = np.asarray(screen_add(Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8)),
                                    thread), np.float32)

    # 极轻的提亮 + 暗角 + 颗粒
    arr = arr * 1.035 + 2.0
    arr = arr * vignette()[..., None]
    arr = arr + grain(fi)[..., None] * 5.2
    arr = np.clip(arr, 0, 255)

    # 字幕
    s_txt, s_a = sub_at(t)
    if s_txt and s_a > 0.01:
        a_sub, sh_sub = subtitle(s_txt)
        arr = arr * (1 - 0.60 * sh_sub * s_a)[..., None]
        al = (a_sub * s_a)[..., None]
        arr = arr * (1 - al) + np.array([238, 232, 220], np.float32) * al

    # 片名卡
    if t >= T_BODY:
        e = t - T_BODY
        arr = endcard(arr, e)

    return Image.fromarray(arr.astype(np.uint8))


def endcard(arr, e):
    k = 1.0 - ease_io(clamp(e / 0.9, 0, 1)) * 0.78
    arr = arr * k
    o1 = ease_io(clamp((e - 0.4) / 1.1, 0, 1))
    o2 = ease_io(clamp((e - 1.4) / 1.0, 0, 1))
    o3 = ease_io(clamp((e - 2.2) / 1.0, 0, 1))
    ar, al = text_layer([S.TITLE], 170, "brush", (242, 228, 198))
    arr = blend_text(arr, ar, al, o1)
    ar, al = text_layer([S.SUBTITLE], 40, "serif", (208, 192, 164), 500, tracking=6)
    arr = _place(arr, ar, al, o2 * 0.95, dy=118)
    ar, al = text_layer(["AIGC 生成画面 · 程序化运镜与合成"], 30, "serif", (196, 182, 162), 400, tracking=3)
    arr = _place(arr, ar, al, o3 * 0.95, dy=222)
    return arr


def _place(arr, ar, al, op, dy=0):
    if op <= 0.01:
        return arr
    if dy:
        ar = np.roll(ar, dy, axis=0)
        al = np.roll(al, dy, axis=0)
        al[:dy] = 0
        ar[:dy] = 0
    return blend_text(arr, ar, al, op)


# ---------------------------------------------------------------- 主循环
def prewarm():
    kinds = []
    for s in S.SHOTS:
        tr = s.get("trans") or {}
        if tr.get("kind") == "line" and tr.get("curve") not in kinds:
            kinds.append(tr["curve"])
    for k in kinds:
        print("  build field:", k, flush=True)
        field(k)
    vignette()


def render(out_path, f0=0, f1=None):
    f1 = N if f1 is None else min(f1, N)
    prewarm()
    cmd = ["ffmpeg", "-y", "-loglevel", "error",
           "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}",
           "-r", str(FPS), "-i", "-",
           "-an", "-c:v", "libx264", "-preset", "medium", "-crf", "17",
           "-pix_fmt", "yuv420p", "-g", "48", out_path]
    p = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    for fi in range(f0, f1):
        im = frame_at(fi / FPS, fi)
        p.stdin.write(im.tobytes())
        if fi % 120 == 0:
            print(f"  {fi}/{f1}  t={fi/FPS:6.2f}s", flush=True)
    p.stdin.close()
    p.wait()
    print("done:", out_path, f"{os.path.getsize(out_path)/1024/1024:.1f} MB")


if __name__ == "__main__":
    out = sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, "build", "video.mp4")
    a = int(sys.argv[sys.argv.index("--from") + 1]) if "--from" in sys.argv else 0
    b = int(sys.argv[sys.argv.index("--to") + 1]) if "--to" in sys.argv else None
    print(f"总帧数 {N}，总时长 {N/FPS:.2f}s")
    render(out, a, b)
