# -*- coding: utf-8 -*-
"""生成阅稿页 site/index.html（+ site/img/ 下的图、submission/封面.png）。

  py -3 scripts/site.py

文案与六帧时间点都从 story.py / out/yixian.mp4 来，改片子重跑一次即可。
HTML 用「占位符替换」而不是 f-string：CSS 里的 {} 太多，f-string 容易踩空。
"""
import os, sys, subprocess, html
from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)
import story as S

OUT = os.path.join(ROOT, "out", "yixian.mp4")
SITE = os.path.join(ROOT, "site")
IMG = os.path.join(SITE, "img")
FONT_SERIF = os.path.join(ROOT, "assets", "fonts", "NotoSerifSC-VF.ttf")
FONT_BRUSH = os.path.join(ROOT, "assets", "fonts", "MaShanZheng.ttf")

PICKS = [
    (12.0, "起", "我叫线。不是画上去的，是站上去的。"),
    (32.0, "材", "舂上几个小时，泥才服。"),
    (56.0, "线", "最细的线，像一根头发。"),
    (86.0, "神", "神不动。动的是我。"),
    (120.0, "金", "金比蝉翼还薄，一口气就吹跑了。"),
    (158.0, "合", "我藏头，收尾。"),
]

CSS = """
  :root { --ink:#0b0a09; --gold:#d6aa5c; --gold-hi:#ffe8b2; --paper:#f2ece2; --dim:#9a8f7e; }
  * { box-sizing:border-box; }
  body { margin:0; background:var(--ink); color:var(--paper);
         font:400 17px/1.85 "Noto Serif SC",Georgia,"Songti SC",serif; letter-spacing:.02em; }
  .wrap { max-width:1120px; margin:0 auto; padding:0 24px; }
  header { padding:80px 0 24px; text-align:center; }
  h1 { font-size:clamp(44px,9vw,92px); margin:0 0 8px; font-weight:400; letter-spacing:.14em;
       color:var(--gold-hi); }
  .sub { color:var(--gold); letter-spacing:.22em; font-size:14px; }
  .meta { color:var(--dim); font-size:13px; letter-spacing:.08em; margin-top:14px; }
  .player { margin:36px 0 8px; }
  .player video { width:100%; display:block; border:1px solid #1e1a15; background:#000; }
  .hint { color:var(--dim); font-size:13px; padding-top:10px; letter-spacing:.04em; }
  .lead { max-width:780px; margin:40px auto 8px; color:#e6ddcd; }
  .lead em { color:var(--gold-hi); font-style:normal; }
  section { padding:56px 0 8px; border-top:1px solid #1b1712; }
  h2 { font-size:13px; letter-spacing:.32em; color:var(--gold); font-weight:400; margin:0 0 26px; }
  figure { margin:0 0 8px; }
  .gallery { display:grid; grid-template-columns:repeat(auto-fit,minmax(320px,1fr)); gap:18px; }
  .gallery img { width:100%; display:block; }
  figcaption { color:var(--dim); font-size:13px; padding-top:8px; letter-spacing:.04em; }
  figcaption b { color:var(--gold); font-weight:400; margin-right:10px; }
  ol.script { list-style:none; margin:0; padding:0; }
  ol.script li { display:flex; gap:18px; padding:9px 0; border-bottom:1px dotted #221d17; }
  .n { color:var(--gold); font-variant-numeric:tabular-nums; font-size:13px; padding-top:4px; }
  table { width:100%; border-collapse:collapse; font-size:15px; }
  td,th { text-align:left; padding:10px 12px; border-bottom:1px solid #1b1712; vertical-align:top; }
  th { color:var(--gold); font-weight:400; font-size:13px; letter-spacing:.1em; white-space:nowrap; }
  a { color:var(--gold-hi); text-decoration:none; border-bottom:1px solid #3a3025; }
  .note { color:var(--dim); font-size:15px; max-width:760px; }
  footer { padding:60px 0 90px; color:#6f6557; font-size:12px; letter-spacing:.1em; text-align:center; }
  @media (max-width:560px) { body { font-size:16px; } header { padding-top:48px; } th { white-space:normal; } }
"""

