# -*- coding: utf-8 -*-
"""声音：edge-tts 旁白 + numpy 合成的环境/音效/箫/低音垫 + 混音。

输出 build/audio.wav（48k / 16bit / 立体声）。
响度对到 -16 LUFS，真峰 ≤ -1.5 dBFS（见 verify.py）。
"""
import os, sys, math, asyncio, subprocess, wave
import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
import story as S

BUILD = os.path.join(ROOT, "build")
VO = os.path.join(BUILD, "vo")
os.makedirs(VO, exist_ok=True)
SR = 48000
TOTAL = sum(s["dur"] for s in S.SHOTS) + S.ENDCARD
N = int(TOTAL * SR) + SR // 2


# ---------------------------------------------------------------- 基础
def idx(t):
    return max(0, int(round(t * SR)))


def add(buf, x, t, gain=1.0):
    i = idx(t)
    n = min(len(x), buf.shape[0] - i)
    if n > 0:
        buf[i:i + n] += x[:n] * gain


def env_ad(n, a=0.01, d=0.3):
    a_n = min(max(1, int(a * SR)), n)
    e = np.ones(n, np.float32)
    e[:a_n] = np.linspace(0, 1, a_n)
    d_n = min(max(1, int(d * SR)), n - a_n)
    if d_n > 0:
        e[n - d_n:] *= np.linspace(1, 0, d_n) ** 2
    return e


def lp_fast(x, k=64):
    """O(n) 的滑动平均（cumsum 实现）。k 越大越闷。"""
    k = max(1, int(k))
    pad = k // 2
    xp = np.pad(x, (pad, k - 1 - pad), mode="edge")
    c = np.concatenate([[0.0], np.cumsum(xp, dtype=np.float64)])
    y = (c[k:] - c[:-k]) / k
    return y[:len(x)].astype(np.float32)


def bp(x, lo=1, hi=8):
    return (lp_fast(x, hi) - lp_fast(lp_fast(x, hi), lo * 4)).astype(np.float32)


# ---------------------------------------------------------------- 旁白
def shot_starts():
    t, out = 0.0, []
    for s in S.SHOTS:
        out.append(t)
        t += s["dur"]
    return out


async def _tts(text, voice, rate, out):
    import edge_tts
    com = edge_tts.Communicate(text, voice, rate=rate)
    await com.save(out)


def read_wav(p):
    with wave.open(p, "rb") as w:
        n = w.getnframes()
        d = np.frombuffer(w.readframes(n), dtype=np.int16).astype(np.float32) / 32768.0
        if w.getnchannels() == 2:
            d = d.reshape(-1, 2).mean(axis=1)
    return d


def build_vo(buf, report):
    st = shot_starts()
    for i, s in enumerate(S.SHOTS):
        if not s.get("sub"):
            continue
        raw = os.path.join(VO, f"{i:02d}.mp3")
        wav = os.path.join(VO, f"{i:02d}.wav")
        for attempt in range(5):
            try:
                if not (os.path.exists(raw) and os.path.getsize(raw) > 3000):
                    print("  tts", i, s["sub"], flush=True)
                    if os.path.exists(raw):
                        os.remove(raw)
                    asyncio.run(_tts(s["sub"], S.VOICE, S.VOICE_RATE, raw))
                r = subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", raw,
                                    "-ar", str(SR), "-ac", "1", wav],
                                   capture_output=True)
                if r.returncode == 0 and os.path.exists(wav) and os.path.getsize(wav) > 3000:
                    break
            except Exception as e:
                print("    retry", attempt, type(e).__name__, flush=True)
            for f in (raw, wav):
                if os.path.exists(f):
                    os.remove(f)
        else:
            raise SystemExit(f"TTS 失败：{s['sub']}")
        x = read_wav(wav)
        d = len(x) / SR
        t0 = st[i] + 0.85
        budget = s["dur"] - 0.85 - 0.35
        report.append(dict(shot=i, text=s["sub"], t0=round(t0, 2),
                           slot=round(budget, 2), vo=round(d, 2),
                           over=round(d - budget, 2)))
        add(buf, x, t0, S.VOICE_GAIN * 0.9)
    return buf


# ---------------------------------------------------------------- 音效
def sfx_room(dur, rng):
    n = int(dur * SR)
    x = lp_fast(rng.normal(0, 1, n).astype(np.float32), 220)
    y = lp_fast(rng.normal(0, 1, n).astype(np.float32), 900) * 0.25
    lfo = 1 + 0.25 * np.sin(np.linspace(0, 12 * np.pi, n)).astype(np.float32)
    return ((x * 0.9 + y) * lfo * env_ad(n, 1.5, 1.5)).astype(np.float32)


