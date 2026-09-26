# yt-context-pack

AI-agent skills for YouTube. Two skills:

- **`skills/yt-context-pack/`** — rich context pack for any video: metadata, engagement, timestamped Whisper transcript, keyframe visual analysis, chapter map, comment pulse. Beyond the transcript.
- **`skills/yt-skill-creator/`** — creates a reusable agent skill from one or more YouTube videos: builds context packs, distills the demonstrated procedure, scaffolds a validated SKILL.md.

## Install

```
npx skills add MRMCBlob/yt-context-pack
```
[![skills.sh](https://skills.sh/b/MRMCBlob/yt-context-pack)](https://skills.sh/MRMCBlob/yt-context-pack)

Or copy any skill folder into `~/.claude/skills/`.

## yt-context-pack

What a pack contains: TL;DR, metrics, chapters/structure with timestamps, visual moments (keyframes + OCR, timestamp-encoded filenames like `kf_04-32.jpg`), key claims (quoted, timestamped, confidence + verify hints), comment pulse (consensus/objections/corrections/sponsors), credibility signals, limitations.

Requirements: Python 3.10–3.13, `pip install faster-whisper==1.2.1 yt-dlp`, ffmpeg (`winget install Gyan.FFmpeg`). The skill's `doctor` command prints exact fix commands.

Run standalone:

```
python skills/yt-context-pack/scripts/build_pack.py "<url>"
```

Five cached stages — re-runs skip finished work. Env: `YT_PACK_MODEL=base|small|…` (`base` auto-used >45 min), `YT_PACK_DEVICE=cuda`.

Self-check: `python skills/yt-context-pack/test_build.py`

## yt-skill-creator

Invoke `/yt-skill-creator create a skill from these youtube videos <url1>, <url2>`. It packs each video with yt-context-pack, distills the repeatable procedure (trusting commenter corrections over the video), scaffolds a lean SKILL.md, validates, installs, and iterates.

## License

MIT
