---
name: yt-context-pack
description: >-
  Builds a rich context pack for any YouTube video — full metadata, engagement
  stats, timestamped transcript, keyframe visual analysis, chapter/structure
  map, and comment consensus. Use when the user shares a YouTube URL and wants
  research, summarization, fact-checking, claim extraction, or "understand
  this video" — not for a quick transcript snippet.
---

# YouTube Context Pack

Scripts gather raw materials; you write the analysis. Never answer video
questions from a transcript alone.

1. **Preflight** — `python scripts/build_pack.py doctor`. Exit 1 → print the
   MISSING lines verbatim (they contain fix commands), stop.
2. **Gather** — `python scripts/build_pack.py "<url>"`. One JSON status line:
   workdir, artifact paths, warnings. Stages cache in `%TEMP%/ytpack/<id>/` —
   re-runs are fast. Transcription ≈ 3–4× realtime CPU; warn for >30 min
   videos, suggest `YT_PACK_MODEL=base` beyond 1 hr.
   - age-restricted/private/live/region-locked → surface yt-dlp's message
     verbatim, do NOT retry.
   - `Unable to extract` (stale extractor) → `pip install -U yt-dlp`, retry
     once, then report and stop.
   - `--no-comments` skips stage E when comments are irrelevant.
3. **Analyze** — read ALL of, in order: every frame in `frames/` (batch once;
   filenames carry timestamps, `kf_04-32.jpg` = 4:32; never re-read), then
   `comments.json` (sorted by likes), then `transcript.md` (chunk reads for
   long videos). Write nothing until all are read.
4. **Compose** — write `<title-slug>.pack.md` following
   `references/pack-template.md` exactly, plus a `pack.json` sidecar with the
   same sections (identity, metrics, structure, visual_moments, claims,
   comments_pulse, credibility, artifacts). Timestamps in `[M:SS]` on every
   claim/visual. Quote claims as stated, then confidence + verify hint.
   Limitations section is mandatory.
5. **Report** — one line: pack path + views, like ratio, N claims, N
   keyframes, comment consensus in ≤8 words.
