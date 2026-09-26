---
name: yt-context-pack
description:
  Builds a rich context pack for any YouTube video: full metadata, engagement
  stats, timestamped transcript, keyframe visual analysis, chapter/structure
  map, and comment consensus. Use when the user shares a YouTube URL and wants
  research, summarization, fact-checking, claim extraction, or "understand
  this video" — not for a quick transcript snippet.
---

# YouTube Context Pack

Scripts gather raw materials; you write the analysis. Never skip the gather
step — do not answer video questions from a transcript alone.

## 1. Preflight

```
python scripts/build_pack.py doctor
```

Exit 0 → continue. Exit 1 → print the MISSING lines verbatim (they contain
exact fix commands), stop, and tell the user.

## 2. Gather

```
python scripts/build_pack.py "<url>"
```

One JSON status line prints to stdout: workdir, artifact paths, warnings.
Stages cache in `%TEMP%/ytpack/<video_id>/` — re-running a video skips
finished work (fast). Transcription is the slow stage (~3-4x realtime CPU);
warn the user before a video longer than ~30 min, and suggest
`YT_PACK_MODEL=base` for >1 hr videos.

Failure handling:
- age-restricted / private / live / region-locked: yt-dlp exits non-zero with
  its message. Surface it verbatim. Do NOT retry.
- `Unable to extract ...` (stale extractor): run `pip install -U yt-dlp`,
  retry ONCE. Still failing → report, stop.
- `--no-comments` flag skips stage E when the user only wants audiovisual
  context or comments are irrelevant to the task.

## 3. Analyze (read everything before writing anything)

Read in this order:
1. All frames in `frames/` (batch them; filenames carry timestamps —
   `kf_04-32.jpg` is at 4:32). Never re-read a frame.
2. `comments.json` if present (already sorted by likes).
3. `transcript.md` — chunk reads for videos over ~40 min.

## 4. Compose

Write `<title-slug>.pack.md` in the current directory, following
`references/pack-template.md` exactly. Then write `pack.json` next to it with
the same schema sections filled in (identity, metrics, structure,
visual_moments, claims, comments_pulse, credibility, artifacts).

Rules:
- Timestamps in `[M:SS]` everywhere a claim or visual is cited.
- Claims quote the video's wording, then your confidence + verify hint.
- Comment pulse separates consensus from objections from corrections
  (corrections with high likes are credibility gold).
- Limitations is mandatory: note disabled comments, missing chapters, frame
  cap, transcript language, anything the pack could not capture.

## 5. Report

One line: pack path + headline stats (views, like ratio, N claims,
N keyframes, comment consensus in ≤8 words).
