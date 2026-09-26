#!/usr/bin/env python3
"""Self-check for build_pack.py: timestamp formatting, pts parsing,
scene-threshold escalation. Plain asserts, run directly."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "scripts"))
import build_pack as bp  # noqa: E402


def test_fmt_ts():
    assert bp.fmt_ts(0) == "0:00"
    assert bp.fmt_ts(4.32 * 60 + 32) == "4:32" or bp.fmt_ts(272) == "4:32"
    assert bp.fmt_ts(272) == "4:32"
    assert bp.fmt_ts(3600) == "60:00"
    assert bp.fmt_ts(-5) == "0:00"
    assert bp.fmt_ts(59.7) == "1:00"


def test_pts_parsing():
    stderr = (
        "[Parsed_showinfo_1 @ 0000025] n:0 pts:108 pts_time:4.32\n"
        "[Parsed_showinfo_1 @ 0000025] n:1 pts:720 pts_time:61.5\n"
        "[Parsed_showinfo_1 @ 0000025] n:2 pts:900 pts_time:130\n"
    )
    import re
    pts = [float(m) for m in re.findall(r"pts_time:([\d.]+)", stderr)]
    assert pts == [4.32, 61.5, 130.0]
    assert bp.fmt_ts(pts[0]) == "0:04"
    assert bp.fmt_ts(pts[1]) == "1:02"


def test_video_id():
    assert bp.video_id_from_url("https://www.youtube.com/watch?v=dQw4w9WgXcQ") == "dQw4w9WgXcQ"
    assert bp.video_id_from_url("https://youtu.be/dQw4w9WgXcQ") == "dQw4w9WgXcQ"
    assert bp.video_id_from_url("https://www.youtube.com/shorts/dQw4w9WgXcQ") == "dQw4w9WgXcQ"
    assert bp.video_id_from_url("dQw4w9WgXcQ") == "dQw4w9WgXcQ"


def test_ts_from_name():
    p = Path("frames/kf_04-32.jpg")
    assert bp._ts_from_name(p) == 272
    assert bp._ts_from_name(Path("frames/kf_003.jpg")) is None


def test_constants():
    # Budget guard: 12 frames at 960px ≈ 12k image tokens — do not raise silently.
    assert bp.MAX_FRAMES == 12
    assert bp.SCENE_THRESHOLDS[0] < bp.SCENE_THRESHOLDS[-1]  # escalation rises
    assert bp.LONG_VIDEO_SEC == 45 * 60


if __name__ == "__main__":
    for name, fn in sorted(list(globals().items())):
        if name.startswith("test_"):
            fn()
            print(f"ok  {name}")
    print("all checks passed")
