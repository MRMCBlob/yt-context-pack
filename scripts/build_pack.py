#!/usr/bin/env python3
"""build_pack.py — gather raw materials for a YouTube context pack.

Stages (each cached in the workdir, re-runs skip completed work):
  A  metadata     meta.json        yt-dlp dump-single-json
  B  download     video.<ext>      yt-dlp <=720p mp4
  C  transcript   transcript.md/json  faster-whisper (always; no auto-subs)
  D  keyframes    frames/kf_*.jpg  ffmpeg scene detection, <=12 frames,
                                filenames encode timestamps (kf_04-32.jpg)
  E  comments     comments.json    yt-dlp --write-comments (non-fatal)

Usage:
  python build_pack.py doctor
  python build_pack.py <url> [--no-comments]

Prints one JSON status line to stdout when done; progress goes to stderr.
Claude reads the artifacts and writes the pack — this script gathers only.
"""

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

# Windows consoles default to cp1252 and crash on emoji-laden titles.
if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

MAX_FRAMES = 12
FILL_INTERVAL = 60          # seconds between uniform supplement frames
LONG_VIDEO_SEC = 45 * 60    # auto-downgrade whisper model past this
SCENE_THRESHOLD_START = 0.30
SCENE_THRESHOLDS = [0.30, 0.40, 0.50]
SCENE_MAX = 18              # rerun at higher threshold above this


def log(msg: str) -> None:
    print(msg, file=sys.stderr, flush=True)


def fmt_ts(seconds: float) -> str:
    s = max(0, int(round(seconds)))
    return f"{s // 60}:{s % 60:02d}"


def video_id_from_url(url: str) -> str:
    m = re.search(
        r"(?:v=|youtu\.be/|/shorts/|/embed/|/live/)([\w-]{11})", url
    ) or re.search(r"^([\w-]{11})$", url.strip())
    if not m:
        raise SystemExit(f"Cannot extract a video id from: {url}")
    return m.group(1)


def ytdlp_cmd() -> list[str]:
    exe = shutil.which("yt-dlp")
    return [exe] if exe else [sys.executable, "-m", "yt_dlp"]


def run(cmd: list[str], **kw) -> subprocess.CompletedProcess:
    log(f"$ {' '.join(str(c) for c in cmd[:6])} ...")
    return subprocess.run(cmd, **kw)


# ---------------------------------------------------------------- stages

def stage_metadata(workdir: Path, url: str) -> dict:
    meta_path = workdir / "meta.json"
    if meta_path.exists():
        return json.loads(meta_path.read_text(encoding="utf-8"))
    r = run(ytdlp_cmd() + ["--dump-single-json", "--no-download", "--no-playlist", url],
            capture_output=True, text=True, encoding="utf-8", errors="replace")
    if r.returncode != 0:
        # Surface yt-dlp's own message verbatim; agent decides, no blind retry.
        raise SystemExit(f"yt-dlp metadata failed:\n{r.stderr.strip()[-2000:]}")
    meta = json.loads(r.stdout)
    meta_path.write_text(json.dumps(meta, ensure_ascii=False), encoding="utf-8")
    return meta


def stage_download(workdir: Path, url: str) -> Path:
    existing = sorted(workdir.glob("video.*"))
    if existing:
        return existing[0]
    r = run(ytdlp_cmd() + [
        "-f", "bv*[height<=720]+ba/b[height<=720]/b",
        "--merge-output-format", "mp4",
        "-o", str(workdir / "video.%(ext)s"),
        "--no-playlist", url,
    ])
    if r.returncode != 0:
        raise SystemExit(f"yt-dlp download failed:\n{r.stderr.strip()[-2000:]}")
    files = sorted(workdir.glob("video.*"))
    if not files:
        raise SystemExit("Download claimed success but no video file found.")
    return files[0]


