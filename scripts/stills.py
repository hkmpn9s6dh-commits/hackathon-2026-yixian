# -*- coding: utf-8 -*-
"""证据帧：为 proof/ 生成关键帧、联系表、以及"线转场"的连拍。

  py -3 scripts/stills.py

产物全部落在 proof/ 下，可重复生成（同一部片子跑两次，文件名与尺寸一致）。
"""
import os, sys, subprocess
from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)
import story as S

OUT = os.path.join(ROOT, "out", "yixian.mp4")
PROOF = os.path.join(ROOT, "proof")
FRAMES = os.path.join(PROOF, "frames")
FONT = os.path.join(ROOT, "assets", "fonts", "NotoSerifSC-VF.ttf")


def grab(t, path):
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-ss", f"{t:.3f}", "-i", OUT,
                    "-frames:v", "1", path], check=True)


def main():
    if not os.path.exists(OUT):
        raise SystemExit("先构建 out/yixian.mp4")
    os.makedirs(FRAMES, exist_ok=True)

    starts, acc = [], 0.0
    for s in S.SHOTS:
        starts.append(acc)
        acc += s["dur"]
    total = acc + S.ENDCARD

    # 1) 每镜一张（中点），900×506
    tiles = []
    for i, s in enumerate(S.SHOTS):
        t = starts[i] + s["dur"] * 0.55
        p = os.path.join(FRAMES, f"shot{i:02d}.png")
        grab(t, p)
        tiles.append((t, p))
    # 2) 片名卡
    grab(total - 1.2, os.path.join(FRAMES, "endcard.png"))

    # 3) 联系表：4 列 5 行 + 时间码
    cw, ch = 480, 270
    sheet = Image.new("RGB", (cw * 4, ch * 5 + 0), (12, 12, 12))
    d = ImageDraw.Draw(sheet)
    f = ImageFont.truetype(FONT, 16)
    for k, (t, p) in enumerate(tiles):
        im = Image.open(p).convert("RGB").resize((cw, ch), Image.LANCZOS)
        x, y = (k % 4) * cw, (k // 4) * ch
        sheet.paste(im, (x, y))
        d.text((x + 8, y + 6), f"{k:02d}  {t:5.1f}s", fill=(214, 170, 92), font=f)
    sheet.save(os.path.join(PROOF, "contact-sheet.jpg"), quality=88)

    # 4) 一处线转场的连拍（证明"画面由线长出来"）
    tr_i = next(i for i, s in enumerate(S.SHOTS)
                if (s.get("trans") or {}).get("kind") == "line"
                and (s.get("trans") or {}).get("dur", 0) >= 2.0 and i > 0)
    tr = S.SHOTS[tr_i]["trans"]
    strip = Image.new("RGB", (cw * 3, ch * 2), (12, 12, 12))
    ds = ImageDraw.Draw(strip)
    for k in range(6):
        t = starts[tr_i] + tr["dur"] * (k / 5) * 0.92
        p = os.path.join(FRAMES, f"tr{tr_i}_{k}.png")
        grab(t, p)
        im = Image.open(p).convert("RGB").resize((cw, ch), Image.LANCZOS)
        x, y = (k % 3) * cw, (k // 3) * ch
        strip.paste(im, (x, y))
        ds.text((x + 8, y + 6), f"+{t - starts[tr_i]:.2f}s", fill=(214, 170, 92), font=f)
    strip.save(os.path.join(PROOF, "transition-strip.jpg"), quality=90)

    print(f"证据帧 {len(tiles)} 张 → {FRAMES}")
    print(f"联系表 → {os.path.join(PROOF, 'contact-sheet.jpg')}")
    print(f"转场连拍（第 {tr_i} 镜 {tr['curve']}）→ {os.path.join(PROOF, 'transition-strip.jpg')}")


if __name__ == "__main__":
    main()