PAGE = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>@@TITLE@@ · @@SUB@@</title>
<meta name="robots" content="noindex">
<style>@@CSS@@</style>
</head>
<body>
<div class="wrap">
  <header>
    <h1>@@TITLE@@</h1>
    <div class="sub">@@SUB@@</div>
    <div class="meta">@@META@@</div>
  </header>

  <div class="player">
    <video controls playsinline preload="metadata" poster="img/@@COVER@@">
      <source src="@@VIDEO@@" type="video/mp4">
      你的浏览器不支持 video 标签；<a href="@@VIDEO@@">点这里下载</a>。
    </video>
    <div class="hint">720p 预览 · 全长 @@DUR@@ · 原片（1080p，9 Mbps）见 <a href="@@REL@@">Release</a></div>
  </div>

  <p class="lead">漆线雕是把漆泥搓成线、再把线盘成浮雕的手艺。这片子不讲大师生平，也不做工艺全景，
  只让这根线自己开口：<em>「我叫线。不是画上去的，是站上去的。」</em>
  它记得自己是被舂出来的、被搓出来的，记得一九七二年被从神像上剥离，
  也记得一九七三年在广交会上，有人问它叫什么。</p>

  <section>
    <h2>六帧</h2>
    <div class="gallery">
@@FIGS@@
    </div>
  </section>

  <section>
    <h2>台词 · 十九句</h2>
    <ol class="script">
@@ROWS@@
    </ol>
  </section>

  <section>
    <h2>怎么做的</h2>
    <table>
      <tr><th>画面</th><td>十八张图版由文生图模型生成（大漆微距、深黑漆底、24K 金线浮雕）；
      每镜是一个取样窗在图版上做缓动裁切，最大放大率 1.46。</td></tr>
      <tr><th>转场</th><td>十六处转场全部由同一条金线完成：曲线预计算成弧长图与距离图，
      线先落进画面，图形再沿「到线的距离」从线向两边绽开。</td></tr>
      <tr><th>声音</th><td>旁白 edge-tts（云希，−12% 语速）；箫、低音垫、舂泥、搓线、贴金、磬
      全部用 numpy 合成，无版权音乐；ffmpeg ebur128 对齐响度。</td></tr>
      <tr><th>判据</th><td>四十七条断言：时长/画幅/字幕上屏/单行不折行/配音不超槽/每镜非废帧/
      转场里金线在场/取样窗不进工具水印/真峰 ≤ −1 dBFS/无三秒以上静音/字体缺字为零。</td></tr>
      <tr><th>史实</th><td>项目编号、蔡氏代数、1972 剥离、1973 命名、《高古游丝》引文，
      逐条核到可打开的来源（<a href="https://www.ihchina.cn/news2_details/14363.html">中国非物质文化遗产网</a>、
      <a href="https://m.news.cctv.com/2020/06/13/ARTIrZHNKP7eM4TgQuELq7JH200613.shtml">央视新闻</a>、
      <a href="https://m.chinanews.com.cn/wap/detail/chs/zw/216076.shtml">中国新闻网</a>、
      <a href="https://www.xmqwzx.com.cn/xmfy/xmfy/xmml/201908/t20190828_68040.htm">厦门市文化馆</a>）。</td></tr>
    </table>
  </section>

  <section>
    <h2>关于 AI</h2>
    <p class="note">AI 只用在一处：把十八张图版画出来。片中所有运动、转场、颗粒、字幕、配乐与音效
    都是代码逐帧算出来的——没有视频生成模型，没有真人素材，没有换脸与声音克隆。
    同一份 <code>story.py</code> 跑出来的每一帧都可复现。</p>
  </section>

  <footer>《@@TITLE@@》· 2026「云创福建」AIGC 创作大赛 · 方向 2 非遗文化</footer>
