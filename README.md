# yt-context-pack

Build a rich **context pack** for any YouTube video — beyond the transcript. An AI-agent skill: give it a URL, it gathers raw materials and synthesizes structured context optimized for agent consumption.

## What a pack contains

- **TL;DR** — what the video argues/shows
- **Metrics** — views, likes, like ratio, channel subs, views/day
- **Chapters / structure map** — with timestamps (derived if the video has none)
- **Visual moments** — keyframes read by the agent, with on-screen text (OCR) and timestamps
- **Key claims** — quoted, timestamped, with confidence + verify hints
- **Comment pulse** — consensus, objections, corrections, sponsor detection
- **Credibility signals** — engagement ratios, flagged tensions
- **Limitations** — what the pack could NOT capture

## Install

```
npx skills add MRMCBlob/yt-context-pack
```

or copy this repo into `~/.claude/skills/yt-context-pack/`.

## Requirements

| Dep | Install | Notes |
|---|---|---|
| Python 3.10–3.13 (3.12 recommended) | `winget install Python.Python.3.12` | |
| faster-whisper 1.2.1 | `pip install faster-whisper==1.2.1` | transcript always via Whisper, no auto-subs |
| yt-dlp | `pip install -U yt-dlp` | near-weekly releases — keep fresh |
| ffmpeg | `winget install Gyan.FFmpeg` | keyframe extraction |

The skill's `doctor` command checks all of these and prints exact fix commands.

## How it works

```
python scripts/build_pack.py "<url>"     # gathers: metadata, download (<=720p),
                                         # whisper transcript, <=12 keyframes, comments
```

One script, five cached stages (re-runs skip finished work). Timestamps are encoded
in keyframe filenames (`kf_04-32.jpg` = 4:32) so the agent can cite visuals without
opening a manifest. The agent then reads all artifacts and writes
`<title>.pack.md` + `pack.json` following `references/pack-template.md`.

Optional env: `YT_PACK_MODEL=base|small|...` (whisper model; `base` is auto-used
for videos > 45 min), `YT_PACK_DEVICE=cuda`.

## Self-check

```
python test_build.py
```

## License

MIT
