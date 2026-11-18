# -*- coding: utf-8 -*-
"""收尾：把 build/seg*.mp4 拼成片、混音、压 1080p 与 720p。

  py -3 scripts/finish.py            # 段 → master → muxed → out/yixian.mp4 + out/yixian-720p.mp4

只做"拼接 + 混音 + 压制"，不重新渲染。build.py 里已经包含这一段的逻辑，
这个脚本是给"渲染已经分段落盘"的场合用的（本机长任务容易被回收，分段落盘更稳）。
"""
import os, sys, subprocess, json

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)
import story as S

BUILD = os.path.join(ROOT, "build")
OUT = os.path.join(ROOT, "out", "yixian.mp4")
OUT720 = os.path.join(ROOT, "out", "yixian-720p.mp4")


def run(cmd):
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        print(r.stderr[-800:])
        raise SystemExit(f"失败：{cmd[0]}")
    return r


def segs():
    out = []
    i = 0
    while os.path.exists(os.path.join(BUILD, f"seg{i}.mp4")):
        out.append(f"seg{i}.mp4")
        i += 1
    return out


def main():
    s = segs()
    if not s:
        raise SystemExit("没有 build/seg*.mp4，先跑 scripts/build.py")
    print(f"拼接 {len(s)} 段…", flush=True)
    lst = os.path.join(BUILD, "list.txt")
    open(lst, "w", encoding="utf-8").write("".join(f"file '{x}'\n" for x in s))
    master = os.path.join(BUILD, "master.mp4")
    run(["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0",
         "-i", lst, "-c", "copy", master])

    print("混音…", flush=True)
    muxed = os.path.join(BUILD, "muxed.mp4")
    run(["ffmpeg", "-y", "-loglevel", "error", "-i", master,
         "-i", os.path.join(BUILD, "audio_raw.wav"),
         "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-ac", "2",
         "-shortest", muxed])

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    for path, vf, crf, extra in (
        (OUT, None, "21", ["-profile:v", "high", "-level", "4.1",
                           "-x264-params", "aq-mode=3:deblock=-1,-1"]),
        (OUT720, "scale=1280:720", "23", ["-profile:v", "high", "-level", "4.0"]),
    ):
        print(f"压制 {os.path.basename(path)}…", flush=True)
        tmp = path + ".part.mp4"
        cmd = ["ffmpeg", "-y", "-loglevel", "error", "-i", muxed]
        if vf:
            cmd += ["-vf", vf]
        cmd += ["-c:v", "libx264", "-preset", "slow", "-crf", crf,
                "-pix_fmt", "yuv420p"] + extra + ["-c:a", "copy",
                "-movflags", "+faststart", tmp]
        run(cmd)
        os.replace(tmp, path)
        info = json.loads(subprocess.check_output(
            ["ffprobe", "-v", "error", "-print_format", "json", "-show_format",
             "-show_streams", path]).decode("utf-8"))
        dur = float(info["format"]["duration"])
        print(f"  {path}  {os.path.getsize(path)/1024/1024:.1f} MB  {dur:.2f}s")


if __name__ == "__main__":
    main()