</div>
</body>
</html>
"""


def grab(t, w=1600):
    p = os.path.join(IMG, f"f{int(t * 10):04d}.jpg")
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-ss", f"{t:.3f}", "-i", OUT,
                    "-frames:v", "1", "-vf", f"scale={w}:-2", "-q:v", "3", p], check=True)
    return os.path.basename(p)


def poster():
    """封面：P15 的盘 + 片名。字压在图上的地方先压一层柔和的暗带，保证字读得清。"""
    import numpy as np

    im = Image.open(os.path.join(ROOT, "assets", "plates", "P15.png")).convert("RGB")
    k = 1920 / im.width
    im = im.crop((0, 0, im.width, int(1080 / k))).resize((1920, 1080), Image.LANCZOS)
    arr = np.asarray(im, np.float32) * 0.72

    # 文字带：y 240–820，上下软边；带内把画面压到 32%，带外 72%
    yy = np.arange(1080, dtype=np.float32)[:, None]
    a = np.clip(np.minimum((yy - 200) / 180.0, (880 - yy) / 180.0), 0, 1)
    arr = arr * (1 - 0.56 * a)[..., None]
    # 径向暗角
    yy2, xx2 = np.mgrid[0:1080, 0:1920].astype(np.float32)
    r = np.sqrt(((xx2 - 960) / 1150) ** 2 + ((yy2 - 540) / 700) ** 2)
    arr = arr * np.clip(1.08 - 0.42 * np.clip(r, 0, 1.6) ** 2.0, 0.35, 1.0)[..., None]
    im = Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8))
    d = ImageDraw.Draw(im)

    f1 = ImageFont.truetype(FONT_BRUSH, 260)
    f2 = ImageFont.truetype(FONT_SERIF, 52)
    f3 = ImageFont.truetype(FONT_SERIF, 30)

    def center(txt, font, y, fill, tracking=0):
        bb = d.textbbox((0, 0), txt, font=font)
        x = (1920 - (bb[2] - bb[0])) // 2 - bb[0]
        d.text((x, y), txt, font=font, fill=fill)

    center(S.TITLE, f1, 300, (0, 0, 0))
    center(S.TITLE, f1, 294, (243, 230, 201))
    center(S.SUBTITLE, f2, 636, (214, 198, 170))
    center("AIGC 创意短片 · 国家级非遗 Ⅷ-55", f3, 730, (196, 182, 160))
    im.save(os.path.join(IMG, "cover.jpg"), quality=92)
    im.save(os.path.join(ROOT, "submission", "封面.png"))
    return "cover.jpg"


def main():
    if not os.path.exists(OUT):
        raise SystemExit("先构建 out/yixian.mp4")
    os.makedirs(IMG, exist_ok=True)
    os.makedirs(os.path.join(ROOT, "submission"), exist_ok=True)
    cover = poster()
    pics = [(grab(t), lab, cap) for t, lab, cap in PICKS]

    figs = "\n".join(
        '      <figure>\n'
        f'        <img src="img/{f}" alt="{html.escape(cap)}" loading="lazy">\n'
        f'        <figcaption><b>{lab}</b>{html.escape(cap)}</figcaption>\n'
        '      </figure>' for f, lab, cap in pics)

    rows = "\n".join(
        f'      <li><span class="n">{i:02d}</span><span>{html.escape(x)}</span></li>'
        for i, s in enumerate(S.SHOTS) if (x := s.get("sub")))

    total = sum(s["dur"] for s in S.SHOTS) + S.ENDCARD
    # 向下取整到秒：179.5 s 应显示 2 分 59 秒，不能四舍五入成 3 分 00 秒
    mm = int(total // 60)
    ss = int(total - mm * 60)
    meta = (f"{mm} 分 {ss:02d} 秒 · 1920×1080 · 24fps · 20 镜 · 18 张 AI 图版 · "
            "程序化运镜与合成")

    REL = ("https://github.com/hkmpn9s6dh-commits/hackathon-2026-yixian/releases/tag/v1")
    VIDEO = ("https://github.com/hkmpn9s6dh-commits/hackathon-2026-yixian/releases/"
             "download/v1/yixian-720p.mp4")
    page = (PAGE.replace("@@CSS@@", CSS)
                .replace("@@VIDEO@@", VIDEO)
                .replace("@@REL@@", REL)
                .replace("@@DUR@@", f"{mm}:{ss:02d}")
                .replace("@@TITLE@@", html.escape(S.TITLE))
                .replace("@@SUB@@", html.escape(S.SUBTITLE))
                .replace("@@META@@", meta)
                .replace("@@COVER@@", cover)
                .replace("@@FIGS@@", figs)
                .replace("@@ROWS@@", rows))
    open(os.path.join(SITE, "index.html"), "w", encoding="utf-8", newline="\n").write(page)
    print("写出", os.path.join(SITE, "index.html"))
    print("图", len(pics) + 1, "张 →", IMG)


if __name__ == "__main__":
    main()