def sfx_clay(dur, rng):
    """舂打：低频闷响 + 粉料碎裂。"""
    n = int(dur * SR)
    t = np.arange(n) / SR
    body = np.sin(2 * np.pi * (62 + 26 * np.exp(-t * 14)) * t) * np.exp(-t * 9)
    crunch = bp(rng.normal(0, 1, n).astype(np.float32), 2, 40) * np.exp(-t * 26) * 0.55
    return (body * 0.9 + crunch).astype(np.float32)


def sfx_rub(dur, rng):
    """搓线：布/木的摩擦，带一点周期性。"""
    n = int(dur * SR)
    t = np.arange(n) / SR
    x = bp(rng.normal(0, 1, n).astype(np.float32), 3, 26)
    mod = 0.55 + 0.45 * np.sin(2 * np.pi * 3.4 * t) ** 2
    return (x * mod * env_ad(n, 0.25, 0.5) * 0.8).astype(np.float32)


def sfx_brush(dur, rng):
    n = int(dur * SR)
    t = np.arange(n) / SR
    x = bp(rng.normal(0, 1, n).astype(np.float32), 6, 60)
    return (x * np.exp(-t * 7) * 0.7).astype(np.float32)


def sfx_metal(dur, rng):
    """贴金：极薄金属屑的细响 + 一点高频亮光。"""
    n = int(dur * SR)
    t = np.arange(n) / SR
    p1 = np.sin(2 * np.pi * 3180 * t + rng.normal(0, .02))
    p2 = np.sin(2 * np.pi * 4720 * t) * 0.6
    p3 = np.sin(2 * np.pi * 6610 * t) * 0.35
    sh = (p1 + p2 + p3) * np.exp(-t * 5.5)
    air = bp(rng.normal(0, 1, n).astype(np.float32), 8, 90) * np.exp(-t * 9) * 0.5
    return ((sh * 0.20 + air) * env_ad(n, 0.004, 0.2)).astype(np.float32)


def sfx_bell(dur, rng):
    """磬：非谐分音，长衰减。"""
    n = int(dur * SR)
    t = np.arange(n) / SR
    f0 = 392.0
    parts = [(1.0, 1.0), (2.76, 0.55), (5.40, 0.30), (8.93, 0.16), (13.3, 0.08)]
    y = np.zeros(n, np.float32)
    for r, a in parts:
        y += a * np.sin(2 * np.pi * f0 * r * t) * np.exp(-t * (1.1 + r * 0.22))
    y = y / np.abs(y).max()
    return (y * env_ad(n, 0.002, 0.3)).astype(np.float32)


def sfx_breath(dur, rng):
    n = int(dur * SR)
    t = np.arange(n) / SR
    x = bp(rng.normal(0, 1, n).astype(np.float32), 4, 60)
    e = np.minimum(1, t / 0.5) * np.exp(-np.maximum(0, t - 0.5) * 3)
    return (x * e * 0.55).astype(np.float32)


SFX = dict(room=sfx_room, clay=sfx_clay, rub=sfx_rub, brush=sfx_brush,
           metal=sfx_metal, bell=sfx_bell, breath=sfx_breath)


# ---------------------------------------------------------------- 音乐
def flute(freq, dur, rng):
    """箫：气声 + 泛音 + 轻微颤音，弱起弱收。"""
    n = int(dur * SR)
    t = np.arange(n) / SR
    vib = 1 + 0.004 * np.sin(2 * np.pi * 4.4 * t + 0.6) * np.minimum(1, t * 1.6)
    ph = 2 * np.pi * freq * np.cumsum(vib) / SR
    y = np.sin(ph) + 0.28 * np.sin(2 * ph) + 0.10 * np.sin(3 * ph) + 0.05 * np.sin(4 * ph)
    breath = bp(rng.normal(0, 1, n).astype(np.float32), 5, 55) * 0.10
    e = np.minimum(1, t / 0.35) * np.minimum(1, np.maximum(0, (dur - t)) / 0.6) ** 1.4
    return ((y * 0.5 + breath) * e).astype(np.float32)


def drone(dur, rng):
    """低音垫：两个五度，慢呼吸。"""
    n = int(dur * SR)
    t = np.arange(n) / SR
    f = [73.42, 110.0, 146.83]
    y = np.zeros(n, np.float32)
    for i, ff in enumerate(f):
        lfo = 1 + 0.22 * np.sin(2 * np.pi * (0.037 + i * 0.011) * t + i)
        y += (0.5 / (i + 1)) * np.sin(2 * np.pi * ff * t + i * 1.1) * lfo
    y = lp_fast(y, 40)
    return (y * env_ad(n, 3.0, 4.0)).astype(np.float32)