def stage_transcript(workdir: Path, video: Path, meta: dict) -> dict:
    md_path = workdir / "transcript.md"
    json_path = workdir / "transcript.json"
    if md_path.exists() and json_path.exists():
        return {"segments": json.loads(json_path.read_text(encoding="utf-8"))}

    from faster_whisper import WhisperModel

    duration = meta.get("duration") or 0
    model_size = os.environ.get("YT_PACK_MODEL")
    if not model_size:
        model_size = "base" if duration > LONG_VIDEO_SEC else "small"
    device = os.environ.get("YT_PACK_DEVICE", "cpu")
    compute = "float16" if device == "cuda" else "int8"
    log(f"transcribing with faster-whisper {model_size} ({device}, {compute}) "
        f"— this is the slow stage")

    model = WhisperModel(model_size, device=device, compute_type=compute)
    # condition_on_previous_text=False kills whisper's repetition-loop failure
    # mode on music/noise stretches; segment timestamps are all we need.
    segments, info = model.transcribe(
        str(video), vad_filter=True, condition_on_previous_text=False
    )
    segs = [
        {"start": round(s.start, 2), "end": round(s.end, 2), "text": s.text.strip()}
        for s in segments
    ]
    json_path.write_text(json.dumps(segs, ensure_ascii=False), encoding="utf-8")

    # Group segments into ~30s blocks so agents read [4:32-5:01] text lines.
    lines, block_start, block_end, buf = [], None, None, []
    for s in segs:
        if block_start is None:
            block_start = s["start"]
        buf.append(s["text"])
        block_end = s["end"]
        if block_end - block_start >= 30:
            lines.append(f"[{fmt_ts(block_start)}-{fmt_ts(block_end)}] {' '.join(buf)}")
            block_start, buf = None, []
    if buf:
        lines.append(f"[{fmt_ts(block_start or 0)}-{fmt_ts(block_end or 0)}] {' '.join(buf)}")

    lang = info.language if hasattr(info, "language") else meta.get("language")
    md_path.write_text(
        f"# Transcript ({lang}, {meta.get('title', '?')})\n\n" + "\n".join(lines),
        encoding="utf-8",
    )
    return {"segments": segs}


def _scene_stderr_to_frames(workdir: Path, video: Path, threshold: float,
                            prefix: str) -> list[dict]:
    """One ffmpeg pass: scene-select, scale, showinfo. Parse pts_time from
    stderr and rename frames to kf_<M>-<SS>.jpg so timestamps live in the
    filename (Claude cites them without opening a manifest)."""
    frames_dir = workdir / "frames" / prefix
    if frames_dir.exists():
        shutil.rmtree(frames_dir)
    frames_dir.mkdir(parents=True)
    r = run([
        "ffmpeg", "-hide_banner", "-i", str(video),
        "-vf", f"select='gt(scene,{threshold})',scale=960:-2,showinfo",
        "-fps_mode", "vfr", "-q:v", "5",
        str(frames_dir / "kf_%03d.jpg"),
    ], capture_output=True, text=True, encoding="utf-8", errors="replace")
    pts = [float(m) for m in re.findall(r"pts_time:([\d.]+)", r.stderr)]
    frames = sorted(frames_dir.glob("kf_*.jpg"))
    out = []
    for i, f in enumerate(frames):
        t = pts[i] if i < len(pts) else None
        if t is not None:
            named = frames_dir / f"kf_{fmt_ts(t).replace(':', '-')}.jpg"
            if named.exists():
                # Two cuts rounding to the same second are near-duplicates.
                f.unlink()
                continue
            f.rename(named)
            f = named
        out.append({"file": str(f.relative_to(workdir)), "t": t})
    return out


def stage_keyframes(workdir: Path, video: Path, duration: float) -> list[dict]:
    final_dir = workdir / "frames"
    if final_dir.exists() and list(final_dir.glob("kf_*.jpg")):
        return [{"file": str(f.relative_to(workdir)),
                 "t": _ts_from_name(f)} for f in sorted(final_dir.glob("kf_*.jpg"))]

    frames, threshold = [], SCENE_THRESHOLD_START
    for threshold in SCENE_THRESHOLDS:
        frames = _scene_stderr_to_frames(workdir, video, threshold, "run")
        if len(frames) <= SCENE_MAX:
            break
        log(f"{len(frames)} scenes at T={threshold}; escalating threshold")
    # Fast-cut/animated videos still saturate every threshold. Even-sample
    # the cut list so frames spread across the whole video, not the intro.
    if len(frames) > MAX_FRAMES:
        step = len(frames) / MAX_FRAMES
        frames = [frames[round(i * step)] for i in range(MAX_FRAMES)]

    # Static slideshows/talking heads yield <4 scene cuts: supplement with
    # uniform samples so every pack has visual coverage.
    if len(frames) < 4:
        have = {f["t"] for f in frames if f["t"] is not None}
        fill_dir = workdir / "frames" / "fill"
        if fill_dir.exists():
            shutil.rmtree(fill_dir)
        fill_dir.mkdir(parents=True)
        run(["ffmpeg", "-hide_banner", "-i", str(video),
             "-vf", f"fps=1/{FILL_INTERVAL},scale=960:-2", "-q:v", "5",
             str(fill_dir / "fill_%03d.jpg")])
        for i, f in enumerate(sorted(fill_dir.glob("fill_*.jpg"))):
            t = i * FILL_INTERVAL
            if t >= duration or len(frames) >= 8:
                break
            if any(h is not None and abs(h - t) < FILL_INTERVAL / 2 for h in have):
                continue
            frames.append({"file": str(f.relative_to(workdir)), "t": t})
    frames.sort(key=lambda f: f["t"] if f["t"] is not None else 1e9)
    frames = frames[:MAX_FRAMES]

    final_dir.mkdir(exist_ok=True)
    for f in frames:
        shutil.copy2(workdir / f["file"], final_dir / Path(f["file"]).name)
    for sub in ("run", "fill"):
        shutil.rmtree(workdir / "frames" / sub, ignore_errors=True)
    # Rewrite paths relative to canonical frames/
    for f in frames:
        f["file"] = "frames/" + Path(f["file"]).name
    (workdir / "frames.json").write_text(
        json.dumps(frames, ensure_ascii=False), encoding="utf-8")
    return frames


