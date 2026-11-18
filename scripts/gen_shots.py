# -*- coding: utf-8 -*-
"""从 story.py 生成 docs/03-SHOTS.md 与 submission/分镜表.csv。

  py -3 scripts/gen_shots.py           # 重新生成
  py -3 scripts/gen_shots.py --check   # 只核对（clone / verify 用，文件不一致就退出 1）

改片子只改 story.py；这张表是它的投影，不许手改。
"""
import os, sys, csv, io

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)
import story as S

CURVE = {"sweep": "横线", "wave": "水波", "coil": "盘线", "diag": "斜线",
         "stair": "阶梯", "dragon": "龙身", None: "—"}


def timeline():
    t, rows = 0.0, []
    for i, s in enumerate(S.SHOTS):
        tr = s.get("trans") or {}
        kind = tr.get("kind", "cut")
        if kind == "line":
            desc = f'线·{CURVE.get(tr.get("curve"), "?")}（{tr.get("mode", "wipe")} {tr["dur"]}s）'
        else:
            desc = "硬切"
        z = s["cam"]["z"]
        rows.append(dict(i=i, t0=t, dur=s["dur"], plate=s["plate"],
                         z=f"{z[0]:.2f}→{z[1]:.2f}", trans=desc,
                         sub=s.get("sub") or "—"))
        t += s["dur"]
    return rows, t


def md():
    rows, body = timeline()
    total = body + S.ENDCARD
    o = io.StringIO()
    o.write("# 03 · 分镜表\n\n")
    o.write("> **本文件由 `scripts/gen_shots.py` 从 `story.py` 生成，不要手改。**\n")
    o.write(f"> 共 {len(rows)} 镜 + 片名卡 {S.ENDCARD}s = **{total:.1f}s**（{total/60:.2f} 分）"
            f"｜{S.W}×{S.H}@{S.FPS}fps｜{int(round(total*S.FPS))} 帧\n\n")
    o.write("| # | 起点 | 时长 | 图版 | 放大率 | 转场 | 字幕 / 旁白 |\n")
    o.write("| --- | --- | --- | --- | --- | --- | --- |\n")
    for r in rows:
        o.write(f'| {r["i"]} | {r["t0"]:6.2f}s | {r["dur"]:4.1f}s | {r["plate"]} | '
                f'{r["z"]} | {r["trans"]} | {r["sub"]} |\n')
    o.write(f"| — | {body:.2f}s | {S.ENDCARD:.1f}s | 片名卡 | — | 承接 | "
            f"《{S.TITLE}》/ {S.SUBTITLE} / AIGC 生成画面 · 程序化运镜与合成 |\n\n")

    subs = [r for r in rows if r["sub"] != "—"]
    o.write("## 统计\n\n")
    o.write(f"- 有字幕镜头 {len(subs)} / {len(rows)}；最短镜 {min(r['dur'] for r in rows):.1f}s，"
            f"最长 {max(r['dur'] for r in rows):.1f}s\n")
    o.write(f"- 线转场 {sum(1 for r in rows if r['trans'].startswith('线'))} 处，"
            f"硬切 {sum(1 for r in rows if r['trans'] == '硬切')} 处\n")
    o.write(f"- 图版 {len(S.PLATES)} 张，全部用到：" +
            "、".join(sorted({r["plate"] for r in rows})) + "\n\n")
    o.write("## 声音\n\n")
    o.write(f"- 旁白：edge-tts `{S.VOICE}`，rate {S.VOICE_RATE}，增益 {S.VOICE_GAIN}\n")
    o.write(f"- 音效 {len(S.SFX)} 处（"
            + "、".join(f"{k}@{p:.2f}" for k, p, g in S.SFX) + "）\n")
    o.write(f"- 配乐：{'开' if S.MUSIC.get('enabled') else '关'}，增益 {S.MUSIC['gain']}"
            "（箫 + 低音垫，全部 numpy 合成）\n")
    return o.getvalue()


def csv_text():
    rows, _ = timeline()
    o = io.StringIO()
    w = csv.writer(o, lineterminator="\n")
    w.writerow(["镜号", "起点(s)", "时长(s)", "图版", "放大率", "转场", "字幕"])
    for r in rows:
        w.writerow([r["i"], f'{r["t0"]:.2f}', f'{r["dur"]:.1f}', r["plate"],
                    r["z"], r["trans"], r["sub"]])
    return o.getvalue()


def main():
    md_p = os.path.join(ROOT, "docs", "03-SHOTS.md")
    csv_p = os.path.join(ROOT, "submission", "分镜表.csv")
    want_md, want_csv = md(), csv_text()
    if "--check" in sys.argv:
        bad = []
        # CSV 带 BOM（Excel 直接打开不乱码），比对时要用 utf-8-sig 读，否则永远"不一致"
        for p, want, enc in ((md_p, want_md, "utf-8"), (csv_p, want_csv, "utf-8-sig")):
            if not os.path.exists(p):
                bad.append(f"{p} 不存在")
            elif open(p, encoding=enc).read() != want:
                bad.append(f"{p} 与 story.py 不一致（改了 story.py 忘了重生成？）")
        if bad:
            print("  FAIL  分镜表：" + "；".join(bad))
            return 1
        print("  PASS  分镜表与 story.py 一致")
        return 0
    os.makedirs(os.path.dirname(md_p), exist_ok=True)
    os.makedirs(os.path.dirname(csv_p), exist_ok=True)
    open(md_p, "w", encoding="utf-8", newline="\n").write(want_md)
    open(csv_p, "w", encoding="utf-8-sig", newline="\n").write(want_csv)
    print("写出", md_p)
    print("写出", csv_p)
    return 0


if __name__ == "__main__":
    sys.exit(main())