def build_music(buf, rng):
    if not S.MUSIC.get("enabled"):
        return buf
    g = S.MUSIC["gain"]
    add(buf, drone(TOTAL, rng), 0.0, g * 0.55)
    # 箫：在几个段落口出气
    st = shot_starts()
    phrases = [(st[4] + 0.6, 7.0, 293.66),      # 搓线（D4）
               (st[7] + 0.8, 9.0, 220.00),      # 神像（A3）
               (st[10] + 0.5, 8.0, 261.63),     # 1972（C4）
               (st[14] + 0.8, 8.5, 196.00),     # 贴金（G3）
               (st[18] + 1.0, 9.0, 293.66)]     # 结尾（D4）
    for t0, d, f in phrases:
        add(buf, flute(f, d, rng), t0, g * 0.85)
        add(buf, flute(f * 1.5, d * 0.55, rng), t0 + d * 0.45, g * 0.32)
    return buf


# ---------------------------------------------------------------- 混音
def duck(buf, vo_mask, depth=0.55):
    """旁白处把音乐压下去（vo_mask 是 0-1 包络）。"""
    return buf * (1 - depth * vo_mask)


def voiced_mask(buf_vo, smooth=0.35):
    a = np.abs(buf_vo)
    k = int(smooth * SR)
    env = lp_fast(a, max(3, k // 4))
    env = env / (env.max() + 1e-9)
    return np.clip(env * 2.2, 0, 1)


def normalize(path, target=-16.0):
    """用 ffmpeg ebur128 测，再整体缩放；返回实测。"""
    r = subprocess.run(["ffmpeg", "-hide_banner", "-i", path, "-af",
                        "ebur128=peak=true", "-f", "null", "-"],
                       capture_output=True, text=True)
    txt = r.stderr
    I = None
    for ln in txt.splitlines():
        if "I:" in ln and "LUFS" in ln:
            try:
                I = float(ln.split("I:")[1].split("LUFS")[0].strip())
            except Exception:
                pass
    return I


def write_wav(path, x):
    x = np.clip(x, -1, 1)
    d = (x * 32767).astype(np.int16)
    d = np.stack([d, d], axis=1)
    with wave.open(path, "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(d.tobytes())


def main():
    rng = np.random.default_rng(20261118)
    n = int(TOTAL * SR)
    vo = np.zeros(n, np.float32)
    rep = []
    print("旁白…", flush=True)
    build_vo(vo, rep)

    bed = np.zeros(n, np.float32)
    print("环境音…", flush=True)
    add(bed, sfx_room(TOTAL, rng), 0.0, 0.05)
    for kind, pos, g in S.SFX:
        t0 = pos * TOTAL
        dur = 3.2 if kind in ("room",) else (2.2 if kind == "bell" else 1.1)
        add(bed, SFX[kind](dur, rng), t0, g * 0.38)

    print("音乐…", flush=True)
    mus = np.zeros(n, np.float32)
    build_music(mus, rng)

    # 旁白与配乐各自按分位对齐，再按 10 dB 差混
    vp = np.percentile(np.abs(vo[vo != 0]), 99.0) + 1e-9
    vo = vo * (0.62 / vp)
    mask = voiced_mask(vo)
    bedm = bed + mus
    bp99 = np.percentile(np.abs(bedm), 99.5) + 1e-9
    bedm = bedm * (0.19 / bp99)
    mix = vo + duck(bedm, mask, 0.35)

    # 软限幅：只削瞬态峰，让整体能推响（真峰 ≤ -1 dBFS）
    thr = 0.62
    a = np.abs(mix)
    over = a > thr
    if over.any():
        mix[over] = np.sign(mix[over]) * (thr + (1 - thr) *
                                          np.tanh((a[over] - thr) / (1 - thr)))

    # 收尾淡出
    fade = int(1.6 * SR)
    mix[-fade:] *= np.linspace(1, 0, fade) ** 1.5
    mix[:int(0.5 * SR)] *= np.linspace(0, 1, int(0.5 * SR))

    peak = np.abs(mix).max() + 1e-9
    mix = mix / peak * 0.58
    out = os.path.join(BUILD, "audio_raw.wav")
    write_wav(out, mix)

    # 响度迭代到目标
    target = -16.0
    for _ in range(3):
        I = normalize(out)
        if I is None:
            break
        g = 10 ** ((target - I) / 20.0)
        g = min(max(g, 0.5), 2.0)
        mix = mix * g
        pk = np.abs(mix).max()
        if pk > 0.82:            # 留 0.8 dB 余量：AAC 编码后真峰会再抬 0.4 dB 左右
            mix = mix * (0.82 / pk)
        write_wav(out, mix)
        print(f"  I={I:.1f} → gain {g:.3f}", flush=True)

    # 报告
    import json
    json.dump(rep, open(os.path.join(BUILD, "vo.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    over = [r for r in rep if r["over"] > 0.3]
    print("配音超槽:", over if over else "无")
    print("最短余量:", min(r["slot"] - r["vo"] for r in rep))
    print("wav:", out, f"{os.path.getsize(out)/1024/1024:.1f} MB  I={normalize(out)} LUFS")


if __name__ == "__main__":
    main()
