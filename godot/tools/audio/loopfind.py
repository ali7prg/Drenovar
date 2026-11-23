"""Seamless loop finder for DRENOVAR music (build 1024).

Finds a loop region [a, b) in a decoded track whose surroundings match (chroma +
band-energy features over a +-3 s window), refines the seam at sample level by
waveform cross-correlation, and renders intro+body with a crossfade so playback can
jump from b back to a without an audible seam. Used by audio_master.py.
"""
import numpy as np

SR = 44100
HOP = 2205  # 50 ms


def features(mono: np.ndarray) -> np.ndarray:
    n = 4096
    frames = 1 + max(0, (len(mono) - n) // HOP)
    win = np.hanning(n).astype(np.float32)
    idx = np.arange(n)[None, :] + HOP * np.arange(frames)[:, None]
    spec = np.abs(np.fft.rfft(mono[idx] * win, axis=1)) ** 2
    freqs = np.fft.rfftfreq(n, 1 / SR)
    valid = (freqs > 55) & (freqs < 5000)
    pitch = np.zeros_like(freqs)
    pitch[valid] = np.round(12 * np.log2(freqs[valid] / 440.0)) % 12
    chroma = np.stack([spec[:, valid & (pitch == k)].sum(1) for k in range(12)], 1)
    chroma = chroma / (chroma.sum(1, keepdims=True) + 1e-12)
    edges = [0, 120, 300, 700, 1500, 3000, 6000, 12000, 22050]
    bands = np.stack([spec[:, (freqs >= edges[i]) & (freqs < edges[i + 1])].sum(1) for i in range(8)], 1)
    bands = np.log10(bands + 1e-9)
    bands = (bands - bands.mean(0)) / (bands.std(0) + 1e-6)
    f = np.concatenate([chroma * 3.0, bands * 0.35], 1)
    f = f - f.mean(0)
    return f / (np.linalg.norm(f, axis=1, keepdims=True) + 1e-9)


def find_loop(stereo: np.ndarray, start_range, end_range, min_len, max_len, window_s=3.0):
    mono = stereo.mean(1).astype(np.float32)
    f = features(mono)
    w = int(window_s * SR / HOP)
    kernel = np.ones(2 * w + 1) / (2 * w + 1)
    best = (-1.0, 0, 0)
    a0, a1 = int(start_range[0] * SR / HOP), int(start_range[1] * SR / HOP)
    b0, b1 = int(end_range[0] * SR / HOP), int(end_range[1] * SR / HOP)
    for lag in range(int(min_len * SR / HOP), int(max_len * SR / HOP) + 1):
        n = len(f) - lag
        if n <= 2 * w:
            break
        sim = (f[:n] * f[lag:lag + n]).sum(1)
        smooth = np.convolve(sim, kernel, mode="same")
        lo, hi = max(a0, b0 - lag, w), min(a1, b1 - lag, n - w)
        if hi <= lo:
            continue
        i = lo + int(np.argmax(smooth[lo:hi]))
        if smooth[i] > best[0]:
            best = (float(smooth[i]), i, i + lag)
    score, fa, fb = best
    a, b = fa * HOP, fb * HOP
    # Sample-level refinement: align b to a by cross-correlating 120 ms of waveform.
    seg = 5292
    ref = mono[a:a + seg]
    search = 2205
    lo = max(0, b - search)
    region = mono[lo:b + search + seg]
    corr = np.correlate(region, ref, mode="valid")
    norm = np.sqrt(np.convolve(region ** 2, np.ones(seg), mode="valid") * (ref ** 2).sum() + 1e-12)
    b = lo + int(np.argmax(corr / norm))
    return a, b, score


def render_loop(stereo: np.ndarray, a: int, b: int, xfade_s=0.6):
    """Intro [0, a) + body [a, b) where body's first `xfade` samples blend the audio
    that follows b (equal power), so b -> a continues seamlessly."""
    x = int(xfade_s * SR)
    x = min(x, len(stereo) - b, b - a)
    out = stereo[:b].copy()
    t = np.linspace(0, np.pi / 2, x, dtype=np.float32)[:, None]
    out[a:a + x] = stereo[a:a + x] * np.sin(t) + stereo[b:b + x] * np.cos(t)
    return out


def seam_report(out: np.ndarray, a: int):
    """Spectral flux at the loop seam (end -> a) against the track's own flux distribution."""
    mono = out.mean(1)
    n = 2048
    def spec(seg):
        return np.abs(np.fft.rfft(seg * np.hanning(n)))
    hop = 1024
    frames = [spec(mono[i:i + n]) for i in range(a, len(mono) - n, hop * 8)]
    flux = [np.linalg.norm(frames[i + 1] - frames[i]) / (np.linalg.norm(frames[i]) + 1e-9) for i in range(len(frames) - 1)]
    seam_seg = np.concatenate([mono[-n // 2:], mono[a:a + n // 2]])
    before = mono[-n - n // 2:-n // 2]
    seam = np.linalg.norm(spec(seam_seg) - spec(before)) / (np.linalg.norm(spec(before)) + 1e-9)
    sample_jump = float(abs(mono[-1] - mono[a]))
    return {"seam_flux": float(seam), "flux_p50": float(np.percentile(flux, 50)), "flux_p95": float(np.percentile(flux, 95)),
            "sample_jump": sample_jump}