def _ts_from_name(f: Path):
    m = re.search(r"kf_(\d+)-(\d+)\.jpg", f.name)
    return int(m.group(1)) * 60 + int(m.group(2)) if m else None


def stage_comments(workdir: Path, url: str) -> list[dict]:
    out = workdir / "comments.json"
    if out.exists():
        return json.loads(out.read_text(encoding="utf-8"))
    r = run(ytdlp_cmd() + [
        "--dump-single-json", "--no-download", "--no-playlist",
        "--write-comments",
        "--extractor-args", "youtube:max_comments=200,20",
        url,
    ], capture_output=True, text=True, encoding="utf-8", errors="replace")
    if r.returncode != 0:
        log(f"comments extraction failed (non-fatal): {r.stderr.strip()[-500:]}")
        return []
    meta = json.loads(r.stdout)
    comments = [
        {"text": c.get("text", ""), "likes": c.get("like_count") or 0,
         "author": c.get("author", ""), "replies": c.get("replies") or 0}
        for c in (meta.get("comments") or [])
    ]
    comments.sort(key=lambda c: c["likes"], reverse=True)
    out.write_text(json.dumps(comments[:200], ensure_ascii=False), encoding="utf-8")
    return comments[:200]


# ---------------------------------------------------------------- doctor

def doctor() -> int:
    ok = True
    v = sys.version_info
    if (3, 10) <= v[:2] <= (3, 13):
        log(f"OK  python {v.major}.{v.minor}.{v.micro}"
            + ("" if v.minor == 12 else " (3.12 recommended)"))
    else:
        ok = False
        log(f"MISS python 3.10-3.13 required (found {v.major}.{v.minor}) — "
            f"ctranslate2 has no wheels for this version. Install: "
            f"winget install Python.Python.3.12")
    try:
        import faster_whisper  # noqa: F401
        log("OK  faster-whisper importable")
    except ImportError:
        ok = False
        log("MISS faster-whisper — fix: pip install faster-whisper==1.2.1")
    if shutil.which("yt-dlp") or shutil.which("yt_dlp") or _module_ok("yt_dlp"):
        log("OK  yt-dlp")
    else:
        ok = False
        log("MISS yt-dlp — fix: pip install -U yt-dlp  (or: winget install yt-dlp.yt-dlp)")
    if shutil.which("ffmpeg"):
        log("OK  ffmpeg")
    else:
        ok = False
        log("MISS ffmpeg — fix: winget install Gyan.FFmpeg  (needed for keyframes)")
    return 0 if ok else 1


def _module_ok(name: str) -> bool:
    return subprocess.run([sys.executable, "-m", name, "--version"],
                          capture_output=True).returncode == 0


# ---------------------------------------------------------------- main

def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("url", nargs="?", help="YouTube video URL")
    ap.add_argument("--no-comments", action="store_true")
    args = ap.parse_args()

    if not args.url or args.url == "doctor":
        sys.exit(doctor())

    vid = video_id_from_url(args.url)
    workdir = Path(tempfile.gettempdir()) / "ytpack" / vid
    workdir.mkdir(parents=True, exist_ok=True)
    log(f"workdir: {workdir}")

    warnings = []
    meta = stage_metadata(workdir, args.url)
    if meta.get("is_live"):
        warnings.append("video is live — pack captures a snapshot")

    video = stage_download(workdir, args.url)
    stage_transcript(workdir, video, meta)
    frames = stage_keyframes(workdir, video, meta.get("duration") or 0)
    if not frames:
        warnings.append("no keyframes extracted")

    if args.no_comments:
        comments = []
        warnings.append("comments skipped (--no-comments)")
    else:
        comments = stage_comments(workdir, args.url)
        if not comments:
            warnings.append("no comments available (disabled or extraction failed)")

    status = {
        "video_id": vid,
        "title": meta.get("title"),
        "stages": {"metadata": "done", "download": "done",
                   "transcript": "done", "keyframes": "done",
                   "comments": "done" if comments else "skipped/empty"},
        "artifacts": {
            "workdir": str(workdir),
            "meta": "meta.json",
            "transcript": "transcript.md",
            "frames": [f["file"] for f in frames],
            "comments": "comments.json" if comments else None,
        },
        "warnings": warnings,
    }
    print(json.dumps(status, ensure_ascii=False))


if __name__ == "__main__":
    main()
