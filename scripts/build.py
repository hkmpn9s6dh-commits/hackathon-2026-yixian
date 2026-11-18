# -*- coding: utf-8 -*-
"""一条命令从零构建《一线》：配音 → 逐帧渲染 → 拼接 → 混音 → 压制 → out/yixian.mp4

  py -3 scripts/build.py              # 全流程（约 20–30 分钟，4 进程并行）
  py -3 scripts/build.py --skip-audio # 复用 build/audio_raw.wav
  py -3 scripts/build.py --skip-video # 只重建声音与压制（复用 build/master.mp4）
  py -3 scripts/build.py --jobs 6     # 并行段数

为什么分段：本机单进程渲 4300 帧要 60 分钟以上，且长任务在回合结束时会被回收。
段与段之间用 -c copy 拼接（同参数、同 GOP，不重编码）。
"""
import os, sys, subprocess, json, time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)
import story as S

BUILD = os.path.join(ROOT, "build")
OUT = os.path.join(ROOT, "out", "yixian.mp4")
N = int(round((sum(s["dur"] for s in S.SHOTS) + S.ENDCARD) * S.FPS))


def run(cmd, **kw):
    print("  $", " ".join(str(c) for c in cmd)[:150], flush=True)
    r = subprocess.run(cmd, **kw)
    if r.returncode != 0:
        raise SystemExit(f"失败（{r.returncode}）：{cmd[0]}")
    return r


def audio():
    print("[1/5] 声音（edge-tts 旁白 + numpy 合成 + 响度对齐）", flush=True)
    if os.path.exists(os.path.join(BUILD, "audio_raw.wav")) and "--skip-audio" in sys.argv:
        print("  复用 build/audio_raw.wav")
        return
    run([sys.executable, os.path.join(HERE, "audio.py")])


def render(jobs=4):
    master = os.path.join(BUILD, "master.mp4")
    if "--skip-video" in sys.argv and os.path.exists(master):
        print("[2/5] 复用 build/master.mp4")
        return master
    print(f"[2/5] 逐帧渲染 {N} 帧 / {jobs} 段并行", flush=True)
    step = N // jobs + 1
    procs = []
    for i in range(jobs):
        a, b = i * step, min((i + 1) * step, N)
        if a >= N:
            break
        log = open(os.path.join(BUILD, f"seg{i}.log"), "w", encoding="utf-8")
        procs.append((i, a, b, log, subprocess.Popen(
            [sys.executable, os.path.join(HERE, "render.py"),
             os.path.join(BUILD, f"seg{i}.mp4"), "--from", str(a), "--to", str(b)],
            stdout=log, stderr=subprocess.STDOUT)))
    t0 = time.time()
    for i, a, b, log, p in procs:
        p.wait()
        log.close()
        if p.returncode != 0:
            raise SystemExit(f"第 {i} 段渲染失败，见 build/seg{i}.log")
        print(f"  段 {i} 完成（{a}–{b} 帧）{time.time() - t0:.0f}s", flush=True)

    print("  拼接（-c copy）", flush=True)
    lst = os.path.join(BUILD, "list.txt")
    with open(lst, "w", encoding="utf-8") as f:
        for i in range(len(procs)):
            f.write(f"file 'seg{i}.mp4'\n")
    run(["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0",
         "-i", lst, "-c", "copy", master])
    return master


def mux(master):
    print("[3/5] 混音", flush=True)
    muxed = os.path.join(BUILD, "muxed.mp4")
    run(["ffmpeg", "-y", "-loglevel", "error", "-i", master,
         "-i", os.path.join(BUILD, "audio_raw.wav"),
         "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-ac", "2",
         "-shortest", muxed])
    return muxed


def encode(muxed):
    print("[4/5] 压到交件规格（CRF 21，上限 9 Mbps，faststart）", flush=True)
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    tmp = OUT + ".part.mp4"
    # 上限 9M 是硬要求：这部片子颗粒重，纯 CRF 21 会冲到 19 Mbps / 430 MB，
    # 既过不了 AC-4（≤400 MB），也不适合邮箱/网盘交件。封顶后约 200 MB / 8.8 Mbps。
    run(["ffmpeg", "-y", "-loglevel", "error", "-i", muxed,
         "-c:v", "libx264", "-preset", "slow", "-crf", "21",
         "-maxrate", "9M", "-bufsize", "18M",
         "-pix_fmt", "yuv420p", "-profile:v", "high", "-level", "4.1",
         "-x264-params", "aq-mode=3:deblock=-1,-1",
         "-c:a", "copy", "-movflags", "+faststart", tmp])
    os.replace(tmp, OUT)
    return OUT


def report():
    print("[5/5] 核对", flush=True)
    info = json.loads(subprocess.check_output(
        ["ffprobe", "-v", "error", "-print_format", "json",
         "-show_format", "-show_streams", OUT]).decode("utf-8"))
    v = [s for s in info["streams"] if s["codec_type"] == "video"][0]
    dur = float(info["format"]["duration"])
    print(f"  {OUT}")
    print(f"  {v['width']}×{v['height']} {v['codec_name']} "
          f"{os.path.getsize(OUT) / 1024 / 1024:.1f} MB {dur:.2f}s "
          f"{int(v.get('bit_rate', 0)) // 1000} kbps")


if __name__ == "__main__":
    jobs = 4
    if "--jobs" in sys.argv:
        jobs = int(sys.argv[sys.argv.index("--jobs") + 1])
    print(f"《{S.TITLE}》总时长 {N / S.FPS:.1f}s / {N} 帧 / {S.W}×{S.H}@{S.FPS}")
    audio()
    master = render(jobs)
    muxed = mux(master)
    encode(muxed)
    report()
    print("完成。")
